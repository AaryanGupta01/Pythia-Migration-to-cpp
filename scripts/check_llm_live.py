#!/usr/bin/env python3
"""Live LLM check (needs GROQ_API_KEY or ANTHROPIC_API_KEY, e.g. from .env): a snippet whose hot functions
use constructs outside PySub, run through the real Engine with the real model. Prints each fix attempt."""
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("PYTHIA_HOME", tempfile.mkdtemp(prefix="pythia-live-"))

from pythia.studio.engine import Engine  # noqa: E402

CODE = '''def squares_sum(n: int) -> int:
    xs = [i * i for i in range(n)]
    total = 0
    for x in xs:
        total += x % 7
    return total


def weighted(vals: list[float]) -> float:
    acc = 0.0
    for i, v in enumerate(vals):
        acc += v * (i + 1) if v > 0 else -v
    return acc


def run() -> None:
    t = 0
    for k in range(300):
        t += squares_sum(20000)
    w = 0.0
    data = [float(i % 13) - 4.0 for i in range(20000)]
    for k in range(300):
        w += weighted(data)
    print(t, w)


run()
'''
events = []
done = threading.Event()


def emit(type, data, stage=None, caption=None):
    events.append((type, data))
    if type == "fix.attempt":
        print(f"  fix.attempt #{data['attempt']} via {data['source']} ok={data['ok']} err={str(data['error'])[:90]!r}")
    if type == "job.done":
        done.set()


eng = Engine()
print("llm:", eng.env()["llm"])
jid = eng.start_job({"kind": "snippet", "code": CODE, "name": "livecheck"},
                    {"offline": False, "trace_cmd": "python livecheck.py"}, emit)
if not done.wait(600):
    sys.exit("timeout")
for f in eng.functions(jid):
    print(f"{f['name']:14} {f['status']:12} {f['speedup']} {f['reason'] or ''}")
ok = any(t == "fix.attempt" for t, _ in events) and any(f["status"] in ("verified", "guarded") for f in eng.functions(jid)
                                                       if f["name"] in ("squares_sum", "weighted"))
print("LIVE LLM OK" if ok else "LIVE LLM FAILED")
sys.exit(0 if ok else 1)
