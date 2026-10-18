#!/usr/bin/env python3
"""Every PySub example shipped in the Playground (studio/web/src/examples.ts) must compile and print exactly what
CPython prints, on its sample stdin. Plain-Python examples (meant for AI conversion) must be rejected by the type
checker with readable errors. Usage: python scripts/check_examples.py"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pythia.studio.server import playground  # noqa: E402

ts = (ROOT / "studio/web/src/examples.ts").read_text(encoding="utf-8")
consts = {m.group(1): m.group(2).replace("\\\\", "\\") for m in re.finditer(r"const (\w+) = `(.*?)`", ts, re.S)}
entries = re.findall(r"\{ id: '(\w+)', title: '([^']+)', note: '([^']+)', code: (\w+)(?:, stdin: (?:'((?:[^'\\]|\\.)*)'|(\w+)))? \}", ts)
ok = True
for eid, title, note, code_name, stdin_lit, stdin_name in entries:
    code = consts[code_name]
    stdin = consts[stdin_name] if stdin_name else (stdin_lit.encode().decode("unicode_escape") if stdin_lit else "")
    comp = playground.compile_snippet(code)
    plain = note.lower().startswith("plain python")
    if plain:
        good = not comp["ok"] and len(comp["diagnostics"]) > 0
        print(f"{'ok ' if good else 'BAD'} {title:40} rejected as expected ({len(comp['diagnostics'])} errors) -> convert with AI")
        ok &= good
        continue
    if not comp["ok"]:
        print(f"BAD {title:40} does not compile: {comp['diagnostics'][:2]}")
        ok = False
        continue
    run = playground.run_snippet(code, Path(tempfile.gettempdir()) / "pythia-pg-cache", stdin)
    good = run["ok"] and run["same"] and not run["python"]["exception"]
    print(f"{'ok ' if good else 'BAD'} {title:40} identical={run.get('same')}  python {run['python']['time_ms'] if run.get('python') else '-'} ms"
          f"  c++ {run['cpp']['time_ms'] if run.get('cpp') else '-'} ms")
    if not good:
        print(run.get("error"), run.get("python"), run.get("cpp"))
    ok &= good
print("EXAMPLES OK" if ok else "EXAMPLES FAILED")
sys.exit(0 if ok else 1)
