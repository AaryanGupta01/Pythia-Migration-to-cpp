#!/usr/bin/env python3
"""Conversion regression suite: every program in scripts/corpus/ (ordinary Python, the kind people paste into
the Playground) goes through the AI converter, then the ORIGINAL runs under CPython and the CONVERTED program runs
compiled to C++ on the same stdin (<name>.stdin, if present); the outputs must match.
Needs GROQ_API_KEY or ANTHROPIC_API_KEY (e.g. in .env).
Usage: python scripts/check_corpus.py [name ...]"""
import json
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

CORPUS = ROOT / "scripts" / "corpus"
names = sys.argv[1:] or sorted(p.stem for p in CORPUS.glob("*.py"))
cache = Path(tempfile.gettempdir()) / "pythia-pg-cache"
out_dir = ROOT / "build" / "corpus"
out_dir.mkdir(parents=True, exist_ok=True)
rows = []
for name in names:
    src = (CORPUS / f"{name}.py").read_text(encoding="utf-8")
    stdin_p = CORPUS / f"{name}.stdin"
    stdin = stdin_p.read_text(encoding="utf-8") if stdin_p.exists() else ""
    t = time.time()
    res = converter.convert(src, {}, playground.compile_snippet, stdin,
                            lambda code, sin, orig: playground.run_snippet(code, cache, sin, orig))
    secs = time.time() - t
    row = {"name": name, "converted": res["ok"], "attempts": len(res["attempts"]), "secs": round(secs, 1)}
    if res["ok"]:
        (out_dir / f"{name}.py").write_text(res["source"], encoding="utf-8")
        run = playground.run_snippet(res["source"], cache, stdin, reference=src)
        row["same"] = bool(run.get("ok") and run.get("same"))
        if run.get("ok"):
            row["py_ms"], row["cpp_ms"] = run["python"]["time_ms"], run["cpp"]["time_ms"]
        if not row["same"]:
            row["why"] = run.get("error") or "output differs"
            if run.get("explain"):                       # a documented PySub limit (64-bit ints, ...), shown to the user
                row["limit"] = run["explain"]
                row["why"] = "known limit, explained to the user: " + run["explain"][:90] + "..."
    else:
        last = res["attempts"][-1] if res["attempts"] else {}
        row["why"] = res.get("error") or ""
        row["errors"] = [f"line {d['line']}: {d['msg']}" for d in (last.get("diagnostics") or [])[:3]]
        if res.get("limit"):                             # converter stopped on a documented limit, with the reason
            row["limit"] = res["error"]
        if res.get("blockers"):
            row["blockers"] = [b["what"] for b in res["blockers"]]
    rows.append(row)
    mark = "ok  " if row.get("same") else "FAIL"
    timing = f"{row['py_ms']:>8} ms -> {row['cpp_ms']:>7} ms" if "py_ms" in row else ""
    print(f"{mark} {name:<14} attempts={row['attempts']} {secs:5.1f}s {timing} {row.get('why', '')}", flush=True)
    for e in row.get("errors", []) + row.get("blockers", []):
        print("       ", e)
(out_dir / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
good = sum(1 for r in rows if r.get("same"))
limits = sum(1 for r in rows if r.get("limit"))
print(f"\n{good}/{len(rows)} programs converted with identical output"
      + (f"; {limits} hit a documented PySub limit that the app explains" if limits else ""))
sys.exit(0 if good + limits == len(rows) else 1)
