"""`python -m pythia.studio.server [--port 8765] [--open]`"""
import argparse
import os
import threading
import time
import webbrowser


def main() -> None:
    ap = argparse.ArgumentParser(prog="pythia.studio.server", description="PYTHIA Studio API + UI server (127.0.0.1 only)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("PYTHIA_PORT", "8765")))
    ap.add_argument("--open", action="store_true", help="open the UI in a browser once the server is up")
    ap.add_argument("--engine", choices=["mock", "real"], help="override PYTHIA_ENGINE")
    ap.add_argument("--home", help="data root (default $PYTHIA_HOME or ~/.pythia-studio)")
    a = ap.parse_args()
    import sys
    if sys.platform == "win32" and os.environ.get("PYTHIA_NO_WSL") != "1" and a.engine != "mock":
        from ..launcher import main as launch
        raise SystemExit(launch(["--port", str(a.port)] + (["--no-open"] if not a.open else [])))
    if a.engine:
        os.environ["PYTHIA_ENGINE"] = a.engine
    import uvicorn
    from .app import create_app
    app = create_app(home=a.home)
    url = f"http://127.0.0.1:{a.port}/"
    print(f"PYTHIA Studio ({type(app.state.engine).__name__}) at {url}", flush=True)
    if a.open:
        def _open():
            time.sleep(1.2)
            try:
                if not webbrowser.open(url):
                    os.system(f"cmd.exe /c start {url} >/dev/null 2>&1")      # WSL without a Linux browser
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=a.port, log_level="warning", ws_ping_interval=None)


if __name__ == "__main__":
    main()
