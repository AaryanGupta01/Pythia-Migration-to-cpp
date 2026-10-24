#!/usr/bin/env python3
"""print() inside a compiled function must interleave with the surrounding Python prints exactly as in CPython, even when
stdout is a pipe (same buffer, same newline translation).  Builds a library module, runs one script twice (plain Python and
with the compiled function) with stdout captured, and compares the bytes.   Usage: python scripts/check_print.py"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pythia.libmode import build_library  # noqa: E402

SRC = '''def loud(n: int) -> int:
    total = 0
    for i in range(n):
        total += i
        print("step", i, total)
    return total
'''
DRIVER = '''import sys
sys.path.insert(0, {lib!r})
print("before")
{imp}
print("result", loud(3))
print("after")
'''
with tempfile.TemporaryDirectory() as td:
    r = build_library(SRC, ["loud"], td, modname="print_lib", filename="print_lib.py")
    assert r.ok, r.error or r.diagnostics
    pure = Path(td, "pure.py")
    pure.write_text(SRC + DRIVER.format(lib=td, imp=""), encoding="utf-8")
    comp = Path(td, "comp.py")
    comp.write_text(DRIVER.format(lib=os.path.dirname(r.so_path), imp="from print_lib import loud"), encoding="utf-8")
    a = subprocess.run([sys.executable, str(pure)], capture_output=True).stdout
    b = subprocess.run([sys.executable, str(comp)], capture_output=True).stdout
    assert a == b, f"stdout differs:\n{a!r}\n{b!r}"
    print(f"print inside a compiled function matches CPython byte for byte ({len(a)} bytes, piped stdout)")
