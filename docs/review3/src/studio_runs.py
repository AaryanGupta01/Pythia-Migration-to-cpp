#!/usr/bin/env python3
"""Runs Studio jobs one at a time on a RUNNING server (zero-LLM path) and records the results.
Usage: python studio_runs.py --base http://127.0.0.1:8797 --out evidence/studio_jobs.json  LABEL=KIND:VALUE[|trace cmd] ...
KIND is demo, path or url. Example:  textlab=demo:textlab|python main.py --small   quanta=demo:quanta
Add --repeat to run each job twice (second run shows the warm build cache)."""
import argparse
import json
import time
import urllib.request
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8797")
ap.add_argument("--out", required=True)
ap.add_argument("--repeat", action="store_true")
ap.add_argument("jobs", nargs="+")
a = ap.parse_args()


def call(method, path, body=None):
    req = urllib.request.Request(a.base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.loads(r.read() or b"null")


doc = json.loads(Path(a.out).read_text()) if Path(a.out).exists() else []
doctor = call("GET", "/api/doctor")
for spec in a.jobs:
    label, rest = spec.split("=", 1)
    rest, _, cmd = rest.partition("|")
    kind, _, value = rest.partition(":")
    inp = {"kind": "demo", "name": value} if kind == "demo" else {"kind": "git", "url": value} if kind == "url" else {"kind": "folder", "path": value}
    for run in range(2 if a.repeat else 1):
        t0 = time.time()
        j = call("POST", "/api/jobs", {"input": inp, "options": {"offline": False, "llm": False, "trace_cmd": cmd}})
        while True:
            st = call("GET", f"/api/jobs/{j['job_id']}")
            if st["state"] in ("done", "failed", "cancelled"):
                break
            time.sleep(3)
        secs = time.time() - t0
        fs = call("GET", f"/api/jobs/{j['job_id']}/functions")
        ev = call("GET", f"/api/jobs/{j['job_id']}/events?after=0")["events"]
        errors = [e["data"].get("message") for e in ev if e["type"] == "error"]
        full = []
        for f in fs:
            if f["status"] in ("verified", "guarded", "declined", "failed"):
                try:
                    d = call("GET", f"/api/jobs/{j['job_id']}/function?id=" + urllib.request.quote(f["id"], safe=""))
                except Exception:  # noqa: BLE001
                    d = {}
                f = dict(f, replay=(d or {}).get("replay"), bench=(d or {}).get("bench"), build=(d or {}).get("build"))
            full.append(f)
        rec = {"label": label if not a.repeat else f"{label} ({'cold' if run == 0 else 'warm'})", "base_label": label,
               "run": run, "job_id": j["job_id"], "input": inp, "trace_cmd": cmd, "state": st["state"], "seconds": round(secs, 1),
               "summary": st.get("summary"), "e2e": st.get("e2e"), "errors": errors, "build": doctor.get("build"),
               "date": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "functions": [{"id": f["id"], "name": f["name"], "file": f["file"], "status": f["status"], "reason": f.get("reason"),
                              "speedup": f.get("speedup"), "probe_speedup": f.get("probe_speedup"), "share": f.get("share"),
                              "calls": f.get("calls"), "replay": f.get("replay"), "bench": f.get("bench")} for f in full]}
        doc = [d for d in doc if d["label"] != rec["label"]] + [rec]
        Path(a.out).write_text(json.dumps(doc, indent=1))
        s = rec["summary"] or {}
        print(f"{rec['label']}: {rec['state']} in {secs:.0f}s {s}", flush=True)
