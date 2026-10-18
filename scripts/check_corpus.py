#!/usr/bin/env python3
"""Conversion regression suite: every program in scripts/corpus/ (ordinary Python, the kind people paste into
the Playground) goes through the converter (in-house first, the LLM only as a fallback), then the ORIGINAL runs under CPython and the CONVERTED program runs
compiled to C++ on the same stdin (<name>.stdin, if present); the outputs must match.
Without GROQ_API_KEY / ANTHROPIC_API_KEY only the in-house converter runs (zero LLM calls); failures are then
triaged into "pending compiler feature" (constructs the compiler is gaining natively) and real gaps.
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
from pythia.convert.pending import triage  # noqa: E402

CORPUS = ROOT / "scripts" / "corpus"
names = sys.argv[1:] or sorted(p.stem for p in CORPUS.glob("*.py"))
if not sys.argv[1:] and (ROOT / "studio" / "examples" / "student_grades.py").exists():
    names.append("../../studio/examples/student_grades")
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
    row = {"name": name, "converted": res["ok"], "attempts": len(res["attempts"]), "secs": round(secs, 1),
           "llm_calls": sum(1 for a in res["attempts"] if a.get("provider") != "pythia")}
    mine = next((a for a in res["attempts"] if a.get("provider") == "pythia"), None)
    if not res["ok"] and mine and mine.get("source"):
        tri = triage(mine["diagnostics"], mine["source"])
        row["pending"], row["real"] = tri["pending"], tri["real"] + mine.get("problems", [])
    if res["ok"]:
        (out_dir / f"{Path(name).name}.py").write_text(res["source"], encoding="utf-8")
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
    mark = "ok  " if row.get("same") else "PEND" if row.get("pending") and not row.get("real") else "FAIL"
    timing = f"{row['py_ms']:>8} ms -> {row['cpp_ms']:>7} ms" if "py_ms" in row else ""
    print(f"{mark} {name:<14} attempts={row['attempts']} {secs:5.1f}s {timing} {row.get('why', '')}", flush=True)
    if row.get("pending"):
        print("        pending compiler feature:", ", ".join(row["pending"]))
    for e in row.get("real", []):
        print("        in-house gap:", e)
    for e in row.get("errors", []) + row.get("blockers", []):
        print("       ", e)
(out_dir / "results.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
good = sum(1 for r in rows if r.get("same"))
limits = sum(1 for r in rows if r.get("limit"))
zero = sum(1 for r in rows if r.get("same") and r["llm_calls"] == 0)
pend = sum(1 for r in rows if r.get("pending") and not r.get("real"))
print(f"\n{zero}/{len(rows)} converted in-house with zero LLM calls; {pend} wait only on pending compiler features; "
      f"{sum(1 for r in rows if r.get('real'))} have in-house gaps")
print(f"\n{good}/{len(rows)} programs converted with identical output"
      + (f"; {limits} hit a documented PySub limit that the app explains" if limits else ""))
sys.exit(0 if good + limits == len(rows) else 1)
