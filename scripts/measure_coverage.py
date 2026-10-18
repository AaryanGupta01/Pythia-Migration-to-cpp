#!/usr/bin/env python3
"""PySub coverage of a real codebase, offline (no LLM, no tracing): how many module-level functions the scanner
accepts as-is, and a ranking of every reason the rest are rejected.

    python scripts/measure_coverage.py https://github.com/TheAlgorithms/Python   [--json out.json]
    python scripts/measure_coverage.py path/to/folder

A function counts as "compiles" when the scanner marks it verifiable (it type-checks as PySub together with
everything it calls). Reasons are counted per function (a function with three blockers counts once for each).
"""
import argparse
import collections
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pythia.studio import ingest, scan  # noqa: E402
from pythia.studio.models import Workspace  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("source", help="GitHub URL or local folder")
ap.add_argument("--json", help="write per-function results here")
ap.add_argument("--top", type=int, default=40)
a = ap.parse_args()

if Path(a.source).is_dir():
    src = Path(a.source)
else:
    src = Path(tempfile.mkdtemp(prefix="pythia-cov-")) / "repo"
    if not ingest._github_zip(a.source, src, lambda *x, **k: None):
        sys.exit("give a GitHub URL or a folder")

files = sorted(p.relative_to(src).as_posix() for p in src.rglob("*.py")
               if not any(part.startswith(".") or part in ("venv", ".venv", "node_modules", "site-packages")
                          for part in p.relative_to(src).parts))
ws = Workspace(ws_id="cov", name=src.name, root=src.parent, original=src, work=src, py_files=files)
recs = scan.scan_workspace(ws)
top = [r for r in recs if "." not in r.qualname]
methods = [r for r in recs if "." in r.qualname]
by = collections.Counter(r.eligibility for r in top)
reasons = collections.Counter()
for r in top:
    if r.eligibility == "verifiable":
        continue
    for part in re.split(r";\s*(?![^()]*\))", r.reason or "unknown"):
        part = re.sub(r"`[^`]*`", "`X`", part.strip())          # group "calls `foo`" with "calls `bar`"
        part = re.sub(r"\d+", "N", part)
        reasons[part[:110]] += 1

n = len(top)
print(f"{src.name}: {len(files)} files, {n} module-level functions (+{len(methods)} methods, not compiled in v1)")
for k in ("verifiable", "fixable", "not_eligible"):
    print(f"  {k:<13} {by.get(k, 0):>6}  ({100 * by.get(k, 0) / max(n, 1):.1f}%)")
print(f"\nTop {a.top} reasons (functions affected):")
for k, v in reasons.most_common(a.top):
    print(f"  {v:>6}  {k}")
if a.json:
    Path(a.json).write_text(json.dumps([{"id": r.id, "eligibility": r.eligibility, "reason": r.reason} for r in recs],
                                       indent=1), encoding="utf-8")
