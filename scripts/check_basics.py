#!/usr/bin/env python3
"""The floor: every basic untyped program in scripts/basics/ must convert in-house (no LLM, no annotations) and,
compiled to C++, print byte-for-byte what CPython prints on the same stdin (incl. the uncaught-exception type).

Format of scripts/basics/*.py: programs separated by `#@@ name` lines; optional `#@@stdin` line inside a program
starts that program's input.   Usage: python scripts/check_basics.py [name ...] [--jobs N] [-v]
Exit 0 only if 100% pass.  Runs the same code path as the app (pythia.studio.converter.convert)."""
import argparse
import concurrent.futures as cf
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["GROQ_API_KEY"] = ""          # zero LLM involvement, whatever .env says
os.environ["ANTHROPIC_API_KEY"] = ""

from pythia.studio import converter  # noqa: E402
from pythia.studio.server import playground  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("names", nargs="*")
ap.add_argument("--jobs", type=int, default=4)
ap.add_argument("-v", "--verbose", action="store_true")
a = ap.parse_args()
cache = Path(tempfile.gettempdir()) / "pythia-basics-cache"


def load():
    out = []
    for f in sorted((ROOT / "scripts" / "basics").glob("*.py")):
        parts = re.split(r"^#@@ (\S+)\n", f.read_text(encoding="utf-8"), flags=re.M)
        for name, body in zip(parts[1::2], parts[2::2]):
            src, _, stdin = body.partition("#@@stdin\n")
            out.append((name, src, stdin))
    return out


def run_one(item):
    name, src, stdin = item
    verify = lambda code, sin, orig: playground.run_snippet(code, cache, sin, orig)  # noqa: E731
    try:
        res = converter.convert(src, {}, playground.compile_snippet, stdin, verify)
    except Exception as e:                                           # a crash is a failure, never a skip
        return name, "CRASH", f"{type(e).__name__}: {e}"
    if not res["ok"]:
        return name, "NOCONV", (res.get("error") or "")[:300]
    final = res["source"]
    run = playground.run_snippet(final, cache, stdin, reference=src)
    if not run.get("ok"):
        return name, "NORUN", (run.get("error") or "")[:300]
    if not run["same"]:
        py, cp = run["python"], run["cpp"]
        return name, "DIFFERS", (run.get("explain") or "") + f" py={py['stdout'][-120:]!r}/{py.get('exception')} " \
                                                              f"cpp={cp['stdout'][-120:]!r}/{cp.get('exception')}"
    return name, "ok", f"{run['python']['time_ms']} ms vs {run['cpp']['time_ms']} ms"


items = [i for i in load() if not a.names or i[0] in a.names]
if not items:
    sys.exit("no programs")
first = run_one(items[0])                                            # warm the runtime object cache single-threaded
results = [first]
with cf.ThreadPoolExecutor(a.jobs) as ex:
    results += list(ex.map(run_one, items[1:]))
bad = [r for r in results if r[1] != "ok"]
for name, status, detail in results:
    if status != "ok" or a.verbose:
        print(f"{status:<7} {name:<28} {detail}")
print(f"\n{len(results) - len(bad)}/{len(results)} basic programs convert and match CPython")
sys.exit(1 if bad else 0)
