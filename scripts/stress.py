#!/usr/bin/env python3
"""Stress the whole pipeline on big real-world Python repos, automatically, no LLM.

    python scripts/stress.py OWNER/REPO [OWNER/REPO ...] [--limit N] [--jobs 6] [--out build/stress]

Downloads each repo (GitHub zip), runs every file through scripts/_stress_one.py (convert -> PySub type check ->
C++ build -> run vs CPython) and prints: per-stage counts, the BUGS (build failures and output differences,
which must be zero), and the most common type-check rejection reasons (the next things to build).
Results go to <out>/<repo>.jsonl so a rerun can be compared with `--compare previous.jsonl`.
"""
import argparse
import collections
import concurrent.futures as cf
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pythia.studio import ingest  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("repos", nargs="+")
ap.add_argument("--limit", type=int, default=0, help="at most N files per repo (0 = all)")
ap.add_argument("--jobs", type=int, default=6)
ap.add_argument("--timeout", type=int, default=90)
ap.add_argument("--out", default=str(ROOT / "build" / "stress"))
ap.add_argument("--top", type=int, default=30)
a = ap.parse_args()
PY = sys.executable
out_dir = Path(a.out)
out_dir.mkdir(parents=True, exist_ok=True)


def fetch(spec: str) -> Path:
    cache = Path(tempfile.gettempdir()) / "pythia-stress-repos" / spec.replace("/", "__")
    if not cache.exists():
        ingest._github_zip(f"https://github.com/{spec}", cache, lambda *x, **k: None)
    return cache


def run_one(f: Path, base: Path) -> dict:
    try:
        p = subprocess.run([PY, "-I", str(ROOT / "scripts" / "_stress_one.py"), str(f), str(base)],
                           capture_output=True, text=True, timeout=a.timeout, cwd=str(ROOT))
        for line in reversed(p.stdout.splitlines()):
            if line.startswith("{"):
                return json.loads(line)
        return {"file": f.relative_to(base).as_posix(), "stage": "convert", "detail": "worker crashed: " + p.stderr[-200:]}
    except subprocess.TimeoutExpired:
        return {"file": f.relative_to(base).as_posix(), "stage": "skip", "detail": "worker timed out"}


def norm(msg: str) -> str:
    msg = re.sub(r"`[^`]*`", "`X`", msg)
    msg = re.sub(r"'[^']*'", "'X'", msg)
    msg = re.sub(r"\b\d+(\.\d+)?\b", "N", msg)
    return msg[:110]


for spec in a.repos:
    base = fetch(spec)
    files = sorted(p for p in base.rglob("*.py")
                   if not any(part.startswith(".") or part in ("venv", "node_modules", "site-packages", "docs")
                              for part in p.relative_to(base).parts))
    if a.limit:
        step = max(1, len(files) // a.limit)
        files = files[::step][:a.limit]
    print(f"\n=== {spec}: {len(files)} files", flush=True)
    rows = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        for i, row in enumerate(ex.map(lambda f: run_one(f, base), files), 1):
            rows.append(row)
            if i % 25 == 0:
                print(f"  ...{i}/{len(files)}", flush=True)
    (out_dir / (spec.replace("/", "__") + ".jsonl")).write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    by = collections.Counter(r["stage"] for r in rows)
    attempted = len(rows) - by["skip"] - by["blocked"]
    print("  stages:", dict(by))
    print(f"  attempted (not skipped/blocked): {attempted}; compiled and identical: {by["same"] + by["driven"]} "
          f"({100 * (by["same"] + by["driven"]) / max(attempted, 1):.0f}%; own-run {by["same"]}, generated-input {by["driven"]})")
    bugs = [r for r in rows if r["stage"] in ("build", "differs", "convert")]
    if bugs:
        print(f"  BUGS ({len(bugs)}):")
        for r in bugs[:25]:
            extra = f" py={r.get('py_out', '')[:60]!r} cpp={r.get('cpp_out', '')[:60]!r}" if r["stage"] == "differs" else ""
            print(f"    {r['stage']:<9} {r['file']}: {r['detail'][:160]}{extra}")
    tc = collections.Counter(norm(r.get("reason") or r["detail"]) for r in rows if r["stage"] == "typecheck")
    print(f"  top type-check rejections ({sum(tc.values())} files):")
    for k, v in tc.most_common(a.top):
        print(f"    {v:>4}  {k}")
    bl = collections.Counter()
    for r in rows:
        if r["stage"] == "blocked":
            for part in r["detail"].split("; "):
                bl[re.sub(r"\(.*", "", part)[:40]] += 1
    print("  out of scope (blocked):", dict(bl.most_common(8)))
