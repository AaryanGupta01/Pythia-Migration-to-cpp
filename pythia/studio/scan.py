"""Static scan: ast-scan every .py, decide eligibility with the REAL PySub parser + typechecker.

Public API (CONTRACTS section 9):
    scan_workspace(ws, emit) -> list[FunctionRecord]
    extract_pysub(rec, ws, annotated_src=None, override_src=None) -> Extract

Design notes
  * `ast` pre-scan gives plain-English reasons for constructs the PySub grammar cannot express
    (closures, numpy, comprehensions...). The final VERIFIABLE verdict always comes from running the
    real `pythia.parser.parse` + `pythia.typecheck.typecheck` on the extracted module.
  * PySub functions are closed (module globals are invisible), so module-level *scalar* constants are
    inlined as literals; list/dict globals are not inlined (mutation + per-call rebuild cost).
"""
from __future__ import annotations

import ast
import builtins
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from .models import FunctionRecord, Workspace
from .pysub_rules import ALL_METHOD_NAMES, BUILTINS, EXC_NAMES, check_source

# ----------------------------------------------------------------------------- tables
IO_BUILTINS = {"open": "file I/O (`open`)", "input": "reads stdin (`input`)",
               "exec": "runs dynamic code (`exec`)", "eval": "runs dynamic code (`eval`)",
               "compile": "runs dynamic code (`compile`)", "__import__": "dynamic import"}
DYNAMIC_BUILTINS = {"isinstance", "issubclass", "type", "getattr", "setattr", "hasattr", "delattr",
                    "vars", "globals", "locals", "id", "callable", "super", "dir"}
FIXABLE_BUILTINS = {"sum", "sorted", "enumerate", "zip", "round", "divmod", "pow", "any", "all",
                    "reversed", "map", "filter", "set", "frozenset", "list", "dict", "tuple", "ord",
                    "chr", "next", "iter", "repr", "format", "hash", "bin", "hex", "oct", "slice"}
UNSUPPORTED_TYPES = {"Optional", "Union", "Tuple", "tuple", "Any", "Callable", "Sequence", "Iterable",
                     "Iterator", "Generator", "Set", "set", "FrozenSet", "frozenset", "Literal", "Type",
                     "object", "bytes", "bytearray", "complex", "Mapping", "MutableMapping", "Deque",
                     "Counter", "DefaultDict", "OrderedDict", "NamedTuple", "TypedDict"}
BARE_CONTAINERS = {"list", "dict", "List", "Dict"}
THIRD_PARTY = {"numpy", "pandas", "scipy", "torch", "tensorflow", "sklearn", "cv2", "PIL", "matplotlib",
               "numba", "jax", "networkx", "sympy"}
IO_MODULES = {"os", "sys", "io", "pathlib", "shutil", "subprocess", "socket", "json", "pickle", "csv",
              "sqlite3", "requests", "urllib", "http", "logging", "tempfile", "glob", "gzip", "zipfile"}
NONDET_MODULES = {"random", "time", "datetime", "uuid", "secrets"}
MISSING_MARK = " (fixable)"
PYSUB_PARAM_TYPES = {"int", "float", "bool", "str", "list", "dict", "List", "Dict", "None"}
_BUILTIN_NAMES = set(dir(builtins))


# ----------------------------------------------------------------------------- results
@dataclass
class Extract:
    ok: bool
    source: str                      # standalone PySub module text; the target function starts at line 1
    helpers: List[str] = field(default_factory=list)       # names of same-module callee functions pulled in
    diagnostics: List[dict] = field(default_factory=list)  # pysub-relative {line,col,kind,msg,phase,fn}
    uses: List[str] = field(default_factory=list)          # module-level constants inlined as literals

    def to_dict(self) -> dict:
        return {"ok": self.ok, "source": self.source, "helpers": self.helpers,
                "diagnostics": self.diagnostics, "uses": self.uses}


@dataclass
class ModuleInfo:
    rel: str
    text: str
    lines: List[str]
    tree: ast.Module
    funcs: Dict[str, ast.AST] = field(default_factory=dict)
    classes: Dict[str, ast.ClassDef] = field(default_factory=dict)
    consts: Dict[str, object] = field(default_factory=dict)     # name -> python scalar
    nonconst_globals: Set[str] = field(default_factory=set)
    imports: Dict[str, Tuple[str, Optional[str]]] = field(default_factory=dict)  # alias -> (module, name|None)
    typing_names: Set[str] = field(default_factory=set)

    def func_text(self, name: str) -> str:
        n = self.funcs[name]
        return "\n".join(self.lines[n.lineno - 1:n.end_lineno])


@dataclass
class Own:
    hard: Dict[str, str] = field(default_factory=dict)
    fix: Dict[str, str] = field(default_factory=dict)
    missing: List[str] = field(default_factory=list)
    callees: Set[str] = field(default_factory=set)
    consts_used: Set[str] = field(default_factory=set)
    globals_used: Set[str] = field(default_factory=set)
    imports_used: Set[str] = field(default_factory=set)
    calls: Set[str] = field(default_factory=set)
    metrics: Dict[str, object] = field(default_factory=dict)


# ----------------------------------------------------------------------------- module model
def _norm(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _scalar_ok(v) -> bool:
    if v is None or isinstance(v, (bool, str)):
        return True if not isinstance(v, str) else (v.isascii() and all(c.isprintable() or c in "\n\t" for c in v))
    if isinstance(v, int):
        return abs(v) < 2 ** 63
    if isinstance(v, float):
        return math.isfinite(v)
    return False


class _NoConst(Exception):
    pass


def _const_eval(n: ast.AST, consts: Dict[str, object]):
    if isinstance(n, ast.Constant):
        if _scalar_ok(n.value):
            return n.value
        raise _NoConst
    if isinstance(n, ast.Name) and n.id in consts:
        return consts[n.id]
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
        v = _const_eval(n.operand, consts)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return -v if isinstance(n.op, ast.USub) else v
        raise _NoConst
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv,
                                                      ast.Mod, ast.Pow)):
        a, b = _const_eval(n.left, consts), _const_eval(n.right, consts)
        num = (int, float)
        if isinstance(a, num) and isinstance(b, num) and not isinstance(a, bool) and not isinstance(b, bool):
            if isinstance(n.op, ast.Pow) and (abs(b) > 64 or abs(a) > 1e6):
                raise _NoConst
            try:
                r = {ast.Add: lambda: a + b, ast.Sub: lambda: a - b, ast.Mult: lambda: a * b,
                     ast.Div: lambda: a / b, ast.FloorDiv: lambda: a // b, ast.Mod: lambda: a % b,
                     ast.Pow: lambda: a ** b}[type(n.op)]()
            except Exception:
                raise _NoConst
            if _scalar_ok(r) and not isinstance(r, complex):
                return r
        raise _NoConst
    raise _NoConst


def render_scalar(v) -> str:
    """PySub literal text for a python scalar. Negatives are parenthesised (precedence-safe)."""
    if v is None:
        return "None"
    if isinstance(v, bool):
        return "True" if v else "False"
    if isinstance(v, int):
        return f"({v})" if v < 0 else str(v)
    if isinstance(v, float):
        r = repr(v)
        return f"({r})" if v < 0 else r
    s = v.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return f'"{s}"'


def build_info(rel: str, text: str) -> ModuleInfo:
    text = _norm(text)
    tree = ast.parse(text)
    info = ModuleInfo(rel, text, text.split("\n"), tree)
    store_count: Dict[str, int] = {}
    global_decl: Set[str] = set()
    for st in tree.body:
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.funcs.setdefault(st.name, st)
            for n in ast.walk(st):
                if isinstance(n, ast.Global):
                    global_decl.update(n.names)
            continue
        if isinstance(st, ast.ClassDef):
            info.classes[st.name] = st
            continue
        if isinstance(st, ast.Import):
            for a in st.names:
                info.imports[(a.asname or a.name).split(".")[0]] = (a.name if a.asname else a.name.split(".")[0], None)
            continue
        if isinstance(st, ast.ImportFrom):
            mod = "." * st.level + (st.module or "")
            for a in st.names:
                if (st.module or "") in ("typing", "typing_extensions", "collections.abc"):
                    info.typing_names.add(a.asname or a.name)
                elif (st.module or "") != "__future__":
                    info.imports[a.asname or a.name] = (mod, a.name)
            continue
        for n in ast.walk(st):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                store_count[n.id] = store_count.get(n.id, 0) + 1
    for st in tree.body:                       # constants, in source order so they may reference earlier ones
        tgt = val = None
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            tgt, val = st.targets[0].id, st.value
        elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
            tgt, val = st.target.id, st.value
        if tgt and store_count.get(tgt) == 1 and tgt not in global_decl:
            try:
                info.consts[tgt] = _const_eval(val, info.consts)
            except _NoConst:
                pass
    info.nonconst_globals = (set(store_count) | global_decl) - set(info.consts)
    return info


def _load_info(ws: Workspace, rel: str) -> ModuleInfo:
    return build_info(rel, (ws.original / rel).read_text(encoding="utf-8", errors="replace"))


# ----------------------------------------------------------------------------- text preparation
def prep_text(text: str, consts: Dict[str, object], strip_doc: bool = True) -> Tuple[str, Set[str]]:
    """Inline scalar constants, normalise typing.List/Dict -> list/dict, strip docstrings.
    Line count is preserved (docstring lines become blank / `pass`). Returns (text, constants_used)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, set()
    lines = [l.encode("utf-8") for l in text.split("\n")]
    edits: List[Tuple[int, int, int, bytes]] = []
    used: Set[str] = set()
    for fn in tree.body:
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        local = {a.arg for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs}
        if fn.args.vararg:
            local.add(fn.args.vararg.arg)
        if fn.args.kwarg:
            local.add(fn.args.kwarg.arg)
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                local.add(n.id)
            elif isinstance(n, ast.ExceptHandler) and n.name:
                local.add(n.name)
        anns = [a.annotation for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs if a.annotation]
        if fn.returns:
            anns.append(fn.returns)
        anns += [n.annotation for n in ast.walk(fn) if isinstance(n, ast.AnnAssign)]
        ann_ids = {id(x) for a in anns for x in ast.walk(a)}
        for n in ast.walk(fn):
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and id(n) not in ann_ids \
                    and n.id in consts and n.id not in local and n.lineno == n.end_lineno:
                edits.append((n.lineno - 1, n.col_offset, n.end_col_offset, render_scalar(consts[n.id]).encode()))
                used.add(n.id)
            elif id(n) in ann_ids and isinstance(n, (ast.Name, ast.Attribute)) and n.lineno == n.end_lineno:
                if isinstance(n, ast.Name) and n.id in ("List", "Dict"):
                    edits.append((n.lineno - 1, n.col_offset, n.end_col_offset, n.id.lower().encode()))
                elif isinstance(n, ast.Attribute) and n.attr in ("List", "Dict") and isinstance(n.value, ast.Name):
                    edits.append((n.lineno - 1, n.col_offset, n.end_col_offset, n.attr.lower().encode()))
    seen = set()
    for ln, c0, c1, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        if (ln, c0) in seen:
            continue
        seen.add((ln, c0))
        b = lines[ln]
        lines[ln] = b[:c0] + rep + b[c1:]
    out = [b.decode("utf-8") for b in lines]
    if strip_doc:
        for fn in tree.body:
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and fn.body:
                d = fn.body[0]
                if isinstance(d, ast.Expr) and isinstance(d.value, ast.Constant) and isinstance(d.value.value, str):
                    for k in range(d.lineno - 1, d.end_lineno):
                        out[k] = ""
                    if len(fn.body) == 1:
                        out[d.lineno - 1] = " " * d.col_offset + "pass"
    return "\n".join(out), used


def _calls_in(text: str) -> Tuple[Set[str], Set[str]]:
    """(names called, names defined at top level) in a chunk of Python text."""
    try:
        t = ast.parse(text)
    except SyntaxError:
        return set(), set()
    called = {n.func.id for n in ast.walk(t) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    defined = {n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return called, defined


def _compose(info: ModuleInfo, target_name: str, target_text: str,
             sib_text: Callable[[str], str]) -> Tuple[str, List[str], List[str], List[Tuple[str, int, int]]]:
    ttext, used = prep_text(target_text, info.consts)
    ttext = ttext.rstrip("\n")
    called, defined = _calls_in(ttext)
    defined = defined | {target_name}
    todo = sorted(c for c in called if c in info.funcs and c not in defined)
    helpers: List[str] = []
    chunks: List[str] = []
    while todo:
        name = todo.pop(0)
        if name in helpers or name in defined:
            continue
        helpers.append(name)
        htext, hused = prep_text(sib_text(name), info.consts)
        used |= hused
        chunks.append(htext.rstrip("\n"))
        c2, d2 = _calls_in(htext)
        todo += sorted(c for c in c2 if c in info.funcs and c not in defined and c not in helpers and c not in todo)
    spans: List[Tuple[str, int, int]] = []
    line = 1
    parts = [ttext] + chunks
    names = [target_name] + helpers
    for nm, part in zip(names, parts):
        n = part.count("\n") + 1
        spans.append((nm, line, line + n - 1))
        line += n + 2
    source = "\n\n\n".join(parts) + "\n"
    return source, helpers, sorted(used), spans


def _fn_for_line(spans, line: int) -> str:
    for nm, a, b in spans:
        if a <= line <= b:
            return nm
    return spans[0][0] if spans else ""


def _run_extract(info: ModuleInfo, name: str, target_text: str, sib_text: Callable[[str], str]) -> Extract:
    source, helpers, uses, spans = _compose(info, name, target_text, sib_text)
    diags = check_source(source, f"{info.rel}::{name}")
    for d in diags:
        d["phase"] = "eligibility"
        d["fn"] = _fn_for_line(spans, d["line"])
    return Extract(not diags, source, helpers, diags, uses)


def extract_pysub(rec: FunctionRecord, ws: Workspace, annotated_src: Optional[str] = None,
                  override_src: Optional[str] = None) -> Extract:
    """Standalone PySub module for `rec`: target first (its line k == pysub line k when override_src is None),
    then transitive same-module callees. Constants inlined, typing.List/Dict normalised, docstrings stripped."""
    info: Optional[ModuleInfo] = rec.private.get("modinfo")
    try:
        if info is None:
            info = _load_info(ws, rec.file)
            rec.private["modinfo"] = info
    except Exception as e:
        return Extract(False, "", [], [{"line": 1, "col": 1, "kind": "InternalError", "msg": f"cannot read {rec.file}: {e}",
                                        "phase": "eligibility", "fn": rec.name}], [])
    sibs: Dict[str, FunctionRecord] = rec.private.get("siblings") or {}

    def sib_text(n: str) -> str:
        s = sibs.get(n)
        return (s.sources.get("annotated") if s is not None else None) or info.func_text(n)

    if "." in rec.qualname or rec.name not in info.funcs:
        return Extract(False, rec.sources.get("original") or "", [], [
            {"line": 1, "col": 1, "kind": "TypeError", "msg": rec.reason or "not a module-level function",
             "phase": "eligibility", "fn": rec.name}], [])
    target = override_src or annotated_src or rec.sources.get("original") or info.func_text(rec.name)
    return _run_extract(info, rec.name, target, sib_text)


# ----------------------------------------------------------------------------- static pre-scan
def _root_name(n: ast.AST) -> Optional[ast.Name]:
    while True:
        if isinstance(n, ast.Name):
            return n
        if isinstance(n, ast.Attribute):
            n = n.value
        elif isinstance(n, ast.Subscript):
            n = n.value
        elif isinstance(n, ast.Call):
            n = n.func
        else:
            return None


def _chain(n: ast.AST) -> str:
    try:
        return ast.unparse(n)
    except Exception:
        return "?"


def _module_reason(chain: str, mod: str) -> str:
    root = mod.split(".")[0]
    if root in THIRD_PARTY:
        return f"calls {root} (`{chain}`) — third-party library code is outside PySub"
    if root in IO_MODULES:
        return f"does file or system I/O (`{chain}`)"
    if root == "math":
        return f"calls `{chain}` — PySub has no math module"
    if root in NONDET_MODULES:
        return f"calls `{chain}` — the `{root}` module is outside PySub"
    return f"calls `{chain}` from module `{mod}`, which is outside PySub"


def _loop_depth(fn: ast.AST) -> int:
    def rec(n, d):
        best = d
        for c in ast.iter_child_nodes(n):
            if isinstance(c, (ast.For, ast.While, ast.AsyncFor)):
                best = max(best, rec(c, d + 1))
            elif isinstance(c, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                best = max(best, rec(c, d + len(c.generators)))
            else:
                best = max(best, rec(c, d))
        return best
    return rec(fn, 0)


def analyze(fn: ast.AST, info: ModuleInfo, is_method: bool = False) -> Own:
    o = Own()
    top = fn
    hard, fix = o.hard, o.fix
    args = top.args
    all_args = args.posonlyargs + args.args + args.kwonlyargs
    if isinstance(top, ast.AsyncFunctionDef):
        hard["async"] = "is an async function"
    if top.decorator_list:
        hard["deco"] = "is decorated (`@" + _chain(top.decorator_list[0]).split("(")[0] + "`)"
    if args.vararg:
        hard["vararg"] = "uses *args"
    if args.kwarg:
        hard["kwarg"] = "uses **kwargs"
    if args.kwonlyargs:
        hard["kwonly"] = "uses keyword-only parameters"
    if args.defaults or any(d is not None for d in args.kw_defaults):
        hard["defaults"] = "has default parameter values (PySub requires every argument)"

    local = {a.arg for a in all_args} | ({args.vararg.arg} if args.vararg else set()) | ({args.kwarg.arg} if args.kwarg else set())
    nodes = list(ast.walk(top))
    nested_defs = {n.name for n in nodes if n is not top and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    local |= nested_defs                           # nested def: reported once, as a closure
    for n in nodes:
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            local.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            local.add(n.name)

    # annotations
    anns: List[Tuple[str, ast.AST]] = [(a.arg, a.annotation) for a in all_args if a.annotation is not None]
    if top.returns is not None:
        anns.append(("return", top.returns))
    anns += [(_chain(n.target), n.annotation) for n in nodes if isinstance(n, ast.AnnAssign)]
    ann_ids = {id(x) for _, a in anns for x in ast.walk(a)}
    for a in all_args:
        if is_method and a.arg == "self":
            continue
        if a.annotation is None:
            o.missing.append(a.arg)
        elif isinstance(a.annotation, ast.Name) and a.annotation.id in BARE_CONTAINERS:
            o.missing.append(a.arg)
    if top.returns is None:
        if any(isinstance(n, ast.Return) and n.value is not None and
               not (isinstance(n.value, ast.Constant) and n.value.value is None) for n in nodes):
            o.missing.append("return")
    elif isinstance(top.returns, ast.Name) and top.returns.id in BARE_CONTAINERS:
        o.missing.append("return")
    # parameters typed as objects of a non-PySub type: method calls / attribute reads on them can never be rewritten away
    obj_params: Dict[str, str] = {}
    for a in all_args:
        ann = a.annotation
        if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
            ann = ast.Name(id=ann.value.split("[")[0].split(".")[-1])
        if isinstance(ann, ast.Attribute):
            ann = ast.Name(id=ann.attr)
        if isinstance(ann, ast.Name) and ann.id not in PYSUB_PARAM_TYPES and ann.id not in BARE_CONTAINERS \
                and not (is_method and a.arg == "self"):
            obj_params[a.arg] = ann.id
    for who, a in anns:
        for x in ast.walk(a):
            if isinstance(x, ast.Name):
                if x.id in info.classes:
                    hard[f"cls:{x.id}"] = f"uses class `{x.id}` (user classes are not supported in v1)"
                elif x.id in UNSUPPORTED_TYPES:
                    hard[f"ty:{x.id}"] = f"uses type `{x.id}`, which PySub does not have"
            elif isinstance(x, ast.BinOp) and isinstance(x.op, ast.BitOr):
                hard["ty:union"] = "uses a union/Optional type, which PySub does not have"

    call_funcs = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
    for_range = {id(n.iter) for n in nodes if isinstance(n, ast.For) and isinstance(n.iter, ast.Call)
                 and isinstance(n.iter.func, ast.Name) and n.iter.func.id == "range"}
    attr_roots = {id(r) for n in nodes if isinstance(n, ast.Attribute) for r in [_root_name(n)] if r is not None}
    raise_calls = {id(n.exc) for n in nodes if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)}
    ret_tuples = {id(n.value) for n in nodes if isinstance(n, ast.Return) and isinstance(n.value, ast.Tuple)}

    for n in nodes:
        if n is top:
            continue
        t = type(n)
        if t in (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda):
            hard["closure"] = "uses a closure (nested function or lambda)"
        elif t in (ast.Yield, ast.YieldFrom):
            hard["yield"] = "is a generator (`yield`)"
        elif t is ast.Await:
            hard["await"] = "uses `await`"
        elif t in (ast.Global, ast.Nonlocal):
            hard["global"] = "uses `global`/`nonlocal`"
        elif t in (ast.With, ast.AsyncWith):
            hard["with"] = "uses a `with` block (context managers / file handling)"
        elif t in (ast.Import, ast.ImportFrom):
            hard["import"] = "imports inside the function"
        elif t is ast.Match:
            hard["match"] = "uses a `match` statement"
        elif t is ast.Delete:
            fix["del"] = "`del` statement — PySub has none (fixable by rewrite)"
        elif t is ast.Assert:
            fix["assert"] = "`assert` — PySub has none (fixable by rewrite)"
        elif t is ast.NamedExpr:
            fix["walrus"] = "walrus operator — PySub has none (fixable by rewrite)"
        elif t is ast.JoinedStr:
            fix["fstr"] = "f-string — PySub has none (fixable by rewrite with str() and +)"
        elif t is ast.ListComp:
            fix["lc"] = "list comprehension — PySub has none (fixable by rewrite)"
        elif t is ast.SetComp:
            fix["sc"] = "set comprehension — PySub has no sets (fixable by rewrite)"
        elif t is ast.DictComp:
            fix["dc"] = "dict comprehension — PySub has none (fixable by rewrite)"
        elif t is ast.GeneratorExp:
            fix["ge"] = "generator expression — PySub has none (fixable by rewrite)"
        elif t is ast.IfExp:
            fix["ifexp"] = "conditional expression (`x if c else y`) — PySub has none (fixable by rewrite)"
        elif t is ast.Set:
            fix["set"] = "set literal — PySub has no sets (fixable by rewrite)"
        elif t is ast.Starred:
            fix["star"] = "star-expression — PySub has none (fixable by rewrite)"
        elif t is ast.Slice:
            fix["slice"] = "slicing (`a[i:j]`) — PySub has none (fixable by rewrite)"
        elif t is ast.Dict and any(k is None for k in n.keys):
            fix["dstar"] = "dict unpacking (`**`) — PySub has none (fixable by rewrite)"
        elif t is ast.Subscript and isinstance(n.slice, ast.Tuple) and id(n) not in ann_ids:
            fix["multiidx"] = "multi-dimensional index `a[i, j]` — use a[i][j] (fixable by rewrite)"
        elif t is ast.Compare:
            if len(n.ops) > 1:
                fix["chain"] = "chained comparison (`a < b < c`) — PySub has none (fixable by rewrite)"
            if any(isinstance(op, (ast.Is, ast.IsNot)) for op in n.ops):
                fix["is"] = "`is` / `is not` comparison — PySub has none (fixable by rewrite)"
        elif t is ast.BinOp:
            if isinstance(n.op, ast.MatMult):
                hard["matmul"] = "uses matrix multiplication (`@`)"
            elif isinstance(n.op, (ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift, ast.RShift)) and id(n) not in ann_ids:
                hard["bitops"] = "uses bitwise operators (|, &, ^, <<, >>), which PySub does not have"
        elif t is ast.UnaryOp and isinstance(n.op, ast.Invert):
            hard["bitops"] = "uses bitwise operators (|, &, ^, <<, >>), which PySub does not have"
        elif t is ast.AugAssign and isinstance(n.op, (ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift, ast.RShift, ast.MatMult)):
            hard["bitops"] = "uses bitwise operators (|, &, ^, <<, >>), which PySub does not have"
        elif t is ast.Constant:
            v = n.value
            if isinstance(v, (bytes, complex)):
                hard["lit"] = "uses a bytes/complex literal"
            elif isinstance(v, int) and not isinstance(v, bool) and abs(v) >= 2 ** 63:
                hard["bigint"] = "uses an integer literal beyond 64 bits"
        elif t is ast.Assign:
            if len(n.targets) > 1:
                fix["chainassign"] = "chained assignment (`a = b = 0`) — fixable by rewrite"
            for tg in n.targets:
                if isinstance(tg, (ast.Tuple, ast.List)):
                    fix["unpack"] = "tuple unpacking (`a, b = ...`) — PySub has no tuples (fixable by rewrite)"
        elif t is ast.AnnAssign:
            if n.value is None:
                fix["annnoval"] = "annotation without a value — fixable by rewrite"
            if not isinstance(n.target, ast.Name):
                fix["annattr"] = "annotated attribute/subscript assignment — fixable by rewrite"
        elif t is ast.For or t is ast.AsyncFor:
            if isinstance(n.target, (ast.Tuple, ast.List)):
                fix["foruppack"] = "loop over tuples (`for a, b in ...`) — PySub has no tuples (fixable by rewrite)"
            if n.orelse:
                fix["forelse"] = "`for ... else` — PySub has none (fixable by rewrite)"
        elif t is ast.While and n.orelse:
            fix["forelse"] = "`while ... else` — PySub has none (fixable by rewrite)"
        elif t is ast.Try:
            if n.finalbody:
                fix["finally"] = "`try ... finally` — PySub has none (fixable by rewrite)"
            if n.orelse:
                fix["tryelse"] = "`try ... else` — PySub has none (fixable by rewrite)"
            for h in n.handlers:
                if isinstance(h.type, ast.Tuple):
                    fix["exctuple"] = "`except (A, B)` — PySub catches one exception type per clause (fixable by rewrite)"
                elif isinstance(h.type, ast.Name) and h.type.id not in EXC_NAMES:
                    fix[f"exc:{h.type.id}"] = (f"catches `{h.type.id}` — PySub only knows "
                                               f"{', '.join(sorted(EXC_NAMES))} (fixable by rewrite)")
        elif t is ast.Raise:
            if n.exc is None:
                fix["bareraise"] = "bare `raise` — fixable by rewrite"
            else:
                nm = n.exc.func if isinstance(n.exc, ast.Call) else n.exc
                if isinstance(nm, ast.Name) and nm.id not in EXC_NAMES:
                    fix[f"raise:{nm.id}"] = (f"raises `{nm.id}` — PySub only raises "
                                             f"{', '.join(sorted(EXC_NAMES))} (fixable by rewrite)")
            if n.cause is not None:
                fix["raisefrom"] = "`raise ... from ...` — fixable by rewrite"
        elif t is ast.Return and isinstance(n.value, ast.Tuple):
            hard["rettuple"] = "returns a tuple (PySub has no tuples)"
        elif t is ast.Tuple and isinstance(n.ctx, ast.Load) and id(n) not in ann_ids and id(n) not in ret_tuples:
            fix["tuple"] = "tuple value — PySub has no tuples (fixable by rewrite)"

        # ---- names, calls, attributes
        if t is ast.Call and id(n) in raise_calls:
            pass                                    # `raise X("msg")`: judged by the Raise rule above
        elif t is ast.Call:
            f = n.func
            if n.keywords:
                fix["kwargs"] = "keyword arguments in a call — PySub has none (fixable by rewrite)"
            if isinstance(f, ast.Name):
                nm = f.id
                o.calls.add(nm)
                if nm in nested_defs:
                    pass
                elif nm in local:
                    hard["fnparam"] = f"calls `{nm}`, a function held in a variable or parameter (no first-class functions)"
                elif nm in info.funcs:
                    o.callees.add(nm)
                elif nm in info.classes:
                    hard[f"cls:{nm}"] = f"constructs class `{nm}` (user classes are not supported in v1)"
                elif nm in info.imports:
                    mod = info.imports[nm][0]
                    o.imports_used.add(mod)
                    root = mod.split(".")[0]
                    if root in THIRD_PARTY or root in IO_MODULES or root in NONDET_MODULES or root == "math":
                        hard[f"mod:{nm}"] = _module_reason(nm, mod)
                    else:
                        hard[f"mod:{nm}"] = f"calls `{nm}` from another module (`{mod}`); cross-module callees are not pulled in"
                elif nm in IO_BUILTINS:
                    hard[f"io:{nm}"] = IO_BUILTINS[nm]
                elif nm in DYNAMIC_BUILTINS:
                    hard[f"dyn:{nm}"] = f"uses dynamic typing (`{nm}`)"
                elif nm == "range":
                    if id(n) not in for_range:
                        fix["range"] = "`range()` outside a for-loop header — fixable by rewrite"
                elif nm in FIXABLE_BUILTINS:
                    fix[f"b:{nm}"] = f"`{nm}()` — PySub has no {nm} (fixable by rewrite)"
                elif nm in BUILTINS:
                    if nm in ("min", "max") and len(n.args) != 2:
                        fix[f"b:{nm}"] = f"`{nm}()` with {len(n.args)} arguments — PySub needs exactly two (fixable by rewrite)"
                elif nm in _BUILTIN_NAMES:
                    fix[f"b:{nm}"] = f"`{nm}()` — not available in PySub (fixable by rewrite)"
                else:
                    hard[f"undef:{nm}"] = f"calls `{nm}`, which is not defined in this module"
            elif isinstance(f, ast.Attribute):
                r = _root_name(f)
                chain = _chain(f)
                o.calls.add(chain if len(chain) < 40 else f.attr)
                if r is not None and r.id in info.imports and r.id not in local:
                    mod = info.imports[r.id][0]
                    o.imports_used.add(mod)
                    hard[f"mod:{chain}"] = _module_reason(chain, mod)
                elif r is not None and r.id in info.classes and r.id not in local:
                    hard[f"cls:{r.id}"] = f"uses class `{r.id}` (user classes are not supported in v1)"
                elif r is not None and r.id in info.nonconst_globals and r.id not in local:
                    hard[f"glob:{r.id}"] = f"uses module-level variable `{r.id}` (mutable global, invisible to PySub)"
                elif r is not None and r.id in obj_params and r.id in local:
                    hard[f"obj:{r.id}"] = (f"calls `.{f.attr}()` on `{r.id}`, an object of type `{obj_params[r.id]}` "
                                           "(user classes cannot cross into PySub)")
                elif f.attr not in ALL_METHOD_NAMES:
                    fix[f"m:{f.attr}"] = f"method `.{f.attr}()` is not in PySub (fixable by rewrite)"
            else:
                hard["dyncall"] = "calls the result of an expression (no first-class functions)"
        elif t is ast.Attribute and id(n) not in call_funcs and id(n) not in ann_ids:
            r = _root_name(n)
            if r is not None and r.id in info.imports and r.id not in local:
                mod = info.imports[r.id][0]
                o.imports_used.add(mod)
                hard[f"mod:{_chain(n)}"] = _module_reason(_chain(n), mod).replace("calls ", "uses ", 1)
            elif r is not None and r.id in obj_params and r.id in local:
                hard[f"obj:{r.id}"] = (f"reads `.{n.attr}` of `{r.id}`, an object of type `{obj_params[r.id]}` "
                                       "(user classes cannot cross into PySub)")
            elif r is not None and r.id in local and not isinstance(n.value, ast.Attribute):
                fix[f"attr:{n.attr}"] = f"attribute access `.{n.attr}` — objects are not PySub values (fixable by rewrite)"
        elif t is ast.Attribute and id(n) in ann_ids:
            r = _root_name(n)
            if r is not None and r.id in info.imports:
                mod = info.imports[r.id][0]
                o.imports_used.add(mod)
                hard[f"mod:{_chain(n)}"] = _module_reason(_chain(n), mod).replace("calls ", "uses ", 1)
        elif t is ast.Name and isinstance(n.ctx, ast.Load) and id(n) not in call_funcs \
                and id(n) not in ann_ids and id(n) not in attr_roots:
            nm = n.id
            if nm in local:
                continue
            if nm in info.consts:
                o.consts_used.add(nm)
                o.globals_used.add(nm)
            elif nm in info.nonconst_globals:
                o.globals_used.add(nm)
                hard[f"glob:{nm}"] = f"reads module-level variable `{nm}` that is not a scalar constant (invisible to PySub)"
            elif nm in info.funcs:
                hard[f"fnval:{nm}"] = f"uses function `{nm}` as a value (PySub has no first-class functions)"
            elif nm in info.classes:
                hard[f"cls:{nm}"] = f"uses class `{nm}` (user classes are not supported in v1)"
            elif nm in info.imports:
                o.imports_used.add(info.imports[nm][0])
                hard[f"mod:{nm}"] = f"uses `{nm}` imported from `{info.imports[nm][0]}`, which is outside PySub"
        # attribute roots that are consts/globals
        if t is ast.Attribute:
            r = _root_name(n)
            if r is not None and r.id in info.nonconst_globals and r.id not in local and r.id not in info.imports:
                o.globals_used.add(r.id)
                hard[f"glob:{r.id}"] = f"reads module-level variable `{r.id}` that is not a scalar constant (invisible to PySub)"

    # metrics
    end = getattr(top, "end_lineno", top.lineno)
    arith = sum(1 for n in nodes if isinstance(n, (ast.BinOp, ast.AugAssign, ast.Compare)))
    expr_nodes = sum(1 for n in nodes if isinstance(n, (ast.expr, ast.stmt)))
    o.metrics = {"size_lines": end - top.lineno + 1, "loop_depth": _loop_depth(top),
                 "arith_density": round(min(1.0, arith / max(1, expr_nodes) * 2.0), 2),
                 "calls": sorted(o.calls), "imports": sorted(o.imports_used),
                 "uses_globals": sorted(o.globals_used)}
    return o


# ----------------------------------------------------------------------------- verdicts
def _short(items: List[str], limit: int = 3) -> str:
    items = [i for i in items if i]
    s = "; ".join(items[:limit])
    return s + (f" (+{len(items) - limit} more)" if len(items) > limit else "")


def _missing_reason(missing: List[str]) -> str:
    names = [("return type" if m == "return" else f"`{m}`") for m in missing]
    return f"missing annotations ({', '.join(names)}) — fixable from observed types"


_RE_REBIND = re.compile(r"variable '(\w+)' was inferred as ([^;]+); cannot rebind to (.+?)\.")
_RE_STATIC = re.compile(r"'(\w+)' has static type ([^;]+); cannot assign (.+)")


def classify_errors(diags: List[dict]) -> Tuple[str, str, str]:
    """(eligibility, reason, fix_kind) from real typechecker/parser diagnostics."""
    hard: List[str] = []
    soft: List[str] = []
    kind = "rewrite"
    for d in diags:
        m = d["msg"]
        mm = _RE_REBIND.search(m) or _RE_STATIC.search(m)
        if mm:
            hard.append(f"variable `{mm.group(1)}` changes type from {mm.group(2).strip()} to {mm.group(3).strip()} (dynamic typing)")
        elif (x := re.search(r"unknown type '(\w+)'", m)):
            hard.append(f"uses type `{x.group(1)}`, which PySub does not have")
        elif (x := re.search(r"name '(\w+)' is not defined", m)):
            hard.append(f"uses name `{x.group(1)}` that is not visible inside a PySub function (module state is invisible)")
        elif (x := re.search(r"function '(\w+)' is not defined", m)):
            hard.append(f"calls `{x.group(1)}`, which is not a function in this module")
        elif "first-class functions" in m or "nested function definitions" in m:
            hard.append("uses a closure / first-class function")
        elif "cannot infer element type of empty" in m or "cannot infer key/value type" in m:
            soft.append(f"empty list/dict literal needs a type annotation (line {d['line']}) — fixable")
            kind = "rewrite"
        elif "bare 'list'" in m or "bare 'dict'" in m:
            soft.append(f"bare list/dict annotation — element types come from observed types (line {d['line']}) — fixable")
            kind = "annotations"
        else:
            soft.append(f"line {d['line']}: {m} — fixable by rewrite")
    if hard:
        return "not_eligible", _short(hard, 2), kind
    return "fixable", _short(soft, 2) or "typechecker rejected the function — fixable by rewrite", kind


def _own_state(o: Own) -> str:
    return "hard" if o.hard else "fix" if (o.fix or o.missing) else "clean"


def _own_reason(o: Own) -> str:
    if o.hard:
        return _short(list(o.hard.values()), 2)
    parts = list(o.fix.values())
    if o.missing:
        parts.append(_missing_reason(o.missing))
    return _short(parts, 3)


def _closure(name: str, owns: Dict[str, Own]) -> List[str]:
    seen, order, stack = {name}, [], sorted(owns[name].callees)
    while stack:
        c = stack.pop(0)
        if c in seen or c not in owns:
            continue
        seen.add(c)
        order.append(c)
        stack += sorted(owns[c].callees)
    return order


def _decide(name: str, info: ModuleInfo, owns: Dict[str, Own]) -> Tuple[str, Optional[str], str, List[dict]]:
    """-> (eligibility, reason, fix_kind, diagnostics for the target)."""
    o = owns[name]
    callees = _closure(name, owns)
    kind = "annotations" if (o.missing and not o.fix) else "rewrite"
    state = _own_state(o)
    reasons = [] if state == "clean" else [_own_reason(o)]
    worst = {"hard": "not_eligible", "fix": "fixable", "clean": "verifiable"}[state]
    for c in callees:
        cs = _own_state(owns[c])
        if cs == "hard":
            return "not_eligible", _short(reasons + [f"calls `{c}`, which is not eligible: {_own_reason(owns[c])}"], 2), kind, []
        if cs == "fix":
            worst = "fixable"
            reasons.append(f"calls `{c}`, which needs a fix: {_own_reason(owns[c])}")
            if owns[c].fix or not owns[c].missing:
                kind = "rewrite"
    if o.hard:
        worst = "not_eligible"

    ext = _run_extract(info, name, info.func_text(name), lambda n: info.func_text(n))
    tdiags = [d for d in ext.diagnostics if d["fn"] == name]
    if worst == "not_eligible":
        return "not_eligible", _short(reasons, 2), kind, tdiags
    if worst == "fixable":
        return "fixable", _short(reasons, 3), kind, tdiags
    if ext.ok:
        return "verifiable", None, kind, []
    elig, reason, k2 = classify_errors(ext.diagnostics)
    if any(d["fn"] != name for d in ext.diagnostics) and elig != "not_eligible":
        reason = f"callee problem — {reason}"
    return elig, reason, k2, tdiags


# ----------------------------------------------------------------------------- scan driver
def _record(info: ModuleInfo, node: ast.AST, qual: str, owns_metrics: Dict, elig: str, reason: Optional[str]) -> FunctionRecord:
    status = {"verifiable": "pending", "fixable": "fixable", "not_eligible": "not_eligible"}[elig]
    rec = FunctionRecord(id=f"{info.rel}::{qual}", file=info.rel, name=node.name, qualname=qual,
                         line=node.lineno, end_line=node.end_lineno, col=node.col_offset,
                         status=status, eligibility=elig, reason=reason)
    rec.metrics = owns_metrics
    rec.sources["original"] = "\n".join(info.lines[node.lineno - 1:node.end_lineno])
    return rec


def scan_workspace(ws: Workspace, emit=None) -> List[FunctionRecord]:
    emit = emit or (lambda *a, **k: None)
    records: List[FunctionRecord] = []
    seen_ids: Set[str] = set()
    for rel in ws.py_files:
        try:
            raw = (ws.original / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            emit("log", {"stream": "system", "level": "warn", "text": f"scan: skipped {rel}: cannot read ({e})"}, stage="scan")
            continue
        try:
            info = build_info(rel, raw)
        except (SyntaxError, ValueError, RecursionError) as e:
            emit("log", {"stream": "system", "level": "warn", "text": f"scan: skipped {rel}: does not parse ({e})"}, stage="scan")
            continue
        owns = {n: analyze(f, info) for n, f in info.funcs.items()}
        recs: Dict[str, FunctionRecord] = {}
        file_recs: List[FunctionRecord] = []
        for name, node in info.funcs.items():
            try:
                elig, reason, kind, diags = _decide(name, info, owns)
            except Exception as e:                               # never crash the scan on one odd function
                elig, reason, kind, diags = "not_eligible", f"could not analyse ({type(e).__name__}: {e})", "rewrite", []
            rec = _record(info, node, name, owns[name].metrics, elig, reason)
            rec.diagnostics = diags
            rec.private.update({"modinfo": info, "siblings": recs, "own": owns[name], "fix_kind": kind})
            recs[name] = rec
            file_recs.append(rec)
        for cname, cnode in info.classes.items():                # v1: methods are reported, not analysed
            for m in cnode.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    try:
                        mo = analyze(m, info, is_method=True).metrics
                    except Exception:
                        mo = {"size_lines": m.end_lineno - m.lineno + 1, "loop_depth": 0, "arith_density": 0.0,
                              "calls": [], "imports": [], "uses_globals": []}
                    rec = _record(info, m, f"{cname}.{m.name}", mo, "not_eligible", f"method of class {cname}")
                    rec.private.update({"modinfo": info, "siblings": recs, "fix_kind": "rewrite"})
                    file_recs.append(rec)
        for rec in sorted(file_recs, key=lambda r: (r.line, r.col)):
            if rec.id in seen_ids:
                continue
            seen_ids.add(rec.id)
            records.append(rec)
            emit("scan.function", {"function": rec.to_summary()}, stage="scan")
    counts = {"functions": len(records),
              "verifiable": sum(r.eligibility == "verifiable" for r in records),
              "fixable": sum(r.eligibility == "fixable" for r in records),
              "not_eligible": sum(r.eligibility == "not_eligible" for r in records)}
    emit("scan.done", counts, stage="scan",
         caption=f"Scanned {counts['functions']} functions: {counts['verifiable']} verifiable, "
                 f"{counts['fixable']} fixable, {counts['not_eligible']} not eligible")
    return records
