"""Where the C++ compiler is, and the platform-specific flags for building with it.

Linux / macOS: the system `c++` (or $CXX).  Windows: the MinGW-w64 GCC that ships inside the PYTHIA Studio
app (`<app>/mingw64`), so nothing has to be installed by hand.  An old compiler on PATH (e.g. MinGW.org GCC 6,
which predates C++17) is skipped with a reason instead of producing baffling build errors.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import sysconfig
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

IS_WIN = os.name == "nt"
MIN_GCC, MIN_CLANG = 8, 7
EXE = ".exe" if IS_WIN else ""


def _bundled_roots() -> List[Path]:
    roots: List[Path] = []
    if os.environ.get("PYTHIA_TOOLCHAIN"):
        roots.append(Path(os.environ["PYTHIA_TOOLCHAIN"]))
    exe = Path(sys.executable).resolve()
    roots += [exe.parent.parent / "mingw64", exe.parent / "mingw64"]          # <app>/python/python.exe
    if IS_WIN:
        la = os.environ.get("LOCALAPPDATA")
        if la:
            roots += [Path(la) / "Programs" / "PYTHIA Studio" / "mingw64", Path(la) / "pythia-dev" / "mingw64"]
    return roots


def _candidates() -> List[str]:
    out: List[str] = []
    for var in ("PYTHIA_CXX", "CXX"):
        v = os.environ.get(var)
        if v:
            out.append(shutil.which(v) or v)
    for r in _bundled_roots():
        g = r / "bin" / f"g++{EXE}"
        if g.is_file():
            out.append(str(g))
    for n in ("c++", "g++", "clang++"):
        p = shutil.which(n)
        if p:
            out.append(p)
    return list(dict.fromkeys(out))


def _version(cc: str) -> Tuple[str, Optional[str]]:
    """(first --version line, reason it is unusable or None)."""
    try:
        r = subprocess.run([cc, "--version"], capture_output=True, text=True, timeout=30, env=env_for(cc))
    except Exception as ex:
        return "", f"{cc} could not be run ({ex})"
    line = (r.stdout.splitlines() or [""])[0].strip()
    m = re.search(r"(\d+)\.(\d+)(?:\.\d+)?", line.split(")")[-1] if ")" in line else line) or re.search(r"(\d+)\.(\d+)", line)
    major = int(m.group(1)) if m else 0
    clang = "clang" in line.lower()
    if major and major < (MIN_CLANG if clang else MIN_GCC):
        return line, f"{cc} is {'clang' if clang else 'GCC'} {major}, too old for C++17 (need {'clang 7' if clang else 'GCC 8'}+)"
    return line, None


@lru_cache(maxsize=None)
def find_cxx() -> Tuple[Optional[str], str, List[str]]:
    """(compiler path or None, its version line, reasons other candidates were skipped)."""
    skipped: List[str] = []
    for cc in _candidates():
        line, why = _version(cc)
        if why is None:
            return cc, line, skipped
        skipped.append(why)
    return None, "", skipped


def env_for(cc: Optional[str] = None) -> Dict[str, str]:
    """Environment for running the compiler: its own bin dir first (MinGW's cc1plus needs its DLLs)."""
    e = dict(os.environ)
    cc = cc or find_cxx()[0]
    if cc and IS_WIN:
        e["PATH"] = str(Path(cc).parent) + os.pathsep + e.get("PATH", "")
    return e


def pic_flags() -> List[str]:
    return [] if IS_WIN else ["-fPIC"]


def python_link_args() -> List[str]:
    """Extra link inputs for a Python extension: on Windows link the interpreter DLL directly and the C/C++
    runtime statically, so the .pyd needs nothing but python3X.dll and the OS."""
    if not IS_WIN:
        return []
    dll = Path(sys.base_prefix) / f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    return ["-static", str(dll)]


def exe_link_args() -> List[str]:
    """Static C++ runtime for stand-alone programs on Windows, so the .exe runs without MinGW on PATH.

    GCC's spec adds default-manifest.o through `%:if-exists(...)`, which splits the path at a space; the app is
    installed under folders that may contain spaces (user names), so the bundled toolchain renames the object and
    we pass it here as an ordinary argument instead."""
    if not IS_WIN:
        return []
    args = ["-static", "-Wl,--stack,536870912"]       # 512 MB main-thread stack: legal deep recursion must work
    cc = find_cxx()[0]
    if cc:
        m = Path(cc).resolve().parent.parent / "x86_64-w64-mingw32" / "lib" / "pythia-default-manifest.o"
        if m.is_file():
            args.append(str(m))
    return args


def ext_suffix() -> str:
    return sysconfig.get_config_var("EXT_SUFFIX") or (".pyd" if IS_WIN else ".so")


def python_headers() -> Optional[str]:
    inc = sysconfig.get_path("include")
    return inc if inc and Path(inc, "Python.h").is_file() else None


def describe() -> Dict[str, object]:
    cc, line, skipped = find_cxx()
    hint = None
    if not cc:
        hint = ("PYTHIA Studio for Windows ships its own compiler; reinstall it from PYTHIA-Studio-Setup.exe"
                if IS_WIN else
                "Install a C++17 compiler: sudo apt install build-essential python3-dev (Linux) or "
                "xcode-select --install (macOS)")
    return {"found": bool(cc), "path": cc, "name": Path(cc).name if cc else None, "version": line or None,
            "skipped": skipped, "hint": hint}
