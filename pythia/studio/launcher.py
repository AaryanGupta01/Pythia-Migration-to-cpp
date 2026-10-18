"""`pythia-studio`: start the server, print the environment doctor, open the UI (browser tab or chromeless app window).

    pythia-studio [--port 8765] [--host 127.0.0.1] [--no-open] [--app] [--offline] [--home DIR] [--doctor]

A second launch while one is already serving on the port just opens another window and exits.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import List, Optional

WINDOW = "1440,900"


def _say(msg: str) -> None:
    print(f"[pythia] {msg}", flush=True)


def is_wsl() -> bool:
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def _probe(port: int) -> Optional[bool]:
    """True: PYTHIA Studio answers on 127.0.0.1:port.  False: something else does.  None: nothing listens."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/doctor", timeout=3) as r:
            return json.load(r).get("app") == "pythia-studio"
    except urllib.error.HTTPError:
        return False
    except Exception:
        pass
    import socket
    with socket.socket() as s:
        s.settimeout(0.5)
        return False if s.connect_ex(("127.0.0.1", port)) == 0 else None


# ---- browser discovery ---------------------------------------------------------------------------

def _which(*names: str) -> Optional[str]:
    return next((p for p in (shutil.which(n) for n in names) if p), None)


def _first_file(*cands: str) -> Optional[str]:
    return next((c for c in cands if c and os.path.isfile(c)), None)


def _win_roots() -> List[str]:
    if is_wsl():
        return ["/mnt/c/Program Files", "/mnt/c/Program Files (x86)"]
    return [os.environ.get("PROGRAMFILES", ""), os.environ.get("PROGRAMFILES(X86)", ""), os.environ.get("LOCALAPPDATA", "")]


def find_chromium() -> Optional[str]:
    """A Chromium-family browser that supports --app=URL; PYTHIA_BROWSER overrides."""
    env = os.environ.get("PYTHIA_BROWSER")
    if env:
        return shutil.which(env) or env
    win = [os.path.join(r, *rel) for r in _win_roots() if r for rel in
           (("Microsoft", "Edge", "Application", "msedge.exe"), ("Google", "Chrome", "Application", "chrome.exe"),
            ("BraveSoftware", "Brave-Browser", "Application", "brave.exe"), ("Chromium", "Application", "chrome.exe"))]
    if sys.platform == "win32" or is_wsl():          # on WSL prefer the Windows browser: it is the one on screen
        hit = _first_file(*win)
        if hit:
            return hit
    if sys.platform == "darwin":
        apps = ("Google Chrome.app/Contents/MacOS/Google Chrome", "Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                "Brave Browser.app/Contents/MacOS/Brave Browser", "Chromium.app/Contents/MacOS/Chromium")
        hit = _first_file(*[os.path.join(base, a) for a in apps for base in ("/Applications", os.path.expanduser("~/Applications"))])
        if hit:
            return hit
    return _which("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge",
                  "microsoft-edge-stable", "brave-browser", "chrome", "msedge")


def _profile_dir(browser: str, home: Path) -> str:
    """Own profile so the app window is a separate process (we can wait on it) and never touches the user's profile."""
    if is_wsl() and browser.startswith("/mnt/"):
        try:   # a Windows exe needs a Windows-side path; \\wsl$ UNC paths break Chromium's profile locking
            la = subprocess.run(["cmd.exe", "/c", "echo %LOCALAPPDATA%"], capture_output=True, text=True, timeout=10, cwd="/mnt/c").stdout.strip()
            return la + "\\pythia-studio\\profile"
        except Exception:
            pass
    return str(home / "app-profile")


def open_ui(url: str, app: bool, home: Path) -> Optional[subprocess.Popen]:
    """Open the UI. In app mode returns the window's Popen (when trackable) so closing the window can stop the server."""
    if app:
        b = find_chromium()
        if b:
            cmd = [b, f"--app={url}", f"--window-size={WINDOW}", f"--user-data-dir={_profile_dir(b, home)}",
                   "--no-first-run", "--no-default-browser-check"]
            try:
                return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/mnt/c" if is_wsl() else None)
            except OSError as e:
                _say(f"could not start {b}: {e}")
        else:
            _say("no Chrome/Edge/Chromium/Brave found for --app; opening your default browser instead "
                 "(set PYTHIA_BROWSER=/path/to/browser to choose one)")
    try:
        if webbrowser.open(url):
            return None
    except Exception:
        pass
    for cmd in (["wslview", url], ["cmd.exe", "/c", "start", "", url], ["explorer.exe", url], ["xdg-open", url], ["open", url]):
        if shutil.which(cmd[0]):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd="/mnt/c" if is_wsl() else None)
                return None
            except OSError:
                continue
    _say(f"open this address in a browser: {url}")
    return None


# ---- main ---------------------------------------------------------------------------------------------

def native_ready() -> bool:
    """Can this interpreter build and load extension modules by itself? (The Windows app bundles MinGW-w64.)"""
    try:
        import pybind11  # noqa: F401
        from .. import toolchain
        return bool(toolchain.find_cxx()[0] and toolchain.python_headers())
    except Exception:
        return False


def _wsl_path(p: Path) -> Optional[str]:
    try:
        r = subprocess.run(["wsl", "-e", "wslpath", "-a", str(p)], capture_output=True, text=True, timeout=30)
        out = r.stdout.strip().replace("\x00", "")
        return out if r.returncode == 0 and out else None
    except Exception:
        return None


def _delegate_to_wsl(a) -> Optional[int]:
    """Native Windows has no C++17 toolchain PYTHIA can use; run the real thing inside WSL2 instead."""
    import shlex
    if shutil.which("wsl") is None:
        _say("PYTHIA Studio compiles to C++ and needs Linux tools. On Windows it runs inside WSL2:")
        _say("  1. open PowerShell as administrator and run:  wsl --install     (then reboot)")
        _say("  2. run:  powershell -ExecutionPolicy Bypass -File scripts\\install.ps1      (from the PYTHIA folder)")
        return 1
    flags = ["--port", str(a.port)]
    if a.offline:
        flags.append("--offline")
    if a.no_open:
        flags.append("--no-open")
    if a.app:
        flags.append("--app")
    root = Path(__file__).resolve().parents[2]
    if (root / "studio.sh").exists():                      # a source checkout: let studio.sh set everything up
        wp = _wsl_path(root)
        if not wp:
            return None
        inner = (f"cd {shlex.quote(wp)} && sed -i 's/\\r$//' studio.sh scripts/*.sh 2>/dev/null; bash ./studio.sh "
                 + " ".join(map(shlex.quote, flags)))
    else:                                                   # an installed package: use the WSL-side install
        inner = ('export PATH="$HOME/.local/bin:$PATH"; if command -v pythia-studio >/dev/null; then pythia-studio '
                 + " ".join(map(shlex.quote, flags))
                 + '; else echo "PYTHIA Studio is not installed inside WSL yet: run scripts\\\\install.ps1"; exit 3; fi')
    _say("Windows detected: running PYTHIA Studio inside WSL2 (Linux compiler toolchain)")
    try:
        return subprocess.call(["wsl", "-e", "bash", "-lc", inner])
    except KeyboardInterrupt:
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    from .envfile import load_env
    load_env()
    ap = argparse.ArgumentParser(prog="pythia-studio", description="PYTHIA Studio: find Python hotspots, verify C++ replacements, splice them in.")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PYTHIA_PORT", "8765")))
    ap.add_argument("--host", default=os.environ.get("PYTHIA_HOST", "127.0.0.1"),
                    help="bind address (default 127.0.0.1; use 0.0.0.0 only in a container or on a trusted network)")
    ap.add_argument("--no-open", action="store_true", help="do not open a window")
    ap.add_argument("--app", action="store_true", help="open a chromeless app window (Chrome/Edge/Chromium/Brave) instead of a browser tab")
    ap.add_argument("--offline", action="store_true", help="replay the bundled LLM answers + prebuilt libs for the demo project (no API key)")
    ap.add_argument("--home", help="data folder (default $PYTHIA_HOME or ~/.pythia-studio)")
    ap.add_argument("--engine", choices=["mock", "real"], help="override PYTHIA_ENGINE")
    ap.add_argument("--doctor", action="store_true", help="print the environment check and exit")
    ap.add_argument("--version", action="store_true")
    ap.add_argument("--export-icon", metavar="FILE", help="write the app icon (.ico or .png by extension) and exit; used by the installers")
    a = ap.parse_args(argv)

    if a.home:
        os.environ["PYTHIA_HOME"] = str(Path(a.home).expanduser())
    if a.offline:
        os.environ["PYTHIA_OFFLINE"] = "1"
    if a.engine:
        os.environ["PYTHIA_ENGINE"] = a.engine
    home = Path(os.environ.get("PYTHIA_HOME") or Path.home() / ".pythia-studio").expanduser()
    from . import doctor
    if a.export_icon:
        from . import branding
        Path(a.export_icon).write_bytes(branding.ico() if a.export_icon.lower().endswith(".ico") else branding.png(256))
        return 0
    if a.version:
        print(doctor._version())
        return 0
    if sys.platform == "win32" and os.environ.get("PYTHIA_NO_WSL") != "1" and not a.doctor and not a.engine \
            and not native_ready():
        rc = _delegate_to_wsl(a)
        if rc is not None:
            return rc
    report = doctor.run(home)
    if a.doctor:
        print(doctor.render(report))
        return 0 if report["ready"] else 1

    shown = "localhost" if a.host in ("0.0.0.0", "::", "") else a.host
    url = f"http://{shown}:{a.port}/"
    seen = _probe(a.port)
    if seen is True:
        _say(f"PYTHIA Studio is already running at {url}")
        if not a.no_open:
            open_ui(url, a.app, home)
        return 0
    if seen is False:
        _say(f"port {a.port} is taken by another program. Pick another: pythia-studio --port {a.port + 1}")
        return 1

    print(f"PYTHIA Studio {report['version']}  (data: {home})\n{doctor.render(report)}", flush=True)
    if a.host not in ("127.0.0.1", "localhost", "::1") and not os.path.exists("/.dockerenv"):   # in Docker the port mapping decides exposure
        _say(f"WARNING: listening on {a.host}. The UI can browse and compile files this user can read; expose it only on a network you trust "
             "(other Host names must be listed in PYTHIA_ALLOWED_HOSTS).")

    import uvicorn
    from .server.app import create_app
    app = create_app(home=str(home))
    server = uvicorn.Server(uvicorn.Config(app, host=a.host, port=a.port, log_level="warning", ws_ping_interval=None))
    _say(f"serving {url}   (Ctrl+C to quit)")

    def opener() -> None:
        for _ in range(100):                        # wait for the socket, then open
            if server.started:
                break
            time.sleep(0.1)
        else:
            return
        t0 = time.time()
        proc = open_ui(url, a.app, home)
        if proc is not None and a.app:
            proc.wait()
            if time.time() - t0 > 3:                # window closed by the user => stop the server
                _say("app window closed, shutting down")
                server.should_exit = True

    if not a.no_open:
        threading.Thread(target=opener, daemon=True).start()
    try:
        server.run()
    except KeyboardInterrupt:
        pass
    _say("bye")
    return 0


if __name__ == "__main__":
    sys.exit(main())
