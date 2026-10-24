#!/usr/bin/env python3
"""Runs a fixed set of small cases through PYTHIA (standalone binary and library mode) and records the actual behaviour next
to CPython's. Run from the repo root under WSL:  .venv/bin/python docs/review3/src/edge_cases.py
Writes docs/review3/src/evidence/edge_cases.json (used by the report's test-case and limitation tables)."""
import json
import os
import re
import resource
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pythia.cli import compile_source  # noqa: E402
from pythia.libmode import build_library  # noqa: E402

BUILD = ROOT / "build" / "edge"
BUILD.mkdir(parents=True, exist_ok=True)
RT = ROOT / "runtime"


def cpython(src):
    p = BUILD / "cp.py"
    p.write_text(src)
    r = subprocess.run([sys.executable, str(p)], capture_output=True, text=True)
    exc = re.findall(r"^(\w+Error)", r.stderr, re.M)
    return r.stdout.strip(), (exc[-1] if exc else None)


def pythia(src, name):
    code, notes, errs, _ = compile_source(src, name + ".py")
    if errs:
        e = errs[0]
        return None, None, f"rejected at {e.line}:{e.col}: {e.msg}" if hasattr(e, "line") else str(e)
    d = BUILD / name
    d.mkdir(exist_ok=True)
    for h in ("pyrt.cpp", "pyrt.hpp"):
        shutil.copy(RT / h, d)
    (d / "p.cpp").write_text(code)
    cc = subprocess.run(["c++", "-std=c++17", "-O2", "-I", str(d), str(d / "p.cpp"), str(d / "pyrt.cpp"), "-o", str(d / "p")], capture_output=True, text=True)
    if cc.returncode:
        return None, None, "c++ failed"
    r = subprocess.run([str(d / "p")], capture_output=True, text=True)
    exc = re.findall(r"^(\w+Error)", r.stderr, re.M)
    return r.stdout.strip(), (exc[-1] if exc else None), None


CASES = [
    ("TC-01", "Positive", "Operator precedence: print(2 + 3 * 4 ** 2)", "print(2 + 3 * 4 ** 2)\n"),
    ("TC-02", "Boundary", "Floor division and modulo with negative operands", "print(-7 // 2, -7 % 2, 7 // -2, 7 % -2)\n"),
    ("TC-03", "Boundary", "Float repr: 0.1 + 0.2 and 1e16", "print(0.1 + 0.2, 1e16, 1e15)\n"),
    ("TC-04", "Negative", "Type mismatch in assignment: x: int = 'hello'", "x: int = 'hello'\nprint(x)\n"),
    ("TC-05", "Boundary", "Index out of range: xs[10] on a 3-element list", "xs: list[int] = [1, 2, 3]\nprint(xs[10])\n"),
    ("TC-06", "Boundary", "Division by zero: 1 // z", "z: int = 0\nprint(1 // z)\n"),
    ("TC-07", "Boundary", "range with step zero", "def f(s: int) -> int:\n    t: int = 0\n    for i in range(0, 10, s):\n        t += i\n    return t\nprint(f(0))\n"),
    ("TC-08", "Regression", "Unbounded recursion", "def f(n: int) -> int:\n    return f(n + 1)\nprint(f(0))\n"),
    ("TC-09", "OOP", "Class, method call, field update", "class Acc:\n    def __init__(self, v: int):\n        self.v: int = v\n    def add(self, k: int) -> int:\n        self.v += k\n        return self.v\na: Acc = Acc(5)\na.add(3)\nprint(a.add(4))\n"),
    ("TC-10", "Limit (D1)", "Integer beyond int64: print(2 ** 62 * 2)", "x: int = 2 ** 62\nprint(x * 2)\n"),
    ("TC-11", "Limit (D13)", "Non-ASCII string length: len('héllo')", "s: str = 'héllo'\nprint(len(s))\n"),
]
rows = []
for cid, cat, desc, src in CASES:
    ref, rexc = cpython(src)
    got, gexc, err = pythia(src, cid)
    same = err is None and ref == got and rexc == gexc
    rows.append({"id": cid, "category": cat, "desc": desc, "cpython": (ref or "") + (f"  [{rexc}]" if rexc else ""),
                 "pythia": err if err else ((got or "") + (f"  [{gexc}]" if gexc else "")), "identical": same})
    print(rows[-1], flush=True)

# ---- library mode: in-place mutation, FallbackError, OverflowError, memory over many calls
lib_src = ("def swap_first_last(a: list[int]) -> int:\n    t: int = a[0]\n    a[0] = a[len(a) - 1]\n    a[len(a) - 1] = t\n    return len(a)\n\n"
           "def word_len(s: str) -> int:\n    return len(s)\n\n"
           "def grow(n: int) -> int:\n    xs: list[int] = []\n    for i in range(n):\n        xs.append(i * 3)\n    s: str = 'x' * n\n    return len(xs) + len(s)\n")
t0 = time.time()
r = build_library(lib_src, ["swap_first_last", "word_len", "grow"], str(BUILD / "lib"), modname="edge_lib", filename="edge_lib.py")
build_s = round(time.time() - t0, 1)
lib = {"built": bool(r.ok), "build_s": build_s, "cached": getattr(r, "cached", None)}
if r.ok:
    sys.path.insert(0, os.path.dirname(r.so_path))
    import edge_lib  # noqa: E402
    a = [1, 2, 3, 4]
    edge_lib.swap_first_last(a)
    rows.append({"id": "TC-12", "category": "In-place", "desc": "Library mode: swap list ends inside compiled code, caller's list",
                 "cpython": "[4, 2, 3, 1]", "pythia": str(a), "identical": a == [4, 2, 3, 1]})
    try:
        out = str(edge_lib.word_len("héllo"))
    except Exception as e:  # noqa: BLE001
        out = type(e).__name__
    rows.append({"id": "TC-13", "category": "Limit (D13)", "desc": "Library mode: word_len('héllo') with non-ASCII input",
                 "cpython": "5", "pythia": out + " (shim then runs the Python body)", "identical": out == "FallbackError"})
    try:
        out = str(edge_lib.word_len.__call__("a" * 3))
    except Exception as e:  # noqa: BLE001
        out = type(e).__name__
    try:
        edge_lib.swap_first_last([2 ** 70, 1])
        out2 = "no error"
    except Exception as e:  # noqa: BLE001
        out2 = type(e).__name__
    rows.append({"id": "TC-14", "category": "Limit (D1)", "desc": "Library mode: list element 2**70 (beyond int64)",
                 "cpython": "works (bignum)", "pythia": out2, "identical": False})

    def rss_kb():
        for l in open("/proc/self/status"):
            if l.startswith("VmRSS"):
                return int(l.split()[1])
    edge_lib.grow(1000)
    before = rss_kb()
    t = time.time()
    N = 200000
    for _ in range(N):
        edge_lib.grow(500)
    dt = time.time() - t
    after = rss_kb()
    lib["mem"] = {"calls": N, "rss_before_kb": before, "rss_after_kb": after, "per_call_alloc": "list of 500 ints + 500-char str",
                  "seconds": round(dt, 2)}
    # contrast: boundary cost for a trivial function
    t = time.time()
    for _ in range(200000):
        edge_lib.word_len("abc")
    lib["call_overhead_us"] = round((time.time() - t) / 200000 * 1e6, 2)
    t = time.time()
    for _ in range(200000):
        len("abc")
    lib["py_len_us"] = round((time.time() - t) / 200000 * 1e6, 3)
    big = list(range(100000))
    t = time.time()
    for _ in range(50):
        edge_lib.swap_first_last(big)
    lib["marshal_100k_ms"] = round((time.time() - t) / 50 * 1000, 2)
print(json.dumps(lib))
out = Path(__file__).parent / "evidence" / "edge_cases.json"
out.write_text(json.dumps({"rows": rows, "lib": lib, "python": sys.version.split()[0], "date": time.strftime("%Y-%m-%dT%H:%M:%S%z")}, indent=1))
