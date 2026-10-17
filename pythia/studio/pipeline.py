"""Pipeline orchestration: ingest -> scan -> trace -> rank -> fix -> compile ->
verify -> benchmark -> splice (-> e2e).  Emits every CONTRACTS §4 event,
maintains journeys and persists after every change.  One function failing
never aborts the job."""
from __future__ import annotations

import math
import os
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import bench as bench_mod
from . import replay as replay_mod
from . import splice as splice_mod
from . import trace as trace_mod
from .export import geomean
from .jobstate import Cancelled, JobState
from .models import FunctionRecord, STATUSES, Workspace

REPO = Path(__file__).resolve().parents[2]
OFFLINE_DIR = REPO / "demo" / "offline_cache"
SLOWER_THAN = 1.1             # measured speedup below this => declined (a wash is not worth the boundary risk)


def fmt_x(v: Optional[float]) -> str:
    return "n/a" if v is None else (f"{v:.1f}x" if v < 100 else f"{v:.0f}x")


class Pipeline:
    def __init__(self, js: JobState, settings: Optional[Dict[str, Any]] = None):
        self.js = js
        self.opt = js.options
        self.settings = settings or {}
        self.offline = bool(self.opt.get("offline") or os.environ.get("PYTHIA_OFFLINE") == "1"
                            or self.settings.get("offline"))
        self.ws: Optional[Workspace] = None
        self.trace: Optional[trace_mod.TraceResult] = None
        self.llm = None
        self.step_detail: Dict[str, List[str]] = {}

    # ------------------------------------------------------------ helpers
    def emit(self, type, data, stage=None, caption=None):
        self.js.emit(type, data, stage=stage, caption=caption)

    def stage(self, name: str, state: str, summary: Optional[str] = None, progress: Optional[float] = None,
              caption: Optional[str] = None):
        self.emit("stage", {"stage": name, "state": state, "summary": summary, "progress": progress},
                  stage=name, caption=caption)
        if state in ("running", "done", "failed") and progress in (None, 0, 1) or state == "failed":
            self.emit("log", {"stream": "system", "level": "error" if state == "failed" else "info",
                              "text": f"[{name}] {state}" + (f" - {summary}" if summary else "")}, stage=name)

    def step(self, step_id: str, title: str, state: str = "running", detail: Optional[str] = None,
             fn_id: Optional[str] = None, caption: Optional[str] = None, stage: Optional[str] = None):
        self.emit("agent.step", {"step_id": step_id, "fn_id": fn_id, "title": title, "state": state,
                                 "detail": detail}, stage=stage, caption=caption)

    def fn_step(self, rec: FunctionRecord, part: str, state: str = "running", caption=None, stage=None):
        """One agent step per function, updated in place: 'edit_distance: PySub ok -> C++ ok -> ...'."""
        parts = self.step_detail.setdefault(rec.id, [])
        if part:
            parts.append(part)
        self.step(f"fn:{rec.id}", rec.name, state, " -> ".join(parts) or None, fn_id=rec.id,
                  caption=caption, stage=stage)

    def save(self, rec: FunctionRecord):
        self.js.persist(rec)

    def err(self, where: str, ex: BaseException, fatal: bool = False):
        self.emit("error", {"where": where, "message": f"{type(ex).__name__}: {ex}", "fatal": fatal})
        self.emit("log", {"stream": "system", "level": "error",
                          "text": "".join(traceback.format_exception_only(type(ex), ex)).strip()})
        if os.environ.get("PYTHIA_DEBUG"):
            traceback.print_exc()

    def recs(self) -> List[FunctionRecord]:
        return list(self.js.records.values())

    def fail_fn(self, rec: FunctionRecord, where: str, ex: BaseException):
        self.err(f"{where}:{rec.id}", ex)
        rec.status = "failed"
        rec.reason = f"internal error during {where}: {type(ex).__name__}: {ex}"
        rec.decision = "rejected"
        self.fn_step(rec, f"{where} error", "failed")
        self.save(rec)

    # ------------------------------------------------------------ run
    def run(self) -> None:
        js = self.js
        try:
            self._run()
            js.state = "cancelled" if js.cancelled() else "done"
        except Cancelled:
            js.state = "cancelled"
        except Exception as ex:                         # fatal: ingest/scan failure or a bug
            self.err("pipeline", ex, fatal=True)
            js.state = "failed"
        finally:
            js.finished = time.time()
            for r in self.recs():
                self.save(r)
            js.summary = self.summary()
            js.persist_job()
            self.emit("job.done", {"state": js.state, "summary": js.summary})
            js.close()

    def summary(self) -> Dict[str, Any]:
        recs = self.recs()
        c = {s: sum(1 for r in recs if r.status == s) for s in STATUSES}
        acc = [r.speedup for r in recs if r.status in ("verified", "guarded") and r.speedup]
        e = self.js.e2e
        return {"functions": len(recs), "verified": c["verified"], "guarded": c["guarded"],
                "fixable": c["fixable"], "not_eligible": c["not_eligible"], "failed": c["failed"],
                "declined": c["declined"], "e2e_speedup": e.get("speedup") if e and e.get("ok") else None,
                "geomean_speedup": geomean(acc)}

    def _run(self) -> None:
        js = self.js
        from . import ingest, scan
        self.emit("job.start", {"job_id": js.job_id, "workspace_id": js.ws_id, "name": js.name,
                                "input_kind": js.input.get("kind"), "options": js.options},
                  caption="Starting analysis")
        js.persist_job()

        # ---- ingest
        self.stage("ingest", "running", caption="Ingesting the project into an isolated workspace copy")
        self.step("ingest", f"Ingesting {js.name}", "running")
        inp = dict(js.raw_input)
        inp["ws_id"] = js.ws_id                      # honoured by ingest when supported
        try:
            ws = ingest.ingest(inp, js.home, self.emit)
        except Exception as ex:
            self.stage("ingest", "failed", str(ex))
            self.step("ingest", f"Ingest failed", "failed", str(ex))
            raise
        self.ws = js.ws = ws
        js.name = ws.name
        js.ws_id = ws.ws_id
        js.persist_job()
        self.stage("ingest", "done", f"{len(ws.py_files)} Python files")
        self.step("ingest", f"Ingested {ws.name}", "done", f"{len(ws.py_files)} Python files, "
                  f"{len(ws.skipped)} skipped")
        js.check()

        # ---- scan
        self.stage("scan", "running", caption="Parsing every function and asking the PYTHIA typechecker what it accepts")
        self.step("scan", "Scanning functions", "running")
        try:
            recs = scan.scan_workspace(ws, self.emit)
        except Exception as ex:
            self.stage("scan", "failed", str(ex))
            raise
        for r in recs:
            js.records[r.id] = r
            self.save(r)
        by = {k: sum(1 for r in recs if r.eligibility == k) for k in ("verifiable", "fixable", "not_eligible")}
        self.stage("scan", "done", f"{len(recs)} functions")
        self.step("scan", "Scanned functions", "done",
                  f"{len(recs)} functions: {by['verifiable']} verifiable, {by['fixable']} fixable, "
                  f"{by['not_eligible']} not eligible",
                  caption=f"{by['verifiable']} functions pass the typechecker as written, {by['fixable']} could be fixed")
        js.check()

        # ---- trace
        self.do_trace()
        js.check()
        # ---- rank
        self.do_rank()
        js.check()
        # ---- fix / compile / verify / benchmark / splice
        self.do_fix()
        js.check()
        cands = self.candidates()
        self.do_compile(cands)
        js.check()
        self.do_verify(cands)
        js.check()
        self.do_bench(cands)
        js.check()
        self.do_splice()
        js.check()
        self.do_e2e()

    # ------------------------------------------------------------ trace
    def do_trace(self) -> None:
        js, ws = self.js, self.ws
        cmd = (self.opt.get("trace_cmd") or "").strip()
        if not cmd:
            self.stage("trace", "skipped", "no entry command",
                       caption="No entry command given: ranking by static heuristics only")
            self.step("trace", "Trace skipped", "info", "no entry command; using static heuristics")
            return
        self.stage("trace", "running", caption=f"Running `{cmd}` under a tracer to find real hotspots")
        self.step("trace", f"Tracing {cmd}", "running")
        targets = {r.id: {"file": r.file, "name": r.name, "line": r.line} for r in self.recs()
                   if "." not in r.qualname}

        def emit_progress(type, data, stage=None, caption=None):
            self.emit(type, data, stage=stage, caption=caption)
            if type == "trace.progress":
                self.step("trace", f"Tracing {cmd}", "running", f"{data['calls']:,} calls recorded")

        tr = trace_mod.run_trace(ws, cmd, float(self.opt.get("trace_timeout_s") or 60), targets,
                                 emit_progress, cancelled=js.cancelled)
        self.trace = tr
        if js.cancelled():
            raise Cancelled()
        if not tr.ok:
            self.stage("trace", "failed", tr.error)
            self.step("trace", "Trace failed", "failed", tr.error)
            self.emit("log", {"stream": "trace", "level": "warn", "text": (tr.error or "") + "\n" + tr.stdout_tail[-500:]})
            return
        profile = []
        for r in self.recs():
            s = tr.per_fn.get(r.id)
            if s:
                r.calls = s["calls"]
                r.share = s["share"]
                r.trace = {"calls": s["calls"], "cum_s": s["cum_s"], "self_s": s["self_s"], "share": s["share"],
                           "arg_types": s["arg_types"], "ret_type": s["ret_type"], "samples": s["samples"],
                           "avg_arg_elems": s["avg_arg_elems"], "avg_ret_elems": s["avg_ret_elems"]}
                profile.append({"id": r.id, "calls": s["calls"], "cum_s": s["cum_s"], "share": s["share"]})
            else:
                r.calls, r.share, r.trace = 0, 0.0, None
            self.save(r)
        profile.sort(key=lambda p: -p["cum_s"])
        self.emit("trace.done", {"total_s": tr.total_s, "exit_code": tr.exit_code, "timed_out": tr.timed_out,
                                 "calls": tr.calls, "profile": profile[:200]}, stage="trace",
                  caption=f"{tr.calls:,} calls recorded in {tr.total_s:.1f}s" + (" (timed out)" if tr.timed_out else ""))
        if tr.stdout_tail:
            self.emit("log", {"stream": "trace", "level": "info", "text": f"$ {cmd}\n{tr.stdout_tail[-1200:]}"}, stage="trace")
        if tr.exit_code not in (0, None) and not tr.timed_out:
            self.emit("log", {"stream": "trace", "level": "warn",
                              "text": f"entry command exited with code {tr.exit_code}\n{tr.stdout_tail[-600:]}"})
        self.stage("trace", "done", f"{tr.calls:,} calls")
        top = profile[0] if profile else None
        self.step("trace", f"Traced {cmd}", "done", f"{tr.calls:,} calls in {tr.total_s:.1f}s"
                  + (f"; hottest: {top['id'].split('::')[-1]} ({top['share'] * 100:.0f}%)" if top else ""))

    # ------------------------------------------------------------ rank
    def do_rank(self) -> None:
        from . import rank
        recs = self.recs()
        self.stage("rank", "running", caption="Scoring hotspots: time share x eligibility x expected benefit")
        profile = {"total_s": self.trace.total_s, "per_fn": self.trace.per_fn} if self.trace and self.trace.ok else None
        try:
            ordered = rank.rank(recs, profile, self.emit)          # emits rank.done
        except Exception as ex:
            self.err("rank", ex)
            ordered = sorted(recs, key=lambda r: -r.score.get("total", 0))
        seen = {r.id for r in ordered}
        self.js.records = {r.id: r for r in ordered + [r for r in recs if r.id not in seen]}
        for r in ordered:
            self.save(r)
        n_dec = sum(1 for r in ordered if r.status == "declined")
        self.stage("rank", "done", f"{len(ordered)} ranked")
        best = next((r for r in ordered if r.eligibility != "not_eligible"), None)
        self.step("rank", "Ranked hotspots", "done",
                  (f"top: {best.name} (score {best.score.get('total', 0):.2f})" if best else "nothing eligible")
                  + (f"; {n_dec} declined (boundary cost)" if n_dec else ""))

    def candidates(self) -> List[FunctionRecord]:
        """Functions we will compile: verifiable, fixed-fixable, and declined (probe)."""
        return [r for r in self.recs() if r.status in ("pending", "declined") and r.eligibility != "not_eligible"
                and r.private.get("module_src")]

    # ------------------------------------------------------------ fix
    def llm_client(self):
        from . import llm
        if not self.opt.get("llm", True):
            return None
        model = self.opt.get("model") or self.settings.get("model")
        try:
            return llm.make_client(model, OFFLINE_DIR / "llm" if self.offline else None, settings=self.settings)
        except Exception as ex:
            self.err("llm", ex)
            return None

    def do_fix(self) -> None:
        from . import annotate, fixer, scan
        js, ws = self.js, self.ws
        fixables = [r for r in self.recs() if r.eligibility == "fixable" and r.status in ("fixable", "declined")]
        self.stage("fix", "running", caption="Fixing near-misses: annotate from observed types, else ask the LLM for a PySub rewrite")
        self.llm = self.llm_client() if fixables else None
        fx = None
        if fixables and self.llm is not None:
            try:
                fx = fixer.Fixer(self.llm, self.offline, OFFLINE_DIR / "llm" if self.offline else None)
            except Exception as ex:
                self.err("fixer", ex)
        done = 0
        for r in self.recs():                                   # eligible-as-written: just extract
            if r.eligibility == "verifiable" and r.status in ("pending", "declined"):
                try:
                    e = scan.extract_pysub(r, ws)
                    if e.ok:
                        r.private["module_src"] = e.source
                        r.sources["pysub"] = e.source
                    else:
                        r.status, r.reason = "not_eligible", self._first_diag(e)
                        r.diagnostics = e.diagnostics
                except Exception as ex:
                    self.fail_fn(r, "extract", ex)
                self.save(r)
        for i, r in enumerate(fixables):
            js.check()
            self.fn_step(r, "typechecker rejected as written", "running",
                         caption=f"{r.name}: {r.reason or 'rejected'}")
            try:
                ok = self.fix_one(r, annotate, fx, scan)
            except Cancelled:
                raise
            except Exception as ex:
                self.fail_fn(r, "fix", ex)
                ok = False
            done += ok
            self.save(r)
            self.stage("fix", "running", f"{done}/{len(fixables)}", progress=(i + 1) / max(len(fixables), 1))
        if not fixables:
            self.stage("fix", "skipped", "nothing to fix")
        else:
            self.stage("fix", "done", f"{done}/{len(fixables)}")
            self.step("fix", "Fixed near-misses", "done", f"{done} of {len(fixables)} fixed"
                      + ("" if self.llm is not None else "; LLM fixer disabled"))

    @staticmethod
    def _first_diag(e) -> str:
        d = (e.diagnostics or [{}])[0]
        return f"line {d.get('line', '?')}: {d.get('msg', 'typecheck failed')}"

    def fix_one(self, r: FunctionRecord, annotate, fx, scan) -> bool:
        ws = self.ws
        # 1. annotation from observed types
        ann = None
        try:
            ann = annotate.annotate(r, r.trace) if r.trace else None
        except Exception as ex:
            self.err(f"annotate:{r.id}", ex)
        if ann:
            r.sources["annotated"] = ann
            e = scan.extract_pysub(r, ws, annotated_src=ann)
            if e.ok:
                return self._fixed(r, e, "annotated from observed types", rewrites=False)
            r.diagnostics = e.diagnostics
        # 2. LLM rewrite
        if fx is None:
            if r.status == "declined":                      # probe not possible without a fix
                return False
            r.reason = (r.reason or "needs a rewrite").rstrip(".") + " (LLM fixer disabled)"
            self.emit("fix.done", {"id": r.id, "ok": False, "reason": r.reason}, stage="fix")
            self.fn_step(r, "LLM fixer disabled", "info")
            return False
        res = fx.fix(r, ws, self.emit)
        if res.attempts:
            r.rewrites = list(res.attempts)
        if res.ok and res.pysub:
            e = scan.extract_pysub(r, ws, override_src=res.pysub)
            if e.ok:
                r.line_map_ok = False
                return self._fixed(r, e, f"LLM rewrite accepted after {len(r.rewrites)} attempt(s)", rewrites=True)
            res.reason = self._first_diag(e)
        r.status, r.eligibility = "not_eligible", "not_eligible"
        r.reason = res.reason or "the LLM could not produce valid PySub"      # fixer already emitted fix.done
        self.fn_step(r, "rewrite failed", "failed")
        return False

    def _fixed(self, r, e, why: str, rewrites: bool) -> bool:
        r.private["module_src"] = e.source
        r.sources["pysub"] = e.source
        r.diagnostics = []
        if r.status == "fixable":
            r.status, r.reason = "pending", None
        if not rewrites:
            self.emit("fix.done", {"id": r.id, "ok": True, "reason": why}, stage="fix",
                      caption=f"{r.name}: {why}")
        self.fn_step(r, "PySub ok")
        return True

    # ------------------------------------------------------------ compile
    def do_compile(self, cands: List[FunctionRecord]) -> None:
        try:
            from pythia.libmode import build_library
        except Exception as ex:
            self.stage("compile", "failed", "library mode unavailable")
            self.err("compile", ex)
            return
        js, ws = self.js, self.ws
        extra = [str(OFFLINE_DIR / "so")] if self.offline and (OFFLINE_DIR / "so").is_dir() else []
        self.stage("compile", "running", caption="Transpiling PySub to C++17 and building pybind11 extensions")
        ok_n = 0
        for i, r in enumerate(cands):
            js.check()
            out = ws.root / "build" / splice_name(r)
            try:
                res = build_library(r.private["module_src"], [r.name], str(out), None, r.file, True,
                                    str(js.home / "build-cache"), extra)
            except Exception as ex:
                self.fail_fn(r, "compile", ex)
                continue
            d = res.to_dict() if hasattr(res, "to_dict") else dict(res)
            r.sources["cpp"], r.sources["wrapper_cpp"] = d.get("cpp"), d.get("wrapper_cpp")
            r.fidelity = d.get("fidelity") or []
            r.cpp_line_map = d.get("cpp_line_map") or {}
            cpp_path = Path(d.get("cpp_path") or out / f"{d.get('modname')}.cpp")
            r.build = {"ok": bool(d.get("ok") and d.get("so_path")), "module": d.get("modname"),
                       "so": d.get("so_path"), "cached": bool(d.get("cached")), "compile_s": d.get("compile_s") or 0.0,
                       "log": d.get("build_log") or "", "exposed": d.get("exposed") or [],
                       "cpp_path": str(cpp_path) if cpp_path.exists() else None, "error": d.get("error")}
            for dg in d.get("diagnostics") or []:
                dg.setdefault("phase", "compile")
            if not r.build["ok"]:
                r.diagnostics = d.get("diagnostics") or r.diagnostics
                msg = (r.diagnostics[0]["msg"] if r.diagnostics else None) or d.get("error") or "build failed"
                if r.diagnostics:
                    r.status, r.eligibility = "not_eligible", "not_eligible"
                    r.reason = f"compiler rejected the function: line {r.diagnostics[0].get('line')}: {msg}"
                else:
                    r.status, r.reason, r.decision = "failed", f"C++ build failed: {str(msg)[:300]}", "rejected"
                self.fn_step(r, "compile failed", "failed")
            else:
                ok_n += 1
                self.fn_step(r, "C++ ok" + (" (cached)" if r.build["cached"] else f" ({r.build['compile_s']:.1f}s)"))
            self.emit("compile.done", {"id": r.id, "ok": r.build["ok"], "cached": r.build["cached"],
                                       "compile_s": r.build["compile_s"], "module": r.build["module"],
                                       "error": None if r.build["ok"] else r.reason,
                                       "diagnostics": d.get("diagnostics") or []}, stage="compile",
                      caption=(f"{r.name}: built " + ("from cache" if r.build["cached"] else f"in {r.build['compile_s']:.1f}s"))
                      if r.build["ok"] else f"{r.name}: compile failed")
            self.emit("log", {"stream": "build", "level": "info" if r.build["ok"] else "error",
                              "text": f"$ c++ -std=c++17 -O3 -flto -shared  {r.build['module']}  ({r.name})"
                                      + "\n" + ((r.build.get("log") or "").strip()[-1500:] or "ok")}, stage="compile")
            self.save(r)
            self.stage("compile", "running", f"{ok_n}/{len(cands)}", progress=(i + 1) / len(cands))
        self.stage("compile", "done" if cands else "skipped", f"{ok_n}/{len(cands)}")

    # ------------------------------------------------------------ verify
    def samples_for(self, r: FunctionRecord) -> Optional[Path]:
        d = self.trace.samples_dir if self.trace and self.trace.ok else None
        return trace_mod.samples_path(d, r.id)

    def do_verify(self, cands: List[FunctionRecord]) -> None:
        js, ws = self.js, self.ws
        todo = [r for r in cands if r.build and r.build.get("ok") and r.status != "declined"]
        self.stage("verify", "running", caption="Oracle replay: recorded calls through Python and through the compiled code")
        good = 0
        for i, r in enumerate(todo):
            js.check()
            try:
                res = replay_mod.replay(r, ws, r.build["so"], r.build["module"], self.samples_for(r))
            except Exception as ex:
                self.fail_fn(r, "verify", ex)
                continue
            status = res["status"]
            r.replay = {k: res.get(k) for k in ("total", "matched", "exc_matches", "first_mismatch",
                                                "skipped", "source", "status", "error") if k in res}
            r.status = status
            if status == "failed":
                r.decision = "rejected"
                fm = res.get("first_mismatch")
                r.reason = ("Replay mismatch (" + fm["kind"] + f") on args {fm['args']}: python {fm['python']}, "
                            f"compiled {fm['cpp']}") if fm else ("Replay failed: " + str(res.get("error")))
                self.fn_step(r, f"replay FAILED ({res['matched']}/{res['total']})", "failed",
                             caption=f"{r.name}: compiled code disagrees with Python, auto-rejected")
            else:
                good += 1
                r.reason = None
                note = " (guarded: has overflow/divergence sites)" if status == "guarded" else ""
                self.fn_step(r, f"{res['matched']}/{res['total']} replays match{note}",
                             caption=f"{r.name}: {res['matched']} of {res['total']} replays match")
            self.emit("verify.result", {"id": r.id, "status": status, "total": res["total"],
                                        "matched": res["matched"], "first_mismatch": res.get("first_mismatch")},
                      stage="verify")
            self.save(r)
            self.stage("verify", "running", f"{good}/{len(todo)}", progress=(i + 1) / len(todo))
        self.stage("verify", "done" if todo else "skipped", f"{good}/{len(todo)}")

    # ------------------------------------------------------------ benchmark
    def do_bench(self, cands: List[FunctionRecord]) -> None:
        js, ws = self.js, self.ws
        todo = [r for r in cands if r.build and r.build.get("ok") and r.status in ("verified", "guarded", "declined")]
        self.stage("benchmark", "running", caption="Timing Python vs compiled on the replayed inputs")
        for i, r in enumerate(todo):
            js.check()
            probe = r.status == "declined"
            try:
                b = bench_mod.bench_function(r, ws, r.build["so"], r.build["module"], self.samples_for(r))
            except Exception as ex:
                self.fail_fn(r, "bench", ex)
                continue
            r.bench = b
            if "error" in b:
                self.emit("log", {"stream": "system", "level": "warn", "text": f"benchmark {r.id}: {b['error']}"})
                self.fn_step(r, "benchmark failed")
                self.save(r)
                continue
            sp = b["speedup"]
            if probe:
                r.probe_speedup = sp
            elif sp < SLOWER_THAN:
                r.status, r.probe_speedup, r.speedup = "declined", sp, None
                r.reason = f"Compiled version measured {sp:.2f}x ({'slower than' if sp < 1 else 'no faster than'} Python): marshalling cost outweighs the saving"
                probe = True
            else:
                r.speedup = sp
            self.emit("bench.result", {"id": r.id, "py_ms": b["py_ms"], "cpp_ms": b["cpp_ms"], "speedup": sp,
                                       "calls_timed": b["calls_timed"], "probe": probe}, stage="benchmark",
                      caption=f"{r.name}: {fmt_x(sp)} faster" + (" (probe only)" if probe else "") if sp >= 1
                      else f"{r.name}: {sp:.2f}x, not worth compiling")
            self.fn_step(r, fmt_x(sp) + (" probe" if probe else ""), "done" if not probe else "info")
            self.save(r)
            self.stage("benchmark", "running", progress=(i + 1) / len(todo))
        self.stage("benchmark", "done" if todo else "skipped",
                   (fmt_x(geomean([r.speedup for r in todo if r.speedup])) + " geomean") if todo else None)

    # ------------------------------------------------------------ splice
    def do_splice(self) -> None:
        ws = self.ws
        self.stage("splice", "running", caption="Replacing each verified function with a thin dispatch to the compiled module")
        files: Dict[str, List[str]] = {}
        for r in self.recs():
            if r.status in ("verified", "guarded") and r.decision != "rejected" and r.build and r.build.get("ok"):
                try:
                    splice_mod.apply(ws, r, r.build["module"], r.build["so"])
                    files.setdefault(r.file, []).append(r.id)
                except Exception as ex:
                    self.err(f"splice:{r.id}", ex)
                    r.decision, r.splice = "rejected", {"applied": False, "diff": ""}
                    r.reason = f"splice failed: {ex}"
                self.save(r)
        n = sum(len(v) for v in files.values())
        self.emit("splice.ready", {"files": [{"path": p, "functions": f} for p, f in files.items()],
                                   "functions": n}, stage="splice",
                  caption=f"{n} function(s) spliced into the workspace copy: review and accept")
        self.stage("splice", "done" if n else "skipped", f"{n} functions")
        for r in self.recs():
            if r.status in ("verified", "guarded"):
                self.fn_step(r, "spliced" if r.splice and r.splice.get("applied") else "", "done")

    # ------------------------------------------------------------ e2e
    def do_e2e(self) -> None:
        js, ws = self.js, self.ws
        cmd = (self.opt.get("trace_cmd") or "").strip()
        spliced = [r for r in self.recs() if r.splice and r.splice.get("applied")]
        if not cmd or not spliced:
            return
        self.stage("benchmark", "running", "end-to-end", caption=f"Running `{cmd}` before and after the splice")
        self.step("e2e", "End-to-end benchmark", "running", cmd)
        tmo = float(self.opt.get("trace_timeout_s") or 60) * 1.5
        runs = 3 if self.trace and self.trace.total_s < 4 else 2 if self.trace and self.trace.total_s < 12 else 1
        try:
            before = bench_mod.bench_e2e(ws, cmd, "original", tmo, runs, js.cancelled)
            js.check()
            after = bench_mod.bench_e2e(ws, cmd, "work", tmo, runs, js.cancelled)
        except Cancelled:
            raise
        except Exception as ex:
            self.err("e2e", ex)
            self.stage("benchmark", "done", "end-to-end failed")
            return
        ok = bool(before["ok"] and after["ok"])
        sp = before["seconds"] / after["seconds"] if after["seconds"] > 0 else None
        match = before["stdout_hash"] == after["stdout_hash"]
        js.e2e = {"cmd": cmd, "before_s": before["seconds"], "after_s": after["seconds"], "speedup": sp,
                  "output_match": match, "ok": ok}
        js.persist_job()
        self.emit("bench.e2e", js.e2e, stage="benchmark",
                  caption=f"End to end: {before['seconds']:.1f}s -> {after['seconds']:.1f}s ({fmt_x(sp)})"
                  + ("" if match else ", output differs!"))
        self.step("e2e", "End-to-end benchmark", "done" if ok and match else "failed",
                  f"{before['seconds']:.2f}s -> {after['seconds']:.2f}s ({fmt_x(sp)})"
                  + ("" if match else "; stdout differs from the original run"))
        self.stage("benchmark", "done", fmt_x(sp))


def splice_name(r: FunctionRecord) -> str:
    from .models import fid_hash
    return fid_hash(r.id)
