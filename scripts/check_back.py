#!/usr/bin/env python3
"""End-to-end check of the analyzer back half (NOT a test suite).

    wsl -e bash -lc 'cd <repo> && ~/pythia-venv/bin/python scripts/check_back.py'

Builds a tiny project under a temp dir, runs the real pipeline (trace -> rank -> compile -> replay ->
bench -> splice -> e2e), then checks: verified functions with speedup, identical output of the spliced
project, fallback when the .so is deleted, a mismatching module is caught by replay, decide() reverts
the splice, export builds a runnable folder, cancellation works.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pythia.studio import replay, trace                      # noqa: E402
from pythia.studio.engine import Engine                      # noqa: E402
from pythia.studio.models import FunctionRecord              # noqa: E402

SRC_M = '''"""numeric kernels"""
import math

def collatz_max(limit: int) -> int:
    best = 0
    for n in range(1, limit):
        x = n
        steps = 0
        while x != 1:
            if x % 2 == 0:
                x = x // 2
            else:
                x = 3 * x + 1
            steps += 1
        if steps > best:
            best = steps
    return best

def sieve_count(n: int) -> int:
    flags = [True] * (n + 1)
    count = 0
    for i in range(2, n + 1):
        if flags[i]:
            count += 1
            j = i * i
            while j <= n:
                flags[j] = False
                j += i
    return count

def total(xs):
    s = 0
    for x in xs:
        s += x * 2
    return s

def decorated(n: int) -> int:
    return n * 2 + 1

def uses_math(x: float) -> float:
    return math.sqrt(x)
'''
MAIN = '''
from pkg.kern import collatz_max, sieve_count, total, decorated, uses_math
print(collatz_max(30000), sieve_count(200000), total([1, 2, 3]), decorated(4), uses_math(16.0))
'''


def ok(msg):
    print("  ok  ", msg)


def wait(eng, jid, timeout=300):
    t0 = time.time()
    while eng.job(jid)["state"] == "running":
        assert time.time() - t0 < timeout, "job timed out"
        time.sleep(0.2)
    return eng.job(jid)


def run(cwd, *args, env=None):
    e = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True, text=True, env=e)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="pythia_check_"))
    proj = tmp / "proj"
    (proj / "pkg").mkdir(parents=True)
    (proj / "pkg" / "__init__.py").write_text("")
    (proj / "pkg" / "kern.py").write_text(SRC_M)
    (proj / "main.py").write_text(MAIN)
    baseline = run(proj, "main.py").stdout
    assert baseline.strip(), "project must run"

    eng = Engine(str(tmp / "home"))
    events = []
    env = eng.env()
    assert env["compiler"]["found"] and env["pybind11"], env
    ok("env: compiler + pybind11 found")

    # ---- full pipeline
    jid = eng.start_job({"kind": "folder", "path": str(proj)}, {"trace_cmd": "python main.py", "trace_timeout_s": 120},
                        lambda t, d, stage=None, caption=None: events.append((t, stage, d)))
    job = wait(eng, jid)
    assert job["state"] == "done", job
    types = {e[0] for e in events}
    for t in ("job.start", "ingest.done", "scan.done", "trace.progress", "trace.done", "rank.done", "compile.done",
              "verify.result", "bench.result", "splice.ready", "bench.e2e", "agent.step", "job.done", "stage"):
        assert t in types, f"missing event {t}: {sorted(types)}"
    ok("all event types emitted: " + ", ".join(sorted(types)))
    funcs = {f["id"]: f for f in eng.functions(jid)}
    for k, f in funcs.items():
        print("     ", k, f["status"], f["speedup"], f["share"])
    good = [f for f in funcs.values() if f["status"] in ("verified", "guarded")]
    assert len(good) >= 2 and all(f["speedup"] and f["speedup"] > 1 for f in good), good
    assert funcs["pkg/kern.py::uses_math"]["status"] == "not_eligible"
    assert funcs["pkg/kern.py::collatz_max"]["share"] > 0.1
    ok(f"{len(good)} functions verified/guarded with speedup > 1")
    rec = eng.function(jid, "pkg/kern.py::collatz_max", stages=True)
    assert [j["key"] for j in rec["journey"]][0] == "original" and len(rec["journey"]) == 16
    assert rec["replay"]["matched"] == rec["replay"]["total"] > 0 and rec["bench"]["speedup"] > 1
    assert rec["splice"]["applied"] and "_pythia_accelerated" in rec["splice"]["diff"]
    assert rec["stages"].get("ok") and rec["build"]["ok"] and rec["sources"]["cpp"]
    ok("record: journey, replay, bench, splice diff, stages, cpp")
    assert job["summary"]["e2e_speedup"] and job["e2e"]["output_match"]
    ok(f"end-to-end {job['e2e']['speedup']:.2f}x, output identical")

    # ---- spliced project runs identically; falls back when the .so is deleted
    ws = eng._ws(job["workspace_id"])
    out = run(ws.work, "main.py", env={"PYTHONPATH": str(ws.work)})
    assert out.stdout == baseline, (out.stdout, out.stderr)
    probe = run(ws.work, "-c", "import pkg.kern as k; print(hasattr(k.collatz_max, '_pythia_native'))")
    assert probe.stdout.strip() == "True", probe
    for so in (ws.work / "_pythia_accel" / "lib").glob("*"):
        so.unlink()
    out = run(ws.work, "main.py", env={"PYTHONPATH": str(ws.work)})
    assert out.stdout == baseline and out.returncode == 0, out
    probe = run(ws.work, "-c", "import pkg.kern as k; print(hasattr(k.collatz_max, '_pythia_native'))")
    assert probe.stdout.strip() == "False"
    ok("spliced project output identical; falls back to Python when .so is missing")

    # ---- decide(): reject reverts the file, accept re-applies (+ restores the .so)
    fid = "pkg/kern.py::collatz_max"
    eng.decide(jid, fid, "rejected")
    assert "_pythia_accelerated(\"" not in (ws.work / "pkg/kern.py").read_text().split("def sieve_count")[0]
    eng.decide(jid, fid, "accepted")
    assert eng.function(jid, fid)["decision"] == "accepted" and eng.function(jid, fid)["splice"]["applied"]
    eng.decide(jid, "all", "pending")
    ok("decide: reject reverts, accept re-applies")

    # ---- tree / file / diff / settings / list_dir
    tree = eng.tree(ws.ws_id)
    kern = next(c for n in tree if n["name"] == "pkg" for c in n["children"] if c["name"] == "kern.py")
    assert kern["badges"]["accelerated"] >= 2 and kern["badges"]["hotspots"] >= 2
    assert "_pythia_accelerated" in eng.read_file(ws.ws_id, "pkg/kern.py")["content"]
    assert "_pythia_accelerated" not in eng.read_file(ws.ws_id, "pkg/kern.py", "original")["content"]
    d = eng.file_diff(jid, "pkg/kern.py")
    assert d["original"] != d["modified"]
    assert eng.list_dir(str(tmp))["entries"] and "has_api_key" in eng.settings()
    ok("tree badges, read_file, file_diff, list_dir, settings")

    # ---- export (folder + zip) is runnable and carries the report
    dest = tmp / "exported"
    p = eng.export(jid, str(dest), False)
    assert (dest / "PYTHIA_REPORT.md").exists() and (dest / "build_accel.sh").exists()
    assert (dest / "_pythia_accel" / "src").is_dir()
    out = run(dest, "main.py", env={"PYTHONPATH": str(dest)})
    assert out.stdout == baseline
    z = eng.export(jid, None, True)
    assert z.endswith(".zip") and Path(z).exists()
    assert "collatz_max" in eng.report(jid)["markdown"]
    ok("export folder + zip, report, runnable")

    # ---- persistence: a fresh Engine sees the finished job and its event log
    eng2 = Engine(str(tmp / "home"))
    assert eng2.job(jid)["state"] == "done" and len(eng2.functions(jid)) == len(funcs)
    assert eng2.events(jid, 0)["last_seq"] >= len(events)
    ok("job reloaded from disk")

    # ---- replay catches a wrong implementation (counterexample) and honours FallbackError
    fake = tmp / "fake"
    fake.mkdir()
    (fake / "bad_mod.py").write_text("class FallbackError(Exception): pass\n"
                                     "def total(xs):\n    return sum(xs) * 2 + (1 if len(xs) == 3 else 0)\n")
    (fake / "fb_mod.py").write_text("class FallbackError(Exception): pass\n"
                                    "def total(xs):\n    raise FallbackError()\n")
    r = FunctionRecord(id="pkg/kern.py::total", file="pkg/kern.py", name="total")
    r.build = {"exposed": [{"name": "total", "params": ["list[int]"], "ret": "int"}]}
    r1 = replay.replay(r, ws, fake / "bad_mod.py", "bad_mod", None)
    assert r1["status"] == "failed" and r1["first_mismatch"]["kind"] == "value", r1
    r2 = replay.replay(r, ws, fake / "fb_mod.py", "fb_mod", None)
    assert r2["status"] == "failed" and r2["skipped"] > 0 and r2["total"] == 0, r2
    ok("replay: wrong module -> failed + counterexample; FallbackError -> skipped")

    # ---- splice edge cases: shebang/docstring/future import, existing decorators, multi-line def, CRLF
    from pythia.studio import splice
    from pythia.studio.models import Workspace
    sroot = tmp / "sp"
    (sroot / "original").mkdir(parents=True)
    weird = ('#!/usr/bin/env python
"""doc"""
from __future__ import annotations
import functools

'
             '@functools.lru_cache(maxsize=None)
@functools.wraps(print)
def f(
    a: int,
    b: int = 2,
) -> int:
    return a + b
')
    (sroot / "original" / "w.py").write_bytes(weird.encode())
    shutil.copytree(sroot / "original", sroot / "work")
    sws = Workspace("sp000000", "sp", sroot, sroot / "original", sroot / "work")
    sr = FunctionRecord(id="w.py::f", file="w.py", name="f")
    (fake / "pythia_zz.py").write_text("def f(a, b=2):
    return a + b
")
    splice.apply(sws, sr, "pythia_zz", fake / "pythia_zz.py")
    new = (sroot / "work" / "w.py").read_bytes().decode()
    assert new.startswith("#!/usr/bin/env python
\"\"\"doc\"\"\"
from __future__"), new
    assert new.index("from _pythia_accel") > new.index("import functools") and "
" not in new.replace("
", "")
    assert new.index("@_pythia_accelerated") > new.index("@functools.wraps") and new.index("@_pythia_accelerated") < new.index("def f(")
    splice.apply(sws, sr, "pythia_zz", fake / "pythia_zz.py")
    assert (sroot / "work" / "w.py").read_bytes().decode() == new
    splice.revert(sws, sr)
    assert (sroot / "work" / "w.py").read_bytes() == weird.encode()
    ok("splice: shebang/docstring/__future__/decorators/multi-line def/CRLF; idempotent; exact revert")

    # ---- trace: sys.setprofile fallback agrees with sys.monitoring
    ws2 = ws
    tg = {"pkg/kern.py::sieve_count": {"file": "pkg/kern.py", "name": "sieve_count", "line": 1}}
    os.environ["PYTHIA_TRACE_NO_MON"] = "1"
    t2 = trace.run_trace(ws2, "python main.py", 60, tg, lambda *a, **k: None)
    del os.environ["PYTHIA_TRACE_NO_MON"]
    assert t2.ok and t2.per_fn["pkg/kern.py::sieve_count"]["calls"] == 1
    assert t2.per_fn["pkg/kern.py::sieve_count"]["arg_types"] == ["int"]
    ok("trace via sys.setprofile fallback")

    # ---- cancellation + trace timeout
    (proj / "slow.py").write_text("import time\nfrom pkg.kern import total\nwhile True:\n    total([1]); time.sleep(0.01)\n")
    t0 = time.time()
    j2 = eng.start_job({"kind": "folder", "path": str(proj)}, {"trace_cmd": "python slow.py", "trace_timeout_s": 3}, None)
    job2 = wait(eng, j2, 120)
    assert job2["state"] == "done" and eng.events(j2)["events"]
    tdone = next(e for e in eng.events(j2)["events"] if e["type"] == "trace.done")["data"]
    assert tdone["timed_out"] and tdone["calls"] > 0
    j3 = eng.start_job({"kind": "folder", "path": str(proj)}, {"trace_cmd": "python slow.py", "trace_timeout_s": 60}, None)
    time.sleep(4)
    eng.cancel(j3)
    job3 = wait(eng, j3, 60)
    assert job3["state"] == "cancelled", job3
    ok("trace timeout kept partial data; cancel stops the job")

    shutil.rmtree(tmp, ignore_errors=True)
    print("CHECK BACK: ALL OK")


if __name__ == "__main__":
    main()
