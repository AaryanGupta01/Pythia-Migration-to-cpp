"""Trace run: execute the user's entry command under the in-process tracer
(`_tracer_boot.py`, installed as sitecustomize) and collect a profile + sampled
call records.  See CONTRACTS §9."""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import proc
from .models import Workspace, fid_hash

HERE = Path(__file__).parent


@dataclass
class TraceResult:
    ok: bool = False
    total_s: float = 0.0
    exit_code: Optional[int] = None
    timed_out: bool = False
    cancelled: bool = False
    per_fn: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    samples_dir: Optional[Path] = None
    stdout_tail: str = ""
    calls: int = 0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["samples_dir"] = str(self.samples_dir) if self.samples_dir else None
        return d


def samples_path(samples_dir: Optional[Path], fid: str) -> Optional[Path]:
    if not samples_dir:
        return None
    p = Path(samples_dir) / (fid_hash(fid) + ".jsonl")
    return p if p.exists() and p.stat().st_size else None


def run_trace(ws: Workspace, cmd: str, timeout_s: float, targets: Dict[str, Dict[str, Any]],
              emit: Callable = lambda *a, **k: None, cancelled: Optional[Callable[[], bool]] = None,
              max_samples: int = 500) -> TraceResult:
    tdir = ws.root / "trace"
    shutil.rmtree(tdir, ignore_errors=True)
    out = tdir / "samples"
    out.mkdir(parents=True)
    shutil.copy(HERE / "_tracer_boot.py", tdir / "sitecustomize.py")
    shutil.copy(HERE / "codec.py", tdir / "_pythia_codec.py")
    bindir = proc.make_bin_dir(tdir)
    cfg = {"out_dir": str(out), "max_samples": max_samples,
           "targets": [{"id": fid, "name": t["name"],
                        "file": os.path.realpath(ws.original / t["file"])} for fid, t in targets.items()]}
    (tdir / "cfg.json").write_text(json.dumps(cfg), encoding="utf-8")

    env = dict(os.environ)
    env.pop("PYTHIA_TRACE_ACTIVE", None)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(tdir), str(ws.original)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["PYTHIA_TRACE_CFG"] = str(tdir / "cfg.json")
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    prog = out / "progress.json"

    def tick(elapsed: float, tail: str):
        calls = seen = 0
        try:
            d = json.loads(prog.read_text(encoding="utf-8"))
            calls, seen = d["calls"], d["functions_seen"]
        except Exception:
            pass
        emit("trace.progress", {"calls": calls, "functions_seen": seen,
                                "elapsed_s": round(elapsed, 2), "stdout_tail": tail[-800:]}, stage="trace")

    try:
        r = proc.run_cmd(cmd, ws.original, env, timeout_s, on_tick=tick, cancelled=cancelled)
    except Exception as ex:
        return TraceResult(ok=False, error=f"could not start trace command: {ex}", samples_dir=out)

    res = TraceResult(total_s=r.elapsed, exit_code=r.exit_code, timed_out=r.timed_out,
                      cancelled=r.cancelled, samples_dir=out,
                      stdout_tail=r.output[-4000:].decode("utf-8", "replace"))
    (tdir / "stdout.log").write_bytes(r.output[:2_000_000])
    try:
        d = json.loads(prog.read_text(encoding="utf-8"))
    except Exception as ex:
        res.error = "tracer produced no data (command not Python, or it exited before importing project code)"
        return res
    res.ok = True
    res.calls = d["calls"]
    total = max(res.total_s, 1e-9)
    for fid, s in d["per_fn"].items():
        s["share"] = min(1.0, s["cum_s"] / total)
        res.per_fn[fid] = s
    emit("trace.progress", {"calls": res.calls, "functions_seen": d["functions_seen"],
                            "elapsed_s": round(res.total_s, 2), "stdout_tail": res.stdout_tail[-800:]},
         stage="trace")
    return res
