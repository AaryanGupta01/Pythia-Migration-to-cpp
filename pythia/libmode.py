"""
PYTHIA :: Library mode (PySub module -> C++17 TU + pybind11 wrapper -> .so)

    from pythia.libmode import build_library
    r = build_library(src, ["edit_distance"], out_dir)      # -> LibResult
    # r.so_path is importable; only the requested functions are exposed.

The transpiled TU has no main(); every function/class in the module is
compiled, but only the requested functions get a Python-visible wrapper.
Wrapper glue is generated here, the reusable marshalling code lives in
runtime/pyrt_bridge.hpp.  Builds are content-addressed (see _build_hash).
"""
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Set, Tuple

from . import ast_nodes as A
from .emit_c import LIST_RT, dict_rt_name
from .lexer import LexError
from .lower import FidelityNote, lower
from .optimize import elide_guards
from .parser import parse
from .typecheck import Ty, typecheck
from .emit_cpp import emit
from . import lib_ext as _lx

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from .paths import RUNTIME as _RUNTIME  # noqa: E402  (wheel or checkout)
RUNTIME = str(_RUNTIME)
RUNTIME_FILES = ("pyrt.cpp", "pyrt.hpp", "pyrt_bridge.hpp")
from . import toolchain as _tc  # noqa: E402
FLAGS = ["-std=c++17", "-O3", "-flto", *_tc.pic_flags(), "-fvisibility=hidden", "-w"]
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class LibResult:
    ok: bool = False
    modname: str = ""
    cpp: str = ""                    # transpiled TU, no main
    wrapper_cpp: str = ""            # pybind11 glue
    so_path: Optional[str] = None
    cached: bool = False
    compile_s: float = 0.0
    build_log: str = ""
    build_hash: str = ""
    diagnostics: List[dict] = field(default_factory=list)   # {line,col,kind,msg}
    fidelity: List[dict] = field(default_factory=list)      # {line,col,cls,detail,mitigation,severity}
    cpp_line_map: Dict[str, List[int]] = field(default_factory=dict)   # pysub line -> lines of `cpp`
    exposed: List[dict] = field(default_factory=list)       # {name,params,ret,param_names,mutates}
    error: Optional[str] = None
    cpp_path: Optional[str] = None
    guard_elision: Optional[dict] = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


# ---------------------------------------------------------------- toolchain
@lru_cache(maxsize=None)
def _compiler() -> Tuple[Optional[str], str]:
    cc, line, _ = _tc.find_cxx()
    return cc, line


@lru_cache(maxsize=None)
def _includes() -> List[str]:
    import pybind11
    inc = [sysconfig.get_path("include"), pybind11.get_include()]
    return ["-I" + p for p in dict.fromkeys(inc)] + ["-I" + RUNTIME]


@lru_cache(maxsize=None)
def _toolchain_id() -> str:
    try:
        import pybind11
        pb = pybind11.__version__
    except Exception:
        pb = "?"
    return "|".join([_compiler()[1], sysconfig.get_config_var("EXT_SUFFIX") or "",
                     " ".join(FLAGS), "pybind11=" + pb, sys.version.split()[0]])


def _runtime_digest() -> str:
    h = hashlib.sha256()
    for fn in RUNTIME_FILES:
        with open(os.path.join(RUNTIME, fn), "rb") as f:
            h.update(fn.encode() + b"\0" + f.read())
    return h.hexdigest()


def default_cache_dir() -> str:
    home = os.environ.get("PYTHIA_HOME") or os.path.join(os.path.expanduser("~"), ".pythia-studio")
    return os.path.join(home, "build-cache")


def _atomic_write(path: str, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _install(src: str, dst: str) -> None:
    """Copy a .so into place without writing through a possibly-loaded file."""
    if os.path.abspath(src) == os.path.abspath(dst):
        return
    if os.path.lexists(dst):
        os.unlink(dst)
    shutil.copyfile(src, dst)


def _run(cmd: List[str]) -> Tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, env=_tc.env_for(cmd[0]))
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def _runtime_object(cache_dir: str) -> Tuple[Optional[str], str]:
    """pyrt.cpp compiled once (per compiler/flags/runtime) and reused."""
    cc = _compiler()[0]
    key = hashlib.sha256((_runtime_digest() + _toolchain_id()).encode()).hexdigest()[:16]
    obj = os.path.join(cache_dir, f"rt-{key}.o")
    if os.path.exists(obj):
        return obj, ""
    tmp = obj + f".{uuid.uuid4().hex[:8]}.tmp.o"
    rc, log = _run([cc, *FLAGS, "-I" + RUNTIME, "-c", os.path.join(RUNTIME, "pyrt.cpp"), "-o", tmp])
    if rc != 0:
        return None, log
    os.replace(tmp, obj)
    return obj, log


def _bridge_pch(cache_dir: str) -> Optional[str]:
    """Precompiled pyrt_bridge.hpp (pybind11 + runtime headers): cuts ~3 s off
    every module build.  Returns the header path to `-include`, or None."""
    cc = _compiler()[0]
    key = hashlib.sha256((_runtime_digest() + _toolchain_id()).encode()).hexdigest()[:16]
    d = os.path.join(cache_dir, f"pch-{key}")
    hdr = os.path.join(d, "pyrt_bridge.hpp")
    if os.path.exists(hdr + ".gch"):
        return hdr
    tmpd = d + f".{uuid.uuid4().hex[:8]}.tmp"
    try:
        os.makedirs(tmpd, exist_ok=True)
        shutil.copyfile(os.path.join(RUNTIME, "pyrt_bridge.hpp"), os.path.join(tmpd, "pyrt_bridge.hpp"))
        rc, _ = _run([cc, *FLAGS, *_includes(), "-x", "c++-header",
                      os.path.join(tmpd, "pyrt_bridge.hpp"), "-o", os.path.join(tmpd, "pyrt_bridge.hpp.gch")])
        if rc != 0:
            shutil.rmtree(tmpd, ignore_errors=True)
            return None
        try:
            os.rename(tmpd, d)
        except OSError:                      # another process won the race
            shutil.rmtree(tmpd, ignore_errors=True)
        return hdr if os.path.exists(hdr + ".gch") else None
    except Exception:
        shutil.rmtree(tmpd, ignore_errors=True)
        return None


# ------------------------------------------------------- AST helper utilities
def _children(n: A.Node):
    for f in dataclasses.fields(n):
        v = getattr(n, f.name)
        if isinstance(v, A.Node):
            yield v
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, A.Node):
                    yield x


def _walk(n: A.Node):
    yield n
    for c in _children(n):
        yield from _walk(c)


def _is_container(t: Optional[Ty]) -> bool:
    return _lx.is_container(t)


def _roots(e: Optional[A.Node]) -> Set[str]:
    """Names whose list/dict object an expression may denote (aliasing)."""
    if e is None:
        return set()
    if isinstance(e, A.Name):
        return {e.id}
    if isinstance(e, (A.Coerce,)):
        return _roots(e.value)
    if isinstance(e, A.Subscript):
        return _roots(e.value)
    if isinstance(e, A.BoolOp):
        return set().union(*[_roots(v) for v in e.values])
    if isinstance(e, A.IfExp):
        return _roots(e.body) | _roots(e.orelse)
    if isinstance(e, A.ListLit):
        return set().union(*[_roots(v) for v in e.elts]) if e.elts else set()
    if isinstance(e, A.MethodCall) and e.method == "pop":
        return _roots(e.recv)
    if isinstance(e, A.Call) and _is_container(e.ty) and e.args:
        return set().union(*[_roots(a) for a in e.args])
    return set()


def _mutated_params(mod: A.Module) -> Dict[str, Set[int]]:
    """For each function: indices of list/dict params the call may mutate.
    Conservative: any escape (stored in an object, passed to a method, ...)
    counts as a mutation, so the wrapper writes the final state back."""
    funcs = {f.name: f for f in mod.funcs}
    mut: Dict[str, Set[int]] = {f.name: set() for f in mod.funcs}
    classes = {c.name for c in mod.classes}
    changed = True
    while changed:
        changed = False
        for f in mod.funcs:
            pnames = [p.name for p in f.params]
            alias: Dict[str, Set[str]] = {p.name: {p.name} for p in f.params if _is_container(p.ty)}
            # flow-insensitive alias closure
            grew = True
            while grew:
                grew = False
                for n in _walk_body(f):
                    tgt = None
                    if isinstance(n, A.Assign) and isinstance(n.target, A.Name) and _is_container(n.value.ty if n.value else None):
                        tgt, src = n.target.id, n.value
                    elif isinstance(n, A.ForEach) and _is_container(_loop_var_ty(f, n)):
                        tgt, src = n.var, n.iter
                    if tgt is None:
                        continue
                    new = set()
                    for r in _roots(src):
                        new |= alias.get(r, set())
                    if new - alias.get(tgt, set()):
                        alias.setdefault(tgt, set()).update(new)
                        grew = True

            def hit(e):
                out = set()
                for r in _roots(e):
                    out |= alias.get(r, set())
                return out

            hits: Set[str] = set()
            for n in _walk_body(f):
                if isinstance(n, (A.Assign, A.AugAssign)):
                    if isinstance(n.target, A.Subscript):
                        hits |= hit(n.target.value) | hit(n.value)
                    elif isinstance(n.target, A.Attribute):
                        hits |= hit(n.value)
                elif isinstance(n, A.MethodCall):
                    if n.method in _lx.MUTATORS and _is_container(n.recv.ty):
                        hits |= hit(n.recv)
                        for a in n.args:
                            hits |= hit(a)
                    elif _is_container_class(n.recv.ty, classes):
                        for a in n.args:
                            hits |= hit(a)
                elif isinstance(n, A.Call):
                    if n.func in funcs:
                        for i, a in enumerate(n.args):
                            if i in mut[n.func]:
                                hits |= hit(a)
                    elif n.func in classes:
                        for a in n.args:
                            hits |= hit(a)
            idx = {i for i, p in enumerate(pnames) if p in hits}
            if idx - mut[f.name]:
                mut[f.name] |= idx
                changed = True
    return mut


def _is_container_class(t: Optional[Ty], classes: Set[str]) -> bool:
    return t is not None and t.name in classes


def _loop_var_ty(f: A.FuncDef, n: A.ForEach) -> Optional[Ty]:
    return f.locals_.get(n.var)


def _walk_body(f: A.FuncDef):
    for s in f.body:
        yield from _walk(s)


def _call_graph_cycle(mod: A.Module) -> Optional[A.FuncDef]:
    names = {f.name: f for f in mod.funcs}
    edges = {f.name: {n.func for s in f.body for n in _walk(s)
                      if isinstance(n, A.Call) and n.func in names} for f in mod.funcs}
    for f in mod.funcs:               # f reaches itself?
        seen, stack = set(), list(edges[f.name])
        while stack:
            g = stack.pop()
            if g == f.name:
                return f
            if g not in seen:
                seen.add(g)
                stack.extend(edges[g])
    return None


# ------------------------------------------------------------- wrapper glue
_SCALAR = {"int": "pyb::I64", "float": "pyb::F64", "bool": "pyb::Bool", "str": "pyb::Str"}


def _trait(t: Optional[Ty]) -> Optional[str]:
    """pyb:: marshalling trait for a PySub type, or None if not exposable."""
    if t is None:
        return None
    ext = _lx.trait(t, _trait)            # Optional, set, dicts of lists/dicts
    if ext is not None:
        return ext
    if t.name in _SCALAR:
        return _SCALAR[t.name]
    if t.name == "list" and t.elem is not None:
        e = t.elem
        if e.name in LIST_RT:
            return f"pyb::List<{_SCALAR[e.name]}, {LIST_RT[e.name]}>"
        if e.name == "list" and e.elem is not None and e.elem.name in LIST_RT:
            return f"pyb::List2<{_trait(e)}>"
    if t.name == "dict" and t.key is not None and t.elem is not None:
        if t.key.name in ("int", "str") and t.elem.name in _SCALAR:
            return f"pyb::Dict<{_SCALAR[t.key.name]}, {_SCALAR[t.elem.name]}, {dict_rt_name(t)}>"
    return None


def _gen_wrapper(modname: str, funcs: List[A.FuncDef], tc, mut: Dict[str, Set[int]]) -> str:
    out = ['',
           '/* ------------------------------------------------------------------',
           ' * pybind11 glue (generated).  Arguments are copied in, results copied',
           ' * out; mutated list/dict arguments are written back in place.',
           ' * ---------------------------------------------------------------- */',
           '#include "pyrt_bridge.hpp"',
           'namespace py = pybind11;', '']
    for f in funcs:
        sig = tc.funcs[f.name]
        ps = f.params
        args = ", ".join(f"py::object a_{p.name}" for p in ps)
        out.append(f"// {f.name}({', '.join(p.name + ': ' + str(t) for p, t in zip(ps, sig.params))}) -> {sig.ret}")
        out.append(f"static py::object w_{f.name}({args}) {{")
        out.append("    pyb::Arena _arena;")
        for i, (p, t) in enumerate(zip(ps, sig.params)):
            out.append(f"    using T{i} = {_trait(t)};")
            out.append(f"    T{i}::C c_{p.name} = T{i}::in(a_{p.name}.ptr());")
        wb = [f"T{i}::back(a_{ps[i].name}.ptr(), c_{ps[i].name});"
              for i in sorted(mut[f.name]) if _is_container(sig.params[i])]
        call = f"f_{f.name}({', '.join('c_' + p.name for p in ps)})"
        has_ret = sig.ret.name != "None"
        if has_ret:
            out.append(f"    using TR = {_trait(sig.ret)};")
            out.append("    TR::C _r{};")
        if wb:
            out.append("    auto _writeback = [&]() {")
            out += [f"        {w}" for w in wb]
            out.append("    };")
        out.append("    try {")
        out.append(f"        {'_r = ' if has_ret else ''}{call};")
        out.append("    } catch (const pyrt::PythonException &_e) {")
        if wb:
            out.append("        _writeback();")
        out.append("        pyb::raise(_e);")
        out.append("    }")
        if wb:
            out.append("    _writeback();")
        out.append("    return pyb::steal(TR::out(_r));" if has_ret else "    return py::none();")
        out.append("}")
        out.append("")
    out.append(f"PYBIND11_MODULE({modname}, m) {{")
    out.append('    m.doc() = "PYTHIA-compiled module (library mode)";')
    out.append('    pyrt::pyrt_set_py_minor(PY_MINOR_VERSION);')
    out.append(f'    pyb::FallbackError = PyErr_NewException("{modname}.FallbackError", PyExc_Exception, nullptr);')
    out.append('    m.attr("FallbackError") = py::reinterpret_borrow<py::object>(pyb::FallbackError);')
    out.append(f'    pyb::SemanticError = PyErr_NewException("{modname}.PythiaSemanticError", PyExc_RuntimeError, nullptr);')
    out.append('    m.attr("PythiaSemanticError") = py::reinterpret_borrow<py::object>(pyb::SemanticError);')
    if getattr(tc, "_fn_globals", None):
        out.append('    pythia_init_globals();')
    for f in funcs:
        pa = "".join(", " + _lx.arg_spec(p) for p in f.params)
        out.append(f'    m.def("{f.name}", &w_{f.name}{pa});')
    out.append("}")
    return "\n".join(out) + "\n"


# ------------------------------------------------------------------- driver
def _fail(res: LibResult, diags: List[dict], error: str) -> LibResult:
    res.ok = False
    res.diagnostics = diags
    res.error = error
    return res


def _fmt_diag(d: dict) -> str:
    return f"{d['line']}:{d['col']}: {d['kind']}: {d['msg']}"


def _front(src: str, filename: str, funcs: Sequence[str], res: LibResult):
    """parse -> typecheck -> lower -> elide -> emit(library). Returns
    (mod, tc, notes, stats, cpp) or None after filling res with diagnostics."""
    try:
        mod, syn = parse(src, filename)
    except LexError as e:
        d = [{"line": e.line, "col": e.col, "kind": "SyntaxError", "msg": e.msg}]
        _fail(res, d, _fmt_diag(d[0]))
        return None
    if syn:
        d = [{"line": x.line, "col": x.col, "kind": x.kind, "msg": x.msg} for x in syn]
        _fail(res, d, _fmt_diag(d[0]))
        return None
    tc, errs = typecheck(mod, filename)
    if errs:
        d = [{"line": x.line, "col": x.col, "kind": x.kind, "msg": x.msg}
             for x in sorted(errs, key=lambda x: (x.line, x.col))]
        _fail(res, d, _fmt_diag(d[0]))
        return None
    # exposure checks
    diags = []
    for name in funcs:
        f = next((g for g in mod.funcs if g.name == name), None)
        if f is None:
            diags.append({"line": 1, "col": 1, "kind": "LibraryError",
                          "msg": f"function {name!r} is not defined at module level"})
            continue
        sig = tc.funcs[name]
        _lx.check_exposed(f, lambda ln, col, msg: diags.append(
            {"line": ln, "col": col, "kind": "LibraryError", "msg": msg}))
        for p, t in list(zip(f.params, sig.params)) + [(None, sig.ret)]:
            if t.name != "None" and _trait(t) is None:
                what = f"parameter {p.name!r}" if p else "return value"
                why = ("class marshalling not supported" if t.name in tc.classes
                       else "unsupported type for marshalling")
                diags.append({"line": f.line, "col": f.col, "kind": "LibraryError",
                              "msg": f"{name}(): {why} ({what}: {t})"})
    res.fidelity = _lx.check_globals(mod, tc, lambda ln, col, msg: diags.append(
        {"line": ln, "col": col, "kind": "LibraryError", "msg": msg}))
    if diags:
        _fail(res, diags, _fmt_diag(diags[0]))
        return None
    notes = lower(mod, tc)
    stats = elide_guards(mod, exposed=set(funcs))
    line_map: dict = {}
    cpp = emit(mod, tc, os.path.basename(filename), library=True, line_map=line_map)
    res.cpp_line_map = line_map
    return mod, tc, notes, stats, cpp


def _library_notes(mod: A.Module, notes: List[FidelityNote]) -> List[dict]:
    out = []
    for n in notes:
        d = dataclasses.asdict(n)
        if n.cls.startswith("D7"):
            d["detail"] = ("PySub objects (str, list, dict) are heap-allocated by the runtime "
                           "and CPython reclaims them by reference counting.")
            d["mitigation"] = ("library wrappers run each call inside a memory arena that frees "
                               "every str/list/dict allocated during the call after the result "
                               "has been copied back; nothing leaks across calls.")
        out.append(d)

    def add(line, col, cls, detail, mit, sev):
        out.append({"line": line, "col": col, "cls": cls, "detail": detail,
                    "mitigation": mit, "severity": sev})

    add(0, 0, "L1 copy semantics at the Python boundary",
        "Arguments are copied into the compiled runtime and results copied back, so object "
        "identity, aliasing between arguments (the same list passed twice) and tuples are "
        "not preserved.",
        "list/dict arguments the function may mutate are written back into the caller's "
        "object in place after the call (also when an exception is raised).", "guarded")
    rec = _call_graph_cycle(mod)
    if rec is not None:
        add(rec.line, rec.col, "L2 recursion depth",
            "CPython raises RecursionError at ~1000 frames; the compiled code recurses on the "
            "native stack and would crash the process on very deep recursion.",
            "none; keep recursion shallow or avoid compiling this function.", "divergent")
    if mod.main:
        add(mod.main[0].line, mod.main[0].col, "L3 module-level statements",
            "Statements outside functions are not part of the compiled library, except the top-level "
            "assignments of module-level variables that compiled functions read: those run once at import.",
            "the original module still executes them in Python.", "guarded")
    for n in _walk(mod):
        if isinstance(n, A.StrLit) and not n.value.isascii():
            add(n.line, n.col, "L4 non-ASCII string literal",
                "str is byte-based in the runtime: len()/indexing count UTF-8 bytes.",
                "avoid non-ASCII literals in compiled functions.", "divergent")
            break
    return out


def _build_hash(cpp: str, wrapper_tpl: str, modname_explicit: Optional[str]) -> str:
    h = hashlib.sha256()
    for part in (cpp, wrapper_tpl, _runtime_digest(), _toolchain_id(), modname_explicit or ""):
        h.update(part.encode("utf-8") + b"\0")
    return h.hexdigest()


def build_library(src: str, funcs: Sequence[str], out_dir: str, modname: Optional[str] = None,
                  filename: str = "<mod>.py", build: bool = True, cache_dir: Optional[str] = None,
                  extra_cache_dirs: Sequence[str] = ()) -> LibResult:
    res = LibResult()
    funcs = list(dict.fromkeys(funcs))
    if modname is not None and not _IDENT.match(modname):
        return _fail(res, [], f"invalid module name {modname!r}")
    if not funcs:
        return _fail(res, [], "no functions requested")
    try:
        front = _front(src, filename, funcs, res)
    except RecursionError:
        return _fail(res, [{"line": 1, "col": 1, "kind": "SyntaxError",
                            "msg": "expression nesting too deep"}], "expression nesting too deep")
    if front is None:
        return res
    mod, tc, notes, stats, cpp = front
    mut = _mutated_params(mod)
    fdefs = [next(g for g in mod.funcs if g.name == n) for n in funcs]

    # modname default depends on the hash, the hash on the wrapper text: hash a
    # wrapper generated with a placeholder name, then substitute the real one.
    wrapper_tpl = _gen_wrapper("@MOD@", fdefs, tc, mut)
    bh = _build_hash(cpp, wrapper_tpl, modname)
    modname = modname or "pythia_" + bh[:8]
    wrapper = wrapper_tpl.replace("@MOD@", modname)

    res.modname, res.cpp, res.wrapper_cpp, res.build_hash = modname, cpp, wrapper, bh
    res.fidelity = _library_notes(mod, notes) + res.fidelity
    res.guard_elision = {"elided": stats.elided, "kept": stats.kept}
    res.exposed = [{"name": f.name,
                    "params": [str(t) for t in tc.funcs[f.name].params],
                    "ret": str(tc.funcs[f.name].ret),
                    "param_names": [p.name for p in f.params],
                    "mutates": [f.params[i].name for i in sorted(mut[f.name])
                                if _is_container(tc.funcs[f.name].params[i])]} for f in fdefs]

    os.makedirs(out_dir, exist_ok=True)
    cpp_path = os.path.join(out_dir, modname + ".cpp")
    with open(cpp_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(cpp + wrapper)
    res.cpp_path = cpp_path
    res.ok = True
    if not build:
        return res

    ext = sysconfig.get_config_var("EXT_SUFFIX") or ".so"
    so_out = os.path.join(out_dir, modname + ext)
    cache_dir = cache_dir or default_cache_dir()
    os.makedirs(cache_dir, exist_ok=True)

    # cache lookup: own dir first, then read-only extras (offline demo cache)
    for d in [cache_dir, *extra_cache_dirs]:
        hit = os.path.join(d, bh + ".so")
        if os.path.exists(hit):
            _install(hit, so_out)
            res.so_path, res.cached, res.build_log = so_out, True, f"cache hit: {hit}"
            return res

    cc = _compiler()[0]
    if cc is None:
        res.ok = False
        skipped = _tc.find_cxx()[2]
        res.error = ("no usable C++17 compiler found. " + (_tc.describe()["hint"] or "")
                     + (f" ({'; '.join(skipped)})" if skipped else ""))
        return res
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:       # runtime object and PCH build concurrently
        f_pch = ex.submit(_bridge_pch, cache_dir)
        obj, rt_log = _runtime_object(cache_dir)
        pch = f_pch.result()
    if obj is None:
        res.ok, res.build_log = False, rt_log
        res.error = "C++ build failed (runtime): " + rt_log[:2000]
        return res
    tmp_so = os.path.join(cache_dir, f"{bh}.{uuid.uuid4().hex[:8]}.tmp.so")
    cmd = [cc, *FLAGS, "-shared", *_includes()]
    link = _tc.python_link_args()
    rc, log = _run(cmd + (["-include", pch] if pch else []) + [cpp_path, obj, *link, "-o", tmp_so])
    if rc != 0 and pch and ("gch" in log or "pch" in log.lower()):
        rc, log = _run(cmd + [cpp_path, obj, *link, "-o", tmp_so])  # PCH trouble: build without
    res.compile_s = round(time.perf_counter() - t0, 3)
    res.build_log = (rt_log + log).strip()
    if rc != 0:
        res.ok = False
        res.error = "C++ build failed: " + log[:2000]
        return res
    os.replace(tmp_so, os.path.join(cache_dir, bh + ".so"))
    _atomic_write(os.path.join(cache_dir, bh + ".meta.json"), json.dumps(
        {"modname": modname, "funcs": funcs, "compile_s": res.compile_s,
         "toolchain": _toolchain_id(), "created": time.time()}).encode())
    _install(os.path.join(cache_dir, bh + ".so"), so_out)
    res.so_path = so_out
    return res
