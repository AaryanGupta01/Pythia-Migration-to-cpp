#!/usr/bin/env python3
"""Saves one function's full record and compiler-stage dump to evidence/journey.json.
Usage: python fetch_journey.py --base http://127.0.0.1:8797 --job JOB --fn "path.py::name" --repo NAME [--url URL --sha SHA --cmd CMD]"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
from pythia.stages import dump_stages  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8797")
ap.add_argument("--job", required=True)
ap.add_argument("--fn", required=True)
ap.add_argument("--repo", required=True)
ap.add_argument("--url", default="")
ap.add_argument("--sha", default="")
ap.add_argument("--cmd", default="")
a = ap.parse_args()
rec = json.load(urllib.request.urlopen(f"{a.base}/api/jobs/{a.job}/function?id=" + urllib.parse.quote(a.fn, safe="")))
src = rec["sources"].get("pysub") or rec["sources"].get("annotated") or rec["sources"].get("original")
stages = dump_stages(src, filename=rec["file"])
keep = {k: rec.get(k) for k in ("id", "file", "name", "line", "status", "reason", "share", "calls", "speedup", "trace", "build", "replay", "bench", "splice", "score", "metrics", "fidelity", "sources")}
keep["sources"] = {k: v for k, v in rec["sources"].items() if k in ("original", "annotated", "pysub", "cpp", "wrapper_cpp")}
(HERE / "evidence" / "journey.json").write_text(json.dumps({"repo": a.repo, "url": a.url, "sha": a.sha, "cmd": a.cmd, "job": a.job, "fn": a.fn,
                                                           "rec": keep, "stages": stages}, indent=1), encoding="utf-8")
print("saved journey for", a.fn)
