"""Typed JSON codec for recorded call arguments / return values.

Wire format (JSON-safe, lossless for floats):
  None -> null          bool -> true/false     int -> JSON integer
  float -> {"f": "0x1.8p+1"}   (float.hex(): bitwise round trip; "inf"/"nan" ok)
  str -> JSON string    list -> JSON array
  dict -> {"d": [[k, v], ...]}   tuple -> {"tu": [...]}
Anything else (objects, sets, ...) raises Unencodable.  A size cap raises TooBig.

`same()` is the replay comparison: exact type, floats compared with
struct.pack('<d') (NaN == NaN by bits), containers recursively.
"""
from __future__ import annotations

import struct
from typing import Any

MAX_NODES = 20000       # total scalar+container nodes per encoded value
MAX_STR = 20000         # chars per string
MAX_DEPTH = 8


class Unencodable(Exception):
    pass


class TooBig(Exception):
    pass


def encode(v: Any, max_nodes: int = MAX_NODES) -> Any:
    budget = [max_nodes]

    def go(x, depth):
        budget[0] -= 1
        if budget[0] < 0:
            raise TooBig("value too large")
        if depth > MAX_DEPTH:
            raise TooBig("value too deep")
        t = type(x)
        if x is None or t is bool or t is int:
            return x
        if t is float:
            return {"f": x.hex()}
        if t is str:
            if len(x) > MAX_STR:
                raise TooBig("string too long")
            return x
        if t is list:
            return [go(e, depth + 1) for e in x]
        if t is tuple:
            return {"tu": [go(e, depth + 1) for e in x]}
        if t is dict:
            return {"d": [[go(k, depth + 1), go(e, depth + 1)] for k, e in x.items()]}
        raise Unencodable(f"cannot encode {t.__name__}")

    return go(v, 0)


def decode(e: Any) -> Any:
    if e is None or isinstance(e, (bool, int, str)):
        return e
    if isinstance(e, list):
        return [decode(x) for x in e]
    if isinstance(e, dict):
        if "f" in e:
            return float.fromhex(e["f"])
        if "d" in e:
            return {_hashable(decode(k)): decode(v) for k, v in e["d"]}
        if "tu" in e:
            return tuple(decode(x) for x in e["tu"])
    raise ValueError(f"bad encoded value: {e!r:.80}")


def _hashable(k):
    return tuple(_hashable(x) for x in k) if isinstance(k, list) else k


def _bits(f: float) -> bytes:
    return struct.pack("<d", f)


def same(a: Any, b: Any) -> bool:
    """Bitwise-faithful equality used by replay."""
    ta = type(a)
    if ta is not type(b):
        return False
    if ta is float:
        return _bits(a) == _bits(b)
    if ta is list or ta is tuple:
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    if ta is dict:
        # ponytail: dict order ignored (== semantics); compare ordered if iteration order starts to matter
        if len(a) != len(b):
            return False
        for k, v in a.items():
            if k not in b or not same(v, b[k]):
                return False
        return True
    return a == b


def display(v: Any, limit: int = 240) -> str:
    """repr-style rendering for counterexamples, truncated."""
    try:
        s = repr(v)
    except Exception as ex:                      # pragma: no cover
        s = f"<unrepr {type(v).__name__}: {ex}>"
    return s if len(s) <= limit else s[:limit - 1] + "…"


def display_args(args: list, limit: int = 240) -> str:
    s = ", ".join(display(a, limit) for a in args)
    return s if len(s) <= limit else s[:limit - 1] + "…"


# ---- observed-type descriptors (shared by the tracer and the synthesiser) ----
def tdesc(v: Any, depth: int = 0) -> str:
    t = type(v)
    if v is None:
        return "None"
    if t is bool:
        return "bool"
    if t is int or t is float or t is str:
        return t.__name__
    if depth > 3:
        return "object"
    if t is list:
        if not v:
            return "list[?]"
        sample = v if len(v) <= 12 else v[:6] + v[-6:]
        d = tdesc(sample[0], depth + 1)
        for e in sample[1:]:
            d = join_types(d, tdesc(e, depth + 1))
        return f"list[{d}]"
    if t is dict:
        if not v:
            return "dict[?,?]"
        items = list(v.items()) if len(v) <= 12 else list(v.items())[:6] + list(v.items())[-6:]
        k, e = tdesc(items[0][0], depth + 1), tdesc(items[0][1], depth + 1)
        for kk, vv in items[1:]:
            k, e = join_types(k, tdesc(kk, depth + 1)), join_types(e, tdesc(vv, depth + 1))
        return f"dict[{k},{e}]"
    if t is tuple:
        return "tuple[" + ",".join(tdesc(e, depth + 1) for e in v[:8]) + "]"
    return "object:" + t.__name__


def _split_args(inner: str):
    out, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
            continue
        depth += ch == "["
        depth -= ch == "]"
        cur += ch
    out.append(cur)
    return out


def join_types(a: str, b: str) -> str:
    """Join two observed type descriptors (int+float -> float, '?' is unknown)."""
    if a == b:
        return a
    for x, y in ((a, b), (b, a)):
        if x == "?":
            return y
    if {a, b} == {"int", "float"}:
        return "float"
    if {a, b} == {"bool", "int"}:
        return "int"
    for head in ("list", "dict", "tuple"):
        if a.startswith(head + "[") and b.startswith(head + "[") and a.endswith("]") and b.endswith("]"):
            pa, pb = _split_args(a[len(head) + 1:-1]), _split_args(b[len(head) + 1:-1])
            if len(pa) == len(pb):
                return f"{head}[" + ",".join(join_types(x, y) for x, y in zip(pa, pb)) + "]"
    parts = sorted(set(a.split("|")) | set(b.split("|")))
    return "|".join(parts)


# ---- input synthesis from type strings (no trace available) ----
def synthesize(param_types: list, n: int = 80, seed: int = 1234) -> list:
    """Small deterministic generator incl. edge cases; returns n lists of ENCODED args."""
    import random
    rng = random.Random(seed)
    ints = [0, 1, -1, 2, 3, 5, 10, -7, 25]
    floats = [0.0, 1.0, -1.0, 0.5, -2.5, 3.14159, 100.0, 1e-3]
    alpha = "abcxyz ABC019_-"

    def gen(t: str, edge: int, depth: int = 0):
        t = t.strip()
        if t == "int":
            return 0 if edge == 1 else rng.choice(ints) if rng.random() < .5 else rng.randint(-20, 60)
        if t == "float":
            return 0.0 if edge == 1 else rng.choice(floats) if rng.random() < .4 else round(rng.uniform(-10, 10), 3)
        if t == "bool":
            return rng.random() < .5
        if t == "str":
            return "" if edge == 1 else "".join(rng.choice(alpha) for _ in range(rng.randint(0, 10)))
        if t.startswith("list[") and t.endswith("]"):
            inner = t[5:-1]
            k = 0 if edge == 1 else rng.choice([0, 1, 1, 2, 3, 5, 8, 8, 13]) if depth == 0 else rng.randint(0, 5)
            return [gen(inner, 0, depth + 1) for _ in range(k)]
        if t.startswith("dict[") and t.endswith("]"):
            kt, vt = _split_args(t[5:-1])
            k = 0 if edge == 1 else rng.randint(0, 5)
            out = {}
            for _ in range(k):
                out[gen(kt, 0, depth + 1)] = gen(vt, 0, depth + 1)
            return out
        raise Unencodable(f"cannot synthesise {t}")

    calls = []
    for i in range(n):
        try:
            calls.append([encode(gen(t, 1 if i == 0 else 0)) for t in param_types])
        except TooBig:
            continue
    return calls
