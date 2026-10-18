#!/usr/bin/env python3
"""End-to-end check of a RUNNING PYTHIA Studio (e.g. the installed Windows app):
key setup -> Playground AI conversion + run -> PySub example run -> demo analysis -> export -> run the export.
Usage: python scripts/check_installed.py --base http://127.0.0.1:8796 [--key-file .env] [--demo quanta|textlab]"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8765")
ap.add_argument("--key-file", default=str(ROOT / ".env"))
ap.add_argument("--demo", default="quanta")
a = ap.parse_args()


def call(method, path, body=None, timeout=600):
    req = urllib.request.Request(a.base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"null")


ok = True


def check(cond, msg):
    global ok
    print(("ok   " if cond else "FAIL ") + msg, flush=True)
    ok &= bool(cond)


env = call("GET", "/api/env")
check(env["compiler"]["found"], f"compiler: {env['compiler']['version']}")
check(call("GET", "/api/doctor")["ready"], "doctor: ready")

# 1. key, as the setup wizard does it
m = re.search(r"GROQ_API_KEY=(\S+)", Path(a.key_file).read_text()) if Path(a.key_file).exists() else None
if m:
    t = call("POST", "/api/settings/test-key", {"provider": "groq", "api_key": m.group(1)})
    check(t["ok"], f"key test: {t}")
    call("PUT", "/api/settings", {"provider": "groq", "api_key": m.group(1), "setup_done": True})
    check(call("GET", "/api/playground/convert/status")["enabled"], "AI conversion enabled after saving the key")
    check(not call("POST", "/api/settings/test-key", {"provider": "groq", "api_key": "gsk_wrong"})["ok"], "a wrong key is rejected")

# 2. Playground: plain Python -> AI conversion -> run original vs converted
src = (ROOT / "studio/examples/student_grades.py").read_text(encoding="utf-8")
stdin = "1\nAda\n91.5\n1\nLinus\n48\n1\nGrace\nabc\n1\nBob\n91.5\n2\n3\n4\nada\n5\n6\n7\n"
if m:
    t0 = time.time()
    conv = call("POST", "/api/playground/convert", {"source": src})
    check(conv["ok"], f"AI conversion in {time.time() - t0:.1f}s, {len(conv['attempts'])} attempt(s), {conv.get('model')}")
    if conv["ok"]:
        run = call("POST", "/api/playground/run", {"source": conv["source"], "stdin": stdin, "reference": src})
        check(run["ok"] and run["same"], f"original (CPython) == converted (C++): {run.get('same')} "
                                         f"[{run['python']['time_ms']} ms vs {run['cpp']['time_ms']} ms]")

# 3. Playground: a PySub program compiled to an .exe from the install folder
sieve = ("def count(n: int) -> int:\n    flags: list[bool] = []\n    for i in range(n + 1):\n        flags.append(True)\n"
         "    c: int = 0\n    for p in range(2, n + 1):\n        if flags[p]:\n            c += 1\n"
         "            for k in range(p * p, n + 1, p):\n                flags[k] = False\n    return c\n\n"
         "print(f\"{count(1000000):,} primes\")\n")
run = call("POST", "/api/playground/run", {"source": sieve, "stdin": ""})
check(run["ok"] and run["same"], f"PySub example: identical={run.get('same')}, CPython {run['python']['time_ms']} ms vs C++ {run['cpp']['time_ms']} ms")

# 4. demo analysis (prebuilt modules make the builds cache hits)
t0 = time.time()
j = call("POST", "/api/jobs", {"input": {"kind": "demo", "name": a.demo}, "options": {"offline": True}})
while True:
    st = call("GET", f"/api/jobs/{j['job_id']}")
    if st["state"] in ("done", "failed", "cancelled"):
        break
    time.sleep(3)
fs = call("GET", f"/api/jobs/{j['job_id']}/functions")
acc = [f for f in fs if f["status"] in ("verified", "guarded")]
ev = call("GET", f"/api/jobs/{j['job_id']}/events?after=0")["events"]
cached = [e["data"]["cached"] for e in ev if e["type"] == "compile.done"]
e2e = (st.get("summary") or {}).get("e2e_speedup")
check(st["state"] == "done" and len(acc) >= 6, f"demo {a.demo}: {len(acc)} accelerated, e2e {e2e and round(e2e, 2)}x, "
      f"{sum(cached)}/{len(cached)} builds from the prebuilt cache, {time.time() - t0:.0f}s")

# 5. export and run the exported project
call("POST", f"/api/jobs/{j['job_id']}/decision", {"id": "all", "decision": "accepted"})
dest = tempfile.mkdtemp(prefix="pythia export ")
out = call("POST", f"/api/jobs/{j['job_id']}/export", {"dest": dest + "/out", "zip": False})["path"]
check(Path(out, "PYTHIA_REPORT.md").exists(), f"exported to {out}")
py = env.get("python_path") or sys.executable
r = subprocess.run([sys.executable, "main.py", "--small"], cwd=out, capture_output=True, text=True, timeout=900)
check(r.returncode == 0 and len(r.stdout) > 100, f"exported project runs (exit {r.returncode}, {len(r.stdout)} bytes of output)")
print("INSTALLED APP OK" if ok else "INSTALLED APP CHECK FAILED")
sys.exit(0 if ok else 1)
