#!/usr/bin/env python3
"""Headless driver for the bundled demo projects: runs a full Studio job through the Engine facade.

    python scripts/demo_job.py smoke  [--demo quanta|textlab|all] [--offline|--online] [--timeout 900]
    python scripts/demo_job.py record [--demo quanta|textlab]            # needs GROQ_API_KEY or ANTHROPIC_API_KEY

`smoke` prints a table per demo and asserts the demo's expectations (EXPECT below): accelerated functions
with speedup > 1, LLM-fixed functions, a boundary-cost decline measured below 1x, not-eligible functions
with reasons, an end-to-end speedup with byte-identical stdout, and (for Quanta) that `python -m unittest`
passes inside the exported, accelerated project.

`record` runs the pipeline ONLINE with a real model, so every LLM reply is written to
demo/offline_cache/llm/<key>.json (provenance "recorded", by PYTHIA_RECORD_LLM_DIR), then snapshots the
.so files and their .meta.json built by that run into demo/offline_cache/so/.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
CACHE = ROOT / "demo" / "offline_cache"

# demo name -> expectations checked by `smoke`
EXPECT = {
    "quanta": {"wins": 6, "llm_fixed": 3, "declined_probe": 1, "not_eligible": 3, "e2e": 2.0, "unittest": True},
    "textlab": {"wins": 3, "llm_fixed": 2, "declined_probe": 1, "not_eligible": 3, "e2e": 1.5, "unittest": False},
}


def load_env_file() -> None:
    """Pick up GROQ_API_KEY / ANTHROPIC_API_KEY from ./.env (never printed)."""
    try:
        from pythia.studio.envfile import load_env
        load_env()
    except Exception:
        pass


def run_job(demo: str, home: Path, offline: bool, llm: bool, timeout: float):
    from pythia.studio.engine import Engine
    eng = Engine(home=str(home))
    events, done = [], threading.Event()

    def emit(type, data, stage=None, caption=None):
        events.append({"type": type, "stage": stage, "caption": caption, "data": data})
        if type == "job.done":
            done.set()
        elif type == "error" and (data or {}).get("fatal"):
            done.set()

    opts = {"offline": offline, "llm": llm, "pace_ms": 0}      # trace command + time budget come from the demo registry
    job_id = eng.start_job({"kind": "demo", "name": demo}, opts, emit)
    t0 = time.time()
    while not done.wait(1.0):
        if time.time() - t0 > timeout:
            eng.cancel(job_id)
            raise SystemExit(f"timeout after {timeout:.0f}s waiting for job {job_id}")
    return eng, job_id, events


def table(funcs, limit=None):
    rows = sorted(funcs, key=lambda f: (-(f.get("share") or 0), f["id"]))
    print(f"{'function':54s} {'status':12s} {'share':>6s} {'speedup':>9s}  reason")
    for f in rows[:limit]:
        sp = f.get("speedup") if f.get("speedup") is not None else f.get("probe_speedup")
        print(f"{f['id'][:54]:54s} {f['status']:12s} {100 * (f.get('share') or 0):5.1f}% "
              f"{('%.1fx' % sp) if sp else '-':>9s}  {(f.get('reason') or '')[:60]}")


def llm_fixed(eng, job_id, funcs):
    out = []
    for f in funcs:
        if f["status"] in ("verified", "guarded"):
            rec = eng.function(job_id, f["id"])
            if rec.get("rewrites"):
                out.append((f, rec))
    return out


def export_and_unittest(eng, job_id, tmp: Path):
    path = Path(eng.export(job_id, str(tmp / "export"), False))
    env = dict(os.environ)
    env["PYTHONPATH"] = str(path)
    env.pop("PYTHIA_ACCEL", None)
    r = subprocess.run([sys.executable, "-m", "unittest"], cwd=path, env=env, capture_output=True, text=True, timeout=600)
    tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
    return r.returncode == 0, "; ".join(tail), path


def smoke_one(demo: str, args) -> int:
    exp = EXPECT[demo]
    offline = args.offline or (not args.online and not (os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")))
    home = Path(tempfile.mkdtemp(prefix=f"pythia-smoke-{demo}-"))
    try:
        eng, job_id, events = run_job(demo, home, offline, True, args.timeout)
        funcs = eng.functions(job_id)
        print(f"\n== {demo}: job {job_id}  (offline={offline})\n")
        table(funcs, 40)
        e2e = [e["data"] for e in events if e["type"] == "bench.e2e"]
        if e2e:
            e = e2e[-1]
            print(f"\nend-to-end: {e['before_s']:.1f}s -> {e['after_s']:.1f}s = {e['speedup']:.2f}x, output match {e['output_match']}")
        wins = [f for f in funcs if f["status"] in ("verified", "guarded") and (f.get("speedup") or 0) > 1]
        fixed = llm_fixed(eng, job_id, funcs)
        declined = [f for f in funcs if f["status"] == "declined" and f.get("probe_speedup") is not None
                    and f["probe_speedup"] < 1]
        not_el = [f for f in funcs if f["status"] == "not_eligible" and f.get("reason")]
        problems = []
        if len(wins) < exp["wins"]:
            problems.append(f"need >={exp['wins']} verified/guarded functions with speedup>1, got {len(wins)}")
        if len(fixed) < exp["llm_fixed"]:
            problems.append(f"need >={exp['llm_fixed']} LLM-fixed functions verified, got {len(fixed)}")
        if len(declined) < exp["declined_probe"]:
            problems.append("need a boundary-cost decline whose probe was measured below 1x")
        if len(not_el) < exp["not_eligible"]:
            problems.append(f"need >={exp['not_eligible']} not_eligible functions with a reason, got {len(not_el)}")
        failed = [f["id"] for f in funcs if f["status"] == "failed"]
        if failed:
            problems.append("a compiled function failed replay: " + ", ".join(failed))
        if not e2e:
            problems.append("no end-to-end measurement")
        else:
            if not e2e[-1].get("output_match", False):
                problems.append("end-to-end stdout differs before/after splice")
            if (e2e[-1].get("speedup") or 0) < exp["e2e"]:
                problems.append(f"end-to-end speedup {e2e[-1].get('speedup')} < {exp['e2e']}")
        if exp["unittest"]:
            ok, tail, path = export_and_unittest(eng, job_id, home)
            print(f"unittest in the exported project ({path.name}): {'OK' if ok else 'FAILED'}  {tail}")
            if not ok:
                problems.append("python -m unittest fails in the exported accelerated project")
        print()
        if problems:
            print(f"SMOKE FAILED ({demo}):\n  " + "\n  ".join(problems))
            return 1
        print(f"SMOKE OK ({demo}): {len(wins)} accelerated, {len(fixed)} LLM-fixed, {len(declined)} declined (measured), "
              f"{len(not_el)} not eligible")
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


def smoke(args) -> int:
    names = list(EXPECT) if args.demo == "all" else [args.demo]
    rc = 0
    for n in names:
        rc |= smoke_one(n, args)
    return rc


def record(args) -> int:
    load_env_file()
    if not (os.environ.get("GROQ_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")):
        print("Neither GROQ_API_KEY (free, https://console.groq.com) nor ANTHROPIC_API_KEY is set: cannot record "
              "LLM replies. Export one (or put it in ./.env) and re-run.", file=sys.stderr)
        return 2
    demo = args.demo if args.demo != "all" else "quanta"
    home = Path(os.environ.get("PYTHIA_HOME") or tempfile.mkdtemp(prefix="pythia-record-"))
    (CACHE / "llm").mkdir(parents=True, exist_ok=True)
    (CACHE / "so").mkdir(parents=True, exist_ok=True)
    os.environ["PYTHIA_RECORD_LLM_DIR"] = str(CACHE / "llm")
    eng, job_id, events = run_job(demo, home, offline=False, llm=True, timeout=args.timeout)
    funcs = eng.functions(job_id)
    table(funcs, 60)
    n_rec = sum(1 for p in (CACHE / "llm").glob("*.json") if json.loads(p.read_text(encoding="utf-8")).get("provenance") == "recorded")
    k = 0
    for so in sorted((home / "build-cache").glob("*.so")):
        if ".tmp." in so.name:
            continue
        shutil.copy2(so, CACHE / "so" / so.name)
        meta = so.with_suffix(".meta.json")
        if meta.exists():
            shutil.copy2(meta, CACHE / "so" / meta.name)
        k += 1
    print(f"\nrecorded LLM replies in {CACHE / 'llm'}: {n_rec} with provenance 'recorded'; copied {k} .so files -> {CACHE / 'so'}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["smoke", "record"])
    ap.add_argument("--demo", default="all", choices=["quanta", "textlab", "all"])
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--online", action="store_true")
    ap.add_argument("--timeout", type=float, default=1500)
    a = ap.parse_args()
    load_env_file()
    sys.exit(smoke(a) if a.cmd == "smoke" else record(a))
