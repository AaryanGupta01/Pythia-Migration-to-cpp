"""Oracle replay: recorded (or synthesised) calls through the ORIGINAL Python
function and the compiled .so in a subprocess worker; compare return value,
exception class and post-call argument state (floats bitwise).  CONTRACTS §7."""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from . import codec
from .models import FunctionRecord, Workspace

WORKER = Path(__file__).parent / "_replay_worker.py"
MIN_CALLS = 50                      # top up sparse traces with synthesised inputs


def param_types(rec: FunctionRecord) -> Optional[List[str]]:
    """Type strings of the compiled signature: libmode's `exposed`, else annotations."""
    for e in (rec.build or {}).get("exposed") or []:
        if e.get("name") == rec.name:
            return list(e["params"])
    for src in (rec.sources.get("pysub"), rec.sources.get("annotated"), rec.sources.get("original")):
        if not src:
            continue
        try:
            for n in ast.parse(_dedent(src)).body:
                if isinstance(n, ast.FunctionDef) and n.name == rec.name:
                    out = []
                    for a in n.args.args:
                        if a.annotation is None:
                            raise ValueError
                        out.append(_norm_type(ast.unparse(a.annotation)))
                    return out
        except (SyntaxError, ValueError):
            continue
    return None


def _dedent(s: str) -> str:
    import textwrap
    return textwrap.dedent(s)


def _norm_type(t: str) -> str:
    for a, b in (("List[", "list["), ("Dict[", "dict["), ("typing.", ""), (", ", ","), (" ", "")):
        t = t.replace(a, b)
    return t


def prepare_calls(rec: FunctionRecord, samples_path: Optional[Path], n_max: int, dest: Path,
                  min_calls: int = MIN_CALLS) -> Tuple[Path, int, str]:
    """Write the calls JSONL the worker reads; returns (path, count, source)."""
    calls: List[dict] = []
    if samples_path and Path(samples_path).exists():
        for line in Path(samples_path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    calls.append(json.loads(line))
                except ValueError:
                    pass
    if len(calls) > n_max:
        step = len(calls) / n_max
        calls = [calls[int(i * step)] for i in range(n_max)]
    source = "trace"
    if len(calls) < min_calls:
        pt = param_types(rec)
        if pt is not None:
            try:
                extra = codec.synthesize(pt, min_calls - len(calls) if calls else min_calls + 30)
                calls += [{"args": a} for a in extra]
                source = "trace+synthesized" if len(calls) > len(extra) else "synthesized"
            except codec.Unencodable:
                pass
    dest.write_text("\n".join(json.dumps(c) for c in calls), encoding="utf-8")
    return dest, len(calls), source


def run_worker(job: Dict[str, Any], ws: Workspace, timeout_s: float) -> Dict[str, Any]:
    """Run the worker; always returns a dict (with "error" on crash/timeout/crash index)."""
    tmp = ws.root / "tmp"
    tmp.mkdir(exist_ok=True)
    fd, jp = tempfile.mkstemp(suffix=".json", dir=tmp)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(job, f)
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.pop("PYTHONPATH", None)
    try:
        p = subprocess.run([sys.executable, str(WORKER), jp], cwd=str(ws.original), env=env,
                           capture_output=True, text=True, timeout=timeout_s)
    except subprocess.TimeoutExpired as ex:
        out = ex.stdout.decode("utf-8", "replace") if isinstance(ex.stdout, bytes) else (ex.stdout or "")
        return {"error": f"timed out after {timeout_s:.0f}s (compiled code may loop forever)",
                "crash_index": _last_index(out), "timeout": True}
    finally:
        try:
            os.unlink(jp)
        except OSError:
            pass
    for line in reversed(p.stdout.splitlines()):
        if line.startswith("RESULT "):
            return json.loads(line[7:])
    sig = f" (signal {-p.returncode})" if p.returncode < 0 else ""
    return {"error": f"worker crashed{sig}: {p.stderr.strip()[-300:]}", "crash_index": _last_index(p.stdout),
            "crashed": True}


def _last_index(out: str) -> Optional[int]:
    for line in reversed(out.splitlines()):
        if line.startswith("@") and line[1:].isdigit():
            return int(line[1:])
    return None


def replay(rec: FunctionRecord, ws: Workspace, so_path, modname: str,
           samples_path: Optional[Path] = None, n_max: int = 500, timeout_s: float = 180) -> Dict[str, Any]:
    tmp = ws.root / "tmp"
    tmp.mkdir(exist_ok=True)
    calls_path, n, source = prepare_calls(rec, samples_path, n_max, tmp / f"calls_{rec.name}.jsonl")
    base = {"total": 0, "matched": 0, "exc_matches": 0, "first_mismatch": None, "skipped": 0,
            "source": source, "status": "failed"}
    if n == 0:
        base["error"] = "no recorded calls and no annotated signature to synthesise inputs from"
        return base
    r = run_worker({"mode": "replay", "original": str(ws.original), "file": rec.file, "name": rec.name,
                    "so": str(so_path), "modname": modname, "calls": str(calls_path), "n_max": n_max},
                   ws, timeout_s)
    if "error" in r:
        base["error"] = r["error"]
        ci = r.get("crash_index")
        if ci is not None:
            lines = calls_path.read_text(encoding="utf-8").splitlines()
            if ci < len(lines):
                args = codec.decode(json.loads(lines[ci])["args"])
                base["first_mismatch"] = {"args": codec.display_args(args), "kind": "exception",
                                          "python": "(not evaluated)", "cpp": r["error"][:120]}
                base["total"] = ci + 1
        return base
    r["source"] = source
    nonexact = any(f.get("severity") in ("guarded", "divergent") for f in rec.fidelity)
    if r["total"] == 0:
        r["status"] = "failed"
        r["error"] = "every call fell back or timed out; nothing could be compared"
    elif r["mismatches"]:
        r["status"] = "failed"
    else:
        r["status"] = "guarded" if nonexact else "verified"
    return r
