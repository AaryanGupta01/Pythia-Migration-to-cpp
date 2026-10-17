"""Tiny .env loader (no dependency): KEY=VALUE lines from <repo>/.env and $PYTHIA_HOME/.env; never overrides real env."""
import os
from pathlib import Path


def load_env(*extra_dirs) -> None:
    here = Path(__file__).resolve().parents[2]
    home = Path(os.environ.get("PYTHIA_HOME") or Path.home() / ".pythia-studio")
    for d in (here, home, Path.cwd(), *map(Path, extra_dirs)):
        f = d / ".env"
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for ln in lines:
            ln = ln.strip()
            if not ln or ln.startswith("#") or "=" not in ln:
                continue
            k, v = ln.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
