"""Where the bundled resources live: inside an installed wheel, or in a dev checkout.

wheel:    pythia/_runtime, pythia/studio/web_dist, pythia/studio/demo_data   (see pyproject.toml force-include)
checkout: <repo>/runtime,  <repo>/studio/web/dist,  <repo>/demo
"""
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent
EXE = Path(sys.executable).resolve() if sys.executable else None
EXE_DIR = EXE.parent if EXE else None
APP_DIR = EXE_DIR.parent if EXE_DIR else None


def _first(*candidates) -> Path:
    valid = [c for c in candidates if c is not None and c.is_dir()]
    if valid:
        return valid[0]
    return [c for c in candidates if c is not None][-1]


RUNTIME = _first(PKG / "_runtime", REPO / "runtime", APP_DIR / "runtime" if APP_DIR else None)
WEB_DIST = _first(PKG / "studio" / "web_dist", REPO / "studio" / "web" / "dist", APP_DIR / "studio" / "web" / "dist" if APP_DIR else None)
DEMO = _first(APP_DIR / "demo" if APP_DIR else None, PKG / "studio" / "demo_data", REPO / "demo")
OFFLINE_DIR = DEMO / "offline_cache"

