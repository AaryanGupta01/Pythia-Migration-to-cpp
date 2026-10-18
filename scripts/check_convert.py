#!/usr/bin/env python3
"""Live check of the Playground's AI conversion (needs GROQ_API_KEY or ANTHROPIC_API_KEY, e.g. in .env):
convert studio/examples/student_grades.py to PySub, then run the ORIGINAL under CPython and the CONVERTED program
compiled to C++ on the same scripted stdin, and require identical output.
Usage: python scripts/check_convert.py [file.py] [--stdin FILE]"""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pythia.studio.envfile import load_env  # noqa: E402

load_env()
from pythia.studio import converter  # noqa: E402
from pythia.studio.server import playground  # noqa: E402

STDIN = "\n".join([
    "1", "Ada Lovelace", "91.5",
    "1", "Linus", "48",
    "1", "Grace", "not-a-number",
    "1", "Grace", "77.25",
    "1", "Ken", "150",
    "1", "Bob", "77.25",
    "1", "Zed", "91.5",
    "2", "3",
    "4", "  grace ",
    "4", "nobody",
    "5", "6", "9", "7"]) + "\n"

src_path = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ROOT / "studio/examples/student_grades.py"
src = src_path.read_text(encoding="utf-8")
t = time.time()
res = converter.convert(src, {}, playground.compile_snippet, STDIN, playground.run_python)
print(f"provider={res.get('provider')} model={res.get('model')} ok={res['ok']} in {time.time() - t:.1f}s")
for a in res["attempts"]:
    print(f"  attempt {a['attempt']}: ok={a['ok']} {a['latency_ms']} ms  errors={len(a['diagnostics'])} {a.get('error') or ''}")
    for d in a["diagnostics"][:4]:
        print(f"      line {d['line']}: {d['msg']}")
if not res["ok"]:
    sys.exit("CONVERSION FAILED: " + str(res.get("error")))
out = ROOT / "build" / "converted_student_grades.py"
out.parent.mkdir(exist_ok=True)
out.write_text(res["source"], encoding="utf-8")
print("converted program saved to", out)
run = playground.run_snippet(res["source"], Path(tempfile.gettempdir()) / "pythia-pg-cache", STDIN, reference=src)
if not run["ok"]:
    sys.exit("RUN FAILED: " + str(run.get("error")))
print(f"CPython (original) {run['python']['time_ms']} ms   C++ (converted) {run['cpp']['time_ms']} ms   same={run['same']}")
if not run["same"]:
    import difflib
    print("".join(difflib.unified_diff(run["python"]["stdout"].splitlines(True), run["cpp"]["stdout"].splitlines(True),
                                       "original (CPython)", "converted (C++)")))
    sys.exit("OUTPUT DIFFERS")
print(run["cpp"]["stdout"][-700:])
print("CONVERT OK: original Python and compiled PySub produce identical output")
