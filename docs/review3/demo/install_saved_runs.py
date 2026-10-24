#!/usr/bin/env python3
"""Copies the saved demo runs in docs/review3/demo/saved_runs/ into a PYTHIA Studio data folder so they can be replayed offline.

    python install_saved_runs.py                 # into %USERPROFILE%\\.pythia-studio  (the installed app's default)
    python install_saved_runs.py --home DIR      # into another PYTHIA_HOME

Then start PYTHIA Studio and click the project under "Recent", or open  http://127.0.0.1:8765/?job=<JOB_ID>&replay=1
(the job ids are listed in LIVE_DEMO.md). Nothing is overwritten if it already exists."""
import argparse
import json
import shutil
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--home", default=str(Path.home() / ".pythia-studio"))
a = ap.parse_args()
src = Path(__file__).resolve().parent / "saved_runs"
home = Path(a.home)
(home / "jobs").mkdir(parents=True, exist_ok=True)
(home / "workspaces").mkdir(parents=True, exist_ok=True)
recent_p = home / "recent.json"
recent = json.loads(recent_p.read_text(encoding="utf-8")) if recent_p.exists() else []
for jd in sorted((src / "jobs").iterdir()):
    meta = json.loads((jd / "job.json").read_text(encoding="utf-8"))
    ws = meta.get("workspace_id")
    wsrc, wdst = src / "workspaces" / ws, home / "workspaces" / ws
    if not wdst.exists():
        shutil.copytree(wsrc, wdst)
        mp = wdst / "workspace.json"
        m = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
        m["root"] = str(wdst)
        mp.write_text(json.dumps(m, indent=1), encoding="utf-8")
    if not (home / "jobs" / jd.name).exists():
        shutil.copytree(jd, home / "jobs" / jd.name)
    if not any(i.get("job_id") == jd.name for i in recent):
        recent.insert(0, {"workspace_id": ws, "ws_id": ws, "name": meta.get("name"), "input_kind": meta.get("input", {}).get("kind", "folder"),
                          "origin": meta.get("name"), "job_id": jd.name, "py_files": len(meta.get("py_files") or []), "ts": time.time()})
    print("installed", meta.get("name"), jd.name)
recent_p.write_text(json.dumps(recent[:30], indent=1), encoding="utf-8")
