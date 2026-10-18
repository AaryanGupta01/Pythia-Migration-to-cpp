"""Environment doctor: what PYTHIA Studio needs on this machine, and how to fix what is missing.

`run(home)` -> {"app", "ready", "checks":[{id,label,ok,required,detail,hint}]}; used by GET /api/doctor and the terminal banner.
"""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import List, Optional

from .. import paths

_OS = platform.system()
_CXX_HINT = {"Darwin": "xcode-select --install",
             "Linux": "sudo apt install build-essential python3-dev python3-venv   (Fedora: sudo dnf install gcc-c++ python3-devel)"
             }.get(_OS, "install g++ or clang++ (on Windows use WSL)")
_HDR_HINT = {"Darwin": "reinstall Python from python.org, or: brew install python",
             "Linux": "sudo apt install python3-dev   (Fedora: sudo dnf install python3-devel)"
             }.get(_OS, "install the Python development headers")


def _du(p: Path) -> int:
    n = 0
    for root, _d, files in os.walk(p):
        for f in files:
            try:
                n += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return n


def human(n: float) -> str:
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return ""


def _check(id: str, label: str, ok, detail: str, hint: Optional[str] = None, required: bool = True) -> dict:
    return {"id": id, "label": label, "ok": bool(ok), "required": required, "detail": detail, "hint": None if ok else hint}


def _version() -> str:
    try:
        from importlib.metadata import version
        return version("pythia-studio")
    except Exception:
        return "dev"


def run(home: Optional[Path] = None) -> dict:
    home = Path(home or os.environ.get("PYTHIA_HOME") or Path.home() / ".pythia-studio")
    c: List[dict] = []
    v = sys.version_info
    c.append(_check("python", "Python >= 3.10", v >= (3, 10),
                    platform.python_version() + ("" if v >= (3, 12) else " (3.12+ gives a faster tracer)"),
                    "Install Python 3.10 or newer (3.12+ recommended)."))

    from .. import toolchain
    cxx, ver, skipped = toolchain.find_cxx()
    c.append(_check("compiler", "C++17 compiler", cxx, (ver or "not found") + (f" [skipped: {'; '.join(skipped)}]" if skipped else ""),
                    toolchain.describe()["hint"] or _CXX_HINT))

    try:
        import pybind11
        pb, pbv = True, getattr(pybind11, "__version__", "")
    except Exception:
        pb, pbv = False, ""
    c.append(_check("pybind11", "pybind11", pb, pbv or "not importable", f"{sys.executable} -m pip install pybind11"))

    inc = sysconfig.get_paths().get("include") or ""
    has_h = bool(inc) and (Path(inc) / "Python.h").is_file()
    c.append(_check("python_headers", "Python headers (Python.h)", has_h, inc or "no include dir", _HDR_HINT))

    c.append(_check("runtime", "C++ runtime sources", (paths.RUNTIME / "pyrt.cpp").is_file(), str(paths.RUNTIME),
                    "Reinstall: pip install --force-reinstall pythia-studio"))
    c.append(_check("web_ui", "Web UI bundle", (paths.WEB_DIST / "index.html").is_file(), str(paths.WEB_DIST),
                    "In a checkout: cd studio/web && npm install && npm run build. Otherwise reinstall the package.", required=False))
    c.append(_check("demo", "Demo project + offline cache", (paths.DEMO / "textlab").is_dir(), str(paths.DEMO),
                    "Reinstall the package to restore the demo.", required=False))

    try:
        home.mkdir(parents=True, exist_ok=True)
        probe = home / ".w"
        probe.write_text("x")
        probe.unlink()
        wr = True
    except OSError:
        wr = False
    c.append(_check("home", "Data folder writable", wr, str(home), "Set PYTHIA_HOME (or --home) to a writable folder."))

    cache = home / "build-cache"
    size = _du(cache) if cache.is_dir() else 0
    c.append(_check("cache", "Build cache", True, f"{human(size)} in {cache}" + ("  (delete it to reclaim space)" if size > (1 << 30) else ""),
                    required=False))

    from . import llm
    try:
        offline = os.environ.get("PYTHIA_OFFLINE") == "1" and (paths.OFFLINE_DIR / "llm").is_dir()
        st = llm.llm_status(None, offline, paths.OFFLINE_DIR / "llm")
    except Exception as e:
        st = {"enabled": False, "provider": None, "hint": str(e)}
    c.append(_check("llm", "LLM fixer", st.get("enabled"),
                    f"{st.get('provider')} ({st.get('model')})" if st.get("enabled") else "disabled (compile/verify still work; use --offline for the demo)",
                    st.get("hint") or "Set GROQ_API_KEY (free) or ANTHROPIC_API_KEY, or run with --offline", required=False))

    wsl = False
    try:
        wsl = "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        pass
    return {"app": "pythia-studio", "version": _version(), "ready": all(x["ok"] for x in c if x["required"]), "checks": c,
            "platform": platform.platform(), "wsl": wsl, "home": str(home)}


def render(d: dict) -> str:
    out = []
    for x in d["checks"]:
        tag = "ok  " if x["ok"] else ("MISS" if x["required"] else "note")
        out.append(f"  [{tag}] {x['label']:<30} {x['detail']}")
        if x["hint"]:
            out.append(f"         -> {x['hint']}")
    out.append("  environment ready" if d["ready"] else "  NOT READY: fix the MISS items above (the UI still starts, compile/verify are disabled)")
    return "\n".join(out)


if __name__ == "__main__":
    _d = run()
    print(render(_d))
    sys.exit(0 if _d["ready"] else 1)
