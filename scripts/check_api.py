#!/usr/bin/env python3
"""HTTP checks against a running PYTHIA Studio (used by check_package.sh and the Docker check).

    python scripts/check_api.py PORT [JOB_TIMEOUT_S] [HOST]

Asserts toolchain + doctor OK, UI/manifest/icons served, foreign Host header rejected, then runs the
demo project offline and requires >= 3 accelerated functions.
"""
import json, sys, time, urllib.error, urllib.request
port, timeout = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 900.0
base = f"http://{sys.argv[3] if len(sys.argv) > 3 else '127.0.0.1'}:{port}"

def call(path, body=None, host=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"content-type": "application/json", **({"Host": host} if host else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read() if path.startswith("/icon") else json.load(r)

env = call("/api/env")
assert env["compiler"]["found"] and env["pybind11"], f"toolchain missing: {env}"
doc = call("/api/doctor")
assert doc["app"] == "pythia-studio" and doc["ready"], [c for c in doc["checks"] if not c["ok"] and c["required"]]
assert call("/icon-192.png")[:4] == b"\x89PNG"
assert json.loads(urllib.request.urlopen(base + "/manifest.webmanifest").read())["name"] == "PYTHIA Studio"
assert b"<div id=\"root\">" in urllib.request.urlopen(base + "/").read(), "web UI not served from the installed package"
try:
    call("/api/env", host="evil.example.com")
    raise SystemExit("Host-header guard did not reject a foreign Host")
except urllib.error.HTTPError as e:
    assert e.code == 403
print(f"env ok: {env['compiler']['version']}; doctor ready; UI + manifest + icons served; foreign Host rejected")

job = call("/api/jobs", {"input": {"kind": "demo"}, "options": {"offline": True, "trace_timeout_s": 120}})["job_id"]
t0 = time.time()
while True:
    j = call(f"/api/jobs/{job}")
    if j.get("state") in ("done", "failed", "cancelled"):
        break
    assert time.time() - t0 < timeout, f"demo job still {j.get('state')} after {timeout:.0f}s"
    time.sleep(2)
fns = call(f"/api/jobs/{job}/functions")
wins = [f for f in fns if f["status"] in ("verified", "guarded") and (f.get("speedup") or 0) > 1]
for f in sorted(wins, key=lambda f: -f["speedup"]):
    print(f"  {f['id']:55s} {f['status']:9s} {f['speedup']:.1f}x")
assert j["state"] == "done", f"job ended {j['state']}"
assert len(wins) >= 3, f"only {len(wins)} accelerated functions (need >= 3) of {len(fns)}"
print(f"demo job {job}: {len(wins)} accelerated functions in {time.time() - t0:.0f}s")
