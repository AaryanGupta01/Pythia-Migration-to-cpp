"""Per-job state: ordered records, event log (events.jsonl), persistence under
$PYTHIA_HOME/jobs/<job_id>/ (CONTRACTS §1) and the 16-node function journey."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import FunctionRecord, JOURNEY_KEYS, Workspace, fid_hash

TITLES = {
    "original": "Original Python", "observed_types": "Observed types (trace)",
    "eligibility": "Eligibility check", "rewrites": "LLM rewrite attempts", "pysub": "Final PySub",
    "tokens": "Tokens", "ast": "AST", "typed_ast": "Typed AST", "pir": "PIR",
    "cpp": "Generated C++", "wrapper": "pybind11 wrapper", "build": "Build (.so)",
    "replay": "Oracle replay", "benchmark": "Benchmark", "splice": "Splice", "status": "Status"}


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


class Cancelled(Exception):
    pass


class JobState:
    def __init__(self, job_id: str, home: Path, input: Dict[str, Any], options: Dict[str, Any],
                 ws_id: str, ext_emit: Optional[Callable] = None):
        self.job_id, self.home, self.options = job_id, Path(home), options
        self.raw_input = dict(input)
        self.input = {k: v for k, v in input.items() if k != "content_b64"}
        self.ws_id = ws_id
        self.ws: Optional[Workspace] = None
        self.name = input.get("name") or input.get("filename") or Path(input.get("path") or input.get("url") or "project").name
        self.dir = self.home / "jobs" / job_id
        self.records: Dict[str, FunctionRecord] = {}
        self.state = "running"
        self.started = time.time()
        self.finished: Optional[float] = None
        self.summary: Optional[Dict[str, Any]] = None
        self.e2e: Optional[Dict[str, Any]] = None
        self.lock = threading.RLock()
        self.cancel_ev = threading.Event()
        self.seq = 0
        self.ext_emit = ext_emit
        self.stage_cache: Dict[str, Any] = {}
        self.pace = float(options.get("pace_ms") or 0) / 1000.0
        self.dir.mkdir(parents=True, exist_ok=True)
        self._events = None

    # ------------------------------------------------------------- events
    def emit(self, type: str, data: Dict[str, Any], stage: Optional[str] = None,
             caption: Optional[str] = None) -> None:
        with self.lock:
            if getattr(self, "_events", None) is None:                  # also true for jobs reloaded from disk
                p = self.dir / "events.jsonl"
                if not self.seq and p.exists():
                    self.seq = sum(1 for _ in open(p, encoding="utf-8"))
                self._events = open(p, "a", encoding="utf-8")
            self.seq += 1
            ev = {"seq": self.seq, "ts": time.time(), "type": type, "stage": stage,
                  "caption": caption, "data": data}
            self._events.write(json.dumps(ev, default=str) + "\n")
            self._events.flush()
        if self.ext_emit:
            try:
                self.ext_emit(type, data, stage=stage, caption=caption)
            except Exception:
                pass
        if self.pace and type not in ("log", "trace.progress", "ingest.progress"):
            time.sleep(self.pace)

    def cancelled(self) -> bool:
        return self.cancel_ev.is_set()

    def check(self) -> None:
        if self.cancel_ev.is_set():
            raise Cancelled()

    def close(self) -> None:
        with self.lock:
            try:
                if self._events:
                    self._events.close()
            except Exception:
                pass
            self._events = None

    # ------------------------------------------------------------- persistence
    def job_dict(self) -> Dict[str, Any]:
        return {"job_id": self.job_id, "workspace_id": self.ws.ws_id if self.ws else self.ws_id,
                "name": self.ws.name if self.ws else self.name, "state": self.state,
                "options": self.options, "input": self.input, "started": self.started,
                "finished": self.finished, "summary": self.summary, "e2e": self.e2e}

    def persist_job(self) -> None:
        with self.lock:
            atomic_write(self.dir / "job.json", json.dumps(self.job_dict(), indent=1, default=str))

    def persist(self, rec: FunctionRecord) -> None:
        with self.lock:
            refresh_journey(rec, final=self.state != "running")
            atomic_write(self.dir / "functions" / (fid_hash(rec.id) + ".json"),
                         json.dumps(rec.to_dict(), default=str))

    def load_records(self) -> None:
        d = self.dir / "functions"
        recs = []
        if d.is_dir():
            for f in d.glob("*.json"):
                try:
                    recs.append(FunctionRecord.from_dict(json.loads(f.read_text(encoding="utf-8"))))
                except Exception:
                    pass
        recs.sort(key=lambda r: (r.file, r.line))
        self.records = {r.id: r for r in recs}


# ------------------------------------------------------------------ journey
def _fmt_types(rec: FunctionRecord) -> str:
    t = rec.trace or {}
    return f"({', '.join(t.get('arg_types') or [])}) -> {t.get('ret_type') or '?'}"


def refresh_journey(rec: FunctionRecord, final: bool) -> None:
    """Derive the 16 journey nodes from the record's current fields."""
    S = rec.status
    ineligible = S == "not_eligible"
    stuck = S == "fixable" and final       # never got fixed (LLM disabled / not attempted)
    dead = ineligible or stuck

    def pend(reason: Optional[str] = None):
        if dead:
            return "skipped", (reason or rec.reason or "function is not eligible")
        return ("skipped", reason or "not reached") if final else ("pending", None)

    n: Dict[str, tuple] = {}
    n["original"] = ("done", f"{rec.metrics.get('size_lines', 0)} lines", None)

    t = rec.trace
    if t and t.get("arg_types") is not None:
        n["observed_types"] = ("done", _fmt_types(rec), None)
    else:
        n["observed_types"] = ("skipped", None, "no trace run" if rec.calls is None else "function was not called during the trace")

    if rec.eligibility == "verifiable":
        n["eligibility"] = ("done", "typechecks as written", None)
    elif rec.eligibility == "fixable":
        ok = rec.sources.get("pysub") is not None
        n["eligibility"] = ("done", "fixed: " + (rec.reason or "rewrite accepted") if ok else "rejected as written, fixable", None)
    else:
        n["eligibility"] = ("failed", None, rec.reason or "not eligible")

    oks = [w for w in rec.rewrites if w.get("ok")]
    if rec.rewrites:
        if oks:
            n["rewrites"] = ("done", f"{len(rec.rewrites)} attempt(s), accepted #{oks[-1].get('attempt')}", None)
        else:
            n["rewrites"] = ("failed", None, (rec.rewrites[-1].get("error") or "no attempt passed the typechecker"))
    elif rec.eligibility == "fixable" and rec.sources.get("annotated") and rec.sources.get("pysub"):
        n["rewrites"] = ("done", "annotation from observed types was enough", None)
    elif stuck:
        n["rewrites"] = ("skipped", None, rec.reason or "LLM fixer disabled")
    else:
        n["rewrites"] = ("skipped", None, "no rewrite needed" if not ineligible else "not attempted")

    if rec.sources.get("pysub"):
        n["pysub"] = ("done", f"{len(rec.sources['pysub'].splitlines())} lines", None)
        for k in ("tokens", "ast", "typed_ast", "pir"):
            n[k] = ("done", "from stage dump", None)
    else:
        st, why = pend()
        for k in ("pysub", "tokens", "ast", "typed_ast", "pir"):
            n[k] = (st, None, why)

    b = rec.build
    if rec.sources.get("cpp"):
        n["cpp"] = ("done", f"{len(rec.sources['cpp'].splitlines())} lines", None)
    elif b and not b.get("ok") and rec.diagnostics:
        n["cpp"] = ("failed", None, "compiler rejected the PySub")
    else:
        st, why = pend()
        n["cpp"] = (st, None, why)
    if rec.sources.get("wrapper_cpp"):
        n["wrapper"] = ("done", "pybind11 glue generated", None)
    else:
        st, why = pend()
        n["wrapper"] = (st, None, why)
    if b and b.get("ok"):
        n["build"] = ("done", f"{b.get('compile_s', 0):.1f}s" + (" (cached)" if b.get("cached") else ""), None)
    elif b:
        n["build"] = ("failed", None, (b.get("error") or (b.get("log") or "")[-300:] or "build failed"))
    else:
        st, why = pend()
        n["build"] = (st, None, why)

    r = rec.replay
    if r and S in ("verified", "guarded", "pending") and r.get("status") != "failed":
        n["replay"] = ("done", f"{r['matched']}/{r['total']} replays match", None)
    elif r and r.get("status") == "failed":
        n["replay"] = ("failed", None, rec.reason or "replay mismatch")
    elif S == "declined":
        n["replay"] = ("skipped", None, "probe only: never spliced")
    else:
        st, why = pend()
        n["replay"] = (st, None, why)

    if rec.bench and not rec.bench.get("error"):
        sp = rec.bench.get("speedup") or 0
        n["benchmark"] = ("done", f"{sp:.1f}x" + (" (probe)" if S == "declined" else ""), None)
    elif rec.bench and rec.bench.get("error"):
        n["benchmark"] = ("failed", None, rec.bench["error"])
    elif S == "failed":
        n["benchmark"] = ("skipped", None, "replay failed")
    else:
        st, why = pend()
        n["benchmark"] = (st, None, why)

    sp = rec.splice
    if sp and sp.get("applied"):
        n["splice"] = ("done", "decorator inserted in work/", None)
    elif S in ("verified", "guarded") and rec.decision == "rejected":
        n["splice"] = ("skipped", None, "rejected by the user: reverted")
    elif S == "declined":
        n["splice"] = ("skipped", None, rec.reason or "declined: not worth the boundary cost")
    elif S == "failed":
        n["splice"] = ("skipped", None, "replay failed: auto-rejected")
    else:
        st, why = pend()
        n["splice"] = (st, None, why)

    if final or S in ("verified", "guarded", "failed", "not_eligible", "declined"):
        bad = S in ("failed", "not_eligible")
        n["status"] = ("failed" if bad else "done", S.replace("_", " "), rec.reason if bad else None)
    else:
        n["status"] = ("pending", None, None) if not final else ("done", S, None)

    rec.journey = [{"key": k, "title": TITLES[k], "state": n[k][0], "summary": n[k][1], "reason": n[k][2]}
                   for k in JOURNEY_KEYS]
