"""Playground: compile a snippet to C++, run it under CPython and as a compiled binary, dump compiler stages.

Same build recipe as tools/oracle.py (copy the runtime, `c++ -std=c++17 -O2`), with timeouts, size limits
and temp dirs that are always cleaned. `pyrt.cpp` is compiled once into a cached object file.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parents[3]
from pythia import toolchain
from pythia.paths import RUNTIME  # wheel or checkout
MAX_SOURCE = 200_000          # bytes
MAX_OUTPUT = 1_000_000        # bytes kept per stream
RUN_TIMEOUT = 10              # seconds, CPython and compiled binary
BUILD_TIMEOUT = 120
EXC_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Interrupt|Exit)):", re.M)


class PlaygroundError(Exception):
    """Carries an HTTP status for the route layer."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _check(source: Any) -> str:
    if not isinstance(source, str):
        raise PlaygroundError("body must be {\"source\": \"<code>\"}", 422)
    if len(source.encode("utf-8")) > MAX_SOURCE:
        raise PlaygroundError(f"source larger than {MAX_SOURCE // 1000} KB", 413)
    return source


def _compile_source():
    try:
        from pythia.cli import compile_source
        return compile_source
    except Exception as e:   # pragma: no cover
        raise PlaygroundError(f"PYTHIA compiler not importable: {e}", 501)


def _diag(d) -> dict:
    return {"line": d.line, "col": d.col, "kind": d.kind, "msg": d.msg}


def _note(n) -> dict:
    return {"line": n.line, "col": n.col, "cls": n.cls, "detail": n.detail, "mitigation": n.mitigation, "severity": n.severity}


def compile_snippet(source: str) -> Dict[str, Any]:
    source = _check(source)
    code, notes, errs, _ = _compile_source()(source, "playground.py")
    if errs:
        return {"ok": False, "cpp": "", "diagnostics": [_diag(d) for d in errs], "fidelity": [], "cpp_line_map": {}}
    return {"ok": True, "cpp": code, "diagnostics": [], "fidelity": [_note(n) for n in notes],
            "cpp_line_map": _line_map(source)}


def _line_map(source: str) -> dict:
    """pysub line -> cpp lines. Library-mode emission shares its prefix with the program's C++ (main comes last),
    so its map is valid for the full program; empty if libmode is missing or can't expose the functions."""
    try:
        import ast
        from pythia.libmode import build_library
        names = tuple(n.name for n in ast.parse(source).body if isinstance(n, ast.FunctionDef))
        if not names:
            return {}
        d = tempfile.mkdtemp(prefix="pythia-pgmap-")
        try:
            r = build_library(source, names, d, build=False)
        finally:
            shutil.rmtree(d, ignore_errors=True)
        return r.cpp_line_map if r.ok else {}
    except Exception:
        return {}


def stages(source: str) -> Dict[str, Any]:
    source = _check(source)
    from .mock_engine import stage_dump         # real dump_stages if importable, else a flagged "mock": true stand-in
    return stage_dump(source, "playground.py")


def _exc_of(stderr: str) -> Optional[str]:
    m = EXC_RE.findall(stderr or "")
    return m[-1].rsplit(".", 1)[-1] if m else None


def _limits():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
        resource.setrlimit(resource.RLIMIT_CPU, (RUN_TIMEOUT + 2, RUN_TIMEOUT + 2))
    except Exception:
        pass


def _run(argv, cwd) -> Dict[str, Any]:
    t = time.perf_counter()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=RUN_TIMEOUT, cwd=cwd,
                           preexec_fn=_limits if os.name == "posix" else None, errors="replace")
    except subprocess.TimeoutExpired:
        return {"stdout": "", "exception": "TimeoutError", "time_ms": RUN_TIMEOUT * 1000.0, "timed_out": True,
                "stderr": f"timed out after {RUN_TIMEOUT} s"}
    ms = round((time.perf_counter() - t) * 1000, 2)
    exc = _exc_of(r.stderr) if r.returncode != 0 else None
    if r.returncode != 0 and exc is None:
        exc = f"exit code {r.returncode}"
    return {"stdout": r.stdout[:MAX_OUTPUT], "exception": exc, "time_ms": ms, "stderr": r.stderr[-4000:]}


def _runtime_object(tmp_cache: Path) -> Path:
    """pyrt.cpp -> cached .o keyed by the runtime sources + compiler."""
    h = hashlib.sha256()
    for f in ("pyrt.cpp", "pyrt.hpp"):
        h.update((RUNTIME / f).read_bytes())
    h.update(b"c++17-O2" + (toolchain.find_cxx()[1] or "").encode())
    obj = tmp_cache / f"pyrt-{h.hexdigest()[:16]}.o"
    if not obj.exists():
        tmp_cache.mkdir(parents=True, exist_ok=True)
        part = obj.with_suffix(f".{os.getpid()}.part")
        cxx = toolchain.find_cxx()[0]
        r = subprocess.run([cxx, "-std=c++17", "-O2", "-c", "-I", str(RUNTIME), str(RUNTIME / "pyrt.cpp"), "-o", str(part)],
                           capture_output=True, text=True, timeout=BUILD_TIMEOUT, env=toolchain.env_for(cxx))
        if r.returncode != 0:
            raise PlaygroundError("runtime failed to compile: " + r.stderr[-800:], 500)
        os.replace(part, obj)
    return obj


def run_snippet(source: str, cache_dir: Path) -> Dict[str, Any]:
    source = _check(source)
    comp = compile_snippet(source)
    if not comp["ok"]:
        d = comp["diagnostics"][0]
        return {"ok": False, "error": f"{d['kind']} at line {d['line']}: {d['msg']}", "diagnostics": comp["diagnostics"],
                "python": None, "cpp": None, "same": False}
    if toolchain.find_cxx()[0] is None:
        return {"ok": False, "error": "no C++17 compiler found. " + (toolchain.describe()["hint"] or ""),
                "python": None, "cpp": None, "same": False}
    tmp = Path(tempfile.mkdtemp(prefix="pythia-pg-"))
    try:
        py = tmp / "snippet.py"
        py.write_text(source, encoding="utf-8")
        python = _run([sys.executable, "-I", str(py)], str(tmp))
        cpp_path = tmp / "snippet.cpp"
        cpp_path.write_text(comp["cpp"], encoding="utf-8")
        for f in ("pyrt.hpp",):
            shutil.copy(RUNTIME / f, tmp)
        obj = _runtime_object(cache_dir)
        binp = tmp / ("snippet.exe" if os.name == "nt" else "snippet")
        t = time.perf_counter()
        cxx = toolchain.find_cxx()[0]
        cc = subprocess.run([cxx, "-std=c++17", "-O2", "-I", str(tmp), str(cpp_path), str(obj),
                             *toolchain.exe_link_args(), "-o", str(binp)],
                            capture_output=True, text=True, timeout=BUILD_TIMEOUT, env=toolchain.env_for(cxx))
        build_ms = round((time.perf_counter() - t) * 1000, 1)
        if cc.returncode != 0:
            return {"ok": False, "error": "generated C++ failed to compile (internal error): " + cc.stderr[-1500:],
                    "python": _public(python), "cpp": None, "same": False}
        cpp = _run([str(binp)], str(tmp))
        cpp["build_ms"] = build_ms
        same = python["stdout"] == cpp["stdout"] and python["exception"] == cpp["exception"]
        return {"ok": True, "python": _public(python), "cpp": _public(cpp), "same": same}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"C++ build timed out after {BUILD_TIMEOUT} s", "python": None, "cpp": None, "same": False}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _public(r: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: r[k] for k in ("stdout", "exception", "time_ms") if k in r}
    for k in ("build_ms", "timed_out"):
        if k in r:
            out[k] = r[k]
    if r.get("stderr") and r.get("exception"):
        out["stderr"] = r["stderr"]
    return out
