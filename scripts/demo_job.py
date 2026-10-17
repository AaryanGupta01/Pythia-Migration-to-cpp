#!/usr/bin/env python3
"""Headless driver for the demo project: runs a full Studio job through the Engine facade.

    python scripts/demo_job.py smoke [--offline|--online] [--timeout 600]   # assertions, used by smoke.sh
    python scripts/demo_job.py record                                       # needs ANTHROPIC_API_KEY

`smoke` asserts: >=3 functions verified/guarded with speedup > 1, >=1 declined, >=1 not_eligible with a
reason; prints a table and exits non-zero otherwise. `record` runs the pipeline online, then writes every
LLM reply it used to demo/offline_cache/llm/<key>.json (provenance "recorded") and copies the built .so
files into demo/offline_cache/so/.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CACHE = ROOT / "demo" / "offline_cache"
TRACE_CMD = "python main.py --small"


def run_job(home: Path, offline: bool, llm: bool, timeout: float):
    from pythia.studio.engine import Engine           # lazy: needs Agents B1/B2/A to have landed
    eng = Engine(home=str(home))
    events, done = [], threading.Event()

    def emit(type, data, stage=None, caption=None):
        events.append({"type": type, "stage": stage, "caption": caption, "data": data})
        if type == "job.done":
            done.set()
        elif type == "error" and (data or {}).get("fatal"):
            done.set()

    opts = {"trace_cmd": TRACE_CMD, "trace_timeout_s": 120, "offline": offline, "llm": llm, "pace_ms": 0}
    job_id = eng.start_job({"kind": "demo"}, opts, emit)
    t0 = time.time()
    while not done.wait(1.0):
        if time.time() - t0 > timeout:
            eng.cancel(job_id)
            raise SystemExit(f"timeout after {timeout:.0f}s waiting for job {job_id}")
    return eng, job_id, events


def table(funcs):
    rows = sorted(funcs, key=lambda f: -(f.get("share") or 0))
    print(f"{'function':44s} {'status':12s} {'share':>6s} {'speedup':>9s}  reason")
    for f in rows:
        sp = f.get("speedup") if f.get("speedup") is not None else f.get("probe_speedup")
        print(f"{f['id'][:44]:44s} {f['status']:12s} {100 * (f.get('share') or 0):5.1f}% "
              f"{('%.1fx' % sp) if sp else '-':>9s}  {(f.get('reason') or '')[:70]}")


def smoke(args):
    offline = args.offline or (not args.online and not os.environ.get("ANTHROPIC_API_KEY"))
    home = Path(tempfile.mkdtemp(prefix="pythia-smoke-"))
    try:
        eng, job_id, events = run_job(home, offline, True, args.timeout)
        funcs = eng.functions(job_id)
        print(f"\njob {job_id}  (offline={offline})\n")
        table(funcs)
        e2e = [e["data"] for e in events if e["type"] == "bench.e2e"]
        if e2e:
            e = e2e[-1]
            print(f"\nend-to-end: {e['before_s']:.1f}s -> {e['after_s']:.1f}s = {e['speedup']:.2f}x, output match {e['output_match']}")
        wins = [f for f in funcs if f["status"] in ("verified", "guarded") and (f.get("speedup") or 0) > 1]
        declined = [f for f in funcs if f["status"] == "declined"]
        not_el = [f for f in funcs if f["status"] == "not_eligible" and f.get("reason")]
        problems = []
        if len(wins) < 3:
            problems.append(f"need >=3 verified/guarded functions with speedup>1, got {len(wins)}")
        if not declined:
            problems.append("need >=1 declined function (boundary cost)")
        if not not_el:
            problems.append("need >=1 not_eligible function with a reason")
        if any(f["status"] == "failed" for f in funcs):
            problems.append("a compiled function failed replay: " + ", ".join(f["id"] for f in funcs if f["status"] == "failed"))
        if e2e and not e2e[-1].get("output_match", True):
            problems.append("end-to-end output differs before/after splice")
        print()
        if problems:
            print("SMOKE FAILED:\n  " + "\n  ".join(problems))
            return 1
        print(f"SMOKE OK: {len(wins)} accelerated, {len(declined)} declined, {len(not_el)} not eligible")
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


def record(args):
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set: cannot record LLM replies. Export a key and re-run "
              "(offline demo keeps working with the authored cache meanwhile).", file=sys.stderr)
        return 2
    home = Path(os.environ.get("PYTHIA_HOME") or Path.home() / ".pythia-studio")
    eng, job_id, events = run_job(home, offline=False, llm=True, timeout=args.timeout)
    (CACHE / "llm").mkdir(parents=True, exist_ok=True)
    (CACHE / "so").mkdir(parents=True, exist_ok=True)
    try:
        from pythia.studio.fixer import cache_key
    except ImportError:
        def cache_key(src, attempt):
            return hashlib.sha256(f"{hashlib.sha256(src.encode()).hexdigest()}|{attempt}".encode()).hexdigest()
    n = 0
    for s in eng.functions(job_id):
        rec = eng.function(job_id, s["id"])
        if not rec.get("rewrites"):
            continue
        src = (rec["sources"].get("annotated") or rec["sources"]["original"])
        for rw in rec["rewrites"]:
            if rw.get("source") != "api":
                continue
            entry = {"model": events[0]["data"].get("options", {}).get("model", "claude-sonnet-5-5"),
                     "attempt": rw["attempt"], "function_sha": hashlib.sha256(src.encode()).hexdigest(),
                     "response": rw["pysub"], "provenance": "recorded"}
            (CACHE / "llm" / f"{cache_key(src, rw['attempt'])}.json").write_text(json.dumps(entry, indent=2))
            n += 1
    k = 0
    for so in (home / "build-cache").glob("*.so"):
        shutil.copy2(so, CACHE / "so" / so.name)
        meta = so.with_suffix(".meta.json")
        if meta.exists():
            shutil.copy2(meta, CACHE / "so" / meta.name)
        k += 1
    print(f"recorded {n} LLM replies -> {CACHE / 'llm'}; copied {k} .so files -> {CACHE / 'so'}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["smoke", "record"])
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    sys.exit(smoke(a) if a.cmd == "smoke" else record(a))
