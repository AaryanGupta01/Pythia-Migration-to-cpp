#!/usr/bin/env python3
"""Build the self-contained Windows app and its installer: dist/PYTHIA-Studio-Setup-<version>.exe

    python packaging/windows/build.py [--no-prebuild] [--no-installer]

What ends up inside (nothing has to be installed on the user's machine):
    python/       relocatable CPython 3.13 (NuGet "python" package) + PYTHIA Studio and its dependencies
    mingw64/      MinGW-w64 GCC 16 (WinLibs, UCRT), pruned to the C++ compiler, linker and Windows SDK
    PYTHIA Studio.exe   GUI launcher (no console) -> pythonw -m pythia_studio --app
    pythia.cmd, pythia-studio.cmd   command-line entry points
Work happens in %LOCALAPPDATA%\\pythia-dev (outside OneDrive); only the final installer is written to dist/.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEV = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "pythia-dev"
DL, WORK = DEV / "dl", DEV / "pkg"
STAGE = WORK / "stage" / "PYTHIA Studio"
VERSION = "1.1.0"

MINGW = ("https://github.com/brechtsanders/winlibs_mingw/releases/download/16.2.0posix-14.0.0-ucrt-r2/"
         "winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r2.zip",
         "d5dbafc4a170e762ca6143151ec918fb9e2c72736fb14cd704abebc6bdd5276a")
PYTHON = ("https://api.nuget.org/v3-flatcontainer/python/3.13.16/python.3.13.16.nupkg", None)
INNO = "https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe"
INNO_PAGE = "https://jrsoftware.org/isdl.php"

# what the compiler needs at run time (everything else in WinLibs is dropped)
KEEP_BIN = {"g++.exe", "c++.exe", "gcc.exe", "cpp.exe", "as.exe", "ld.exe", "ld.bfd.exe", "ar.exe", "ranlib.exe",
            "nm.exe", "strip.exe", "gcc-ar.exe", "gcc-nm.exe", "gcc-ranlib.exe", "windres.exe", "objdump.exe",
            "x86_64-w64-mingw32-g++.exe", "x86_64-w64-mingw32-gcc.exe"}
DROP_LIBEXEC = ("f951", "cc1obj", "cc1objplus", "gnat1", "d21", "go1", "rust1", "cobol1", "a68", "lto-dump", "m2",
                "crab1", "gm2")
DROP_LIB = ("python3", "libpython", "libgfortran", "libbfd", "libyasm", "libopcodes", "libctf", "libsframe", "cmake",
            "pkgconfig", "libgdiagnostics", "libgccjit", "libgo", "libgnat", "libgphobos", "libgdruntime", "libobjc")


def log(msg: str) -> None:
    print(f"[build {time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run(cmd, **kw) -> None:
    log("$ " + " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def fetch(url: str, dest: Path, sha256: str | None = None) -> Path:
    if not dest.exists():
        log(f"downloading {url}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".part")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pythia-build"})) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
        tmp.replace(dest)
    if sha256:
        h = hashlib.sha256()
        with open(dest, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        if h.hexdigest() != sha256:
            dest.unlink()
            raise SystemExit(f"checksum mismatch for {dest.name}; deleted, run again")
    return dest


def clean_env() -> dict:
    """A PATH with nothing but Windows itself, so nothing from the build machine leaks into the checks."""
    e = {k: v for k, v in os.environ.items() if k.upper() not in ("PATH", "PYTHONPATH", "PYTHONHOME", "CXX", "PYTHIA_CXX")}
    sysroot = os.environ.get("SystemRoot", r"C:\Windows")
    e["PATH"] = os.pathsep.join([sysroot + r"\System32", sysroot, sysroot + r"\System32\WindowsPowerShell\v1.0"])
    e["PYTHONNOUSERSITE"] = "1"
    return e


def stage_python() -> Path:
    nupkg = fetch(PYTHON[0], DL / "python.nupkg", PYTHON[1])
    dst = STAGE / "python"
    log("staging Python")
    with zipfile.ZipFile(nupkg) as z:
        for n in z.namelist():
            if n.startswith("tools/") and not n.endswith("/"):
                out = dst / n[len("tools/"):]
                out.parent.mkdir(parents=True, exist_ok=True)
                with z.open(n) as src, open(out, "wb") as f:
                    shutil.copyfileobj(src, f)
    py = dst / "python.exe"
    env = clean_env()
    run([py, "-m", "ensurepip", "--upgrade"], env=env)
    run([py, "-m", "pip", "install", "--no-warn-script-location", "--disable-pip-version-check", "-q",
         "-r", ROOT / "requirements-studio.txt"], env=env)
    run([py, "-m", "pip", "install", "--no-warn-script-location", "--disable-pip-version-check", "-q", "--no-deps",
         "--force-reinstall", str(ROOT)], env=env)
    for rel in ("Lib/test", "Lib/idlelib", "Lib/turtledemo", "Lib/tkinter", "Lib/ensurepip", "tcl", "Scripts"):
        shutil.rmtree(dst / rel, ignore_errors=True)
    return py


def stage_mingw() -> Path:
    full = WORK / "mingw-full"
    if not (full / "mingw64" / "bin" / "g++.exe").exists():
        z = fetch(MINGW[0], DL / "mingw.zip", MINGW[1])
        log("extracting MinGW-w64 (one time)")
        shutil.rmtree(full, ignore_errors=True)
        with zipfile.ZipFile(z) as zf:
            zf.extractall(full)
    src, dst = full / "mingw64", STAGE / "mingw64"
    log("staging a pruned MinGW-w64")

    def ignore(d: str, names):
        rel = Path(d).relative_to(src).as_posix()
        drop = set()
        for n in names:
            low = n.lower()
            if rel == ".":
                if n in ("share", "doc", "opt", "etc", "mingwvars.bat"):
                    drop.add(n)
            elif rel == "bin":
                if not (low.endswith(".dll") or n in KEEP_BIN):
                    drop.add(n)
            elif rel.startswith("libexec"):
                if any(low.startswith(x) for x in DROP_LIBEXEC):
                    drop.add(n)
            elif rel == "lib":
                if any(low.startswith(x) for x in DROP_LIB):
                    drop.add(n)
            elif rel == "include":
                if low.startswith(("python", "libyasm", "bfd", "ctf", "dis-asm", "sframe", "libgdiag", "libgccjit",
                                   "libiberty", "plugin-api", "ansidecl", "symcat", "diagnostics")):
                    drop.add(n)
        return drop

    shutil.copytree(src, dst, ignore=ignore)
    # GCC's `%:if-exists(default-manifest.o%s)` breaks on install paths with spaces; PYTHIA passes the object
    # explicitly instead (pythia.toolchain.exe_link_args), so rename it out of the spec's reach.
    man = dst / "x86_64-w64-mingw32" / "lib" / "default-manifest.o"
    if man.exists():
        man.rename(man.with_name("pythia-default-manifest.o"))
    return dst


def build_launcher(py: Path, mingw: Path) -> None:
    log("building PYTHIA Studio.exe")
    tmp = WORK / "launcher"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    env = clean_env()
    run([py, "-m", "pythia_studio", "--export-icon", tmp / "pythia.ico"], env=env)
    shutil.copy(HERE / "launcher.rc", tmp)
    env["PATH"] = str(mingw / "bin") + os.pathsep + env["PATH"]
    run([mingw / "bin" / "windres.exe", "launcher.rc", "-O", "coff", "-o", "launcher_res.o"], cwd=tmp, env=env)
    run([mingw / "bin" / "gcc.exe", "-O2", "-s", "-municode", "-mwindows", HERE / "launcher.c", tmp / "launcher_res.o",
         mingw / "x86_64-w64-mingw32" / "lib" / "pythia-default-manifest.o", "-o", STAGE / "PYTHIA Studio.exe"], env=env)
    shutil.copy(tmp / "pythia.ico", WORK / "pythia.ico")


def write_extras() -> None:
    (STAGE / "pythia.cmd").write_text('@echo off\r\nset "PYTHIA_TOOLCHAIN=%~dp0mingw64"\r\n"%~dp0python\\python.exe" -m pythia.cli %*\r\n', encoding="ascii")
    (STAGE / "pythia-studio.cmd").write_text('@echo off\r\nset "PYTHIA_TOOLCHAIN=%~dp0mingw64"\r\n"%~dp0python\\python.exe" -m pythia_studio %*\r\n', encoding="ascii")
    shutil.copy(ROOT / "LICENSE", STAGE / "LICENSE.txt")
    (STAGE / "README.txt").write_text(
        "PYTHIA Studio " + VERSION + "\r\n\r\n"
        "Start it from the Start menu (PYTHIA Studio) or double-click 'PYTHIA Studio.exe'.\r\n"
        "The first start asks for an optional AI key (free from console.groq.com).\r\n\r\n"
        "Command line (from this folder): pythia prog.py --run      pythia-studio --doctor\r\n"
        "Your data and settings live in %USERPROFILE%\\.pythia-studio (log: logs\\studio.log).\r\n"
        "User guide: https://github.com/Vishalvivek2007/Pythia/blob/main/USER_GUIDE.md\r\n", encoding="utf-8")
    demo_dst = STAGE / "demo"
    shutil.rmtree(demo_dst, ignore_errors=True)
    shutil.copytree(ROOT / "demo", demo_dst)
    log("bundled demo projects into STAGE / demo")


def smoke(py: Path) -> None:
    log("smoke test of the staged app (clean PATH, bundled compiler only)")
    env = clean_env()
    env["PYTHIA_TOOLCHAIN"] = str(STAGE / "mingw64")
    env["PYTHIA_HOME"] = str(WORK / "smoke-home")
    shutil.rmtree(WORK / "smoke-home", ignore_errors=True)
    code = r'''
import sys, tempfile
from pythia import toolchain
from pythia.libmode import build_library
cc = toolchain.find_cxx()
assert cc[0] and "mingw64" in cc[0], cc
src = "def dot(a: list[float], b: list[float]) -> float:\n    s: float = 0.0\n    for i in range(len(a)):\n        s += a[i] * b[i]\n    return s\n"
r = build_library(src, ["dot"], tempfile.mkdtemp())
assert r.ok, r.error
import importlib.util
spec = importlib.util.spec_from_file_location(r.modname, r.so_path); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
assert m.dot([1.0, 2.0], [3.0, 4.0]) == 11.0
print("compiled module OK with", cc[1])
import subprocess, os
d = tempfile.mkdtemp()
open(os.path.join(d, "hello.py"), "w").write("name: str = 'world'\nprint(f'hello {name}', sum([1, 2, 3]))\n")
out = subprocess.run([sys.executable, "-m", "pythia.cli", os.path.join(d, "hello.py"), "-o", os.path.join(d, "hello.cpp"), "--run"],
                     capture_output=True, text=True)
assert "hello world 6" in out.stdout, out.stdout + out.stderr
print("stand-alone executable OK")
'''
    run([py, "-I", "-c", code], env=env)
    run([py, "-I", "-m", "pythia_studio", "--doctor"], env=env)


def prebuild_demo(py: Path, reuse: bool = False) -> None:
    """Run the Quanta demo once with the staged app and ship its compiled modules, so a user's first demo run
    reuses them instead of compiling ~50 modules (cache keys are exact, so this is always sound)."""
    home = WORK / "prebuild-home"
    if reuse and (home / "build-cache").is_dir():
        log("reusing the demo modules prebuilt by an earlier build")
    else:
        _run_prebuild(py, home)
    _ship_prebuilt(home)


def _run_prebuild(py: Path, home: Path) -> None:
    log("prebuilding the demo's compiled modules (takes several minutes)")
    shutil.rmtree(home, ignore_errors=True)
    env = clean_env()
    env["PYTHIA_TOOLCHAIN"] = str(STAGE / "mingw64")
    env["PYTHIA_HOME"] = str(home)
    code = r'''
import threading, time
from pythia.studio.engine import Engine
done = threading.Event()
def emit(t, d, stage=None, caption=None):
    if t == "job.done": done.set()
eng = Engine()
for demo in ("quanta", "textlab"):
    done.clear()
    jid = eng.start_job({"kind": "demo", "name": demo}, {"offline": True}, emit)
    done.wait(3600)
    fs = eng.functions(jid)
    print(demo, sum(f["status"] in ("verified", "guarded") for f in fs), "accelerated", flush=True)
'''
    run([py, "-I", "-c", code], env=env)


def _ship_prebuilt(home: Path) -> None:
    so_dir = next((STAGE / "python" / "Lib" / "site-packages" / "pythia" / "studio").glob("demo_data")) / "offline_cache" / "so"
    for f in so_dir.glob("*"):
        f.unlink()                                          # the checkout's Linux builds are useless here
    n = 0
    for f in (home / "build-cache").glob("*"):
        if f.is_file() and (f.suffix == ".so" or f.name.endswith(".meta.json")) and ".tmp" not in f.name:
            shutil.copy(f, so_dir / f.name)
            n += 1
    log(f"shipped {n} prebuilt files for the demo")


def iscc() -> Path:
    for c in (DEV / "innosetup" / "ISCC.exe", Path(os.environ.get("ProgramFiles(x86)", "")) / "Inno Setup 6" / "ISCC.exe",
              Path(os.environ.get("ProgramFiles", "")) / "Inno Setup 6" / "ISCC.exe"):
        if c.exists():
            return c
    inst = DL / "innosetup.exe"
    try:
        fetch(INNO, inst)
    except Exception:
        import re                                   # pinned release gone: take the current one from the download page
        page = urllib.request.urlopen(urllib.request.Request(INNO_PAGE, headers={"User-Agent": "pythia-build"})).read().decode("latin-1")
        url = re.search(r"https://[^\"]*innosetup-[0-9.]+\.exe", page).group(0)
        fetch(url, inst)
    if inst.read_bytes()[:2] != b"MZ":
        inst.unlink()
        raise SystemExit("the Inno Setup download is not an executable; install Inno Setup 6 manually and run again")
    run([inst, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CURRENTUSER", "/NOICONS", f"/DIR={DEV / 'innosetup'}"])
    c = DEV / "innosetup" / "ISCC.exe"
    if not c.exists():
        raise SystemExit("Inno Setup did not install; install it from https://jrsoftware.org and run again")
    return c


def installer() -> Path:
    tmp_out = DEV / "out"
    tmp_out.mkdir(parents=True, exist_ok=True)
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    setup_name = f"PYTHIA-Studio-Setup-{VERSION}.exe"
    for f in (tmp_out / setup_name, out / setup_name):
        if f.exists():
            try:
                f.unlink()
            except OSError:
                pass
    run([iscc(), f"/DStageDir={STAGE}", f"/DOutDir={tmp_out}", f"/DAppVersion={VERSION}", f"/DIconFile={WORK / 'pythia.ico'}",
         f"/DLicenseFile={ROOT / 'LICENSE'}", "/Q", HERE / "pythia-studio.iss"])
    dest_exe = out / setup_name
    shutil.copy2(tmp_out / setup_name, dest_exe)
    return dest_exe


def make_portable_zip() -> Path:
    out = ROOT / "dist"
    out.mkdir(exist_ok=True)
    zip_base = out / f"PYTHIA-Studio-{VERSION}-portable"
    log(f"creating portable zip: {zip_base}.zip")
    shutil.make_archive(str(zip_base), "zip", STAGE.parent, STAGE.name)
    return out / f"PYTHIA-Studio-{VERSION}-portable.zip"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-prebuild", action="store_true", help="skip shipping prebuilt demo modules")
    ap.add_argument("--no-installer", action="store_true", help="stop after staging (no Inno Setup)")
    ap.add_argument("--reuse-prebuilt", action="store_true", help="ship the demo modules from the last build instead of rebuilding")
    ap.add_argument("--only-installer", action="store_true", help="only build the installer from existing STAGE")
    a = ap.parse_args()
    if os.name != "nt":
        raise SystemExit("build the Windows app on Windows")
    if a.only_installer:
        if not STAGE.is_dir():
            raise SystemExit(f"STAGE directory not found: {STAGE}")
        exe = installer()
        log(f"installer: {exe} ({exe.stat().st_size / 1e6:.0f} MB)")
        return
    t0 = time.time()
    shutil.rmtree(STAGE, ignore_errors=True)
    STAGE.mkdir(parents=True)
    mingw = stage_mingw()
    py = stage_python()
    build_launcher(py, mingw)
    write_extras()
    smoke(py)
    if not a.no_prebuild:
        prebuild_demo(py, a.reuse_prebuilt)
    size = sum(f.stat().st_size for f in STAGE.rglob("*") if f.is_file())
    log(f"staged app: {STAGE} ({size / 1e6:.0f} MB)")
    port_zip = make_portable_zip()
    log(f"portable zip: {port_zip} ({port_zip.stat().st_size / 1e6:.0f} MB)")
    if not a.no_installer:
        exe = installer()
        log(f"installer: {exe} ({exe.stat().st_size / 1e6:.0f} MB)")
    log(f"done in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
