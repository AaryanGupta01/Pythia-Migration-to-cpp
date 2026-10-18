"""Deterministic annotation inference (no LLM): fill in missing parameter / return / field types.

Evidence, strongest first: defaults, doctest + call-site literals (`priors`), how the parameter is used in the
body (range(n) -> int, .append -> list, x / 2.5 -> float ...). The real PySub typechecker is the oracle: for each
unannotated slot we try its candidate types and keep the one that leaves the fewest diagnostics (coordinate
descent). Return types are read off the checker's own "returning T from a function declared -> bool" message.

    fill(texts, check, priors) -> (new_texts, notes)

`texts` are PySub-bound chunks (one top-level function or class each, already renamed/const-inlined);
`check(texts)` returns the list of diagnostics for the assembled module. Edits never add or remove lines
inside a function signature, so line numbers of function chunks stay valid.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

BARE = {"list", "dict", "List", "Dict"}
LISTS = ["list[int]", "list[float]", "list[str]", "list[bool]", "list[list[int]]", "list[list[float]]",
         "list[list[str]]", "list[list[bool]]"]
DICTS = ["dict[str, int]", "dict[int, int]", "dict[str, float]", "dict[str, str]", "dict[int, str]",
         "dict[int, float]", "dict[str, bool]", "dict[int, bool]"]
LADDER = ["int", "float", "str", "bool"] + LISTS[:4] + DICTS[:4]
STR_ONLY = {"lower", "upper", "strip", "lstrip", "rstrip", "title", "capitalize", "swapcase", "isdigit", "isalpha",
            "isalnum", "isspace", "isupper", "islower", "startswith", "endswith", "find", "rfind", "split",
            "splitlines", "replace", "format", "zfill", "ljust", "rjust", "center", "encode", "casefold", "partition"}
LIST_ONLY = {"append", "extend", "insert", "remove", "sort", "reverse", "clear", "copy"}
DICT_ONLY = {"get", "keys", "values", "items", "setdefault", "update", "popitem"}
_RET_MSG = re.compile(r"returning (.+?) from a function declared -> bool")


# ----------------------------------------------------------------------------- literal types
def _unify(a: Optional[str], b: Optional[str]) -> Optional[str]:
    if a is None or b is None:
        return None
    if a == b:
        return a
    if {a, b} <= {"int", "float"}:
        return "float"
    if {a, b} <= {"int", "bool"}:
        return "int"
    ma, mb = re.fullmatch(r"list\[(.*)\]", a), re.fullmatch(r"list\[(.*)\]", b)
    if ma and mb:
        u = _unify(ma.group(1), mb.group(1))
        return f"list[{u}]" if u else None
    return None


def lit_type(n: ast.AST) -> Optional[str]:
    """PySub type text of a literal expression, 'list'/'dict' for empty ones, None if unknown."""
    if isinstance(n, ast.Constant):
        v = n.value
        return {bool: "bool", int: "int", float: "float", str: "str"}.get(type(v))
    if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
        t = lit_type(n.operand)
        return t if t in ("int", "float") else None
    if isinstance(n, ast.List):
        if not n.elts:
            return "list"
        t = lit_type(n.elts[0])
        for e in n.elts[1:]:
            t = _unify(t, lit_type(e))
        return f"list[{t}]" if t and t not in ("list", "dict") else None
    if isinstance(n, ast.Dict):
        if not n.keys:
            return "dict"
        if any(k is None for k in n.keys):
            return None
        k = lit_type(n.keys[0])
        for e in n.keys[1:]:
            k = _unify(k, lit_type(e))
        v = lit_type(n.values[0])
        for e in n.values[1:]:
            v = _unify(v, lit_type(e))
        return f"dict[{k}, {v}]" if k in ("int", "str") and v in ("int", "float", "str", "bool") else None
    return None


def doctest_calls(src: str, fname: str) -> List[List[Optional[str]]]:
    """Argument literal types of every `>>> fname(...)` call in the function's docstring."""
    out: List[List[Optional[str]]] = []
    try:
        fn = ast.parse(src).body[0]
        doc = ast.get_docstring(fn) or ""
    except Exception:
        return out
    for line in doc.split("\n"):
        line = line.strip()
        if not line.startswith(">>>"):
            continue
        try:
            e = ast.parse(line[3:].strip(), mode="eval")
        except SyntaxError:
            continue
        for c in ast.walk(e):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name) and c.func.id == fname:
                out.append([lit_type(a) for a in c.args])
    return out


# ----------------------------------------------------------------------------- usage evidence
def _parents(fn: ast.AST) -> Dict[ast.AST, ast.AST]:
    return {c: p for p in ast.walk(fn) for c in ast.iter_child_nodes(p)}


def param_kinds(fn: ast.AST, p: str) -> List[str]:
    """Ordered evidence kinds for parameter `p`: int float num str bool list dict seq."""
    ev: List[str] = []
    par = _parents(fn)
    for n in ast.walk(fn):
        if not (isinstance(n, ast.Name) and n.id == p and isinstance(n.ctx, ast.Load)):
            continue
        up = par.get(n)
        if isinstance(up, ast.Call):
            f = up.func
            if n in up.args and isinstance(f, ast.Name):
                if f.id == "range" or f.id == "chr":
                    ev.append("int")
                elif f.id == "ord":
                    ev.append("str")
                elif f.id in ("len", "sorted", "list", "reversed", "enumerate", "zip", "tuple", "set"):
                    ev.append("seq")
                elif f.id in ("sum", "any", "all"):
                    ev.append("list")
                elif f.id in ("abs", "round", "min", "max"):
                    ev.append("num")
            elif n is f:
                pass
        elif isinstance(up, ast.Attribute) and up.value is n:
            call = par.get(up)
            m = up.attr
            if m in STR_ONLY:
                ev.append("str")
            elif m in LIST_ONLY:
                ev.append("list")
            elif m in DICT_ONLY:
                ev.append("dict")
            elif m == "join" and isinstance(call, ast.Call):
                ev.append("str")
        elif isinstance(up, ast.Subscript):
            if up.value is n:
                sl = up.slice
                if isinstance(sl, ast.Slice):
                    ev.append("seq")
                elif isinstance(sl, ast.Constant) and isinstance(sl.value, str):
                    ev.append("dict")
                else:
                    ev.append("seq")
            else:
                ev.append("int")
        elif isinstance(up, ast.For) and up.iter is n:
            ev.append("seq")
        elif isinstance(up, (ast.BinOp, ast.AugAssign, ast.Compare)):
            if isinstance(up, ast.BinOp):
                others, ops = [up.right if up.left is n else up.left], [up.op]
            elif isinstance(up, ast.AugAssign):
                others, ops = [up.value], [up.op]
            else:
                others, ops = [x for x in [up.left] + up.comparators if x is not n], list(up.ops)
            if isinstance(up, ast.Compare) and any(isinstance(o, (ast.In, ast.NotIn)) for o in ops):
                if up.comparators and up.comparators[0] is n:
                    ev.append("seq")
                continue
            for o in others:
                t = lit_type(o)
                if t == "float":
                    ev.append("float")
                elif t == "str":
                    ev.append("str")
                elif t == "bool":
                    ev.append("bool")
                elif t == "int":
                    ev.append("int" if any(isinstance(x, (ast.Mod, ast.FloorDiv, ast.LShift, ast.RShift,
                                                          ast.BitAnd, ast.BitOr, ast.BitXor)) for x in ops) else "num")
                elif t and t.startswith("list"):
                    ev.append("list")
            if any(isinstance(x, (ast.Div, ast.Pow)) for x in ops):
                ev.append("num")
        elif isinstance(up, ast.UnaryOp) and isinstance(up.op, ast.USub):
            ev.append("num")
    for n in ast.walk(fn):                       # `p += 1`-style updates
        if isinstance(n, ast.AugAssign) and isinstance(n.target, ast.Name) and n.target.id == p:
            t = lit_type(n.value)
            if t in ("int", "float", "str"):
                ev.append(t)
    return ev


def _expand(kind: str) -> List[str]:
    return {"int": ["int", "float"], "float": ["float", "int"], "num": ["int", "float"], "str": ["str"],
            "bool": ["bool", "int"], "list": LISTS, "dict": DICTS,
            "seq": ["list[int]", "str", "list[str]", "list[float]", "list[bool]"] + LISTS[4:],
            }.get(kind, [])


def candidates(kinds: List[str], priors: List[str], default: Optional[str], cap: int = 16) -> List[str]:
    out: List[str] = []

    def add(t: str):
        if t and t not in out:
            out.append(t)
    if default:
        add(default)
    for t in priors:
        if t in ("list", "dict"):
            kinds = [t] + kinds
        else:
            add(t)
    if "float" in kinds and "num" in kinds:
        kinds = ["float"] + [k for k in kinds if k != "float"]
    for k in kinds:
        for t in _expand(k):
            add(t)
    for t in LADDER:
        add(t)
    return out[:cap]


# ----------------------------------------------------------------------------- slots and edits
@dataclass
class Slot:
    chunk: int
    fn: str                      # function (or Class.method) name
    kind: str                    # 'param' | 'return' | 'field'
    name: str                    # param/field name, '' for return
    cands: List[str] = field(default_factory=list)
    value: Optional[str] = None


def _bpos(line: str, bytecol: int) -> int:
    return len(line.encode("utf-8")[:bytecol].decode("utf-8", "ignore"))


def _header_close(text: str, node: ast.AST) -> Optional[Tuple[int, int]]:
    """(row, char col) just after the `)` that closes the parameter list of `node`."""
    try:
        toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    for i, t in enumerate(toks):
        if t.type == tokenize.NAME and t.string == "def" and t.start[0] == node.lineno \
                and i + 2 < len(toks) and toks[i + 1].string == node.name:
            depth = 0
            for u in toks[i + 2:]:
                if u.type == tokenize.OP and u.string in "([{":
                    depth += 1
                elif u.type == tokenize.OP and u.string in ")]}":
                    depth -= 1
                    if depth == 0:
                        return u.end
    return None


def _functions(tree: ast.Module) -> List[Tuple[str, ast.FunctionDef, Optional[ast.ClassDef]]]:
    out = []
    for st in tree.body:
        if isinstance(st, ast.FunctionDef):
            out.append((st.name, st, None))
        elif isinstance(st, ast.ClassDef):
            for m in st.body:
                if isinstance(m, ast.FunctionDef):
                    out.append((f"{st.name}.{m.name}", m, st))
    return out


def _returns_value(fn: ast.FunctionDef) -> bool:
    for n in ast.walk(fn):
        if isinstance(n, ast.Return) and n.value is not None and \
                not (isinstance(n.value, ast.Constant) and n.value.value is None):
            return True
    return False


def _has_fields(cls: ast.ClassDef) -> bool:
    return any(isinstance(s, ast.AnnAssign) for s in cls.body)


def _self_attrs(init: ast.FunctionDef) -> Dict[str, ast.AST]:
    out: Dict[str, ast.AST] = {}
    for n in ast.walk(init):
        if isinstance(n, ast.Assign) and len(n.targets) == 1:
            t = n.targets[0]
            if isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self":
                out.setdefault(t.attr, n.value)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Attribute) \
                and isinstance(n.target.value, ast.Name) and n.target.value.id == "self":
            out.setdefault(n.target.attr, n.value)
    return out


class _Chunk:
    def __init__(self, text: str):
        self.text = text
        try:
            self.tree: Optional[ast.Module] = ast.parse(text)
        except SyntaxError:
            self.tree = None
        self.lines = text.split("\n")
        self.fns = _functions(self.tree) if self.tree else []


def _apply(chunk: _Chunk, assign: Dict[Tuple[str, str, str], str]) -> str:
    """Text of `chunk` with the slot values applied. assign keys: (fn, kind, name)."""
    if chunk.tree is None or not assign:
        return chunk.text
    lines = list(chunk.lines)
    edits: List[Tuple[int, int, int, str]] = []         # (row, c0, c1, text)  row 1-based
    inserts: List[Tuple[int, str]] = []                  # (before row, text)
    for qual, fn, cls in chunk.fns:
        for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs:
            t = assign.get((qual, "param", a.arg))
            if not t:
                continue
            ln = lines[a.lineno - 1]
            if a.annotation is not None:
                if a.annotation.lineno == a.annotation.end_lineno:
                    edits.append((a.annotation.lineno, _bpos(chunk.lines[a.annotation.lineno - 1], a.annotation.col_offset),
                                  _bpos(chunk.lines[a.annotation.lineno - 1], a.annotation.end_col_offset), t))
            else:
                c = _bpos(chunk.lines[a.lineno - 1], a.col_offset) + len(a.arg)
                nxt = ln[c:c + 1]
                edits.append((a.lineno, c, c, f": {t} " if nxt == "=" else f": {t}"))
        r = assign.get((qual, "return", ""))
        if r:
            if fn.returns is not None:
                if fn.returns.lineno == fn.returns.end_lineno:
                    edits.append((fn.returns.lineno, _bpos(chunk.lines[fn.returns.lineno - 1], fn.returns.col_offset),
                                  _bpos(chunk.lines[fn.returns.lineno - 1], fn.returns.end_col_offset), r))
            else:
                pos = _header_close(chunk.text, fn)
                if pos:
                    edits.append((pos[0], pos[1], pos[1], f" -> {r}"))
        if cls is not None and qual.endswith(".__init__"):
            fields = [(k[2], v) for k, v in assign.items() if k[0] == qual and k[1] == "field"]
            if fields and cls.body:
                first = cls.body[0]
                ind = " " * first.col_offset
                inserts.append((first.lineno, "\n".join(f"{ind}{n}: {v}" for n, v in fields)))
    for row, c0, c1, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        ln = lines[row - 1]
        lines[row - 1] = ln[:c0] + rep + ln[c1:]
    for row, rep in sorted(inserts, reverse=True):
        lines[row - 1:row - 1] = rep.split("\n")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- the driver
def _param_names(fn: ast.FunctionDef) -> List[ast.arg]:
    return fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs


def _build_slots(chunks: List[_Chunk], priors: Dict[str, List[List[Optional[str]]]]) -> List[Slot]:
    slots: List[Slot] = []
    for ci, ch in enumerate(chunks):
        for qual, fn, cls in ch.fns:
            ps = _param_names(fn)
            ndef = len(fn.args.defaults)
            pos = fn.args.posonlyargs + fn.args.args
            defaults = {a.arg: d for a, d in zip(pos[len(pos) - ndef:], fn.args.defaults)} if ndef else {}
            defaults.update({a.arg: d for a, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults) if d is not None})
            call_priors = priors.get(qual, [])
            for idx, a in enumerate(ps):
                if cls is not None and idx == 0 and a.arg == "self":
                    continue
                bare = isinstance(a.annotation, ast.Name) and a.annotation.id in BARE
                if a.annotation is not None and not bare:
                    continue
                pidx = idx - (1 if cls is not None else 0)
                pri: List[str] = []
                for c in call_priors:
                    if pidx < len(c) and c[pidx]:
                        pri.append(c[pidx])
                pri = sorted(set(pri), key=lambda t: (-pri.count(t), pri.index(t)))
                if len(set(pri)) > 1:                       # int+float call sites -> float; otherwise keep order
                    u = pri[0]
                    for t in pri[1:]:
                        u = _unify(u, t) or u
                    pri = [u] + [t for t in pri if t != u]
                dflt = lit_type(defaults[a.arg]) if a.arg in defaults else None
                if dflt in ("list", "dict"):
                    dflt = None
                kinds = param_kinds(fn, a.arg)
                if bare:
                    kinds = [("list" if a.annotation.id.lower() == "list" else "dict")] + kinds
                    pri = [t for t in pri if t.startswith(a.annotation.id.lower())]
                s = Slot(ci, qual, "param", a.arg, candidates(kinds, pri, dflt))
                s.value = s.cands[0]
                slots.append(s)
            if fn.name != "__init__" and (fn.returns is None or
                                          (isinstance(fn.returns, ast.Name) and fn.returns.id in BARE)) \
                    and _returns_value(fn):
                slots.append(Slot(ci, qual, "return", ""))
            if cls is not None and fn.name == "__init__" and not _has_fields(cls):
                for attr, val in _self_attrs(fn).items():
                    t = lit_type(val) if val is not None else None
                    if isinstance(val, ast.Name) and val.id in {a.arg for a in ps}:
                        s = Slot(ci, qual, "field", attr, ["@" + val.id])
                    else:
                        if t in ("list", "dict"):
                            t = None
                        s = Slot(ci, qual, "field", attr, candidates([], [], t, cap=10))
                    s.value = s.cands[0]
                    slots.append(s)
    return slots


def fill(texts: List[str], check: Callable[[List[str]], List[dict]],
         priors: Optional[Dict[str, List[List[Optional[str]]]]] = None) -> Tuple[List[str], List[str]]:
    chunks = [_Chunk(t) for t in texts]
    slots = _build_slots(chunks, priors or {})
    if not slots:
        return texts, []
    ret_slots = [s for s in slots if s.kind == "return"]
    assigned_ret: Dict[int, str] = {}

    def assignment(extra: Optional[Dict[int, str]] = None) -> Dict[int, Dict[Tuple[str, str, str], str]]:
        per: Dict[int, Dict[Tuple[str, str, str], str]] = {}
        params = {(s.chunk, s.fn, s.name): s.value for s in slots if s.kind == "param"}
        for s in slots:
            v = s.value
            if s.kind == "return":
                v = (extra or {}).get(id(s)) or assigned_ret.get(id(s))
            elif s.kind == "field" and v and v.startswith("@"):
                v = params.get((s.chunk, s.fn, v[1:]))
            if v:
                per.setdefault(s.chunk, {})[(s.fn, s.kind, s.name)] = v
        return per

    def render(extra=None) -> List[str]:
        per = assignment(extra)
        return [_apply(c, per.get(i, {})) if i in per else c.text for i, c in enumerate(chunks)]

    def score(extra=None) -> int:
        return len(check(render(extra)))

    best = score()
    # parameters + fields: coordinate descent
    for _round in range(2):
        changed = False
        for s in slots:
            if s.kind == "return" or best == 0 or len(s.cands) < 2:
                continue
            keep = s.value
            for cand in s.cands:
                if cand == keep:
                    continue
                s.value = cand
                sc = score()
                if sc < best:
                    best, keep, changed = sc, cand, True
                    if best == 0:
                        break
            s.value = keep
        if not changed or best == 0:
            break
    # return types: ask the checker what is returned
    for _round in range(3):
        progress = False
        for s in ret_slots:
            if id(s) in assigned_ret:
                continue
            diags = check(render({id(s): "bool"}))
            got = set()
            for d in diags:
                m = _RET_MSG.search(d["msg"])
                if m:
                    got.add(m.group(1))
            if not got:
                assigned_ret[id(s)] = "bool"
            elif got <= {"int", "float"}:
                assigned_ret[id(s)] = "float" if "float" in got else "int"
            elif len(got) == 1 and not (got & {"None", "<error>", "?"}) and "?" not in next(iter(got)):
                assigned_ret[id(s)] = next(iter(got))
            else:
                continue
            progress = True
        if not progress:
            break
    best = score()
    if best:                                             # callee return types may now change the best parameter
        for s in slots:
            if s.kind != "param" or len(s.cands) < 2 or best == 0:
                continue
            keep = s.value
            for cand in s.cands:
                if cand == keep:
                    continue
                s.value = cand
                sc = score()
                if sc < best:
                    best, keep = sc, cand
                    if best == 0:
                        break
            s.value = keep
    out = render()
    notes = [f"{s.fn}.{s.name}: {s.value}" if s.kind != "return" else f"{s.fn} -> {assigned_ret.get(id(s))}"
             for s in slots if (s.value if s.kind != "return" else assigned_ret.get(id(s)))]
    return out, notes
