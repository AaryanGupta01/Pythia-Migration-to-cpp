#!/usr/bin/env python3
"""Severity and class histogram of the Semantic Fidelity Report over tests/positive (compile only, no C++ build)."""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from pythia.cli import compile_source
sev, cls, per_prog, n_ok = collections.Counter(), collections.Counter(), [], 0
for f in sorted((ROOT / "tests/positive").glob("*.py")):
    code, notes, errs, st = compile_source(f.read_text(encoding="utf-8"), str(f))
    if errs:
        continue
    n_ok += 1
    per_prog.append(len(notes))
    for n in notes:
        sev[n.severity] += 1
        cls[n.cls.split()[0]] += 1
out = {"programs": n_ok, "notes": sum(sev.values()), "severity": dict(sev),
       "classes": dict(sorted(cls.items(), key=lambda kv: int(kv[0][1:]))), "median_per_program": sorted(per_prog)[len(per_prog)//2]}
(ROOT / "docs/review3/src/evidence/fidelity_stats.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out))
