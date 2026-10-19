"""The type lattice of the in-house converter.

A type is None (nothing known yet), a scalar name, or a tuple:
  'int' 'float' 'bool' 'str' 'None'
  'num'                  an int on some paths and a float on others (renders as float; unsafe to print)
  ('list', T) ('set', T) ('iter', T) ('dict', K, V) ('tuple', (T1, ...)) ('opt', T)
  ('cls', Name)          an instance of a user class
  ('rec', rid)           a dict used as a record; becomes a synthesized class
  ('clsref', Name) ('fn', qual) ('mod', name) ('range',) ('lambda',)   values that never get annotated
  ('bad', why)           incompatible evidence; absorbing
"""
from __future__ import annotations

from typing import Callable, Optional

NUMERIC = ("bool", "int", "float", "num")
MAX_DEPTH = 5
CONTAINERS = ("list", "set", "iter")


def bad(why: str):
    return ("bad", why)


def is_bad(t) -> bool:
    return isinstance(t, tuple) and t[0] == "bad"


def depth(t) -> int:
    if not isinstance(t, tuple):
        return 0
    if t[0] in CONTAINERS or t[0] == "opt":
        return 1 + depth(t[1])
    if t[0] == "dict":
        return 1 + max(depth(t[1]), depth(t[2]))
    if t[0] == "tuple":
        return 1 + max((depth(x) for x in t[1]), default=0)
    return 0


def join(a, b):
    """Least upper bound of two pieces of evidence."""
    if a is None:
        return b
    if b is None or a == b:
        return a
    if is_bad(a):
        return a
    if is_bad(b):
        return b
    if a == "None" or b == "None":
        o = b if a == "None" else a
        return o if isinstance(o, tuple) and o[0] == "opt" else ("opt", o)
    if isinstance(a, tuple) and a[0] == "opt" or isinstance(b, tuple) and b[0] == "opt":
        ua = a[1] if isinstance(a, tuple) and a[0] == "opt" else a
        ub = b[1] if isinstance(b, tuple) and b[0] == "opt" else b
        j = join(ua, ub)
        return j if is_bad(j) else ("opt", j)
    if {a, b} <= {"int", "float", "num"}:
        return "num"
    if isinstance(a, tuple) and isinstance(b, tuple) and a[0] == b[0]:
        k = a[0]
        if k in CONTAINERS:
            r = (k, join(a[1], b[1]))
        elif k == "dict":
            r = (k, join(a[1], b[1]), join(a[2], b[2]))
        elif k == "tuple" and len(a[1]) == len(b[1]):
            r = (k, tuple(join(x, y) for x, y in zip(a[1], b[1])))
        else:
            r = None
        if r is not None:
            for part in _parts(r):
                if is_bad(part):
                    return part
            return r if depth(r) <= MAX_DEPTH else bad("a container nested too deeply")
    return bad(f"{show(a)} and {show(b)}")


def _parts(t):
    if t[0] in CONTAINERS:
        return [t[1]]
    if t[0] == "dict":
        return [t[1], t[2]]
    return list(t[1])


def elem(t):
    """What iterating over a value of type t yields."""
    if t is None:
        return None
    if t == "str":
        return "str"
    if isinstance(t, tuple):
        if t[0] in CONTAINERS:
            return t[1]
        if t[0] == "dict":
            return t[1]
        if t[0] == "range":
            return "int"
        if t[0] == "tuple":
            r = None
            for x in t[1]:
                r = join(r, x)
            return r
        if t[0] == "bad":
            return t
    return None


def contains(t, pred: Callable) -> bool:
    if pred(t):
        return True
    if not isinstance(t, tuple):
        return False
    if t[0] in CONTAINERS or t[0] == "opt":
        return contains(t[1], pred)
    if t[0] == "dict":
        return contains(t[1], pred) or contains(t[2], pred)
    if t[0] == "tuple":
        return any(contains(x, pred) for x in t[1])
    return False


def complete(t) -> bool:
    """No unknown part left."""
    if t is None:
        return False
    if not isinstance(t, tuple):
        return True
    if t[0] in CONTAINERS or t[0] == "opt":
        return complete(t[1])
    if t[0] == "dict":
        return complete(t[1]) and complete(t[2])
    if t[0] == "tuple":
        return all(complete(x) for x in t[1])
    return t[0] != "bad"


def render(t, rec_name: Callable[[object], str] = lambda r: "Record", optional: str = "Optional[{}]") -> Optional[str]:
    """Annotation text, or None if the type can't be written down."""
    if t is None:
        return None
    if t in ("num", "float_sentinel"):
        return "float"
    if isinstance(t, str):
        return t
    k = t[0]
    if k in ("list", "set"):
        e = render(t[1], rec_name, optional)
        return e and f"{k}[{e}]"
    if k == "dict":
        a, b = render(t[1], rec_name, optional), render(t[2], rec_name, optional)
        return a and b and f"dict[{a}, {b}]"
    if k == "tuple":
        parts = [render(x, rec_name, optional) for x in t[1]]
        return None if not parts or None in parts else f"tuple[{', '.join(parts)}]"
    if k == "opt":
        e = render(t[1], rec_name, optional)
        return e and optional.format(e)
    if k == "cls":
        return t[1]
    if k == "rec":
        return rec_name(t[1])
    return None


def show(t) -> str:
    """Human-readable, for messages."""
    if t is None:
        return "unknown"
    if t == "num":
        return "int or float"
    if t == "float_sentinel":
        return "float"
    if isinstance(t, tuple):
        if t[0] == "bad":
            return "conflicting types"
        if t[0] == "rec":
            return "record dict"
        if t[0] == "iter":
            return f"iterator of {show(t[1])}"
        if t[0] in ("fn", "clsref", "mod", "range", "lambda"):
            return {"fn": "function", "clsref": "class", "mod": "module", "range": "range", "lambda": "lambda"}[t[0]]
    r = render(t, lambda rid: "record")
    return r or "unknown"


if __name__ == "__main__":
    assert join("int", "float") == "num" and join("num", "int") == "num"
    assert join(("list", None), ("list", "int")) == ("list", "int")
    assert join("None", ("cls", "A")) == ("opt", ("cls", "A"))
    assert is_bad(join("str", "int"))
    assert render(("dict", "str", ("list", ("tuple", ("int", "str"))))) == "dict[str, list[tuple[int, str]]]"
    print("ok")
