#!/usr/bin/env python3
"""Snapshot a finished job into demo/sample_run/ (the bundled sample run the app seeds on first start).
Usage: python scripts/make_sample_job.py <job_id> [--home ~/.pythia-studio]"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("job_id")
ap.add_argument("--home", default=os.environ.get("PYTHIA_HOME") or str(Path.home() / ".pythia-studio"))
a = ap.parse_args()
home = Path(a.home).expanduser()
jd = home / "jobs" / a.job_id
meta = json.loads((jd / "job.json").read_text(encoding="utf-8"))
if meta.get("state") != "done":
    sys.exit(f"job {a.job_id} is {meta.get('state')}, not done")
ws_id = meta["workspace_id"]
out = ROOT / "demo" / "sample_run"
shutil.rmtree(out, ignore_errors=True)
shutil.copytree(jd, out / "jobs" / a.job_id)
(out / "jobs" / a.job_id / "sample.flag").unlink(missing_ok=True)
ws = home / "workspaces" / ws_id
for sub in ("original", "work"):
    shutil.copytree(ws / sub, out / "workspaces" / ws_id / sub,
                    ignore=shutil.ignore_patterns("*.so", "__pycache__", "*.pyc", "lib"))
shutil.copy(ws / "workspace.json", out / "workspaces" / ws_id / "workspace.json")
size = sum(f.stat().st_size for f in out.rglob("*") if f.is_file())
print(f"sample run written to {out} ({size / 1e6:.1f} MB)")
