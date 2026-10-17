#!/usr/bin/env python3
"""Drive a running Studio server (default :8765) through every input kind, accept/reject and export.
Usage: python scripts/check_inputs.py [--base http://127.0.0.1:8765]"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8765")
ap.add_argument("--only", default="")
a = ap.parse_args()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SNIPPET = '''def collatz_steps(n: int) -> int:
    steps: int = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


def total(limit: int) -> int:
    s: int = 0
    for i in range(1, limit):
        s += collatz_steps(i)
    return s


print(total(30000))
'''


def call(method, path, body=None):
    req = urllib.request.Request(a.base + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read() or b"null")


def run_job(name, inp, opts=None, timeout=420):
    t0 = time.time()
    j = call("POST", "/api/jobs", {"input": inp, "options": opts or {"offline": True}})
    jid = j["job_id"]
    while time.time() - t0 < timeout:
        st = call("GET", f"/api/jobs/{jid}")
        if st["state"] in ("done", "failed", "cancelled"):
            break
        time.sleep(1.5)
    fns = call("GET", f"/api/jobs/{jid}/functions")
    from collections import Counter
    print(f"{name:8} job={jid} state={st['state']} {dict(Counter(f['status'] for f in fns))} "
          f"({time.time() - t0:.0f}s)")
    return jid, st, fns


ok = True
only = a.only.split(",") if a.only else []
want = lambda n: not only or n in only  # noqa: E731

if want("snippet"):
    jid, st, fns = run_job("snippet", {"kind": "snippet", "code": SNIPPET, "name": "collatz"},
                           {"offline": True, "trace_cmd": "python collatz.py"})
    acc = [f for f in fns if f["status"] in ("verified", "guarded")]
    ok &= st["state"] == "done" and len(acc) >= 1
if want("file"):
    jid, st, fns = run_job("file", {"kind": "file", "filename": "collatz.py",
                                     "content_b64": base64.b64encode(SNIPPET.encode()).decode()})
    ok &= st["state"] == "done" and any(f["status"] in ("verified", "guarded", "fixable") for f in fns)
if want("folder"):
    jid, st, fns = run_job("folder", {"kind": "folder", "path": os.path.join(ROOT, "demo", "textlab")},
                           {"offline": True, "trace_cmd": "python main.py --small"})
    ok &= st["state"] == "done" and sum(f["status"] in ("verified", "guarded") for f in fns) >= 3
if want("git"):
    repo = os.path.expanduser("~/.pythia-studio/demo-remote/textlab.git")
    if not os.path.isdir(repo):
        subprocess.run(["bash", os.path.join(ROOT, "scripts", "make_demo_repo.sh")], check=True)
    jid, st, fns = run_job("git", {"kind": "git", "url": "file://" + repo},
                           {"offline": True, "trace_cmd": "python main.py --small"})
    ok &= st["state"] == "done" and sum(f["status"] in ("verified", "guarded") for f in fns) >= 3
if want("export"):
    jid, st, fns = run_job("export", {"kind": "demo"})
    top = next(f for f in fns if f["status"] in ("verified", "guarded"))
    rej = next(f for f in fns if f["status"] in ("verified", "guarded") and f["id"] != top["id"])
    call("POST", f"/api/jobs/{jid}/decision", {"id": top["id"], "decision": "accepted"})
    call("POST", f"/api/jobs/{jid}/decision", {"id": rej["id"], "decision": "rejected"})
    dest = tempfile.mkdtemp(prefix="pythia-export-")
    res = call("POST", f"/api/jobs/{jid}/export", {"dest": dest + "/out", "zip": False})
    out = res["path"]
    print("exported to", out, sorted(os.listdir(out))[:12])
    base = subprocess.run([sys.executable, os.path.join(ROOT, "demo/textlab/main.py"), "--small"],
                          capture_output=True, text=True, cwd=os.path.join(ROOT, "demo/textlab"))
    acc = subprocess.run([sys.executable, "main.py", "--small"], capture_output=True, text=True, cwd=out)
    same = base.stdout == acc.stdout and acc.returncode == 0
    rep = os.path.exists(os.path.join(out, "PYTHIA_REPORT.md")) and os.path.exists(os.path.join(out, "build_accel.sh"))
    rejected_src = open(os.path.join(out, rej["file"]), encoding="utf-8").read()
    print(f"export: output identical={same} report+build_accel={rep} "
          f"rejected-fn-reverted={('accelerated(' not in rejected_src.split('def ' + rej['name'])[0][-200:])}")
    ok &= same and rep

print("INPUTS OK" if ok else "INPUTS FAILED")
sys.exit(0 if ok else 1)
