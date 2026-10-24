#!/usr/bin/env python3
"""Detects the environment used for every measurement and writes evidence/env.json."""
import json, os, platform, re, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEV = Path(os.environ["LOCALAPPDATA"]) / "pythia-dev"
PY = DEV / "python" / "python.exe"
GXX = DEV / "mingw64" / "bin" / "g++.exe"

def run(*a, **k):
    return subprocess.run(list(map(str, a)), capture_output=True, text=True, encoding="utf-8", **k).stdout.strip()

def ver(mod):
    return run(PY, "-c", f"import importlib.metadata as m; print(m.version('{mod}'))")

def nm(p):
    return json.loads((ROOT / "studio/web/node_modules" / p / "package.json").read_text())["version"]

ps = lambda c: run("powershell", "-NoProfile", "-Command", c)
cpu = ps("(Get-CimInstance Win32_Processor).Name")
cores = ps("(Get-CimInstance Win32_Processor).NumberOfCores")
threads = ps("(Get-CimInstance Win32_Processor).NumberOfLogicalProcessors")
ram = round(int(ps("(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory")) / 2**30, 1)
osn = ps("(Get-CimInstance Win32_OperatingSystem).Caption") + " " + ps("(Get-CimInstance Win32_OperatingSystem).Version")
wsl = run("wsl", "-e", "bash", "-lc", "uname -r; lsb_release -ds 2>/dev/null; python3 --version; c++ --version | head -1").replace("\x00", "").splitlines()
wsl_py = run("wsl", "-e", "bash", "-lc", f"/mnt/c/{str(ROOT)[3:].replace(chr(92), '/')}/.venv/bin/python --version").replace("\x00", "")
env = {
    "cpu": cpu, "cores": cores, "threads": threads, "ram": ram, "os": osn.strip(),
    "wsl": f"Ubuntu, kernel {wsl[0]}" if wsl else "?",
    "py_win": run(PY, "--version").split()[-1], "py_wsl": wsl_py.split()[-1] if wsl_py else "?",
    "gcc_win": run(GXX, "--version").splitlines()[0], "gcc_wsl": [l for l in wsl if "c++" in l or "g++" in l][0] if any("c++" in l or "g++" in l for l in wsl) else "?",
    "pybind": ver("pybind11"), "fastapi": ver("fastapi"), "uvicorn": ver("uvicorn"), "pydantic": ver("pydantic"),
    "node": run("node", "--version").lstrip("v"), "react": nm("react"), "vite": nm("vite"), "ts": nm("typescript"), "monaco": nm("monaco-editor"),
    "playwright": run(sys.executable, "-c", "import importlib.metadata as m; print(m.version('playwright'))"),
    "mpl": run(sys.executable, "-c", "import matplotlib; print(matplotlib.__version__)"),
    "docx": run(sys.executable, "-c", "import importlib.metadata as m; print(m.version('python-docx'))"),
    "system_python": sys.version.split()[0],
}
(HERE / "evidence" / "env.json").write_text(json.dumps(env, indent=1))
print(json.dumps(env, indent=1))
