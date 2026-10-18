#!/usr/bin/env python3
"""Run one analysis job on a RUNNING PYTHIA Studio and summarise it: a bundled demo or any project folder.
Usage: python scripts/check_project.py --base http://127.0.0.1:8765 (--demo quanta | --path DIR) [--cmd "python main.py"]
       [--offline] [--min-accelerated N]"""
import argparse
import json
import sys
import time
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8765")
ap.add_argument("--demo")
ap.add_argument("--path")
ap.add_argument("--cmd", default="")
ap.add_argument("--offline", action="store_true")
ap.add_argument("--min-accelerated", type=int, default=1)
a = ap.parse_args()


def call(method, path, body=None):
    req = urllib.request.Request(a.base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read() or b"null")


inp = {"kind": "demo", "name": a.demo} if a.demo else {"kind": "folder", "path": a.path}
t0 = time.time()
j = call("POST", "/api/jobs", {"input": inp, "options": {"offline": a.offline, "trace_cmd": a.cmd}})
while True:
    st = call("GET", f"/api/jobs/{j['job_id']}")
    if st["state"] in ("done", "failed", "cancelled"):
        break
    time.sleep(3)
fs = call("GET", f"/api/jobs/{j['job_id']}/functions")
ev = call("GET", f"/api/jobs/{j['job_id']}/events?after=0")["events"]
errors = [e["data"].get("message") for e in ev if e["type"] == "error"]
stages = {e["data"]["stage"]: e["data"]["state"] for e in ev if e["type"] == "stage"}
by = {}
for f in fs:
    by[f["status"]] = by.get(f["status"], 0) + 1
acc = by.get("verified", 0) + by.get("guarded", 0)
s = st.get("summary") or {}
print(f"{a.demo or a.path}: state={st['state']} in {time.time() - t0:.0f}s, {len(fs)} functions {by}")
print("  stages:", stages)
print(f"  accelerated={acc} geomean={s.get('geomean_speedup')} e2e={s.get('e2e_speedup')}")
for e in errors:
    print("  ERROR:", e)
for f in fs:
    if f["status"] == "failed":
        print(f"  failed: {f['id']}: {(f.get('reason') or '')[:140]}")
ok = st["state"] == "done" and not errors and acc >= a.min_accelerated
print("PROJECT OK" if ok else "PROJECT CHECK FAILED")
sys.exit(0 if ok else 1)
