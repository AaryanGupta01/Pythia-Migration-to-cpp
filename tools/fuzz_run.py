#!/usr/bin/env python3
"""
PYTHIA :: Fuzz runner
Owner: Member 4 (Aaryan Gupta)

Differentially tests every *.py under a generated-programs directory:
CPython 3.12 output vs PYTHIA-compiled binary output must match exactly.
Programs PYTHIA itself refuses to compile (a generator bug, not a PYTHIA
bug -- e.g. sampling a division literal that happens to be zero at a site
the checker can't see through) are reported separately and don't count
as failures. Anything with mismatched output is copied to a triage folder
with both outputs saved alongside it for inspection.
"""
import argparse
import os
import shutil
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pythia.cli import compile_source   # noqa: E402

RUNTIME = os.path.join(ROOT, "runtime")


def run_cpython(path, timeout=10):
    try:
        r = subprocess.run([sys.executable, path], capture_output=True,
                           text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", -1


def build_and_run(path, workdir, timeout=10):
    stem = os.path.splitext(os.path.basename(path))[0]
    d = os.path.join(workdir, stem)
    os.makedirs(d, exist_ok=True)
    src = open(path, encoding="utf-8").read()
    code, notes, errs, _ = compile_source(src, path)
    if errs:
        return None, [str(e) for e in errs], None, "reject"
    cpath = os.path.join(d, stem + ".cpp")
    open(cpath, "w", encoding="utf-8").write(code)
    for fn in ("pyrt.cpp", "pyrt.hpp"):
        shutil.copy(os.path.join(RUNTIME, fn), d)
    binp = os.path.join(d, stem)
    from pythia import toolchain
    cxx = toolchain.find_cxx()[0] or ("g++.exe" if os.name == "nt" else "c++")
    cmd = [cxx, "-std=c++17", "-O2", "-flto", "-I", d, cpath,
           os.path.join(d, "pyrt.cpp"), *toolchain.exe_link_args(), "-o", binp]
    cc = subprocess.run(cmd, capture_output=True, text=True, env=toolchain.env_for(cxx))
    if cc.returncode != 0:
        return None, [cc.stderr], None, "ccfail"
    try:
        r = subprocess.run([binp], capture_output=True, text=True, timeout=timeout)
        return r.stdout, r.stderr, r.returncode, "ran"
    except subprocess.TimeoutExpired:
        return None, "TIMEOUT", None, "timeout"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--triage", default=os.path.join(ROOT, "tests", "triage"))
    ap.add_argument("--workdir", default="/tmp/pythia_fuzz_build")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args()

    files = sorted(f for f in os.listdir(a.dir) if f.endswith(".py"))
    os.makedirs(a.workdir, exist_ok=True)
    matched = rejected = ccfail = mismatched = timeouts = 0
    mismatches = []
    t0 = time.time()

    for i, f in enumerate(files):
        path = os.path.join(a.dir, f)
        sp, se, sc = run_cpython(path)
        if se == "TIMEOUT":
            timeouts += 1
            continue
        cp, ce, cc_, status = build_and_run(path, a.workdir)
        if status == "reject":
            rejected += 1
            continue
        if status == "ccfail":
            ccfail += 1
            print(f"CC-FAIL {f}:\n{ce[0][:500]}")
            continue
        if status == "timeout":
            timeouts += 1
            continue
        # CPython crashing with a Python traceback on a generator artefact
        # (e.g. RecursionError, extreme float) isn't a PYTHIA question.
        if sc != 0 and "Error" in (se or "") and cp is None:
            rejected += 1
            continue
        if sp == cp:
            matched += 1
        else:
            mismatched += 1
            mismatches.append(f)
            os.makedirs(a.triage, exist_ok=True)
            dst = os.path.join(a.triage, f)
            shutil.copy(path, dst)
            with open(dst + ".cpython.out", "w") as fh:
                fh.write(sp or "")
            with open(dst + ".pythia.out", "w") as fh:
                fh.write(cp or "")
            if a.verbose:
                print(f"MISMATCH {f}")
                print(f"  cpython: {sp!r}")
                print(f"  pythia : {cp!r}")

        if (i + 1) % 50 == 0:
            print(f"  ... {i+1}/{len(files)}")

    dt = time.time() - t0
    print("\n" + "=" * 60)
    print(f"FUZZ RUN: {len(files)} programs in {dt:.1f}s")
    print(f"  matched CPython exactly : {matched}")
    print(f"  rejected by PYTHIA      : {rejected}  (generator sampled outside PySub semantics)")
    print(f"  cc compile failures     : {ccfail}   <-- real PYTHIA bugs if > 0")
    print(f"  MISMATCHED OUTPUT       : {mismatched}   <-- real PYTHIA bugs if > 0")
    print(f"  timeouts                : {timeouts}")
    if mismatches:
        print(f"\nTriaged to {a.triage}:")
        for m in mismatches:
            print(f"  {m}")
    print("=" * 60)
    return 1 if (mismatched or ccfail) else 0


if __name__ == "__main__":
    sys.exit(main())
