"""Static scan: decide eligibility by asking the REAL PySub parser + typechecker.

Public API (CONTRACTS section 9):
    scan_workspace(ws, emit) -> list[FunctionRecord]
    extract_pysub(rec, ws, annotated_src=None, override_src=None, infer=False) -> Extract

Design
  * The compiler is the judge. `analyze()` hard-rejects only what no compiler version will handle (third-party
    and system modules, I/O, async, generators, closures, decorators, *args/**kwargs ...). Everything else is
    decided by type-checking the extracted unit; `classify_errors` turns the compiler's diagnostics into
    plain-English reasons. Nothing here lists PySub's features, so new compiler features need no scanner edit.
  * The extracted unit is a standalone module: the target, then every function / class / module-level variable it
    needs, pulled from the whole project (same module or other modules, renamed on collision). Scalar module
    constants are inlined as literals; other module-level values are emitted as module-level assignments.
  * Missing annotations are inferred deterministically (see infer.py), never with an LLM.
"""
from __future__ import annotations

import ast
import builtins
import math
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from . import infer as infer_mod
from .models import FunctionRecord, Workspace
from .pysub_rules import BUILTINS, check_source

# ----------------------------------------------------------------------------- tables
IO_BUILTINS = {"open": "file I/O (`open`)", "input": "reads stdin (`input`)",
               "exec": "runs dynamic code (`exec`)", "eval": "runs dynamic code (`eval`)",
               "compile": "runs dynamic code (`compile`)", "__import__": "dynamic import"}
DYNAMIC_BUILTINS = {"issubclass", "type", "getattr", "setattr", "hasattr", "delattr",
                    "vars", "globals", "locals", "id", "callable", "dir"}
THIRD_PARTY = {"numpy", "pandas", "scipy", "torch", "tensorflow", "sklearn", "cv2", "PIL", "matplotlib",
               "numba", "jax", "networkx", "sympy", "requests", "bs4", "flask", "django", "yaml", "tqdm"}
IO_MODULES = {"os", "sys", "io", "pathlib", "shutil", "subprocess", "socket", "json", "pickle", "csv",
              "sqlite3", "requests", "urllib", "http", "logging", "tempfile", "glob", "gzip", "zipfile",
              "threading", "multiprocessing", "asyncio", "argparse", "getpass", "platform", "signal"}
NONDET_MODULES = {"random", "time", "datetime", "uuid", "secrets"}
# modules the compiler supports (or is gaining): never hard-rejected here, the type checker decides
ALLOWED_MODULES = {"math", "typing", "string", "__future__", "typing_extensions",
                   "collections", "itertools", "functools", "heapq", "bisect", "dataclasses"}
STDLIB = set(getattr(sys, "stdlib_module_names", ())) | {"collections", "itertools", "functools"}
MUTATING_METHODS = {"append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse", "update",
                    "setdefault", "add", "discard", "popitem", "appendleft", "popleft"}
_BUILTIN_NAMES = set(dir(builtins))


# ----------------------------------------------------------------------------- results
@dataclass
class Extract:
    ok: bool
    source: str                      # standalone PySub module text; the target function starts at line 1
    helpers: List[str] = field(default_factory=list)       # names of callee functions pulled in
    diagnostics: List[dict] = field(default_factory=list)  # pysub-relative {line,col,kind,msg,phase,fn}
    uses: List[str] = field(default_factory=list)          # module-level names inlined / emitted
    classes: List[str] = field(default_factory=list)       # project classes pulled in
    hard: List[str] = field(default_factory=list)          # plain-English hard blockers found in pulled-in code
    inferred: List[str] = field(default_factory=list)      # annotations added by deterministic inference
    helper_src: Dict[str, str] = field(default_factory=dict)   # helper name -> original Python text

    def to_dict(self) -> dict:
        return {"ok": self.ok, "source": self.source, "helpers": self.helpers,
                "diagnostics": self.diagnostics, "uses": self.uses, "classes": self.classes,
                "inferred": self.inferred}


@dataclass
class ModuleInfo:
    rel: str
    text: str
    lines: List[str]
    tree: ast.Module
    funcs: Dict[str, ast.AST] = field(default_factory=dict)
    classes: Dict[str, ast.ClassDef] = field(default_factory=dict)
    consts: Dict[str, object] = field(default_factory=dict)     # name -> python scalar
    gvars: Dict[str, ast.stmt] = field(default_factory=dict)    # name -> module-level assignment (non-scalar value)
    nonconst_globals: Set[str] = field(default_factory=set)
    unsafe: Dict[str, str] = field(default_factory=dict)        # global name -> why it cannot be carried over
    imports: Dict[str, Tuple[str, Optional[str]]] = field(default_factory=dict)  # alias -> (module, name|None)
    star_imports: List[str] = field(default_factory=list)
    typing_names: Set[str] = field(default_factory=set)

    def func_text(self, name: str) -> str:
        n = self.funcs[name]
        return "\n".join(self.lines[n.lineno - 1:n.end_lineno])

    def class_text(self, name: str) -> str:
        n = self.classes[name]
        return "\n".join(self.lines[n.lineno - 1:n.end_lineno])

    def stmt_text(self, st: ast.stmt) -> str:
        return "\n".join(self.lines[st.lineno - 1:st.end_lineno])

    @property
    def lits(self) -> Dict[str, ast.stmt]:                      # backwards-compatible alias
        return self.gvars


@dataclass
class Own:
    hard: Dict[str, str] = field(default_factory=dict)
    fix: Dict[str, str] = field(default_factory=dict)           # unused (kept for older callers)
    missing: List[str] = field(default_factory=list)
    callees: Set[str] = field(default_factory=set)
    consts_used: Set[str] = field(default_factory=set)
    globals_used: Set[str] = field(default_factory=set)
    imports_used: Set[str] = field(default_factory=set)
    calls: Set[str] = field(default_factory=set)
    metrics: Dict[str, object] = field(default_factory=dict)


@dataclass
class Sym:
    kind: str                       # func | class | gvar | const | module
    info: Optional[ModuleInfo]
    name: str = ""
    value: object = None


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


def _toplevel_stmts(tree: ast.Module):
    """Module-level statements, looking through `if`/`try` blocks (conditional imports)."""
    for st in tree.body:
        yield st
        if isinstance(st, (ast.If, ast.Try)):
            sub = st.body + st.orelse + (st.finalbody if isinstance(st, ast.Try) else []) \
                + [x for h in (st.handlers if isinstance(st, ast.Try) else []) for x in h.body]
            for x in sub:
                if isinstance(x, (ast.Import, ast.ImportFrom)):
                    yield x


def build_info(rel: str, text: str) -> ModuleInfo:
    text = _norm(text)
    tree = ast.parse(text)
    info = ModuleInfo(rel, text, text.split("\n"), tree)
    store_count: Dict[str, int] = {}
    global_decl: Set[str] = set()
    mutated: Set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Global):
            global_decl.update(n.names)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in MUTATING_METHODS:
            r = n.func.value
            while isinstance(r, (ast.Attribute, ast.Subscript)):
                r = r.value
            if isinstance(r, ast.Name):
                mutated.add(r.id)
        elif isinstance(n, (ast.Subscript, ast.Attribute)) and isinstance(n.ctx, (ast.Store, ast.Del)):
            r = n
            while isinstance(r, (ast.Attribute, ast.Subscript)):
                r = r.value
            if isinstance(r, ast.Name):
                mutated.add(r.id)
        elif isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name):
            mutated.add(n.target.id)
    for st in _toplevel_stmts(tree):
        if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
            info.funcs.setdefault(st.name, st)
        elif isinstance(st, ast.ClassDef):
            info.classes[st.name] = st
        elif isinstance(st, ast.Import):
            for a in st.names:
                info.imports[(a.asname or a.name).split(".")[0]] = (a.name if a.asname else a.name.split(".")[0], None)
        elif isinstance(st, ast.ImportFrom):
            mod = "." * st.level + (st.module or "")
            for a in st.names:
                if a.name == "*":
                    info.star_imports.append(mod)
                elif (st.module or "") in ("typing", "typing_extensions", "collections.abc"):
                    info.typing_names.add(a.asname or a.name)
                elif (st.module or "") != "__future__":
                    info.imports[a.asname or a.name] = (mod, a.name)
        else:
            for n in ast.walk(st):
                if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
                    store_count[n.id] = store_count.get(n.id, 0) + 1
    for st in tree.body:                       # constants, in source order so they may reference earlier ones
        tgt = val = None
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            tgt, val = st.targets[0].id, st.value
        elif isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name) and st.value is not None:
            tgt, val = st.target.id, st.value
        if tgt and store_count.get(tgt) == 1 and tgt not in global_decl and tgt not in mutated:
            try:
                info.consts[tgt] = _const_eval(val, info.consts)
                continue
            except _NoConst:
                pass
            info.gvars[tgt] = st
    stored = set(store_count) | global_decl
    info.nonconst_globals = stored - set(info.consts)
    for nm in info.nonconst_globals:
        if nm in info.gvars:
            continue
        if nm in global_decl:
            info.unsafe[nm] = "is rebound by a `global` statement while the program runs"
        elif nm in mutated:
            info.unsafe[nm] = "is modified while the program runs (so a copy would go stale)"
        elif store_count.get(nm, 0) > 1:
            info.unsafe[nm] = "is assigned more than once"
        else:
            info.unsafe[nm] = "is not a fixed constant"
    return info


# ----------------------------------------------------------------------------- the project (cross-module view)
class Project:
    """All parsed modules of one workspace + import resolution + per-symbol analysis caches."""

    def __init__(self):
        self.infos: Dict[str, ModuleInfo] = {}
        self.records: Dict[Tuple[str, str], FunctionRecord] = {}
        self._dotted: Dict[str, str] = {}
        self._suffix: Dict[str, List[str]] = {}
        self._an: Dict[Tuple[str, str, str], Own] = {}
        self._calls: Optional[Dict[Tuple[str, str], List[List[Optional[str]]]]] = None

    # -------------------------------------------------------------- module index
    def add(self, info: ModuleInfo) -> None:
        self.infos[info.rel] = info
        stem = info.rel[:-3] if info.rel.endswith(".py") else info.rel
        if stem.endswith("/__init__"):
            stem = stem[:-9]
        elif stem == "__init__":
            stem = ""
        dotted = stem.replace("/", ".")
        self._dotted[dotted] = info.rel
        parts = dotted.split(".") if dotted else []
        for i in range(len(parts)):
            self._suffix.setdefault(".".join(parts[i:]), []).append(info.rel)

    def module(self, mod: str, frm: ModuleInfo, depth_guard: int = 0) -> Optional[ModuleInfo]:
        level = len(mod) - len(mod.lstrip("."))
        name = mod[level:]
        if level:
            base = frm.rel.split("/")[:-1]
            if frm.rel.endswith("__init__.py") or True:
                base = base[:len(base) - (level - 1)] if level > 1 else base
            parts = base + ([p for p in name.split(".") if p])
            dotted = ".".join(parts)
            rel = self._dotted.get(dotted)
            return self.infos.get(rel) if rel else None
        if name in self._dotted:
            return self.infos[self._dotted[name]]
        here = ".".join(frm.rel.split("/")[:-1] + name.split("."))
        if here in self._dotted:
            return self.infos[self._dotted[here]]
        hits = self._suffix.get(name, [])
        if len(hits) == 1:
            return self.infos[hits[0]]
        return None

    # -------------------------------------------------------------- symbol resolution
    def resolve_name(self, info: ModuleInfo, name: str, depth: int = 0) -> Optional[Sym]:
        if name in info.funcs:
            return Sym("func", info, name)
        if name in info.classes:
            return Sym("class", info, name)
        if name in info.gvars:
            return Sym("gvar", info, name)
        if name in info.consts:
            return Sym("const", info, name, info.consts[name])
        if depth > 6:
            return None
        if name in info.imports:
            mod, orig = info.imports[name]
            if orig is None:
                m = self.module(mod, info)
                return Sym("module", m, mod) if m else None
            m = self.module(mod, info)
            if m is not None and m is not info:
                s = self.resolve_name(m, orig, depth + 1)
                if s is not None:
                    return s
            sub = self.module(mod + ("" if mod.endswith(".") else ".") + orig, info)
            return Sym("module", sub, orig) if sub else None
        for mod in info.star_imports:
            m = self.module(mod, info)
            if m is not None and m is not info:
                s = self.resolve_name(m, name, depth + 1)
                if s is not None:
                    return s
        return None

    def resolve_chain(self, info: ModuleInfo, chain: List[str]) -> Optional[Sym]:
        """`m.f`, `pkg.mod.f`: the project symbol a dotted reference denotes, if it is project code."""
        if len(chain) < 2:
            return None
        root = self.resolve_name(info, chain[0])
        cur: Optional[ModuleInfo] = None
        i = 1
        if root is not None and root.kind == "module":
            cur = root.info
        elif chain[0] in info.imports and info.imports[chain[0]][1] is None:
            base = info.imports[chain[0]][0]                       # `import a.b.c` binds `a`
            while i < len(chain) - 1:
                nxt = self.module(base + "." + chain[i], info)
                base += "." + chain[i]
                i += 1
                if nxt is not None:
                    cur = nxt
            if cur is None:
                return None
        else:
            return None
        while i < len(chain) - 1:                                  # sub-module hops
            nxt = self.resolve_name(cur, chain[i])
            if nxt is None or nxt.kind != "module" or nxt.info is None:
                return None
            cur, i = nxt.info, i + 1
        s = self.resolve_name(cur, chain[-1]) if cur is not None else None
        return s if s is not None and s.kind != "module" else None

    def is_project_module(self, info: ModuleInfo, alias: str) -> bool:
        s = self.resolve_name(info, alias)
        if s is not None:
            return True
        if alias in info.imports and info.imports[alias][1] is None:
            base = info.imports[alias][0]
            return self.module(base, info) is not None or any(
                k == base or k.startswith(base + ".") for k in self._dotted)
        return False

    # -------------------------------------------------------------- texts
    def func_text(self, info: ModuleInfo, name: str) -> str:
        rec = self.records.get((info.rel, name))
        return (rec.sources.get("annotated") if rec is not None else None) or info.func_text(name)

    # -------------------------------------------------------------- analysis cache
    def analysis(self, info: ModuleInfo, kind: str, name: str) -> Own:
        key = (info.rel, kind, name)
        o = self._an.get(key)
        if o is None:
            o = self._an[key] = self._analyse(info, kind, name)
        return o

    def _analyse(self, info: ModuleInfo, kind: str, name: str) -> Own:
        if kind == "func":
            return analyze(info.funcs[name], info, project=self)
        if kind == "gvar":
            st = info.gvars[name]
            fn = ast.parse("def _g():\n    pass\n").body[0]
            fn.body = [st]
            return analyze(fn, info, project=self, synthetic=True)
        o = Own()
        cls = info.classes[name]
        if cls.decorator_list:
            decos = [_chain(d).split('(')[0] for d in cls.decorator_list]
            bad_decos = [d for d in decos if d not in ("dataclass", "dataclasses.dataclass")]
            if bad_decos:
                o.hard["deco"] = f"class `{name}` is decorated with unsupported `@{bad_decos[0]}`"
        bases = [b for b in cls.bases if not (isinstance(b, ast.Name) and b.id == "object")]
        if len(bases) > 1:
            o.hard["bases"] = f"class `{name}` uses multiple inheritance (not supported)"
        for m in cls.body:
            if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for k, v in analyze(m, info, is_method=True, project=self).hard.items():
                    o.hard.setdefault(f"{m.name}:{k}", f"method `{name}.{m.name}` {v}")
        return o

    # -------------------------------------------------------------- call sites (priors for inference)
    def call_types(self, info: ModuleInfo, name: str) -> List[List[Optional[str]]]:
        if self._calls is None:
            self._calls = {}
            for rel, mi in self.infos.items():
                for n in ast.walk(mi.tree):
                    if isinstance(n, ast.Call) and n.args:
                        sym = None
                        if isinstance(n.func, ast.Name):
                            sym = self.resolve_name(mi, n.func.id)
                        elif isinstance(n.func, ast.Attribute):
                            ch = _chain_list(n.func)
                            sym = self.resolve_chain(mi, ch) if ch else None
                        if sym is not None and sym.kind == "func" and sym.info is not None:
                            self._calls.setdefault((sym.info.rel, sym.name), []).append(
                                [infer_mod.lit_type(a) for a in n.args])
        return self._calls.get((info.rel, name), [])


# ----------------------------------------------------------------------------- text preparation
def _locals_of(fn: ast.AST) -> Set[str]:
    local: Set[str] = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.arg):
            local.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            local.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            local.add(n.name)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not fn:
            local.add(n.name)
    return local


def _chain_list(n: ast.AST) -> Optional[List[str]]:
    out: List[str] = []
    while isinstance(n, ast.Attribute):
        out.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        out.append(n.id)
        return out[::-1]
    return None


class _Rewriter(ast.NodeVisitor):
    def __init__(self, consts, rename, attr_map, defren):
        self.consts, self.rename, self.attr_map, self.defren = consts, rename, attr_map, defren
        self.stack: List[Set[str]] = []
        self.ann = 0
        self.edits: List[Tuple[int, int, int, bytes]] = []
        self.used: Set[str] = set()
        self.depth = 0

    def local(self, name: str) -> bool:
        return any(name in s for s in self.stack)

    def edit(self, n: ast.AST, rep: str):
        if n.lineno == n.end_lineno:
            self.edits.append((n.lineno - 1, n.col_offset, n.end_col_offset, rep.encode()))

    def visit_annotation(self, a):
        if a is not None:
            self.ann += 1
            self.visit(a)
            self.ann -= 1

    def _def(self, node):
        if self.depth == 0 and node.name in self.defren and self.defren[node.name] != node.name:
            self._rename_def(node, "def")
        self.stack.append(_locals_of(node))
        self.depth += 1
        for d in node.decorator_list:
            self.visit(d)
        a = node.args
        for x in a.posonlyargs + a.args + a.kwonlyargs + [y for y in (a.vararg, a.kwarg) if y]:
            self.visit_annotation(x.annotation)
        for d in a.defaults + [k for k in a.kw_defaults if k is not None]:
            self.visit(d)
        self.visit_annotation(node.returns)
        for s in node.body:
            self.visit(s)
        self.depth -= 1
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _def

    def _rename_def(self, node, kw):
        ln = self.lines[node.lineno - 1]
        m = re.compile(rf"\b{kw}\s+({re.escape(node.name)})\b").search(ln)
        if m:
            c0 = len(ln[:m.start(1)].encode())
            self.edits.append((node.lineno - 1, c0, c0 + len(node.name.encode()), self.defren[node.name].encode()))

    def visit_ClassDef(self, node):
        if self.depth == 0 and node.name in self.defren and self.defren[node.name] != node.name:
            self._rename_def(node, "class")
        self.depth += 1
        for b in node.bases:
            self.visit(b)
        for s in node.body:
            self.visit(s)
        self.depth -= 1

    def visit_AnnAssign(self, node):
        self.visit(node.target)
        self.visit_annotation(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_Name(self, n):
        if self.ann:
            if n.id in ("List", "Dict"):
                self.edit(n, n.id.lower())
            elif n.id in self.rename and not self.local(n.id):
                self.edit(n, self.rename[n.id])
            return
        if not isinstance(n.ctx, ast.Load) or self.local(n.id):
            return
        if n.id in self.consts:
            self.edit(n, render_scalar(self.consts[n.id]))
            self.used.add(n.id)
        elif n.id in self.rename:
            self.edit(n, self.rename[n.id])

    def visit_Attribute(self, n):
        ch = _chain_list(n)
        if ch is not None:
            if self.ann and n.attr in ("List", "Dict") and len(ch) == 2:
                self.edit(n, n.attr.lower())
                return
            key = ".".join(ch)
            if key in self.attr_map and not self.local(ch[0]) and isinstance(n.ctx, ast.Load):
                rep = self.attr_map[key]
                self.edit(n, rep)
                return
        self.generic_visit(n)


def prep_text(text: str, consts: Dict[str, object], strip_doc: bool = True,
              rename: Optional[Dict[str, str]] = None, attr_map: Optional[Dict[str, str]] = None,
              defren: Optional[Dict[str, str]] = None) -> Tuple[str, Set[str]]:
    """Inline scalar constants, normalise typing.List/Dict -> list/dict, rename pulled-in symbols, strip
    docstrings. Line count is preserved (docstring lines become blank / `pass`).
    Returns (text, constants_used)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, set()
    rw = _Rewriter(consts, rename or {}, attr_map or {}, defren or {})
    rw.lines = text.split("\n")
    rw.visit(tree)
    lines = [l.encode("utf-8") for l in rw.lines]
    seen = set()
    for ln, c0, c1, rep in sorted(rw.edits, key=lambda e: (e[0], e[1]), reverse=True):
        if (ln, c0) in seen:
            continue
        seen.add((ln, c0))
        b = lines[ln]
        lines[ln] = b[:c0] + rep + b[c1:]
    out = [b.decode("utf-8") for b in lines]
    if strip_doc:
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and fn.body:
                d = fn.body[0]
                if isinstance(d, ast.Expr) and isinstance(d.value, ast.Constant) and isinstance(d.value.value, str):
                    for k in range(d.lineno - 1, d.end_lineno):
                        out[k] = ""
                    if len(fn.body) == 1:
                        out[d.lineno - 1] = " " * d.col_offset + "pass"
    return "\n".join(out), rw.used


# ----------------------------------------------------------------------------- unit builder
class _Item:
    def __init__(self, key, kind, info, name, final, text):
        self.key, self.kind, self.info, self.name, self.final, self.text = key, kind, info, name, final, text
        self.out = ""
        self.deps: List[Tuple[str, str, str]] = []
        self.original = text


class _Refs(ast.NodeVisitor):
    """Names / dotted references inside a chunk that denote project symbols."""

    def __init__(self, project: Project, info: ModuleInfo, defined: Set[str]):
        self.p, self.info, self.defined = project, info, defined
        self.stack: List[Set[str]] = []
        self.names: Dict[str, Sym] = {}
        self.attrs: Dict[str, Sym] = {}

    def local(self, name):
        return any(name in s for s in self.stack)

    def _def(self, node):
        self.stack.append(_locals_of(node))
        self.generic_visit(node)
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = _def

    def visit_Name(self, n):
        if isinstance(n.ctx, ast.Load) and not self.local(n.id) and n.id not in self.defined:
            s = self.p.resolve_name(self.info, n.id)
            if s is not None:
                self.names[n.id] = s

    def visit_Attribute(self, n):
        ch = _chain_list(n)
        if ch is not None and not self.local(ch[0]) and ch[0] not in self.defined:
            s = self.p.resolve_chain(self.info, ch)
            if s is not None:
                self.attrs[".".join(ch)] = s
                return
        self.generic_visit(n)


def _module_stem(info: ModuleInfo) -> str:
    stem = info.rel.rsplit("/", 1)[-1][:-3]
    if stem == "__init__" and "/" in info.rel:
        stem = info.rel.rsplit("/", 2)[-2]
    return re.sub(r"\W", "_", stem)


class Unit:
    def __init__(self):
        self.source = ""
        self.items: List[_Item] = []
        self.spans: List[Tuple[str, int, int]] = []
        self.hard: List[str] = []
        self.texts: List[str] = []
        self.inferred: List[str] = []

    @property
    def helpers(self):
        return [i.final for i in self.items[1:] if i.kind == "func"]

    @property
    def classes(self):
        return [i.final for i in self.items if i.kind == "class"]


def _assemble(texts: List[str]) -> str:
    return "\n\n\n".join(t.rstrip("\n") for t in texts) + "\n"


class _Builder:
    def __init__(self, project: Project, info: ModuleInfo, name: str, text: str, check_root_hard: bool = False):
        self.p, self.info, self.name = project, info, name
        self.items: Dict[Tuple[str, str, str], _Item] = {}
        self.order: List[_Item] = []
        self.used_names: Set[str] = set(BUILTINS) | {name}
        self.hard: List[str] = []
        self.uses: Set[str] = set()
        self.root = self._new((info.rel, "func", name), "func", info, name, name, text)

    def _new(self, key, kind, info, name, final, text):
        it = _Item(key, kind, info, name, final, text)
        self.items[key] = it
        self.order.append(it)
        return it

    def _final_name(self, info, name):
        if name not in self.used_names:
            self.used_names.add(name)
            return name
        base = f"{name}_{_module_stem(info)}"
        cand, k = base, 2
        while cand in self.used_names:
            cand, k = f"{base}{k}", k + 1
        self.used_names.add(cand)
        return cand

    def ensure(self, sym: Sym) -> _Item:
        key = (sym.info.rel, sym.kind, sym.name)
        it = self.items.get(key)
        if it is not None:
            return it
        info = sym.info
        if sym.kind == "func":
            text = self.p.func_text(info, sym.name)
        elif sym.kind == "class":
            text = info.class_text(sym.name)
        else:
            text = info.stmt_text(info.gvars[sym.name])
        it = self._new(key, sym.kind, info, sym.name, self._final_name(info, sym.name), text)
        own = self.p.analysis(info, sym.kind, sym.name)
        if own.hard:
            what = {"func": "function", "class": "class", "gvar": "module-level variable"}[sym.kind]
            where = "" if info.rel == self.info.rel else f" (in {info.rel})"
            self.hard.append(f"uses {what} `{sym.name}`{where}, which is not eligible: "
                             + _short(list(own.hard.values()), 2))
        return it

    def process(self, it: _Item) -> None:
        try:
            tree = ast.parse(it.text)
        except SyntaxError:
            it.out = it.text
            return
        defined = {s.name for s in tree.body if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        if it.kind == "gvar":
            defined = set()
        refs = _Refs(self.p, it.info, defined)
        refs.visit(tree)
        consts: Dict[str, object] = {}
        rename: Dict[str, str] = {}
        attrs: Dict[str, str] = {}
        for ident, s in refs.names.items():
            if s.kind == "const":
                consts[ident] = s.value
            elif s.kind in ("func", "class", "gvar"):
                dep = self.ensure(s)
                it.deps.append(dep.key)
                if dep.final != ident:
                    rename[ident] = dep.final
        for chain, s in refs.attrs.items():
            if s.kind == "const":
                attrs[chain] = render_scalar(s.value)
                self.uses.add(s.name)
            else:
                dep = self.ensure(s)
                it.deps.append(dep.key)
                attrs[chain] = dep.final
        defren = {it.name: it.final} if it.final != it.name else {}
        it.out, used = prep_text(it.text, consts, True, rename, attrs, defren)
        it.out = it.out.rstrip("\n")
        self.uses |= used

    def run(self) -> None:
        i = 0
        while i < len(self.order):
            self.process(self.order[i])
            i += 1


def _gvar_order(items: List[_Item]) -> List[_Item]:
    byk = {i.key: i for i in items}
    out: List[_Item] = []
    seen: Set[Tuple[str, str, str]] = set()

    def visit(it):
        if it.key in seen:
            return
        seen.add(it.key)
        for d in it.deps:
            if d in byk and byk[d].kind == "gvar":
                visit(byk[d])
        out.append(it)
    for it in items:
        if it.kind == "gvar":
            visit(it)
    return out


def build_unit(project: Project, info: ModuleInfo, name: str, text: str, infer: bool = False,
               trace_priors: Optional[List[List[Optional[str]]]] = None) -> Unit:
    b = _Builder(project, info, name, text)
    b.run()
    u = Unit()
    u.hard = b.hard
    funcs_classes = [i for i in b.order if i.kind != "gvar"]
    gvars = _gvar_order(b.order)
    u.items = funcs_classes + gvars
    texts = [i.out for i in u.items]
    if infer:
        priors: Dict[str, List[List[Optional[str]]]] = {}
        for it in u.items:
            if it.kind != "func":
                continue
            pri = list(infer_mod.doctest_calls(it.original, it.name))
            pri += project.call_types(it.info, it.name)
            if it is b.root and trace_priors:
                pri += trace_priors
            if pri:
                priors[it.final] = pri
            for ch_name in ():
                pass
        # class methods: doctests are rare; call-site priors only
        texts, u.inferred = infer_mod.fill(texts, lambda ts: check_source(_assemble(ts)), priors)
    u.texts = texts
    u.source = _assemble(texts)
    line = 1
    for it, t in zip(u.items, texts):
        n = t.rstrip("\n").count("\n") + 1
        u.spans.append((it.final, line, line + n - 1))
        line += n + 2
    u.uses = sorted(b.uses | {i.name for i in u.items if i.kind == "gvar"})
    return u


def _fn_for_line(spans, line: int) -> str:
    for nm, a, b in spans:
        if a <= line <= b:
            return nm
    return spans[0][0] if spans else ""


def _project_for(ws: Workspace) -> Project:
    p = getattr(ws, "_project", None)
    if p is None:
        p = Project()
        for rel in ws.py_files:
            try:
                p.add(build_info(rel, (ws.original / rel).read_text(encoding="utf-8", errors="replace")))
            except (SyntaxError, ValueError, RecursionError, OSError):
                continue
        try:
            ws._project = p
        except Exception:
            pass
    return p


def _run_extract(project: Project, info: ModuleInfo, name: str, target_text: str, infer: bool = False,
                 trace_priors=None) -> Tuple[Extract, Unit]:
    u = build_unit(project, info, name, target_text, infer, trace_priors)
    diags = check_source(u.source, f"{info.rel}::{name}")
    for d in diags:
        d["phase"] = "eligibility"
        d["fn"] = _fn_for_line(u.spans, d["line"])
    if u.hard:
        diags = [{"line": 1, "col": 1, "kind": "Eligibility", "msg": h, "phase": "eligibility", "fn": name}
                 for h in u.hard] + diags
    helper_src = {i.final: i.original for i in u.items[1:] if i.kind == "func"}
    ex = Extract(not diags, u.source, u.helpers, diags, u.uses, u.classes, list(u.hard), u.inferred, helper_src)
    return ex, u


def extract_pysub(rec: FunctionRecord, ws: Workspace, annotated_src: Optional[str] = None,
                  override_src: Optional[str] = None, infer: bool = False) -> Extract:
    """Standalone PySub module for `rec`: target first (its line k == pysub line k when override_src is None),
    then the callees / classes / module variables it needs (from any module of the project). Constants inlined,
    typing.List/Dict normalised, docstrings stripped. With infer=True, missing annotations are inferred."""
    try:
        project: Project = rec.private.get("project") or _project_for(ws)
        info: Optional[ModuleInfo] = rec.private.get("modinfo") or project.infos.get(rec.file)
        if info is None:
            raise KeyError(rec.file)
        rec.private["modinfo"], rec.private["project"] = info, project
    except Exception as e:
        return Extract(False, "", [], [{"line": 1, "col": 1, "kind": "InternalError", "msg": f"cannot read {rec.file}: {e}",
                                        "phase": "eligibility", "fn": rec.name}], [])
    if "." in rec.qualname or rec.name not in info.funcs:
        return Extract(False, rec.sources.get("original") or "", [], [
            {"line": 1, "col": 1, "kind": "TypeError", "msg": rec.reason or "not a module-level function",
             "phase": "eligibility", "fn": rec.name}], [])
    target = override_src or annotated_src or rec.sources.get("original") or info.func_text(rec.name)
    tp = None
    tr = rec.trace or {}
    if infer and tr.get("arg_types"):
        from .annotate import resolve_type
        tp = [[resolve_type(t) for t in tr["arg_types"]]]
    ex, _ = _run_extract(project, info, rec.name, target, infer, tp)
    return ex


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


def module_problem(root: str, chain: str, mod: str, verb: str = "calls") -> Optional[str]:
    """Plain-English reason a reference into a non-project module is a hard stop; None if the compiler may handle it."""
    r = mod.split(".")[0].lstrip(".")
    if r in ALLOWED_MODULES or mod in ("collections.abc",):
        return None
    if r in THIRD_PARTY:
        return f"{verb} {r} (`{chain}`) — third-party library code is outside PySub"
    if r in IO_MODULES:
        return f"does file or system I/O (`{chain}`)"
    if r in NONDET_MODULES:
        return f"{verb} `{chain}` — the `{r}` module (clocks / randomness) is outside PySub"
    if r in STDLIB:
        return f"{verb} `{chain}` from the standard-library module `{r}`, which PySub does not support"
    return f"{verb} `{chain}` from `{mod}`, an external library that is outside PySub"


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


def analyze(fn: ast.AST, info: ModuleInfo, is_method: bool = False, project: Optional[Project] = None,
            synthetic: bool = False) -> Own:
    """Hard blockers only (what no compiler version will handle), plus metrics and the list of unannotated
    parameters. Everything else is decided by type-checking the extracted unit."""
    o = Own()
    top = fn
    hard = o.hard
    args = top.args
    all_args = args.posonlyargs + args.args + args.kwonlyargs
    if isinstance(top, ast.AsyncFunctionDef):
        hard["async"] = "is an async function"
    if top.decorator_list and not synthetic:
        hard["deco"] = "is decorated (`@" + _chain(top.decorator_list[0]).split("(")[0] + "`)"
    if args.vararg:
        hard["vararg"] = "uses *args"
    if args.kwarg:
        hard["kwarg"] = "uses **kwargs"

    local = {a.arg for a in all_args} | ({args.vararg.arg} if args.vararg else set()) | ({args.kwarg.arg} if args.kwarg else set())
    nodes = list(ast.walk(top))
    nested_defs = {n.name for n in nodes if n is not top and isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    local |= nested_defs
    for n in nodes:
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            local.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            local.add(n.name)
        elif isinstance(n, ast.arg):
            local.add(n.arg)

    def is_class(name: str) -> bool:
        if name in info.classes:
            return True
        s = project.resolve_name(info, name) if project else None
        return s is not None and s.kind == "class"

    # annotations: which parameters / return need one, and objects that cannot cross the compiled boundary
    anns: List[Tuple[str, ast.AST]] = [(a.arg, a.annotation) for a in all_args if a.annotation is not None]
    if top.returns is not None:
        anns.append(("return", top.returns))
    anns += [(_chain(n.target), n.annotation) for n in nodes if isinstance(n, ast.AnnAssign)]
    ann_ids = {id(x) for _, a in anns for x in ast.walk(a)}
    BARE = {"list", "dict", "List", "Dict"}
    for a in all_args:
        if is_method and a.arg == "self":
            continue
        if a.annotation is None or (isinstance(a.annotation, ast.Name) and a.annotation.id in BARE):
            o.missing.append(a.arg)
    if top.returns is None or (isinstance(top.returns, ast.Name) and top.returns.id in BARE):
        if any(isinstance(n, ast.Return) and n.value is not None and
               not (isinstance(n.value, ast.Constant) and n.value.value is None) for n in nodes):
            o.missing.append("return")
    # Project classes crossing boundary are marshalled via classes_lib trait system

    call_funcs = {id(n.func) for n in nodes if isinstance(n, ast.Call)}
    attr_roots = {id(r) for n in nodes if isinstance(n, ast.Attribute) for r in [_root_name(n)] if r is not None}
    raise_calls = {id(n.exc) for n in nodes if isinstance(n, ast.Raise) and isinstance(n.exc, ast.Call)}

    def project_alias(name: str) -> bool:
        return project is not None and project.is_project_module(info, name)

    for n in nodes:
        if n is top:
            continue
        t = type(n)
        if t in (ast.FunctionDef, ast.AsyncFunctionDef):
            hard["closure"] = "defines a nested function (closure)"
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
        elif t is ast.BinOp and isinstance(n.op, ast.MatMult):
            hard["matmul"] = "uses matrix multiplication (`@`)"
        elif t is ast.Constant:
            v = n.value
            if isinstance(v, (bytes, complex)):
                hard["lit"] = "uses a bytes/complex literal"
            elif isinstance(v, int) and not isinstance(v, bool) and abs(v) >= 2 ** 63:
                hard["bigint"] = "uses an integer literal beyond 64 bits"

        # ---- names, calls, attributes
        if t is ast.Call and id(n) in raise_calls:
            pass
        elif t is ast.Call:
            f = n.func
            if isinstance(f, ast.Name):
                nm = f.id
                o.calls.add(nm)
                if nm in local:
                    continue
                sym = project.resolve_name(info, nm) if project else None
                if nm in info.funcs:
                    o.callees.add(nm)
                elif sym is not None or nm in info.classes:
                    pass
                elif nm in info.imports:
                    mod = info.imports[nm][0]
                    o.imports_used.add(mod)
                    why = module_problem(nm, f"{mod}.{info.imports[nm][1]}" if info.imports[nm][1] else nm, mod)
                    if why and not (project and project.module(mod, info)):
                        hard[f"mod:{nm}"] = why
                elif nm in IO_BUILTINS:
                    hard[f"io:{nm}"] = IO_BUILTINS[nm]
                elif nm in DYNAMIC_BUILTINS:
                    hard[f"dyn:{nm}"] = f"uses dynamic typing (`{nm}`)"
                elif nm in BUILTINS or nm in _BUILTIN_NAMES or nm in info.typing_names:
                    pass
                else:
                    hard[f"undef:{nm}"] = f"calls `{nm}`, which is not defined in this module or its imports"
            elif isinstance(f, ast.Attribute):
                r = _root_name(f)
                chain = _chain(f)
                o.calls.add(chain if len(chain) < 40 else f.attr)
                if r is not None and r.id in info.imports and r.id not in local and not project_alias(r.id):
                    mod = info.imports[r.id][0]
                    o.imports_used.add(mod)
                    why = module_problem(r.id, chain, mod)
                    if why:
                        hard[f"mod:{chain}"] = why
                elif r is not None and r.id in info.unsafe and r.id not in local:
                    hard[f"glob:{r.id}"] = f"uses module-level variable `{r.id}`, which {info.unsafe[r.id]}"
        elif t is ast.Attribute and id(n) not in call_funcs:
            r = _root_name(n)
            if r is not None and r.id in info.imports and r.id not in local and not project_alias(r.id):
                mod = info.imports[r.id][0]
                o.imports_used.add(mod)
                why = module_problem(r.id, _chain(n), mod, "uses")
                if why:
                    hard[f"mod:{_chain(n)}"] = why
        elif t is ast.Name and isinstance(n.ctx, ast.Load) and id(n) not in call_funcs and id(n) not in attr_roots:
            nm = n.id
            if nm in local:
                continue
            if nm in info.consts:
                o.consts_used.add(nm)
                o.globals_used.add(nm)
            elif nm in info.gvars or nm in info.funcs or nm in info.classes:
                o.globals_used.add(nm)
            elif nm in info.unsafe:
                o.globals_used.add(nm)
                hard[f"glob:{nm}"] = f"reads module-level variable `{nm}`, which {info.unsafe[nm]}"
            elif nm in info.imports:
                mod, orig = info.imports[nm]
                o.imports_used.add(mod)
                if not (project and project.resolve_name(info, nm)):
                    why = module_problem(nm, f"{mod}.{orig}" if orig else nm, mod, "uses")
                    if why:
                        hard[f"mod:{nm}"] = why
        # attribute roots that are unsafe globals
        if t is ast.Attribute:
            r = _root_name(n)
            if r is not None and r.id in info.unsafe and r.id not in local and r.id not in info.imports:
                o.globals_used.add(r.id)
                hard[f"glob:{r.id}"] = f"uses module-level variable `{r.id}`, which {info.unsafe[r.id]}"

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
    return f"missing annotations ({', '.join(names)})"


_RE_REBIND = re.compile(r"variable '(\w+)' was inferred as ([^;]+); cannot rebind to (.+?)\.")
_RE_STATIC = re.compile(r"'(\w+)' has static type ([^;]+); cannot assign (.+)")


def classify_errors(diags: List[dict], source: Optional[str] = None) -> Tuple[str, str, str]:
    """(eligibility, reason, fix_kind) from real typechecker/parser diagnostics."""
    from .reasons import explain
    return explain(diags, source)


def _decide(project: Project, info: ModuleInfo, name: str, node: ast.AST):
    """-> (eligibility, reason, fix_kind, diagnostics for the target, scratch)."""
    own = project.analysis(info, "func", name)
    scratch: Dict[str, object] = {"own": own}
    if own.hard:
        return "not_eligible", _short(list(own.hard.values()), 2), "rewrite", [], scratch
    text = info.func_text(name)
    ex, u = _run_extract(project, info, name, text)
    scratch["unit_funcs"] = ex.helpers
    if ex.hard:
        return "not_eligible", _short(ex.hard, 2), "rewrite", [], scratch
    if ex.ok:
        return "verifiable", None, "rewrite", [], scratch
    diags, kind, src = ex.diagnostics, "rewrite", ex.source
    slots = infer_mod._build_slots([infer_mod._Chunk(t) for t in u.texts], {})
    if slots:
        ex2, u2 = _run_extract(project, info, name, text, infer=True)
        if ex2.hard:
            return "not_eligible", _short(ex2.hard, 2), "rewrite", [], scratch
        if ex2.ok:
            scratch["inferred"] = ex2.inferred
            names = own.missing or [s.name or "return type" for s in slots if s.chunk == 0]
            return "fixable", _missing_reason(names) + " — types will be inferred from usage", "annotations", [], scratch
        diags, src = ex2.diagnostics, ex2.source
    elig, reason, k2 = classify_errors(diags, src)
    if any(d.get("fn") != name for d in diags) and elig != "not_eligible":
        reason = f"a function it calls has a problem — {reason}"
    return elig, reason, k2, [d for d in diags if d.get("fn") == name], scratch


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
    project = Project()
    for rel in ws.py_files:
        try:
            raw = (ws.original / rel).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            emit("log", {"stream": "system", "level": "warn", "text": f"scan: skipped {rel}: cannot read ({e})"}, stage="scan")
            continue
        try:
            project.add(build_info(rel, raw))
        except (SyntaxError, ValueError, RecursionError) as e:
            emit("log", {"stream": "system", "level": "warn", "text": f"scan: skipped {rel}: does not parse ({e})"}, stage="scan")
            continue
    try:
        ws._project = project
    except Exception:
        pass
    for rel, info in project.infos.items():
        file_recs: List[FunctionRecord] = []
        for name, node in info.funcs.items():
            try:
                elig, reason, kind, diags, scratch = _decide(project, info, name, node)
                own = scratch.get("own")
                metrics = own.metrics
            except Exception as e:                               # never crash the scan on one odd function
                elig, reason, kind, diags, scratch = "not_eligible", f"could not analyse ({type(e).__name__}: {e})", "rewrite", [], {}
                own = None
                metrics = analyze(node, info, project=project).metrics
            rec = _record(info, node, name, metrics, elig, reason)
            rec.diagnostics = diags
            rec.private.update({"modinfo": info, "project": project, "own": own, "fix_kind": kind,
                                "inferred": scratch.get("inferred")})
            project.records[(rel, name)] = rec
            file_recs.append(rec)
        for cname, cnode in info.classes.items():                # v1: methods are reported, not analysed
            for m in cnode.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    try:
                        mo = analyze(m, info, is_method=True, project=project).metrics
                    except Exception:
                        mo = {"size_lines": m.end_lineno - m.lineno + 1, "loop_depth": 0, "arith_density": 0.0,
                              "calls": [], "imports": [], "uses_globals": []}
                    rec = _record(info, m, f"{cname}.{m.name}", mo, "not_eligible", f"method of class {cname}")
                    rec.private.update({"modinfo": info, "project": project, "fix_kind": "rewrite"})
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
