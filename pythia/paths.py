"""Where the bundled resources live: inside an installed wheel, or in a dev checkout.

wheel:    pythia/_runtime, pythia/studio/web_dist, pythia/studio/demo_data   (see pyproject.toml force-include)
checkout: <repo>/runtime,  <repo>/studio/web/dist,  <repo>/demo
"""
from pathlib import Path

PKG = Path(__file__).resolve().parent
REPO = PKG.parent


def _first(*candidates: Path) -> Path:
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[-1]


RUNTIME = _first(PKG / "_runtime", REPO / "runtime")
WEB_DIST = _first(PKG / "studio" / "web_dist", REPO / "studio" / "web" / "dist")
DEMO = _first(PKG / "studio" / "demo_data", REPO / "demo")
OFFLINE_DIR = DEMO / "offline_cache"
