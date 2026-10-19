"""Files mode: script collections (LeetCode / GfG / DSA repositories, exercise folders) are not applications with one
entry point, so there is nothing to trace and no function is hot. Instead every FILE is converted whole, compiled to C++
and verified against CPython, either on its own output or, for entry-less code (`class Solution`), on generated inputs.

Each file becomes one record in the existing model (id `path::<file>`), so the Studio shows, filters and exports them
like functions. The per-file work runs in a subprocess with a time limit (pythia.studio.filework), in parallel.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from .models import FunctionRecord

MIN_FILES = 8                  # fewer files than this with no entry command: the normal function pipeline
FILE_TIMEOUT_S = 150
WORKERS = max(2, min(6, (os.cpu_count() or 4)))


def applies(p) -> bool:
    mode = (p.opt.get("mode") or "auto").lower()
    if mode == "files":
        return True
    if mode == "functions":
        return False
    if (p.opt.get("trace_cmd") or "").strip():                 # a real entry command: trace and accelerate hot functions
        return False
    return len(p.ws.py_files) >= MIN_FILES


def _run_worker(p, rel: str) -> Dict[str, Any]:
    cmd = [sys.executable, "-m", "pythia.studio.filework", str(p.ws.original / rel), str(p.ws.original)]
    kw: Dict[str, Any] = {}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=FILE_TIMEOUT_S, stdin=subprocess.DEVNULL,
                           errors="replace", **kw)
    except subprocess.TimeoutExpired:
        return {"file": rel, "stage": "skip", "status": "skipped", "detail": f"took longer than {FILE_TIMEOUT_S} s"}
    for line in reversed(r.stdout.splitlines()):
        if line.startswith("@@RESULT "):
            try:
                return json.loads(line[9:])
            except ValueError:
                break
    return {"file": rel, "stage": "convert", "status": "failed",
            "detail": "the converter process ended without an answer: " + (r.stderr.strip()[-200:] or "no output")}


def _record(rel: str, r: Dict[str, Any]) -> FunctionRecord:
    orig = r.get("original") or ""
    status = r.get("status", "failed")
    ok = status == "verified"
    st = {"verified": "verified", "failed": "failed"}.get(status, "not_eligible")
    reason = r.get("reason") or (None if ok else r.get("detail"))
    rec = FunctionRecord(id=f"{rel}::<file>", file=rel, name=Path(rel).stem, qualname="<file>", line=1,
                         end_line=max(1, orig.count("\n") + 1), status=st,
                         eligibility="verifiable" if ok else "not_eligible", reason=reason)
    rec.sources = {"original": orig, "annotated": None, "pysub": r.get("source"), "cpp": r.get("cpp"),
                   "wrapper_cpp": None}
    rec.fidelity = list(r.get("fidelity") or [])
    rec.cpp_line_map = r.get("cpp_line_map") or {}
    rec.metrics["size_lines"] = orig.count("\n") + 1
    if ok:
        calls = r.get("calls")
        rec.build = {"ok": True, "cached": False, "compile_s": 0.0, "module": None, "so": None, "exposed": [],
                     "kind": "whole file", "log": ""}
        rec.replay = {"total": calls or 1, "matched": calls or 1, "exc_matches": 0, "first_mismatch": None,
                      "skipped": 0, "status": "verified",
                      "source": "generated inputs" if r.get("stage") == "driven" else "the program's own output"}
        t = r.get("timing") or {}
        py, cp = t.get("python_ms"), t.get("cpp_ms")
        if py and cp and py >= 150 and cp > 0:                 # shorter runs are process start-up, not computation
            rec.speedup = py / cp
        if r.get("detail"):
            rec.rewrites = []
    rec.private["file_mode"] = True
    rec.private["file_result"] = {k: v for k, v in r.items() if k not in ("original", "source", "cpp")}
    return rec


def run(p) -> None:
    """Replaces scan .. e2e of the normal pipeline."""
    from .server import playground
    js, ws = p.js, p.ws
    files = list(ws.py_files)
    p.stage("scan", "running", caption="Script collection: converting every file whole (no entry command to trace)")
    p.step("scan", "Files mode", "running", f"{len(files)} files")
    try:                                                       # build the shared runtime object once, not per worker
        playground._runtime_object(Path(tempfile.gettempdir()) / "pythia-file-cache")
    except Exception as ex:
        p.err("runtime", ex)
    p.stage("scan", "done", f"{len(files)} files")
    for st, why in (("trace", "files are converted whole"), ("rank", "nothing to rank: every file is its own unit")):
        p.stage(st, "skipped", why)
    p.stage("fix", "running", "0/%d" % len(files), progress=0.0,
            caption="Converting each file in-house: types inferred, rewritten, compiled and checked against CPython")
    done = ok = 0
    t0 = time.time()
    counts: Dict[str, int] = {}
    with cf.ThreadPoolExecutor(WORKERS) as ex:
        futs = {ex.submit(_run_worker, p, rel): rel for rel in files}
        for fut in cf.as_completed(futs):
            js.check()
            rel = futs[fut]
            try:
                r = fut.result()
            except Exception as e:                              # a worker crash is a result, not a stop
                r = {"file": rel, "stage": "convert", "status": "failed", "detail": f"{type(e).__name__}: {e}"}
            rec = _record(rel, r)
            js.records[rec.id] = rec
            p.save(rec)
            counts[r.get("stage", "?")] = counts.get(r.get("stage", "?"), 0) + 1
            p.emit("scan.function", {"function": rec.to_summary()}, stage="scan")
            if rec.status == "verified":
                ok += 1
                p.emit("compile.done", {"id": rec.id, "ok": True, "cached": False, "compile_s": 0.0, "module": None,
                                        "error": None, "diagnostics": []}, stage="compile",
                       caption=f"{rec.name}: compiled to C++")
                p.emit("verify.result", {"id": rec.id, "status": "verified", "total": rec.replay["total"],
                                         "matched": rec.replay["matched"], "first_mismatch": None}, stage="verify")
            elif rec.status == "failed":
                p.emit("verify.result", {"id": rec.id, "status": "failed", "total": 1, "matched": 0,
                                         "first_mismatch": {"args": "", "kind": r.get("stage"), "python": "",
                                                            "cpp": rec.reason or ""}}, stage="verify")
            p.fn_step(rec, rec.reason or (r.get("detail") or "verified"),
                      "done" if rec.status == "verified" else "failed" if rec.status == "failed" else "info")
            done += 1
            p.stage("fix", "running", f"{done}/{len(files)}", progress=done / max(1, len(files)))
    p.stage("fix", "done", f"{done} files converted")
    p.stage("compile", "done", f"{ok} compiled")
    p.stage("verify", "done", f"{ok}/{done} verified")
    p.stage("benchmark", "skipped", "script collection: process start-up dominates short files")
    _write_converted(p)
    p.stage("splice", "done", f"{ok} files converted")
    js.e2e = {}
    p.step("scan", "Files mode", "done",
           f"{ok} of {done} files compiled and verified in {time.time() - t0:.0f} s "
           f"({counts.get('driven', 0)} on generated inputs, {counts.get('same', 0)} on their own output)")


def _write_converted(p) -> None:
    """The converted programs and their C++ go into the workspace copy, so Export carries them."""
    ws = p.ws
    for r in p.recs():
        res = r.private.get("file_result") or {}
        if r.status != "verified" or not r.sources.get("pysub"):
            continue
        base = ws.work / "_pythia_converted" / r.file
        base.parent.mkdir(parents=True, exist_ok=True)
        try:
            base.with_suffix(".pysub.py").write_text(r.sources["pysub"], encoding="utf-8", newline="\n")
            if r.sources.get("cpp"):
                base.with_suffix(".cpp").write_text(r.sources["cpp"], encoding="utf-8", newline="\n")
            r.splice = {"applied": True, "diff": "", "path": f"_pythia_converted/{r.file}"}
        except OSError as ex:
            p.err(f"write:{r.id}", ex)
