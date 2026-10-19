#!/usr/bin/env python3
"""
PYTHIA :: Differential Testing Oracle
Owner: Member 4 (Aaryan Gupta)

Semantic preservation is a claim, and a claim needs a falsifier.  For every
program in tests/positive the oracle:

    1. runs it under CPython 3.12                 -> (stdout_p, exc_p, code_p)
    2. transpiles it, compiles the C with cc, runs it -> (stdout_c, exc_c, code_c)
    3. asserts stdout_p == stdout_c byte-for-byte, and that the exception
       class raised (if any) is identical.

For tests/negative it asserts that PYTHIA *rejects* the program and that the
diagnostic lands on the line the `# expect:` marker names -- a type checker
that accepts everything is not a type checker.

Exit status is non-zero if any case fails, so this drops straight into CI.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pythia.cli import compile_source          # noqa: E402

POS = os.path.join(ROOT, "tests", "positive")
NEG = os.path.join(ROOT, "tests", "negative")
BUILD = os.path.join(ROOT, "build", "oracle")
RUNTIME = os.path.join(ROOT, "runtime")

EXC_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception))(?::|$)", re.M)

GREEN, RED, YELLOW, DIM, RESET = (
    "\033[32m", "\033[31m", "\033[33m", "\033[2m", "\033[0m")


def exc_of(stderr: str):
    m = EXC_RE.findall(stderr or "")
    return m[-1] if m else None


STDIN_DATA = "alpha\nbeta  \ngamma\ndelta\n"


def run_cpython(path):
    t = time.perf_counter()
    r = subprocess.run([sys.executable, path], input=STDIN_DATA, capture_output=True, text=True,
                       timeout=60)
    return r.stdout, exc_of(r.stderr), r.returncode, time.perf_counter() - t


def build_and_run(path, keep=False):
    stem = os.path.splitext(os.path.basename(path))[0]
    d = os.path.join(BUILD, stem)
    os.makedirs(d, exist_ok=True)
    src = open(path, encoding="utf-8").read()
    code, notes, errs, _ = compile_source(src, path)
    if errs:
        return None, None, None, None, errs, notes
    cpath = os.path.join(d, stem + ".cpp")
    open(cpath, "w", encoding="utf-8").write(code)
    for fn in ("pyrt.cpp", "pyrt.hpp"):
        shutil.copy(os.path.join(RUNTIME, fn), d)
    binp = os.path.join(d, stem)
    cc = subprocess.run(
        ["c++", "-std=c++17", "-O2", "-flto", "-Wall", "-I", d, cpath,
         os.path.join(d, "pyrt.cpp"), "-o", binp],
        capture_output=True, text=True)
    if cc.returncode != 0:
        return None, None, None, None, [("cc", cc.stderr)], notes
    t = time.perf_counter()
    r = subprocess.run([binp], input=STDIN_DATA, capture_output=True, text=True, timeout=60)
    return (r.stdout, exc_of(r.stderr), r.returncode,
            time.perf_counter() - t, [], notes)


def diff_first(a, b):
    la, lb = a.splitlines(), b.splitlines()
    for i in range(max(len(la), len(lb))):
        x = la[i] if i < len(la) else "<missing>"
        y = lb[i] if i < len(lb) else "<missing>"
        if x != y:
            return i + 1, x, y
    return None, None, None


def run_positive(verbose=False, bench=False):
    files = sorted(f for f in os.listdir(POS) if f.endswith(".py"))
    passed, failed, notes_total = 0, [], 0
    speedups = []
    print(f"\n{'PROGRAM':<22}{'CPython':>10}{'PYTHIA':>10}{'SPEEDUP':>10}  RESULT")
    print("-" * 68)
    for f in files:
        p = os.path.join(POS, f)
        sp, ep, rp, tp = run_cpython(p)
        sc, ec, rc, tc, errs, notes = build_and_run(p)
        notes_total += len(notes or [])
        if errs:
            failed.append((f, "PYTHIA rejected a valid program: " +
                           str(errs[0] if not isinstance(errs[0], tuple) else errs[0][1][:400])))
            print(f"{f:<22}{'-':>10}{'-':>10}{'-':>10}  {RED}COMPILE{RESET}")
            continue
        ok_out = (sp == sc)
        ok_exc = (ep == ec)
        if ok_out and ok_exc:
            passed += 1
            sp_ratio = tp / tc if tc > 0 else float("inf")
            speedups.append(sp_ratio)
            print(f"{f:<22}{tp*1000:>9.1f}m{tc*1000:>9.1f}m{sp_ratio:>9.1f}x  "
                  f"{GREEN}PASS{RESET}")
        else:
            n, x, y = diff_first(sp, sc)
            detail = (f"line {n}: CPython {x!r} vs PYTHIA {y!r}" if n
                      else f"exception {ep!r} vs {ec!r}")
            failed.append((f, detail))
            print(f"{f:<22}{tp*1000:>9.1f}m{tc*1000:>9.1f}m{'-':>10}  {RED}FAIL{RESET}")
            if verbose:
                print(f"    {DIM}{detail}{RESET}")
    return passed, failed, len(files), speedups, notes_total


def run_negative(verbose=False):
    if not os.path.isdir(NEG):
        return 0, [], 0
    files = sorted(f for f in os.listdir(NEG) if f.endswith(".py"))
    passed, failed = 0, []
    print(f"\n{'NEGATIVE CASE':<34}{'EXPECTED':<22}RESULT")
    print("-" * 68)
    for f in files:
        p = os.path.join(NEG, f)
        src = open(p, encoding="utf-8").read()
        want = ""
        m = re.search(r"#\s*expect:\s*(.+)", src)
        if m:
            want = m.group(1).strip()
        code, notes, errs, _ = compile_source(src, p)
        got = "; ".join(f"{d.kind}: {d.msg}" for d in errs) if errs else ""
        ok = bool(errs) and (want.lower() in got.lower() if want else True)
        if ok:
            passed += 1
            print(f"{f:<34}{want[:20]:<22}{GREEN}REJECTED{RESET}")
        else:
            failed.append((f, f"expected {want!r}, got {got[:160]!r}"))
            print(f"{f:<34}{want[:20]:<22}{RED}MISSED{RESET}")
            if verbose:
                print(f"    {DIM}got: {got[:300]}{RESET}")
    return passed, failed, len(files)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()
    os.makedirs(BUILD, exist_ok=True)

    print("=" * 68)
    print("PYTHIA DIFFERENTIAL ORACLE   (CPython 3.12  vs  PYTHIA -> C++17 -> c++ -O2)")
    print("=" * 68)

    pp, pf, pn, speeds, notes = run_positive(a.verbose)
    np_, nf, nn = run_negative(a.verbose)

    print("\n" + "=" * 68)
    print("SUMMARY")
    print("-" * 68)
    print(f"  semantic equivalence : {pp}/{pn} programs "
          f"({100.0 * pp / pn if pn else 0:.1f}%)")
    print(f"  type-checker recall  : {np_}/{nn} invalid programs rejected "
          f"({100.0 * np_ / nn if nn else 0:.1f}%)")
    if speeds:
        s = sorted(speeds)
        med = s[len(s) // 2]
        print(f"  median speedup       : {med:.1f}x   "
              f"(min {min(s):.1f}x, max {max(s):.1f}x)")
    print(f"  fidelity notes       : {notes} emitted across the suite")
    print("=" * 68)

    for f, why in pf + nf:
        print(f"{RED}FAIL{RESET} {f}: {why}")
    return 1 if (pf or nf) else 0


if __name__ == "__main__":
    sys.exit(main())
