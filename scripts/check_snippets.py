#!/usr/bin/env python3
"""The pasted-snippet experience, offline: every snippet in scripts/snippets/*.py (separated by `#@@ name` lines)
goes through the in-house converter, the PySub type checker, and, when it has output, a CPython-vs-C++ run.
Usage: python scripts/check_snippets.py [name ...]"""
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pythia.convert import to_pysub  # noqa: E402
from pythia.studio import explain  # noqa: E402
from pythia.studio.server import playground  # noqa: E402

want = set(sys.argv[1:])
cache = Path(tempfile.gettempdir()) / "pythia-pg-cache"
rows = []
for f in sorted((ROOT / "scripts" / "snippets").glob("*.py")):
    for chunk in re.split(r"^#@@ (\S+)\n", f.read_text(encoding="utf-8"), flags=re.M)[1:][::1]:
        pass
    parts = re.split(r"^#@@ (\S+)\n", f.read_text(encoding="utf-8"), flags=re.M)
    for name, src in zip(parts[1::2], parts[2::2]):
        if want and name not in want:
            continue
        r = to_pysub(src, "", run=False, check=False)
        c = playground.compile_snippet(r.source)
        status, detail = "TYPECHECK", ""
        if c["ok"]:
            has_out = "print(" in r.source
            if not has_out:
                status = "COMPILES"
            else:
                run = playground.run_snippet(r.source, cache, "", reference=src)
                status = "SAME" if run.get("ok") and run.get("same") else "DIFFERS"
                if status == "DIFFERS":
                    detail = (run.get("error") or "")[:160] or f"{run['python']['stdout'][:60]!r} vs {run['cpp']['stdout'][:60]!r}"
        else:
            d = c["diagnostics"][0]
            detail = f"line {d['line']}: {d['msg']}"
            blocks = explain.blockers(src)
            if blocks:
                status, detail = "BLOCKED", blocks[0]["what"]
        rows.append((name, status, detail))
        print(f"{status:<9} {name:<22} {detail}", flush=True)
ok = sum(1 for _n, s, _d in rows if s in ("SAME", "COMPILES"))
print(f"\n{ok}/{len(rows)} snippets compile (or compile and match CPython)")
sys.exit(0 if ok == len(rows) else 1)
