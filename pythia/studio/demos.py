"""Bundled demo projects: `{kind: "demo", name: <key>}` ingests one of these (default: quanta)."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..paths import DEMO as DEMO_ROOT   # wheel (studio/demo_data) or checkout (demo/)

DEFAULT_DEMO = "quanta"

DEMOS: Dict[str, dict] = {
    "quanta": {
        "title": "Quanta: analytics and simulation toolkit",
        "description": "A 3,800-line pure-Python toolkit (simulation, graphs, text, linear algebra, statistics, "
                       "CLI, tests). About 30 s to run; a realistic mix of hot numeric kernels and glue code.",
        "dir": "quanta",
        "trace_cmd": "python main.py --small",
        "trace_timeout_s": 240,
    },
    "textlab": {
        "title": "TextLab: quick demo",
        "description": "A 480-line text and numerics workbench. About 10 s to run; handy for a fast end-to-end "
                       "pass.",
        "dir": "textlab",
        "trace_cmd": "python main.py --small",
        "trace_timeout_s": 120,
    },
}


def resolve(name: str | None) -> dict:
    """Registry entry for `name` (None means the default demo) with the absolute source path under `path`."""
    key = (name or DEFAULT_DEMO).strip().lower()
    if key not in DEMOS:
        raise ValueError(f"unknown demo {name!r}; available: {', '.join(sorted(DEMOS))}")
    entry = dict(DEMOS[key])
    entry["name"] = key
    entry["path"] = DEMO_ROOT / entry["dir"]
    return entry


def _count(root: Path) -> tuple:
    files = lines = 0
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        files += 1
        lines += sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
    return files, lines


def list_demos() -> List[dict]:
    """`GET /api/demos`: name, title, description, python files, lines, default trace command."""
    out = []
    for key in DEMOS:
        e = resolve(key)
        files, lines = _count(e["path"]) if e["path"].is_dir() else (0, 0)
        out.append({"name": key, "title": e["title"], "description": e["description"], "files": files,
                    "lines": lines, "trace_cmd": e["trace_cmd"], "default": key == DEFAULT_DEMO})
    return out
