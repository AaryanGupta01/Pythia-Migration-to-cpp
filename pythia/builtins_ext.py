"""
PYTHIA :: builtins and standard-library surface -- typing, emission and fidelity notes.

Dispatch tables for what the core `typecheck.py` / `emit_c.py` / `lower.py` delegate here with a one-line hook:
the math module, bitwise operators, slicing, the extra str / list / dict methods, pow(), bin/hex/oct, int(s, base),
repr() and the %-format helpers.  Runtime counterparts are the `px_*` block of runtime/pyrt.hpp; parse-time sugar
(imports, slices, str.format, %-formatting) is in parse_ext.py.
"""
from typing import Optional

from . import ast_nodes as A
from . import parse_ext as PX
from .typecheck import Ty, INT, FLOAT, BOOL, STR, NONE, ERR, NUMERIC, list_of, widens_to

BITOPS = ("&", "|", "^", "<<", ">>")
INTLIKE = ("int", "bool")

# names the studio's rule extractor lists (it reads typecheck.py's source, which only sees the hook)
METHOD_TABLE = {
    "str": ["zfill", "center", "ljust", "rjust", "isnumeric", "isdecimal", "istitle", "isascii", "casefold",
            "removeprefix", "removesuffix", "expandtabs", "rsplit", "splitlines", "rindex", "split", "find", "rfind",
            "index", "count", "startswith", "endswith"],
    "list": ["index"],
    "dict": ["keys", "values", "pop", "setdefault", "update", "copy", "clear", "fromkeys"],
}
BUILTIN_NAMES = {"pow", "bin", "hex", "oct", "repr"}

_VIEW_CONSUMERS = ("len", "sorted", "list", "sum", "min", "max")


def _is_view(n: A.Node) -> bool:
    return isinstance(n, A.MethodCall) and n.method in ("keys", "values")


def mark_view_ok(tc, node: A.Node) -> None:
    """d.keys() / d.values() are accepted only where their value cannot be told apart from a list."""
    if _is_view(node):
        tc.__dict__.setdefault("view_ok", set()).add(id(node))


def _intlike(t: Ty) -> bool:
    return t.name in INTLIKE


def _need(tc, a: A.Node, ok, what: str) -> Ty:
    t = tc.synth(a)
    if t is not ERR and not ok(t):
        tc.err(a, f"{what}, found {t}")
    return t


def _nokw(tc, e) -> bool:
    if getattr(e, "kwargs", None):
        tc.err(e.kwargs[0], f"keyword argument {e.kwargs[0].name!r} is outside the PySub subset here")
        return False
    return True


def _count(tc, e, lo: int, hi: int, what: str) -> bool:
    if not (lo <= len(e.args) <= hi):
        want = str(lo) if lo == hi else f"{lo} to {hi}"
        tc.err(e, f"{what}() takes {want} argument(s) in PySub, {len(e.args)} given")
        for a in e.args:
            tc.synth(a)
        return False
    return True


# ------------------------------------------------------------------------------------------------ typing: calls
def synth_call(tc, e: A.Call) -> Optional[Ty]:
    f = e.func
    if f in _VIEW_CONSUMERS:
        for a in e.args:
            mark_view_ok(tc, a)
        return None
    if f in tc.funcs or f in tc.classes:
        return None
    if f == "__slice":
        return _slice(tc, e)
    if f.startswith("math."):
        return _math(tc, e)
    if f == "int" and len(e.args) == 2:
        if not _nokw(tc, e):
            return ERR
        s = _need(tc, e.args[0], lambda t: t == STR, "int() with a base needs a str (TypeError in CPython)")
        _need(tc, e.args[1], _intlike, "int() base must be an int")
        return INT
    if f == "pow":
        return _pow(tc, e)
    if f in ("bin", "hex", "oct"):
        if _nokw(tc, e) and _count(tc, e, 1, 1, f):
            _need(tc, e.args[0], _intlike, f"{f}() needs an int")
        return STR
    if f == "repr":
        if _nokw(tc, e) and _count(tc, e, 1, 1, f):
            _need(tc, e.args[0], lambda t: t.name in NUMERIC or t == STR, "repr() supports int, float, bool and str in PySub")
        return STR
    if f == "__pct_d":
        _need(tc, e.args[0], lambda t: t.name in NUMERIC, "%d format: a real number is required (TypeError in CPython)")
        return INT
    if f == "__pct_i":
        _need(tc, e.args[0], _intlike, "%x / %o format: an integer is required (TypeError in CPython)")
        return INT
    if f == "__pct_c":
        _need(tc, e.args[0], lambda t: _intlike(t) or t == STR, "%c requires an int or a one-character str")
        return STR
    return None


def _slice(tc, e) -> Ty:
    base = tc.synth(e.args[0])
    for a in e.args[1:]:
        if not isinstance(a, A.NoneLit):
            _need(tc, a, _intlike, "slice indices must be integers or None")
    if base is ERR:
        return ERR
    if base == STR or base.name == "list":
        return base
    return tc.err(e, f"{base} does not support slicing in PySub (only str and list do)")


def _math(tc, e) -> Ty:
    name = e.func[5:]
    if name in PX.MATH_CALL_CONSTS:
        return FLOAT
    spec = PX.MATH_FUNCS.get(name)
    if spec is None:
        return tc.err(e, f"math.{name} is not supported in PySub")
    lo, hi, kind, ret = spec
    rt = {"F": FLOAT, "I": INT, "B": BOOL}[ret]
    for kw in getattr(e, "kwargs", None) or []:
        if name == "isclose" and kw.name in ("rel_tol", "abs_tol"):
            _need(tc, kw.value, lambda t: t.name in NUMERIC, f"math.isclose {kw.name} must be a number")
        else:
            tc.err(kw, f"keyword argument {kw.name!r} is outside the PySub subset for math.{name}()")
    if not _count(tc, e, lo, hi, f"math.{name}"):
        return rt
    for a in e.args:
        if kind == "i":
            _need(tc, a, _intlike, f"math.{name}() needs an integer ('float' object cannot be interpreted as an integer)")
        else:
            _need(tc, a, lambda t: t.name in NUMERIC, f"math.{name}() needs a number")
    return rt


def _neg_literal(a: A.Node) -> bool:
    return isinstance(a, A.UnaryOp) and a.op == "-" and isinstance(a.operand, A.IntLit) and a.operand.value > 0


def _pow(tc, e) -> Ty:
    if not (_nokw(tc, e) and _count(tc, e, 2, 3, "pow")):
        return ERR
    ts = [tc.synth(a) for a in e.args]
    if any(t is ERR for t in ts):
        return ERR
    if any(t.name not in NUMERIC for t in ts):
        return tc.err(e, "pow() needs numbers")
    if len(ts) == 3:
        if not all(_intlike(t) for t in ts):
            return tc.err(e, "pow() with three arguments needs integers (TypeError in CPython)")
        return INT
    if FLOAT in ts or _neg_literal(e.args[1]):
        return FLOAT                     # int ** negative literal is a float in CPython
    return INT                           # a negative exponent in a variable raises PythiaSemanticError at run time, as `**` does


# ----------------------------------------------------------------------------------------------- typing: operators
def bitop_result(tc, node, op: str, lt: Ty, rt: Ty) -> Ty:
    if lt is ERR or rt is ERR:
        return ERR
    if _intlike(lt) and _intlike(rt):
        return BOOL if (op in "&|^" and lt == BOOL and rt == BOOL) else INT
    return tc.err(node, f"operator {op!r} is not defined for {lt} and {rt} (bitwise operators need int or bool)")


def invert_result(tc, node, t: Ty) -> Ty:
    if t is ERR:
        return ERR
    if _intlike(t):
        return INT
    return tc.err(node, f"unary '~' is not defined for {t}")


# ---------------------------------------------------------------------------------------------- typing: methods
# name -> (min, max, kinds, result);  kinds: s str, S str-or-None literal, i int, b bool/int
#   result: S str, B bool, I int, L list[str]
_STR = {
    "zfill": (1, 1, "i", "S"), "center": (1, 2, "is", "S"), "ljust": (1, 2, "is", "S"), "rjust": (1, 2, "is", "S"),
    "isnumeric": (0, 0, "", "B"), "isdecimal": (0, 0, "", "B"), "istitle": (0, 0, "", "B"), "isascii": (0, 0, "", "B"),
    "casefold": (0, 0, "", "S"), "removeprefix": (1, 1, "s", "S"), "removesuffix": (1, 1, "s", "S"),
    "expandtabs": (0, 1, "i", "S"), "rsplit": (0, 2, "Si", "L"), "split": (0, 2, "Si", "L"),
    "splitlines": (0, 1, "b", "L"),
    "find": (1, 3, "sii", "I"), "rfind": (1, 3, "sii", "I"), "index": (1, 3, "sii", "I"), "rindex": (1, 3, "sii", "I"),
    "count": (1, 3, "sii", "I"), "startswith": (1, 3, "sii", "B"), "endswith": (1, 3, "sii", "B"),
}
_OLD_ARITY = {"find": 1, "rfind": 1, "index": 1, "count": 1, "startswith": 1, "endswith": 1}   # core logic handles these


def is_fromkeys(tc, e) -> bool:
    return (isinstance(e.recv, A.Name) and e.recv.id == "dict" and e.method == "fromkeys"
            and tc.scope.lookup("dict") is None)


def synth_fromkeys(tc, e) -> Ty:
    if not (_nokw(tc, e) and _count(tc, e, 2, 2, "dict.fromkeys")):
        return ERR
    kt, vt = tc.synth(e.args[0]), tc.synth(e.args[1])
    if kt is ERR or vt is ERR:
        return ERR
    if kt.name != "list" or kt.elem is None or kt.elem.name not in ("int", "str"):
        return tc.err(e.args[0], f"dict.fromkeys() needs a list[int] or list[str] of keys, found {kt}")
    if vt.name not in ("int", "float", "bool", "str"):
        return tc.err(e.args[1], f"dict.fromkeys() needs an int, float, bool or str value, found {vt}")
    return Ty("dict", vt, kt.elem)


def synth_method(tc, e: A.MethodCall, recv: Ty) -> Optional[Ty]:
    m, n = e.method, len(e.args)
    if recv == STR:
        if m in ("partition", "rpartition"):
            return tc.err(e, f"str.{m}() returns a tuple, and PySub has no tuples; use find() and slicing")
        if m == "format":
            return tc.err(e, "str.format() needs a string-literal template, e.g. \"{} {}\".format(a, b)")
        if m == "join":
            for a in e.args:
                mark_view_ok(tc, a)
            return None
        spec = _STR.get(m)
        if spec is None:
            return None
        if m in _OLD_ARITY and n == _OLD_ARITY[m]:
            return None
        if m == "split" and n <= 1 and not (n and isinstance(e.args[0], A.NoneLit)):
            return None
        lo, hi, kinds, ret = spec
        if not _count(tc, e, lo, hi, m):
            return ERR
        for a, k in zip(e.args, kinds):
            if k == "s":
                _need(tc, a, lambda t: t == STR, f"{m}() argument must be str")
            elif k == "S":
                if not isinstance(a, A.NoneLit):
                    _need(tc, a, lambda t: t == STR, f"{m}() separator must be str or None")
            elif k == "i":
                _need(tc, a, _intlike, f"{m}() argument must be an int")
            else:
                _need(tc, a, _intlike, f"{m}() argument must be a bool")
        return {"S": STR, "B": BOOL, "I": INT, "L": list_of(STR)}[ret]
    if recv.name == "list" and m == "index" and n > 1:
        el = recv.elem
        if el is None or not (el.name in ("int", "float", "bool", "str") or el.name in tc.classes):
            return tc.err(e, f"index() on a {recv} needs element equality, which nested lists don't have in PySub")
        if not _count(tc, e, 1, 3, "index"):
            return ERR
        tc._want(e.args[0], el, "index() value")
        for a in e.args[1:]:
            tc._want(a, INT, "index() start/stop")
        return INT
    if recv.name == "dict" and m in METHOD_TABLE["dict"]:
        return _dict_method(tc, e, recv)
    return None


def _dict_method(tc, e, recv: Ty) -> Ty:
    m, n = e.method, len(e.args)
    if recv.key is None:
        return tc.err(e, "cannot use dict methods on a dict whose key/value types are not yet known")
    if m == "fromkeys":
        return tc.err(e, "fromkeys() is called on dict itself: dict.fromkeys(keys, value)")
    if m in ("keys", "values"):
        _count(tc, e, 0, 0, m)
        if id(e) not in tc.__dict__.get("view_ok", ()):
            return tc.err(e, f"d.{m}() is a live view in CPython; PySub accepts it only directly in a `for` loop, `in`, "
                             f"len(), sorted(), list(), sum(), min(), max() or str.join()")
        return list_of(recv.key if m == "keys" else recv.elem)
    if m in ("copy", "clear"):
        _count(tc, e, 0, 0, m)
        return recv if m == "copy" else NONE
    if m == "update":
        if _count(tc, e, 1, 1, m):
            t = tc.synth(e.args[0])
            if t is not ERR and t != recv:
                tc.err(e.args[0], f"update() needs a {recv}, found {t}")
        return NONE
    if m == "pop":
        if _count(tc, e, 1, 2, m):
            tc._want(e.args[0], recv.key, "pop() key")
            if n == 2:
                tc._want(e.args[1], recv.elem, "pop() default")
        return recv.elem
    if m == "setdefault":
        if _count(tc, e, 2, 2, m):
            tc._want(e.args[0], recv.key, "setdefault() key")
            tc._want(e.args[1], recv.elem, "setdefault() default")
        return recv.elem
    return ERR


# ------------------------------------------------------------------------------------------------------ emission
def _f(em, a: A.Node) -> str:
    s = em.ex(a)
    return s if a.ty == FLOAT else f"((double)({s}))"


def _i(em, a: A.Node) -> str:
    return f"((int64_t)({em.ex(a)}))"


_M1 = {"sqrt", "exp", "sin", "cos", "tan", "asin", "acos", "atan", "sinh", "cosh", "tanh", "asinh", "acosh", "atanh",
       "degrees", "radians", "fabs", "log1p", "expm1"}
_M2 = {"atan2": "px_atan2", "hypot": "px_hypot", "copysign": "px_copysign", "fmod": "px_fmod", "pow": "px_math_pow"}


def _kwarg(e, name: str):
    for kw in getattr(e, "kwargs", None) or []:
        if kw.name == name:
            return kw.value
    return None


def _opt(em, a, default: str) -> str:
    return default if a is None else _i(em, a)


def _slice_args(em, e) -> str:
    out = []
    for a in e.args[1:]:
        out.append("false, 0" if isinstance(a, A.NoneLit) else f"true, {_i(em, a)}")
    return ", ".join(out)


def emit_call(em, e: A.Call) -> Optional[str]:
    n = e.func
    if n in em.tc.funcs or n in em.tc.classes:
        return None
    a = e.args
    if n == "__slice":
        base = a[0]
        fn = "px_str_slice" if base.ty == STR else "px_slice"
        return f"{fn}({em.ex(base)}, {_slice_args(em, e)})"
    if n.startswith("math."):
        return _emit_math(em, e)
    if n == "int":
        t = a[0].ty
        if len(a) == 2:
            return f"px_int_from_str({em.ex(a[0])}, {_i(em, a[1])})"
        if t == STR:
            return f"px_int_from_str({em.ex(a[0])}, 10)"
        if t == FLOAT:
            return f"px_f2i({em.ex(a[0])})"
        return None
    if n == "float" and a[0].ty == STR:
        return f"px_f64_from_str({em.ex(a[0])})"
    if n == "format" and a[0].ty.name in INTLIKE:
        fn = "px_format_i64" if a[0].ty == INT else "px_format_bool_spec"
        return f"{fn}({em.ex(a[0])}, {em.ex(a[1])})"
    if n == "pow":
        if len(a) == 3:
            return f"px_pow_mod({_i(em, a[0])}, {_i(em, a[1])}, {_i(em, a[2])})"
        if e.ty == INT:
            return f"py_pow_i64({_i(em, a[0])}, {_i(em, a[1])})"
        return f"px_pow_f64({_f(em, a[0])}, {_f(em, a[1])})"
    if n in ("bin", "hex", "oct"):
        return f"px_radix_str({_i(em, a[0])}, {dict(bin=2, oct=8, hex=16)[n]})"
    if n == "repr":
        t = a[0].ty
        x = em.ex(a[0])
        return (f"px_repr_str_obj({x})" if t == STR else f"pystr_from_f64({x})" if t == FLOAT
                else f"pystr_from_bool({x})" if t == BOOL else f"pystr_from_i64({x})")
    if n == "__pct_d":
        return f"px_f2i({em.ex(a[0])})" if a[0].ty == FLOAT else _i(em, a[0])
    if n == "__pct_i":
        return _i(em, a[0])
    if n == "__pct_c":
        return f"px_pct_c_str({em.ex(a[0])})" if a[0].ty == STR else f"px_pct_c({_i(em, a[0])})"
    return None


def _emit_math(em, e) -> str:
    name, a = e.func[5:], e.args
    if name == "inf":
        return "std::numeric_limits<double>::infinity()"
    if name == "nan":
        return "std::numeric_limits<double>::quiet_NaN()"
    if name in _M1:
        return f"px_{name}({_f(em, a[0])})"
    if name in ("log2", "log10"):
        return f"px_{name}({_f(em, a[0])}, {'true' if a[0].ty != FLOAT else 'false'})"
    if name == "log":
        xi = "true" if a[0].ty != FLOAT else "false"
        if len(a) == 1:
            return f"px_log({_f(em, a[0])}, {xi})"
        bi = "true" if a[1].ty != FLOAT else "false"
        return f"px_log_b({_f(em, a[0])}, {xi}, {_f(em, a[1])}, {bi})"
    if name in _M2:
        return f"{_M2[name]}({_f(em, a[0])}, {_f(em, a[1])})"
    if name in ("floor", "ceil", "trunc"):
        if a[0].ty != FLOAT:
            return _i(em, a[0])
        return f"{ {'floor': 'px_floor_i', 'ceil': 'px_ceil_i', 'trunc': 'px_f2i'}[name] }({em.ex(a[0])})"
    if name == "isclose":
        rel, ab = _kwarg(e, "rel_tol"), _kwarg(e, "abs_tol")
        return (f"px_isclose({_f(em, a[0])}, {_f(em, a[1])}, {_f(em, rel) if rel is not None else '1e-09'}, "
                f"{_f(em, ab) if ab is not None else '0.0'})")
    if name in ("isfinite", "isinf", "isnan"):
        return f"std::{name}({_f(em, a[0])})"
    if name in ("gcd", "lcm"):
        acc = _i(em, a[0])
        if len(a) == 1:
            return f"px_{name}({acc}, {'0' if name == 'gcd' else '1'})"
        for x in a[1:]:
            acc = f"px_{name}({acc}, {_i(em, x)})"
        return acc
    if name == "perm" and len(a) == 1:
        v = em.fresh()
        return f"[&]() {{ int64_t {v} = {_i(em, a[0])}; return px_perm({v}, {v}); }}()"
    return f"px_{name}({', '.join(_i(em, x) for x in a)})"


def emit_bitop(em, e, l: str, r: str) -> str:
    op = e.op
    if op in ("&", "|", "^"):
        s = f"(({l}) {op} ({r}))"
        return f"((bool)({s}))" if e.ty == BOOL else s
    return f"{'px_lshift' if op == '<<' else 'px_rshift'}((int64_t)({l}), (int64_t)({r}))"


_KEEP = ("find", "rfind", "index", "count", "startswith", "endswith")


def emit_method(em, e: A.MethodCall) -> Optional[str]:
    m, a = e.method, e.args
    if isinstance(e.recv, A.Name) and e.recv.id == "dict" and m == "fromkeys" and e.recv.ty is None:
        from .emit_c import dict_rt_name, list_rt_name
        return f"px_dfromkeys<{dict_rt_name(e.ty)}>({em.ex(a[0])}, {em.ex(a[1])})"
    rt = e.recv.ty
    if rt is None:
        return None
    r = em.ex(e.recv)
    if rt == STR:
        n = len(a)
        if m in _OLD_ARITY and n == _OLD_ARITY[m]:
            return None
        if m == "split" and n <= 1 and not (n and isinstance(a[0], A.NoneLit)):
            return None
        sep = lambda x: "nullptr" if (x is None or isinstance(x, A.NoneLit)) else em.ex(x)
        if m == "zfill":
            return f"px_zfill({r}, {_i(em, a[0])})"
        if m in ("center", "ljust", "rjust"):
            return f"px_{m}({r}, {_i(em, a[0])}, {em.ex(a[1]) if n > 1 else 'pystr_lit(" ")'})"
        if m in ("isnumeric", "isdecimal"):
            return f"pystr_isdigit({r})"
        if m in ("istitle", "isascii", "casefold"):
            return f"px_{m}({r})"
        if m in ("removeprefix", "removesuffix"):
            return f"px_{m}({r}, {em.ex(a[0])})"
        if m == "expandtabs":
            return f"px_expandtabs({r}, {_i(em, a[0]) if a else '8'})"
        if m in ("split", "rsplit"):
            return f"px_{m}({r}, {sep(a[0]) if a else 'nullptr'}, {_i(em, a[1]) if n > 1 else '-1'})"
        if m == "splitlines":
            return f"px_splitlines({r}, {em.truthy(em.ex(a[0]), a[0].ty) if a else 'false'})"
        if m in _STR_RANGE:
            start = _i(em, a[1]) if n > 1 else "0"
            end = _i(em, a[2]) if n > 2 else "INT64_MAX"
            return f"px_str_{m}({r}, {em.ex(a[0])}, {start}, {end})"
        return None
    if rt.name == "list" and m == "index" and len(a) > 1:
        v = em.ex(a[0])
        return f"px_list_index({r}, {v}, {_i(em, a[1])}, {_i(em, a[2]) if len(a) > 2 else 'INT64_MAX'})"
    if rt.name == "dict" and m in METHOD_TABLE["dict"]:
        k = [em.ex(x) for x in a]
        if m == "keys":
            return f"pyl_keys({r})"
        if m == "values":
            return f"px_dvalues({r})"
        if m == "pop":
            return f"px_dpop({r}, {k[0]})" if len(a) == 1 else f"px_dpop_default({r}, {k[0]}, {k[1]})"
        if m == "setdefault":
            return f"px_dsetdefault({r}, {k[0]}, {k[1]})"
        if m == "update":
            return f"(px_dupdate({r}, {k[0]}), 0)"
        if m == "copy":
            return f"px_dcopy({r})"
        if m == "clear":
            return f"(px_dclear({r}), 0)"
    return None


_STR_RANGE = ("find", "rfind", "index", "rindex", "count", "startswith", "endswith")


# ------------------------------------------------------------------------------------------------ fidelity notes
_TRANSC = {"exp", "log", "log2", "log10", "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sinh", "cosh", "tanh",
           "asinh", "acosh", "atanh", "log1p", "expm1", "hypot", "pow"}
_BIGINT = {"factorial", "comb", "perm", "lcm", "gcd"}
_UNICODE = {"isnumeric", "isdecimal", "istitle", "casefold", "isascii"}


def lower_notes(lw, e: A.Node) -> None:
    from .lower import D_INTWIDTH, D_NEGINDEX, D_ASCII
    if isinstance(e, A.Call):
        f = e.func
        if f.startswith("math."):
            name = f[5:]
            if name in _TRANSC:
                lw.note(e, "D14 libm last-bit differences",
                        f"math.{name} calls the C library of the compiling toolchain; CPython calls its own platform's libm "
                        "(MSVC CRT on Windows). Results are correctly rounded for sqrt and exact cases, but may differ in the "
                        "last bit elsewhere, which would change a printed repr.",
                        "format results (e.g. f'{x:.6f}') when output must be bit-identical.", "guarded")
            if name in _BIGINT:
                lw.note(e, D_INTWIDTH,
                        f"math.{name} returns an arbitrary-precision int in CPython; the compiled result is int64.",
                        "a result beyond int64 raises OverflowError instead of returning a big int.", "guarded")
            if name in ("floor", "ceil", "trunc"):
                lw.note(e, D_INTWIDTH, f"math.{name} of a float beyond int64 range returns a big int in CPython.",
                        "raises OverflowError instead.", "guarded")
        elif f == "__slice":
            lw.note(e, D_NEGINDEX, "Python clamps out-of-range slice bounds and accepts negative bounds and steps.",
                    "bounds are normalised exactly as CPython's PySlice_AdjustIndices; step 0 raises ValueError.", "exact")
        elif f in ("pow", "int") and (f == "pow" or len(e.args) == 2):
            lw.note(e, D_INTWIDTH, f"{f}() on ints returns an arbitrary-precision int in CPython; the compiled result is "
                    "int64.", "a result beyond int64 raises OverflowError instead of returning a big int.", "guarded")
        elif f == "int" and e.args and e.args[0].ty == STR:
            lw.note(e, D_INTWIDTH, "int(str) of a number beyond int64 returns a big int in CPython.",
                    "raises OverflowError instead of ValueError/returning a big int.", "guarded")
    elif isinstance(e, A.MethodCall) and e.recv is not None and e.recv.ty == STR and e.method in _UNICODE:
        lw.note(e, D_ASCII, f"str.{e.method}() is Unicode-aware in CPython; compiled strings are ASCII bytes.",
                "identical for ASCII text.", "guarded")


def binop_notes(lw, n: A.Node, op: str, lt: Ty, rt: Ty) -> None:
    from .lower import D_INTWIDTH
    if op == "<<" and lt in (INT, BOOL):
        lw.note(n, D_INTWIDTH, "a << n is arbitrary precision in CPython; the compiled result is int64.",
                "a result beyond int64 raises OverflowError instead of returning a big int.", "guarded")
