#!/usr/bin/env python3
"""Fixed-kernel benchmark: CPython vs PYTHIA-compiled C++17 binary, whole-process wall time, N runs, medians.
Run from the repo root under WSL:  .venv/bin/python docs/review3/src/bench_kernels.py [--runs 7]
Writes docs/review3/src/evidence/bench_kernels.json. Same compile flags as tools/oracle.py (-std=c++17 -O2 -flto)."""
import argparse
import json
import os
import platform
import shutil
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pythia.cli import compile_source  # noqa: E402
from pythia.parser import parse  # noqa: E402
from pythia.typecheck import typecheck  # noqa: E402
from pythia.lower import lower  # noqa: E402
from pythia.emit_cpp import emit  # noqa: E402


def compile_no_elision(src, path):
    mod, _ = parse(src, path)
    tc, _ = typecheck(mod, path)
    lower(mod, tc)
    return emit(mod, tc, os.path.basename(path), library=False)

ap = argparse.ArgumentParser()
ap.add_argument("--runs", type=int, default=7)
a = ap.parse_args()
KER = Path(__file__).parent / "kernels"
BUILD = ROOT / "build" / "bench_kernels"
BUILD.mkdir(parents=True, exist_ok=True)
RT = ROOT / "runtime"


def timed(cmd):
    t = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return time.perf_counter() - t, r


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip()


cpu = next((l.split(":", 1)[1].strip() for l in open("/proc/cpuinfo") if l.startswith("model name")), "?")
env = {"cpu": cpu, "logical_cpus": os.cpu_count(), "os": platform.platform(), "python": sys.version.split()[0],
       "gxx": sh(["c++", "--version"]).splitlines()[0], "runs": a.runs, "flags": "-std=c++17 -O2 -flto"}

empty = BUILD / "empty.py"
empty.write_text("print(0)\n")
env["cpython_startup_ms"] = round(st.median(timed([sys.executable, str(empty)])[0] for _ in range(9)) * 1000, 1)

rows = []
for f in sorted(KER.glob("k*.py")):
    src = f.read_text(encoding="utf-8")
    code, notes, errs, opt = compile_source(src, str(f))
    if errs:
        rows.append({"kernel": f.stem, "error": str(errs[0])[:200]})
        continue
    d = BUILD / f.stem
    d.mkdir(exist_ok=True)
    for h in ("pyrt.cpp", "pyrt.hpp"):
        shutil.copy(RT / h, d)
    cpp = d / (f.stem + ".cpp")
    cpp.write_text(code, encoding="utf-8")
    binp = d / f.stem
    t = time.perf_counter()
    cc = subprocess.run(["c++", "-std=c++17", "-O2", "-flto", "-I", str(d), str(cpp), str(d / "pyrt.cpp"), "-o", str(binp)],
                        capture_output=True, text=True)
    build_s = time.perf_counter() - t
    if cc.returncode:
        rows.append({"kernel": f.stem, "error": "c++ failed: " + cc.stderr[:200]})
        continue
    # variant without guard elision (isolates the interval-analysis pass)
    bin_ne = d / (f.stem + "_noelide")
    cpp_ne = d / (f.stem + "_noelide.cpp")
    cpp_ne.write_text(compile_no_elision(src, str(f)), encoding="utf-8")
    subprocess.run(["c++", "-std=c++17", "-O2", "-flto", "-I", str(d), str(cpp_ne), str(d / "pyrt.cpp"), "-o", str(bin_ne)],
                   capture_output=True, text=True, check=True)
    py_t, c_t, n_t = [], [], []
    same = True
    ref = None
    for _ in range(a.runs):
        tp, rp = timed([sys.executable, str(f)])
        tc, rc = timed([str(binp)])
        tn, rn = timed([str(bin_ne)])
        n_t.append(tn)
        same &= (rn.stdout == rp.stdout)
        py_t.append(tp)
        c_t.append(tc)
        ref = rp.stdout
        same &= (rp.stdout == rc.stdout and rp.returncode == rc.returncode)
    rows.append({"kernel": f.stem, "output": ref.strip()[:60], "identical": same,
                 "py_ms": round(st.median(py_t) * 1000, 1), "py_min": round(min(py_t) * 1000, 1), "py_max": round(max(py_t) * 1000, 1),
                 "cpp_ms": round(st.median(c_t) * 1000, 1), "cpp_min": round(min(c_t) * 1000, 1), "cpp_max": round(max(c_t) * 1000, 1),
                 "speedup": round(st.median(py_t) / st.median(c_t), 1),
                 "noelide_ms": round(st.median(n_t) * 1000, 1), "elision_gain": round(st.median(n_t) / st.median(c_t), 2),
                 "elided": opt.elided if opt else None, "kept": opt.kept if opt else None, "build_s": round(build_s, 1),
                 "guards": sum(1 for n in notes if getattr(n, "severity", "") == "guarded"), "notes": len(notes)})
    print(rows[-1], flush=True)

env["date"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
out = Path(__file__).parent / "evidence" / "bench_kernels.json"
out.write_text(json.dumps({"env": env, "rows": rows}, indent=1))
ok = [r for r in rows if "speedup" in r]
print(f"{len(ok)}/{len(rows)} kernels; all identical={all(r['identical'] for r in ok)}; "
      f"geomean={st.geometric_mean([r['speedup'] for r in ok]):.1f}x median={st.median([r['speedup'] for r in ok]):.1f}x")
