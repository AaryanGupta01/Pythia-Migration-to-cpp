"""The Engine facade (CONTRACTS §5): the only thing the server imports from the analyzer."""
from __future__ import annotations

import base64
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from . import export as export_mod
from . import splice as splice_mod
from .jobstate import JobState, atomic_write
from .models import FunctionRecord, Workspace
from .pipeline import OFFLINE_DIR, Pipeline

LANG = {".py": "python", ".md": "markdown", ".json": "json", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml",
        ".txt": "plaintext", ".cfg": "ini", ".ini": "ini", ".sh": "shell", ".cpp": "cpp", ".hpp": "cpp",
        ".c": "c", ".h": "c", ".js": "javascript", ".ts": "typescript", ".html": "html", ".css": "css",
        ".csv": "plaintext"}
HIDDEN_DIRS = {"__pycache__", ".git", "_pythia_accel", "node_modules", ".venv", "venv", ".pytest_cache"}
MAX_FILE = 2_000_000


def default_home() -> Path:
    return Path(os.environ.get("PYTHIA_HOME") or Path.home() / ".pythia-studio")


class Engine:
    def __init__(self, home: Optional[str] = None):
        from .envfile import load_env
        load_env()
        from . import samples
        self.home = Path(home) if home else default_home()
        (self.home / "jobs").mkdir(parents=True, exist_ok=True)
        (self.home / "workspaces").mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, JobState] = {}
        self._lock = threading.RLock()
        self._env_cache: Optional[Dict[str, Any]] = None
        samples.seed(self.home)

    # ------------------------------------------------------------ settings / env
    def _settings_full(self) -> Dict[str, Any]:
        s = {"offline": False, "model": None, "api_key": None, "provider": "auto"}
        p = self.home / "settings.json"
        if p.exists():
            try:
                s.update(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass
        return s

    def _public_settings(self, s: Dict[str, Any]) -> Dict[str, Any]:
        out = {k: v for k, v in s.items() if k != "api_key"}
        out["has_api_key"] = bool(s.get("api_key") or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("GROQ_API_KEY"))
        return out

    def settings(self) -> Dict[str, Any]:
        return self._public_settings(self._settings_full())

    def update_settings(self, patch: Dict[str, Any]) -> Dict[str, Any]:
        s = self._settings_full()
        for k in ("offline", "model", "api_key", "provider"):
            if k in patch:
                s[k] = patch[k] if patch[k] != "" else None
        atomic_write(self.home / "settings.json", json.dumps(s, indent=1))
        try:
            os.chmod(self.home / "settings.json", 0o600)
        except OSError:
            pass
        return self._public_settings(s)

    def env(self) -> Dict[str, Any]:
        s = self._settings_full()
        cxx = None
        for c in ("c++", "g++", "clang++"):
            p = shutil.which(c)
            if p:
                try:
                    v = subprocess.run([p, "--version"], capture_output=True, text=True, timeout=10).stdout.splitlines()[0]
                except Exception:
                    v = ""
                cxx = {"found": True, "name": c, "version": v, "hint": None}
                break
        if not cxx:
            cxx = {"found": False, "name": None, "version": None,
                   "hint": "Install a C++17 compiler: sudo apt install build-essential (Linux/WSL) or xcode-select --install (macOS)"}
        try:
            import pybind11  # noqa: F401
            pyb = True
        except Exception:
            pyb = False
        from . import llm as llm_mod
        offline_available = (OFFLINE_DIR / "llm").is_dir() or (OFFLINE_DIR / "so").is_dir()
        offline = bool(s.get("offline") or os.environ.get("PYTHIA_OFFLINE") == "1")
        llm_info = llm_mod.llm_status(s.get("model"), offline and offline_available, OFFLINE_DIR / "llm", settings=s)
        if offline and not llm_info["enabled"]:
            llm_info = llm_mod.llm_status(s.get("model"), False, None, settings=s)
        wsl = False
        try:
            wsl = "microsoft" in Path("/proc/version").read_text().lower()
        except Exception:
            pass
        return {"compiler": cxx, "pybind11": pyb, "python": sys.version.split()[0], "platform": platform.platform(),
                "llm": llm_info,
                "offline_available": offline_available, "offline": offline, "wsl": wsl}

    # ------------------------------------------------------------ jobs
    def start_job(self, input: Dict[str, Any], options: Optional[Dict[str, Any]], emit: Optional[Callable]) -> str:
        job_id = uuid.uuid4().hex[:8]
        ws_id = uuid.uuid4().hex[:8]
        opts = {"trace_cmd": None, "trace_timeout_s": 60, "offline": False, "llm": True,
                "model": self._settings_full().get("model"), "pace_ms": 0}
        opts.update(options or {})
        if input.get("kind") == "demo":
            from .demos import resolve
            demo = resolve(input.get("name"))              # each demo ships a known entry point and a time budget
            if not (opts.get("trace_cmd") or "").strip():
                opts["trace_cmd"] = demo["trace_cmd"]
            opts["trace_timeout_s"] = max(float(opts.get("trace_timeout_s") or 0), float(demo["trace_timeout_s"]))
        js = JobState(job_id, self.home, input, opts, ws_id, emit)
        with self._lock:
            self._jobs[job_id] = js
        js.persist_job()

        def run():
            p = Pipeline(js, self._settings_full())
            try:
                p.run()
            finally:
                self._remember_recent(js)

        threading.Thread(target=run, daemon=True, name=f"pythia-job-{job_id}").start()
        return job_id

    def _remember_recent(self, js: JobState) -> None:
        if not js.ws:
            return
        p = self.home / "recent.json"
        try:
            items = json.loads(p.read_text(encoding="utf-8")) if p.exists() else []
        except Exception:
            items = []
        ws = js.ws
        items = [i for i in items if i.get("workspace_id") != ws.ws_id and
                 not (i.get("origin") and i.get("origin") == ws.origin and i.get("input_kind") == ws.input_kind)]
        items.insert(0, {"workspace_id": ws.ws_id, "ws_id": ws.ws_id, "name": ws.name, "input_kind": ws.input_kind,
                         "origin": ws.origin, "job_id": js.job_id, "py_files": len(ws.py_files), "ts": time.time()})
        atomic_write(p, json.dumps(items[:20], indent=1))

    def _job(self, job_id: str) -> JobState:
        with self._lock:
            js = self._jobs.get(job_id)
            if js:
                return js
            d = self.home / "jobs" / job_id
            if not (d / "job.json").exists():
                raise KeyError(f"unknown job {job_id}")
            meta = json.loads((d / "job.json").read_text(encoding="utf-8"))
            js = JobState.__new__(JobState)
            js.job_id, js.home, js.options = job_id, self.home, meta.get("options", {})
            js.input, js.raw_input = meta.get("input", {}), meta.get("input", {})
            js.ws_id, js.name = meta.get("workspace_id"), meta.get("name")
            js.dir, js.lock = d, threading.RLock()
            js.state, js.started, js.finished = meta.get("state", "failed"), meta.get("started"), meta.get("finished")
            if js.state == "running":                       # crashed / restarted mid-run
                js.state = "failed"
            js.summary, js.e2e = meta.get("summary"), meta.get("e2e")
            js.cancel_ev, js.ext_emit, js.stage_cache, js.pace, js.seq = threading.Event(), None, {}, 0, 0
            js._events = None
            js.ws = self._load_ws(js.ws_id, js.name)
            js.records = {}
            js.load_records()
            self._jobs[job_id] = js
            return js

    def _load_ws(self, ws_id: Optional[str], name: Optional[str]) -> Optional[Workspace]:
        if not ws_id:
            return None
        root = self.home / "workspaces" / ws_id
        if not root.is_dir():
            return None
        meta = {}
        try:
            meta = json.loads((root / "workspace.json").read_text(encoding="utf-8"))
        except Exception:
            pass
        return Workspace(ws_id=ws_id, name=meta.get("name") or name or ws_id, root=root,
                         original=root / "original", work=root / "work",
                         py_files=meta.get("py_files") or [], skipped=meta.get("skipped") or [],
                         input_kind=meta.get("input_kind", ""), origin=meta.get("origin", ""))

    def cancel(self, job_id: str) -> None:
        js = self._job(job_id)
        js.cancel_ev.set()

    def job(self, job_id: str) -> Dict[str, Any]:
        js = self._job(job_id)
        d = js.job_dict()
        if js.state != "running" and not d.get("summary"):
            d["summary"] = Pipeline(js).summary()
        return d

    def jobs(self) -> List[Dict[str, Any]]:
        out = []
        for d in sorted((self.home / "jobs").iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                out.append(self.job(d.name))
            except Exception:
                continue
        return out

    def recent(self) -> List[Dict[str, Any]]:
        p = self.home / "recent.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []

    def events(self, job_id: str, after: int = 0) -> Dict[str, Any]:
        """Full event log from disk (helper for REST replay)."""
        evs, last = [], 0
        p = self._job(job_id).dir / "events.jsonl"
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                last = e["seq"]
                if e["seq"] > after:
                    evs.append(e)
        return {"events": evs, "last_seq": last}

    # ------------------------------------------------------------ functions
    def functions(self, job_id: str) -> List[Dict[str, Any]]:
        js = self._job(job_id)
        with js.lock:
            return [r.to_summary() for r in js.records.values()]

    def function(self, job_id: str, fid: str, stages: bool = False) -> Dict[str, Any]:
        js = self._job(job_id)
        with js.lock:
            rec = js.records.get(fid)
            if rec is None:
                raise KeyError(f"unknown function {fid}")
            d = rec.to_dict()
        if stages:
            src = rec.sources.get("pysub") or rec.sources.get("annotated") or rec.sources.get("original")
            key = (fid, hash(src))
            if key not in js.stage_cache:
                try:
                    from pythia.stages import dump_stages
                    js.stage_cache[key] = dump_stages(src or "", filename=rec.file) if src else {"ok": False, "diagnostics": []}
                except Exception as ex:
                    js.stage_cache[key] = {"ok": False, "error": f"{type(ex).__name__}: {ex}", "diagnostics": []}
            d["stages"] = js.stage_cache[key]
        return d

    def decide(self, job_id: str, fid: str, decision: str) -> Dict[str, Any]:
        from . import samples
        if decision not in ("accepted", "rejected", "pending"):
            raise ValueError(f"bad decision {decision!r}")
        js = self._job(job_id)
        with js.lock:
            if fid == "all":
                targets = [r for r in js.records.values() if r.status in ("verified", "guarded")]
            else:
                if fid not in js.records:
                    raise KeyError(f"unknown function {fid}")
                targets = [js.records[fid]]
            for r in targets:
                if r.status not in ("verified", "guarded"):
                    continue                                   # failed/declined/etc. can't be accepted
                try:
                    if samples.is_sample(js.dir):               # bundled sample: nothing to splice, just record
                        pass
                    elif decision == "rejected":
                        splice_mod.revert(js.ws, r)
                    else:
                        splice_mod.apply(js.ws, r, r.build["module"], r.build["so"])
                    r.decision = decision
                except Exception as ex:
                    js.emit("error", {"where": f"decide:{r.id}", "message": str(ex), "fatal": False})
                js.persist(r)
        return {"functions": self.functions(job_id)}

    # ------------------------------------------------------------ workspace files
    def _ws(self, ws_id: str) -> Workspace:
        ws = self._load_ws(ws_id, None)
        if ws is None:
            raise KeyError(f"unknown workspace {ws_id}")
        return ws

    def _latest_records(self, ws_id: str) -> Dict[str, FunctionRecord]:
        best, best_t = None, -1.0
        for js in list(self._jobs.values()):
            if js.ws_id == ws_id and (js.started or 0) > best_t:
                best, best_t = js, js.started or 0
        if best is None:
            for d in (self.home / "jobs").iterdir():
                try:
                    m = json.loads((d / "job.json").read_text(encoding="utf-8"))
                except Exception:
                    continue
                if m.get("workspace_id") == ws_id and (m.get("started") or 0) > best_t:
                    best_t, best = m.get("started") or 0, d.name
            if best is not None:
                best = self._job(best)
        return best.records if best else {}

    def tree(self, ws_id: str) -> List[Dict[str, Any]]:
        ws = self._ws(ws_id)
        recs = self._latest_records(ws_id)
        hot: Dict[str, int] = {}
        acc: Dict[str, int] = {}
        for r in recs.values():
            if r.status in ("verified", "guarded", "fixable", "declined", "failed"):
                hot[r.file] = hot.get(r.file, 0) + 1
            if r.splice and r.splice.get("applied"):
                acc[r.file] = acc.get(r.file, 0) + 1
        count = [0]

        def walk(d: Path, rel: str) -> List[Dict[str, Any]]:
            nodes = []
            try:
                entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
            except OSError:
                return nodes
            for p in entries:
                if p.name in HIDDEN_DIRS or p.name.endswith(".pyc") or count[0] > 6000:
                    continue
                count[0] += 1
                r = f"{rel}/{p.name}" if rel else p.name
                if p.is_dir():
                    ch = walk(p, r)
                    nodes.append({"path": r, "name": p.name, "type": "dir", "children": ch,
                                  "badges": {"hotspots": sum(c["badges"]["hotspots"] for c in ch),
                                             "accelerated": sum(c["badges"]["accelerated"] for c in ch)}})
                else:
                    nodes.append({"path": r, "name": p.name, "type": "file",
                                  "badges": {"hotspots": hot.get(r, 0), "accelerated": acc.get(r, 0)}})
            return nodes

        return walk(ws.work if ws.work.exists() else ws.original, "")

    def read_file(self, ws_id: str, rel: str, version: str = "work") -> Dict[str, Any]:
        ws = self._ws(ws_id)
        base = (ws.work if version == "work" else ws.original).resolve()
        p = (base / rel).resolve()
        if base not in p.parents or not p.is_file():
            raise FileNotFoundError(rel)
        data = p.read_bytes()
        try:
            text = data[:MAX_FILE].decode("utf-8")
        except UnicodeDecodeError:
            text = "(binary file)"
        return {"path": rel, "content": text, "language": LANG.get(p.suffix.lower(), "plaintext"),
                "size": len(data)}

    def file_diff(self, job_id: str, rel: str) -> Dict[str, str]:
        js = self._job(job_id)
        out = {}
        for k, base in (("original", js.ws.original), ("modified", js.ws.work)):
            p = (base / rel)
            try:
                out[k] = p.read_text(encoding="utf-8") if p.is_file() else ""
            except UnicodeDecodeError:
                out[k] = ""
        return out

    def list_dir(self, path: Optional[str]) -> Dict[str, Any]:
        p = Path(path).expanduser() if path else Path.home()
        if not p.is_dir():
            p = p.parent if p.parent.is_dir() else Path.home()
        entries = []
        try:
            for c in sorted(p.iterdir(), key=lambda c: (not c.is_dir(), c.name.lower())):
                if c.name.startswith(".") and c.name not in (".github",):
                    continue
                try:
                    entries.append({"name": c.name, "type": "dir" if c.is_dir() else "file"})
                except OSError:
                    continue
                if len(entries) >= 1000:
                    break
        except OSError:
            pass
        return {"path": str(p.resolve()), "parent": str(p.resolve().parent) if p.resolve().parent != p.resolve() else None,
                "entries": entries}

    # ------------------------------------------------------------ export / report
    def export(self, job_id: str, dest: Optional[str] = None, zip: bool = False) -> str:
        from . import samples
        js = self._job(job_id)
        if samples.is_sample(js.dir):
            raise ValueError("This is the bundled sample run (nothing was compiled on this machine). Run the demo project to export a real accelerated copy.")
        with js.lock:
            recs = list(js.records.values())
            jd = self._report_job(js)
        d = Path(dest).expanduser() if dest else None
        if d is not None and zip and d.is_dir():
            d = d / f"{js.ws.name}-accelerated.zip"
        try:
            out = export_mod.export(js.ws, recs, d, zip, jd)
        except Exception as ex:
            js.emit("error", {"where": "export", "message": f"{type(ex).__name__}: {ex}", "fatal": False})
            raise
        js.emit("export.done", {"path": str(out), "zip": zip, "files": export_mod.count_files(out)},
                stage="export", caption=f"Exported the accelerated project to {out}")
        return str(out)

    def _report_job(self, js: JobState) -> Dict[str, Any]:
        d = js.job_dict()
        if not d.get("summary"):
            d["summary"] = Pipeline(js).summary()
        return d

    def report(self, job_id: str) -> Dict[str, Any]:
        js = self._job(job_id)
        with js.lock:
            recs = list(js.records.values())
            jd = self._report_job(js)
        return {"markdown": export_mod.report_md(jd, recs),
                "json": {"job": jd, "functions": [r.to_dict() for r in recs]}}
