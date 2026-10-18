"""
PYTHIA :: tuples (type rules + C++ emission), kept out of the shared dispatch chains.

A PySub tuple is fixed-size and heterogeneous: tuple[int, str] is a std::tuple<int64_t, PyStr *> value.
Tuples are immutable in Python and PySub has no `is`, so value semantics are exact.

Typing is deliberately strict: a tuple type only ever matches itself (no int -> float widening inside a
tuple), because CPython keeps the element's own type -- `t: tuple[float] = (1,)` prints (1,), not (1.0,).
Unpacking (`a, b = v`, `for k, v in ...`) is desugared by the parser into plain assignments through the
hidden builtin __pythia_unpack(v, n), so every later pass (optimizer, alias analysis) sees ordinary code.
"""
import hashlib
from typing import Optional

from . import ast_nodes as A
from .typecheck import Ty, INT, FLOAT, BOOL, STR, NONE, ERR, list_of

PRIM = ("int", "float", "bool", "str")


def tuple_of(elts) -> Ty:
    return Ty("tuple", elts=tuple(elts))


# ------------------------------------------------------------------ type predicates
def orderable(t: Optional[Ty]) -> bool:
    """Values that compare with < (and ==) exactly like CPython: prim, or tuples of those."""
    if t is None:
        return False
    if t.name in PRIM:
        return True
    return t.name == "tuple" and all(orderable(x) for x in t.elts)


hashable_key = orderable               # dict keys: int/float/bool/str or (nested) tuples of those


def reprable(t: Optional[Ty]) -> bool:
    """Printable by the generic C++ repr (py_value_repr): prim, tuples, lists of those, tuple-keyed dicts."""
    if t is None:
        return False
    if t.name in PRIM:
        return True
    if t.name == "tuple":
        return all(reprable(x) for x in t.elts)
    if t.name == "list":
        return t.elem is not None and t.elem.name != "list" and reprable(t.elem)
    if t.name == "dict":
        return t.key is not None and reprable(t.key) and reprable(t.elem)
    return False


def involves_tuple(t: Optional[Ty]) -> bool:
    if t is None:
        return False
    if t.name == "tuple":
        return True
    return involves_tuple(t.elem) or involves_tuple(t.key)


def homogeneous(t: Ty) -> Optional[Ty]:
    """The shared element type of a non-empty tuple whose elements all have one type, else None."""
    if t.name != "tuple" or not t.elts or any(x != t.elts[0] for x in t.elts):
        return None
    return t.elts[0]


def generic_dict(t: Ty) -> bool:
    """dict types outside the eight monomorphic runtime dicts: tuple keys or tuple values."""
    return t.name == "dict" and (involves_tuple(t.key) or involves_tuple(t.elem))


# ------------------------------------------------------------------ type checking
def resolve(tc, te: A.TypeExpr) -> Ty:
    if not te.params:
        return tc.err(te, "bare 'tuple' is not allowed; write tuple[int, str] (one type per element)")
    if any(p.name == "..." for p in te.params):
        return tc.err(te, "variable-length tuple[T, ...] is outside the PySub subset: PySub tuples have a fixed "
                          "size; use list[T] for a sequence of any length")
    elts = [tc.resolve_type(p) for p in te.params]
    if any(t is ERR for t in elts):
        return ERR
    if any(t == NONE for t in elts):
        return tc.err(te, "a tuple element cannot have type None")
    return tuple_of(elts)


def resolve_dict(tc, te: A.TypeExpr, k: Ty, v: Ty) -> Ty:
    """dict[K, V] where K or V is a tuple: served by the generic runtime dict (PyDictT)."""
    if k is ERR or v is ERR:
        return ERR
    if not hashable_key(k):
        return tc.err(te, f"dict key type must be int, str or a tuple of int, float, bool, str; found {k}")
    if not (v.name in PRIM or (v.name == "tuple" and reprable(v))):
        return tc.err(te, f"dict value type must be int, float, bool, str or a tuple of those; found {v}")
    return Ty("dict", v, k)


def synth_lit(tc, e: A.TupleLit) -> Ty:
    ts = [tc.synth(x) for x in e.elts]
    if any(t is ERR for t in ts):
        return ERR
    for x, t in zip(e.elts, ts):
        if (t.name == "list" and t.elem is None) or (t.name == "dict" and t.key is None):
            return tc.err(x, "cannot infer the type of an empty list/dict inside a tuple; annotate the variable, "
                             "e.g. t: tuple[list[int], int] = ([], 0)")
    return tuple_of(ts)


def check_lit(tc, e: A.TupleLit, expected: Ty) -> Ty:
    """Checking mode: push tuple[T1, T2] element types into the literal (empty lists, nested tuples)."""
    if expected.name != "tuple" or len(expected.elts) != len(e.elts):
        return tc.synth(e)
    ts = [tc.check_expr(x, w) for x, w in zip(e.elts, expected.elts)]
    e.ty = ERR if any(t is ERR for t in ts) else tuple_of(ts)
    return e.ty


def const_index(e: A.Node) -> Optional[int]:
    if isinstance(e, A.IntLit):
        return e.value
    if isinstance(e, A.UnaryOp) and e.op in ("-", "+") and isinstance(e.operand, A.IntLit):
        return -e.operand.value if e.op == "-" else e.operand.value
    return None


def subscript(tc, e: A.Subscript, base: Ty) -> Ty:
    tc.synth(e.index)
    k = const_index(e.index)
    if k is None:
        return tc.err(e.index, "a tuple index must be an integer constant such as t[0] or t[-1] (each position "
                               "has its own static type); use a list for indexing by a variable")
    n = len(base.elts)
    if not -n <= k < n:
        return tc.err(e.index, f"tuple index {k} is out of range for {base} (it has {n} element(s))")
    e.tuple_index = k % n
    return base.elts[e.tuple_index]


def compare(tc, e: A.Compare, lt: Ty, rt: Ty) -> Ty:
    if lt is ERR or rt is ERR:
        return BOOL
    if e.op in ("in", "not in"):
        el = homogeneous(rt)
        if el is None or el != lt or not orderable(el):
            return tc.err(e, f"`{e.op}` on a tuple needs all its elements to have the type of the left operand "
                             f"(int, float, bool, str or tuples of those); found {lt} {e.op} {rt}")
        return BOOL
    if lt != rt:
        return tc.err(e, f"cannot compare {lt} with {rt}: PySub compares tuples only of the same type")
    if not orderable(lt):
        return tc.err(e, f"cannot compare {lt}: tuple comparison needs int, float, bool, str or tuple elements")
    return BOOL


def binop(tc, node: A.Node, op: str, lt: Ty, rt: Ty) -> Ty:
    if op == "+" and lt.name == "tuple" and rt.name == "tuple":
        return tuple_of(lt.elts + rt.elts)
    if op == "*":
        return tc.err(node, "repeating a tuple with * is outside the PySub subset (its size would depend on a "
                            "run-time value); write the elements out or use a list")
    return tc.err(node, f"operator {op!r} is not defined for {lt} and {rt}")


def unpack_call(tc, e: A.Call) -> Ty:
    """__pythia_unpack(v, n): the parser's desugaring of `a, b = v`; evaluates to v after the length check."""
    v, n = e.args[0], e.args[1].value
    t = tc.synth(v)
    if t is ERR:
        return ERR
    if t.name == "tuple":
        if len(t.elts) != n:
            why = ("too many values to unpack" if len(t.elts) > n else "not enough values to unpack")
            return tc.err(e, f"cannot unpack {t} into {n} target(s) ({why}: expected {n}, got {len(t.elts)})")
        return t
    if t.name == "list" or t == STR:
        return t
    return tc.err(e, f"cannot unpack non-iterable {t} object" if t.name in PRIM or t.name in tc.classes
                  else f"unpacking a {t} is outside the PySub subset (unpack a tuple, a list or a str)")


def items_call(tc, e: A.MethodCall, recv: Ty) -> Ty:
    """d.items() -> list[tuple[K, V]], only where CPython's live view can't be told apart from a list."""
    tc._margs(e, 0, 0, "items")
    if not getattr(e, "items_ok", False):
        return tc.err(e, "d.items() is supported directly in a for loop (`for k, v in d.items():`) or as the "
                         "argument of list()/sorted() in PySub (a dict_items view prints differently from a list)")
    return list_of(tuple_of([recv.key, recv.elem]))


def mark_items(node) -> None:
    if isinstance(node, A.MethodCall) and node.method == "items":
        node.items_ok = True


def tolist_node(e: A.Node) -> A.Node:
    """Iterating a homogeneous tuple: wrap it so the emitter sees a list (lower.py)."""
    c = A.Call(e.line, e.col, func="__pythia_tolist", args=[e])
    c.ty = list_of(homogeneous(e.ty))
    return c


# ------------------------------------------------------------------ C++ emission
def ctype_tuple(t: Ty) -> str:
    from .emit_c import ctype
    return "std::tuple<" + ", ".join(ctype(x).strip() for x in t.elts) + "> "


def dict_t_name(t: Ty) -> str:
    """Deterministic name for a generic (tuple-keyed or tuple-valued) dict type; see splice_dict_defs."""
    name = "PyDictT_" + hashlib.sha1(str(t).encode()).hexdigest()[:10]
    _DICT_T[name] = t
    return name


_DICT_T: dict = {}


def splice_dict_defs(em, marker: int) -> None:
    """Define, after the #include, every generic dict type the emitted code mentions: NAME, NAME_new, NAME_set..."""
    import re
    from .emit_c import ctype
    used = sorted(set(re.findall(r"PyDictT_[0-9a-f]{10}", "\n".join(em.buf))))
    if not used:
        return
    lines = ["/* dicts with tuple keys/values: generic runtime dict */"]
    for n in used:
        t = _DICT_T[n]
        k, v = ctype(t.key).strip(), ctype(t.elem).strip()
        lines.append(f"using {n} = PyDictT<{k}, {v}>;")
        lines.append(f"static inline {n} *{n}_new() {{ return arena_new<{n}>(); }}")
        lines.append(f"static inline void {n}_set({n} *d, {k} key, {v} val) {{ pyd_set(d, key, val); }}")
        lines.append(f"static inline {v} {n}_get({n} *d, {k} key) {{ return pyd_get(d, key); }}")
        lines.append(f"static inline {v} {n}_get_default({n} *d, {k} key, {v} val) "
                     f"{{ return pyd_get_default(d, key, val); }}")
        lines.append(f"static inline bool {n}_contains({n} *d, {k} key) {{ return pyd_contains(d, key); }}")
    lines.append("")
    em.buf[marker:marker] = lines
    if em.track:
        em.src_of[marker:marker] = [0] * len(lines)


def emit_lit(em, e: A.TupleLit) -> str:
    # a braced initialiser evaluates its elements left to right, as Python does
    return f"{ctype_tuple(e.ty).strip()}{{" + ", ".join(em.ex(x) for x in e.elts) + "}"


def emit_compare(em, e: A.Compare) -> str:
    l, r = em.ex(e.left), em.ex(e.right)
    if e.op in ("in", "not in"):
        test = f"pyt_contains({r}, {l})"
        return test if e.op == "in" else f"(!{test})"
    fn = {"==": "pyl_eqv", "!=": "!pyl_eqv", "<": "pyt_lt", "<=": "pyt_le", ">": "pyt_gt", ">=": "pyt_ge"}[e.op]
    return f"({fn}({l}, {r}))"


def emit_call(em, e: A.Call) -> Optional[str]:
    """Calls with tuple semantics; None means 'not mine, emit normally'."""
    n = e.func
    if n == "__pythia_unpack":
        v, k = e.args[0], e.args[1].value
        if v.ty.name == "tuple":
            return em.ex(v)
        return f"pystr_unpack({em.ex(v)}, {k})" if v.ty == STR else f"pyl_unpack({em.ex(v)}, {k})"
    if n == "__pythia_tolist":
        from .emit_c import ctype
        return f"pyt_to_list<{ctype(e.ty.elem).strip()}>({em.ex(e.args[0])})"
    if not e.args or e.args[0].ty is None:
        return None
    a = e.args[0]
    if n == "len" and a.ty.name == "tuple":
        return f"pyt_len({em.ex(a)})"
    if n == "str" and a.ty.name == "tuple":
        return f"py_repr_pystr({em.ex(a)})"
    return None
