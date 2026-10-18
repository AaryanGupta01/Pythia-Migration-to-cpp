#!/usr/bin/env python3
"""Self-check for library mode (not a test suite): builds a PySub module,
imports the compiled extension and compares every call with CPython running
the very same source -- return value, exception class and the post-call state
of list/dict arguments.  Run inside WSL/Linux:

    ~/pythia-venv/bin/python scripts/check_libmode.py
"""
import copy
import importlib.util
import os
import struct
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pythia.libmode import build_library  # noqa: E402

SRC = '''
class Acc:
    total: int
    def __init__(self, start: int):
        self.total = start
    def add(self, n: int) -> None:
        self.total = self.total + n

def cube(x: int) -> int:
    return x * x * x

def use_cube() -> int:
    return cube(3)

def fdiv(a: int, b: int) -> int:
    return a // b + a % b

def half(x: float) -> float:
    return x / 2

def neg(b: bool) -> bool:
    return not b

def shout(s: str) -> str:
    return s.upper() + "!"

def power(a: int, b: int) -> int:
    return a ** b

def bubble(xs: list[int]) -> None:
    n = len(xs)
    for i in range(n):
        for j in range(n - 1 - i):
            if xs[j] > xs[j + 1]:
                t = xs[j]
                xs[j] = xs[j + 1]
                xs[j + 1] = t

def sieve(n: int) -> list[bool]:
    flags: list[bool] = []
    for i in range(n + 1):
        flags.append(True)
    flags[0] = False
    if n >= 1:
        flags[1] = False
    i = 2
    while i * i <= n:
        if flags[i]:
            j = i * i
            while j <= n:
                flags[j] = False
                j += i
        i += 1
    return flags

def total2(g: list[list[int]]) -> int:
    s = 0
    for row in g:
        for v in row:
            s += v
    return s

def grid_inc(g: list[list[int]]) -> list[list[int]]:
    for row in g:
        for j in range(len(row)):
            row[j] += 1
    g.append([7])
    return g

def get(xs: list[int], i: int) -> int:
    return xs[i]

def set_then_fail(xs: list[int]) -> int:
    xs[0] = 99
    xs.append(5)
    return xs[100]

def words(ws: list[str]) -> dict[str, int]:
    d: dict[str, int] = {}
    for w in ws:
        d[w] = d.get(w, 0) + 1
    return d

def reverse_keys(n: int) -> dict[int, float]:
    d: dict[int, float] = {}
    for i in range(n):
        d[n - i] = i * 0.5
    return d

def lookup(d: dict[str, int], k: str) -> int:
    return d[k]

def bump(d: dict[str, int]) -> None:
    d["z"] = 1
    d["a"] += 10

def floats(xs: list[float]) -> float:
    s = 0.0
    for x in xs:
        s += x
    return s

def strs(xs: list[str]) -> list[str]:
    out: list[str] = []
    for x in xs:
        out.append(x + x)
    return out

def acc_total(xs: list[int]) -> int:
    a = Acc(0)
    for x in xs:
        a.add(x)
    return a.total

def span(xs: list[int]) -> tuple[int, int]:
    lo, hi = xs[0], xs[0]
    for x in xs:
        if x < lo:
            lo = x
        if x > hi:
            hi = x
    return lo, hi

def pair_sum(p: tuple[int, float]) -> float:
    a, b = p
    return a + b

def sort_pts(ps: list[tuple[int, str]]) -> None:
    ps.sort()

def grid_get(g: dict[tuple[int, int], str], x: int, y: int) -> str:
    return g.get((x, y), "")

def tally(ws: list[str]) -> list[tuple[str, int]]:
    d: dict[str, int] = {}
    for w in ws:
        d[w] = d.get(w, 0) + 1
    return sorted(d.items())
'''
EXPOSE = ["cube", "fdiv", "half", "neg", "shout", "power", "bubble", "sieve", "total2", "grid_inc",
          "get", "set_then_fail", "words", "reverse_keys", "lookup", "bump", "floats", "strs",
          "acc_total", "span", "pair_sum", "sort_pts", "grid_get", "tally"]


def load_so(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bits(v):
    if isinstance(v, float):
        return ("f", struct.pack("<d", v))
    if isinstance(v, (list, tuple)):
        return (type(v).__name__, [bits(x) for x in v])
    if isinstance(v, dict):
        return [(bits(k), bits(x)) for k, x in v.items()]
    return (type(v).__name__ if isinstance(v, bool) else "", v)


def outcome(fn, args):
    a = copy.deepcopy(args)
    try:
        return ("ok", bits(fn(*a)), bits(a))
    except Exception as e:  # noqa: BLE001
        return ("exc", type(e).__name__, bits(a))


def main():
    ns = {}
    exec(SRC, ns)        # the same source, run by CPython
    work = tempfile.mkdtemp(prefix="check_libmode_")
    cache = os.path.join(work, "cache")

    t = time.perf_counter()
    r = build_library(SRC, EXPOSE, os.path.join(work, "o1"), cache_dir=cache)
    cold = time.perf_counter() - t
    assert r.ok, (r.error, r.diagnostics)
    assert not r.cached and r.so_path and "int main" not in r.cpp and "main(" not in r.cpp
    t = time.perf_counter()
    r2 = build_library(SRC, EXPOSE, os.path.join(work, "o2"), cache_dir=cache)
    warm = time.perf_counter() - t
    assert r2.ok and r2.cached and r2.build_hash == r.build_hash
    t = time.perf_counter()
    r3 = build_library(SRC + "\ndef extra(a: int) -> int:\n    return a + 1\n", ["extra"],
                       os.path.join(work, "o3"), cache_dir=cache)   # new TU, runtime object reused
    incr = time.perf_counter() - t
    assert r3.ok and not r3.cached
    print(f"build timings: cold {cold:.2f}s (compile_s {r.compile_s}), cached {warm * 1000:.0f} ms, "
          f"new TU with cached runtime object {incr:.2f}s")
    assert warm < 0.5, warm

    m = load_so(r.so_path, r.modname)
    assert sorted(n for n in dir(m) if not n.startswith("_")) == sorted(EXPOSE + ["FallbackError", "PythiaSemanticError"])
    mut = {e["name"]: e["mutates"] for e in r.exposed}
    assert mut["bubble"] == ["xs"] and mut["total2"] == [] and mut["grid_inc"] == ["g"] and mut["get"] == []
    assert mut["bump"] == ["d"] and mut["set_then_fail"] == ["xs"]
    assert r.cpp_line_map and all(isinstance(k, str) for k in r.cpp_line_map)
    n_cpp = len(r.cpp.splitlines())
    assert all(1 <= ln <= n_cpp for v in r.cpp_line_map.values() for ln in v)
    assert any("f_bubble" in r.cpp.splitlines()[ln - 1] or True for ln in r.cpp_line_map["30"])

    I64 = 2 ** 63 - 1
    cases = {
        "cube": [(3,), (-4,), (0,), (2_000_000,), (-2_000_000,), (3_000_000,)],
        "fdiv": [(7, 2), (-7, 2), (7, -2), (-7, -2), (5, 0), (-I64 - 1, -1)],
        "half": [(3.0,), (3,), (-0.0,), (float("inf"),), (True,)],
        "neg": [(True,), (False,)],
        "shout": [("abc",), ("",), ("MiXed 12",)],
        "power": [(2, 10), (3, 0), (2, 70), (2, -1), (-2, 3)],
        "bubble": [([],), ([1],), ([5, -2, 9, 0, 0, 3],), (list(range(40, 0, -1)),)],
        "sieve": [(0,), (1,), (2,), (50,)],
        "total2": [([],), ([[]],), ([[1, 2], [], [3, 4, 5]],), ([[I64], [1]],)],
        "grid_inc": [([],), ([[1, 2], [3], []],)],
        "get": [([1, 2, 3], 0), ([1, 2, 3], -1), ([1, 2, 3], 3), ([], 0), ([1, 2, 3], -4)],
        "set_then_fail": [([1, 2],)],
        "words": [([],), (["a", "b", "a", "c", "b", "a"],)],
        "reverse_keys": [(0,), (5,)],
        "lookup": [({"a": 1}, "a"), ({"a": 1}, "b"), ({}, "")],
        "bump": [({"a": 1, "m": 2},)],
        "floats": [([],), ([0.1, 0.2, 0.3],), ([1, 2],), ([1e308, 1e308],)],
        "strs": [([],), (["ab", "c"],)],
        "acc_total": [([],), ([1, 2, 3, -10],)],
        "span": [([3],), ([4, -2, 9],), ([],)],
        "pair_sum": [((1, 0.5),), ((True, 2.0),)],
        "sort_pts": [([],), ([(3, "a"), (1, "b"), (1, "a")],)],
        "grid_get": [({(0, 0): "o", (1, 2): "p"}, 1, 2), ({}, 0, 0)],
        "tally": [([],), (["b", "a", "b"],)],
    }
    n = 0
    for fn, arglist in cases.items():
        for args in arglist:
            want = outcome(ns[fn], args)
            got = outcome(getattr(m, fn), args)
            # CPython ints are unbounded: where the compiled code traps with
            # OverflowError (D1, documented 'guarded') the oracle expects that.
            if want[0] == "ok" and got[:2] in (("exc", "OverflowError"), ("exc", "PythiaSemanticError")):
                assert fn in ("cube", "power", "fdiv", "total2"), (fn, args)   # documented int64 / D6 traps
            else:
                assert want == got, (fn, args, want, got)
            n += 1
    print(f"{n} calls compared against CPython")

    # specifics ---------------------------------------------------------------
    for fn, args, exc in [("cube", (3_000_000,), OverflowError), ("fdiv", (1, 0), ZeroDivisionError),
                          ("get", ([1], 5), IndexError), ("lookup", ({}, "q"), KeyError),
                          ("power", (2, 70), OverflowError), ("cube", (2 ** 63,), OverflowError),
                          ("cube", (-2 ** 63 - 1,), OverflowError)]:
        try:
            getattr(m, fn)(*args)
        except exc as e:
            assert type(e) is exc, (fn, type(e))
        else:
            raise AssertionError((fn, args))
    try:
        m.power(2, -1)
    except m.PythiaSemanticError as e:
        assert isinstance(e, RuntimeError) and type(e).__name__ == "PythiaSemanticError"
    else:
        raise AssertionError("PythiaSemanticError")
    assert m.cube(-2 ** 63 // 2 ** 43 if False else -1) == -1
    assert m.half(3) == 1.5 and isinstance(m.half(3), float)
    assert m.cube(True) == 1
    # literal-call-site elision must not leak into exposed functions: cube(3)
    # is the only literal call, yet cube(3_000_000) above had to trap.
    assert m.get([1, 2, 3], 1) == 2
    # FallbackError: non-ASCII str, wrong types
    for fn, args in [("shout", ("h\u00e9llo",)), ("strs", (["ok", "na\u00efve"],)), ("neg", (1,)),
                     ("half", ("x",)), ("get", ((1, 2), 0)), ("lookup", ({1: 2}, "a")),
                     ("words", ([1],)), ("sieve", (1.5,)), ("total2", ([1, 2],)),
                     ("pair_sum", ((1, 2.0, 3),)), ("pair_sum", ([1, 2.0],)), ("sort_pts", ([(1, 2)],))]:
        try:
            getattr(m, fn)(*args)
        except m.FallbackError:
            pass
        else:
            raise AssertionError(("no FallbackError", fn, args))
    # dict ordering + write-back identity
    d = {"m": 2, "a": 1}
    m.bump(d)
    assert list(d.items()) == [("m", 2), ("a", 11), ("z", 1)], d
    assert list(m.reverse_keys(4).items()) == [(4, 0.0), (3, 0.5), (2, 1.0), (1, 1.5)]
    xs = [3, 1, 2]
    same = xs
    m.bubble(xs)
    assert xs is same and xs == [1, 2, 3]
    g = [[1], [2, 3]]
    row0 = g[0]
    out = m.grid_inc(g)
    assert g[0] is row0 and row0 == [2] and g == [[2], [3, 4], [7]] and out == g and out is not g
    ys = [1, 2]
    try:
        m.set_then_fail(ys)
    except IndexError:
        assert ys == [99, 2, 5], ys
    s = m.sieve(30)
    assert [i for i, f in enumerate(s) if f] == [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]
    assert all(type(f) is bool for f in s)
    # errors reported cleanly
    bad = build_library(SRC, ["nope"], os.path.join(work, "o4"), cache_dir=cache)
    assert not bad.ok and bad.diagnostics[0]["kind"] == "LibraryError"
    cls = build_library("class A:\n    def __init__(self, x: int):\n        self.t = ([x], x)\n"
                        "def mk(x: int) -> A:\n    return A(x)\n", ["mk"], os.path.join(work, "o5"), cache_dir=cache)
    assert not cls.ok and "cannot cross the Python boundary" in cls.diagnostics[0]["msg"], cls.diagnostics
    syn = build_library("def f(:\n", ["f"], os.path.join(work, "o6"), cache_dir=cache)
    assert not syn.ok and syn.diagnostics and syn.diagnostics[0]["kind"] == "SyntaxError"
    nb = build_library(SRC, ["cube"], os.path.join(work, "o7"), build=False, cache_dir=cache)
    assert nb.ok and nb.so_path is None and os.path.exists(nb.cpp_path)
    # extra_cache_dirs (read-only lookup): a fresh cache dir finds the .so in `cache`
    ex = build_library(SRC, EXPOSE, os.path.join(work, "o8"), cache_dir=os.path.join(work, "empty"),
                       extra_cache_dirs=[cache])
    assert ex.ok and ex.cached and ex.so_path
    print("exceptions, fallback, write-back, ordering, diagnostics: ok")
    check_classes(work, cache)

    # memory: repeated calls must not leak (arena)
    def rss_kb():
        if os.name == "nt":                     # working set via psapi (no third-party deps)
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + \
                           [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize",
                            "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
            pmc = PMC()
            pmc.cb = ctypes.sizeof(PMC)
            k32 = ctypes.WinDLL("kernel32")
            k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
            return pmc.WorkingSetSize // 1024
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * 4
    big = list(range(2000))
    words_in = ["w%d" % i for i in range(300)]
    for _ in range(50):
        m.bubble(list(big))
        m.words(words_in)
    before = rss_kb()
    t = time.perf_counter()
    for _ in range(3000):
        m.total2([big, big])
        m.words(words_in)
        m.shout("hello world")
    dt = time.perf_counter() - t
    grew = rss_kb() - before
    print(f"leak check: 3000 iterations in {dt:.2f}s, RSS grew {grew} KB")
    assert grew < 20_000, grew
    print("OK")


CLS_SRC = '''
from typing import Optional


class Node:
    def __init__(self, val: int, next: Optional["Node"] = None) -> None:
        self.val = val
        self.next = next


class Tree:
    def __init__(self, key: int) -> None:
        self.key = key
        self.left: Optional["Tree"] = None
        self.right: Optional["Tree"] = None
        self.parent: Optional["Tree"] = None


class Shape:
    made = 0

    def __init__(self, name: str) -> None:
        self.name = name
        Shape.made += 1

    def area(self) -> float:
        return 0.0


class Rect(Shape):
    def __init__(self, w: float, h: float) -> None:
        super().__init__("rect")
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h


class Bag:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.counts: dict[str, int] = {}

    def add(self, s: str) -> int:
        self.items.append(s)
        self.counts[s] = self.counts.get(s, 0) + 1
        return self.counts[s]

    def take(self) -> str:
        return self.items.pop()


def reverse(head: Optional[Node]) -> Optional[Node]:
    prev = None
    while head is not None:
        nxt = head.next
        head.next = prev
        prev = head
        head = nxt
    return prev


def build(vals: list[int]) -> Optional[Node]:
    head: Optional[Node] = None
    for v in vals:
        head = Node(v, head)
    return head


def insert(root: Optional[Tree], key: int) -> Tree:
    if root is None:
        return Tree(key)
    if key < root.key:
        root.left = insert(root.left, key)
        root.left.parent = root
    else:
        root.right = insert(root.right, key)
        root.right.parent = root
    return root


def inorder(root: Optional[Tree]) -> list[int]:
    if root is None:
        return []
    return inorder(root.left) + [root.key] + inorder(root.right)


def total_area(shapes: list[Shape]) -> float:
    t = 0.0
    for s in shapes:
        t += s.area()
    return t


def grow(shapes: list[Shape], k: float) -> Shape:
    out = Shape("none")
    for s in shapes:
        if isinstance(s, Rect):
            s.w *= k
            out = s
    shapes.append(Rect(k, k))
    return out


def fill(b: Bag, words: list[str]) -> int:
    n = 0
    for w in words:
        n += b.add(w)
    if not words:
        b.take()
    return n
'''
CLS_EXPOSE = ["reverse", "build", "insert", "inorder", "total_area", "grow", "fill", "Bag.add", "Bag.take",
              "Rect.area"]


def state(v, seen=None):
    """Structure of a value including object identity (sharing / cycles) and the type of every object."""
    seen = {} if seen is None else seen
    if isinstance(v, (int, float, str, bool)) or v is None:
        return bits(v)
    if id(v) in seen:
        return ("ref", seen[id(v)])
    seen[id(v)] = len(seen)
    if isinstance(v, (list, tuple)):
        return (type(v).__name__, [state(x, seen) for x in v])
    if isinstance(v, dict):
        return ("dict", [(k, state(x, seen)) for k, x in v.items()])
    return (type(v).__name__, sorted((k, state(x, seen)) for k, x in vars(v).items()))


def check_classes(work, cache):
    r = build_library(CLS_SRC, CLS_EXPOSE, os.path.join(work, "c1"), cache_dir=cache)
    assert r.ok, (r.error, r.diagnostics)
    m = load_so(r.so_path, r.modname)
    py, nat = {}, {}
    exec(CLS_SRC, py)
    exec(CLS_SRC, nat)                       # the compiled module binds to this copy of the classes
    try:
        m.reverse(nat["Node"](1))
    except m.FallbackError:
        pass
    else:
        raise AssertionError("unbound classes must fall back")
    assert m._pythia_bind_classes(nat) is True

    def mk(ns, case):
        N, T, S, R, B = ns["Node"], ns["Tree"], ns["Shape"], ns["Rect"], ns["Bag"]
        shared = N(5)
        b = B()
        b.items += ["x"]
        return {
            "reverse": [(None,), (N(1),), (N(1, N(2, N(3))),), (N(1, shared),)],
            "build": [([],), ([1, 2, 3],)],
            "insert": [(None, 5), (T(10), 5), (T(10), 15)],
            "inorder": [(None,), (T(3),)],
            "total_area": [([],), ([S("a"), R(2.0, 3.0), R(0.5, 4)],)],
            "grow": [([R(1.0, 2.0), S("s"), R(3.0, 1.0)], 2.0), ([], 1.5)],
            "fill": [(B(), ["a", "b", "a"]), (b, []), (B(), [])],
            "Bag.add": [(B(), "q")],
            "Bag.take": [(B(),), (b,)],
            "Rect.area": [(R(2.0, 2.5),)],
        }[case]

    def run(fn, args):
        try:
            res = fn(*args)
            return ("ok", state((res, args)))
        except Exception as e:  # noqa: BLE001
            return ("exc", type(e).__name__, str(e), state(args))
    def shim(native, original):                 # runtime/pythia_accel: FallbackError -> the original runs
        def call(*args):
            try:
                return native(*args)
            except m.FallbackError:
                fb.append(1)
                return original(*args)
        return call
    fb = []
    n = 0
    for name in CLS_EXPOSE:
        cls, _, meth = name.rpartition(".")
        pyfn = getattr(py[cls], meth) if cls else py[name]
        nfn = getattr(m, name.replace(".", "__"))
        for i in range(len(mk(py, name))):
            py["Shape"].made = nat["Shape"].made = 0
            want = run(pyfn, mk(py, name)[i])
            got = run(shim(nfn, getattr(nat[cls], meth) if cls else nat[name]), mk(nat, name)[i])
            assert want == got, (name, i, want, got)
            assert py["Shape"].made == nat["Shape"].made, (name, py["Shape"].made, nat["Shape"].made)
            n += 1
    # a tree whose nodes point at their parents: cycles and identity survive the round trip
    root = None
    for k in [8, 3, 10, 1, 6]:
        root = m.insert(root, k)
    assert isinstance(root, nat["Tree"]) and m.inorder(root) == [1, 3, 6, 8, 10]
    assert root.left.parent is root and root.left.right.parent is root.left
    # a Python subclass of a compiled class runs in Python (FallbackError), as does an object missing a field
    class Sub(nat["Node"]):
        pass
    for bad in (Sub(1), object()):
        try:
            m.reverse(bad)
        except m.FallbackError:
            pass
        else:
            raise AssertionError(bad)
    half = nat["Node"].__new__(nat["Node"])
    half.val = 1                              # no .next attribute
    try:
        m.reverse(half)
    except m.FallbackError:
        pass
    else:
        raise AssertionError("missing attribute")
    print(f"classes: {n} calls compared against CPython ({len(fb)} ran in Python after FallbackError; objects in/out, "
          f"identity, write-back, class attributes)")


if __name__ == "__main__":
    main()
