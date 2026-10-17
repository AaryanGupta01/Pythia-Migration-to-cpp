"""Bundled sample run: a finished demo job (events, function records, workspace text) copied into the user's data
folder on first start, so the app opens with an instant, repeatable run to browse and replay (no waiting on a build).

Layout of demo/sample_run/:  jobs/<job_id>/{job.json,events.jsonl,functions/*.json}  workspaces/<ws_id>/{original,work,workspace.json}
Sample jobs carry a `sample.flag` file: decisions are recorded but nothing is spliced, and export asks for a real run.
"""
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from ..paths import DEMO

SAMPLE_DIR = DEMO / "sample_run"
FLAG = "sample.flag"


def is_sample(job_dir: Path) -> bool:
    return (Path(job_dir) / FLAG).exists()


def seed(home: Path) -> None:
    src = SAMPLE_DIR
    if not (src / "jobs").is_dir():
        return
    try:
        recent_p = home / "recent.json"
        recent = json.loads(recent_p.read_text(encoding="utf-8")) if recent_p.exists() else []
        for wd in sorted((src / "workspaces").iterdir()) if (src / "workspaces").is_dir() else []:
            dest = home / "workspaces" / wd.name
            if not dest.exists():
                shutil.copytree(wd, dest)
                meta_p = dest / "workspace.json"
                meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
                meta["root"] = str(dest)
                meta_p.write_text(json.dumps(meta, indent=1), encoding="utf-8")
        for jd in sorted((src / "jobs").iterdir()):
            dest = home / "jobs" / jd.name
            if dest.exists():
                continue
            shutil.copytree(jd, dest)
            (dest / FLAG).write_text("bundled sample run\n", encoding="utf-8")
            meta = json.loads((dest / "job.json").read_text(encoding="utf-8"))
            if not any(i.get("job_id") == jd.name for i in recent):
                recent.append({"workspace_id": meta.get("workspace_id"), "ws_id": meta.get("workspace_id"),
                               "name": (meta.get("name") or "demo") + " (sample run)", "input_kind": "demo",
                               "origin": "", "job_id": jd.name, "py_files": 0, "ts": time.time() - 86400})
        (home / "recent.json").write_text(json.dumps(recent[:20], indent=1), encoding="utf-8")
    except Exception:
        pass                                                  # a damaged sample must never stop the app
