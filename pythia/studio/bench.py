"""Benchmarks: per-function Python vs compiled (median of repeats on replayed
args) and end-to-end entry-command timing before/after splice."""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import proc
from .models import FunctionRecord, Workspace
from .replay import WORKER, prepare_calls, run_worker


def bench_function(rec: FunctionRecord, ws: Workspace, so_path, modname: str,
                   samples_path: Optional[Path] = None, timeout_s: float = 240) -> Dict[str, Any]:
    tmp = ws.root / "tmp"
    tmp.mkdir(exist_ok=True)
    calls_path, n, _ = prepare_calls(rec, samples_path, 500, tmp / f"bench_{rec.name}.jsonl")
    if n == 0:
        return {"error": "no inputs to benchmark with"}
    return run_worker({"mode": "bench", "original": str(ws.original), "file": rec.file, "name": rec.name,
                       "so": str(so_path), "modname": modname, "calls": str(calls_path), "n_max": 500},
                      ws, timeout_s)


def bench_e2e(ws: Workspace, cmd: str, which: str, timeout_s: float, runs: int = 1,
              cancelled: Optional[Callable[[], bool]] = None) -> Dict[str, Any]:
    """Run the entry command in original/ or work/; median seconds over `runs`."""
    root = ws.original if which == "original" else ws.work
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PATH"] = str(proc.make_bin_dir(ws.root / "trace")) + os.pathsep + env.get("PATH", "")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env.pop("PYTHIA_TRACE_CFG", None)
    times, hashes, ok = [], set(), True
    for _ in range(max(1, runs)):
        r = proc.run_cmd(cmd, root, env, timeout_s, cancelled=cancelled)
        times.append(r.elapsed)
        hashes.add(hashlib.sha256(r.output).hexdigest())
        ok = ok and r.exit_code == 0 and not r.timed_out
        if r.cancelled:
            break
    times.sort()
    return {"seconds": times[len(times) // 2], "stdout_hash": sorted(hashes)[0] if len(hashes) == 1 else "unstable:" + ",".join(sorted(hashes)),
            "ok": ok}
