#!/usr/bin/env python3
"""One-shot sanity check of the Studio API server against the mock engine (not a test suite).

    python scripts/check_server.py

Starts the app on a free port with the mock engine, runs a job, consumes the WebSocket stream to
`job.done`, and asserts the CONTRACTS section 4/6 shapes. Exits non-zero on the first failure.
"""
import io
import json
import os
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn                                                     # noqa: E402
from websockets.sync.client import connect                         # noqa: E402

from pythia.studio.server.app import create_app                    # noqa: E402
from pythia.studio.server.mock_engine import MockEngine            # noqa: E402

JOURNEY = ["original", "observed_types", "eligibility", "rewrites", "pysub", "tokens", "ast", "typed_ast", "pir", "cpp",
           "wrapper", "build", "replay", "benchmark", "splice", "status"]
EVENT_TYPES = {"job.start", "stage", "ingest.progress", "ingest.done", "scan.function", "scan.done", "trace.progress",
               "trace.done", "rank.done", "fix.attempt", "fix.done", "compile.done", "verify.result", "bench.result",
               "bench.e2e", "splice.ready", "export.done", "agent.step", "log", "error", "job.done"}
SUMMARY_KEYS = {"id", "file", "name", "qualname", "line", "end_line", "col", "status", "eligibility", "reason", "decision",
                "score", "share", "calls", "speedup", "probe_speedup"}
RECORD_KEYS = SUMMARY_KEYS | {"metrics", "trace", "sources", "line_map_ok", "cpp_line_map", "rewrites", "diagnostics",
                              "fidelity", "build", "replay", "bench", "splice", "journey"}


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Api:
    def __init__(self, port):
        self.base = f"http://127.0.0.1:{port}"

    def call(self, method, path, body=None, raw=None, ctype=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": ctype or "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                payload = r.read()
                return r.status, (json.loads(payload) if "json" in r.headers.get("content-type", "") else payload)
        except urllib.error.HTTPError as e:
            payload = e.read()
            return e.code, json.loads(payload)

    def get(self, p):
        return self.call("GET", p)

    def post(self, p, b=None):
        return self.call("POST", p, b if b is not None else {})


def ok(api, method, path, body=None, status=200):
    code, out = api.call(method, path, body)
    assert code == status, f"{method} {path} -> {code} {out}"
    return out


def stream(port, job, after=0, limit=None):
    evs = []
    with connect(f"ws://127.0.0.1:{port}/api/jobs/{job}/ws?after={after}", max_size=None) as ws:
        try:
            for m in ws:
                evs.append(json.loads(m))
                if limit and len(evs) >= limit:
                    break
        except Exception:
            pass
    return evs


def contiguous(evs, start=1):
    assert [e["seq"] for e in evs] == list(range(start, start + len(evs))), "seq gap or duplicate"
    assert all(e["ts"] > 0 and {"type", "stage", "caption", "data"} <= set(e) for e in evs)


def serve(home, port):
    app = create_app(engine=MockEngine(home), home=home)
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error", ws_ping_interval=None))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", port), 0.2).close()
            return srv
        except OSError:
            time.sleep(0.1)
    raise SystemExit("server did not start")


def main():
    home = tempfile.mkdtemp(prefix="pythia-check-")
    port = free_port()
    srv = serve(home, port)
    api = Api(port)
    t0 = time.time()

    # --- env / settings / errors
    env = ok(api, "GET", "/api/env")
    assert {"compiler", "pybind11", "python", "platform", "llm", "offline_available", "offline", "wsl"} <= set(env)
    st = ok(api, "PUT", "/api/settings", {"offline": True})
    assert st["offline"] is True and ok(api, "GET", "/api/settings")["offline"] is True
    ok(api, "PUT", "/api/settings", {"offline": False})
    code, out = api.get("/api/jobs/nope")
    assert code == 404 and "error" in out, (code, out)
    code, out = api.post("/api/jobs", {"input": {"kind": "bogus"}})
    assert code == 400 and "error" in out, (code, out)
    code, out = api.get("/api/nothing")
    assert code == 404 and "error" in out
    code, _ = api.get("/")
    assert code == 200                                              # UI page or the "not built" page

    # --- run a job and consume the WS stream (full coverage run incl. export)
    r = ok(api, "POST", "/api/jobs", {"input": {"kind": "demo"}, "options": {"fast": True, "export": True}})
    job, ws_id = r["job_id"], r["workspace_id"]
    assert len(job) == 8 and ws_id
    evs = stream(port, job)
    contiguous(evs)
    assert evs[0]["type"] == "job.start" and evs[-1]["type"] == "job.done", [e["type"] for e in evs[-3:]]
    missing = EVENT_TYPES - {e["type"] for e in evs}
    assert not missing, f"event types never emitted: {missing}"
    done = evs[-1]["data"]
    assert done["state"] == "done" and done["summary"]["verified"] >= 3, done
    stages = [e["data"]["stage"] for e in evs if e["type"] == "stage"]
    assert {"ingest", "scan", "trace", "rank", "fix", "compile", "verify", "benchmark", "splice", "export"} <= set(stages)
    assert any(e["data"]["function"]["id"] == "textlab/text/distance.py::edit_distance" for e in evs if e["type"] == "scan.function")
    print(f"ok  WS stream: {len(evs)} events, {len({e['type'] for e in evs})} event types, job.done {done['summary']}")

    # --- replay from /events, partial replays, WS with `after`
    full = ok(api, "GET", f"/api/jobs/{job}/events")
    assert full["last_seq"] == len(evs) and full["events"] == evs, "GET /events differs from the live stream"
    tail = ok(api, "GET", f"/api/jobs/{job}/events?after=100")
    assert tail["events"] == evs[100:] and tail["events"][0]["seq"] == 101
    assert stream(port, job, after=len(evs) - 5) == evs[-5:]
    assert (Path(home) / "jobs" / job / "events.jsonl").read_text().count("\n") == len(evs)
    code, _ = api.get("/api/jobs/zzzzzzzz/events")
    assert code == 404

    # --- reconnect mid-stream: no gaps, no duplicates
    r2 = ok(api, "POST", "/api/jobs", {"input": {"kind": "snippet", "code": "x", "name": "snip"}, "options": {"pace_ms": 3}})
    j2 = r2["job_id"]
    first = stream(port, j2, limit=40)
    rest = stream(port, j2, after=first[-1]["seq"])
    contiguous(first + rest)
    assert (first + rest)[-1]["type"] == "job.done"
    print(f"ok  reconnect: {len(first)} + {len(rest)} events, contiguous")
    cancel_job = ok(api, "POST", "/api/jobs", {"input": {"kind": "demo"}, "options": {"pace_ms": 20}})["job_id"]
    time.sleep(0.3)
    ok(api, "POST", f"/api/jobs/{cancel_job}/cancel")
    ev3 = stream(port, cancel_job)
    assert ev3[-1]["type"] == "job.done" and ev3[-1]["data"]["state"] == "cancelled"

    # --- job endpoints
    j = ok(api, "GET", f"/api/jobs/{job}")
    assert {"job_id", "workspace_id", "name", "state", "options", "started", "finished", "summary"} <= set(j) and j["state"] == "done"
    assert any(x["job_id"] == job for x in ok(api, "GET", "/api/jobs"))
    funcs = ok(api, "GET", f"/api/jobs/{job}/functions")
    assert len(funcs) >= 80 and len({f["file"] for f in funcs}) >= 6, len(funcs)
    for f in funcs:
        assert SUMMARY_KEYS <= set(f) and "total" in f["score"], f
    statuses = {f["status"] for f in funcs}
    assert {"verified", "guarded", "not_eligible", "declined", "failed"} <= statuses, statuses
    fid = "textlab/text/distance.py::edit_distance"
    rec = ok(api, "GET", f"/api/jobs/{job}/function?id={urllib.request.quote(fid)}&stages=1")
    assert RECORD_KEYS <= set(rec), RECORD_KEYS - set(rec)
    assert [n["key"] for n in rec["journey"]] == JOURNEY
    assert rec["status"] == "verified" and rec["replay"]["matched"] == rec["replay"]["total"] > 0
    assert rec["sources"]["cpp"] and rec["sources"]["wrapper_cpp"] and rec["splice"]["diff"].startswith("---")
    assert {"tokens", "ast", "typed_ast", "pir", "cpp"} <= set(rec["stages"])
    fx = ok(api, "GET", f"/api/jobs/{job}/function?id={urllib.request.quote('textlab/ml/kmeans.py::update_centroids')}")
    assert fx["eligibility"] == "fixable" and fx["status"] == "verified" and fx["rewrites"][-1]["ok"] and fx["line_map_ok"] is False
    sev = {n["severity"] for f in funcs for n in ok(api, "GET", f"/api/jobs/{job}/function?id={urllib.request.quote(f['id'])}")["fidelity"]}
    assert sev == {"exact", "guarded", "divergent"}, sev
    code, _ = api.get(f"/api/jobs/{job}/function?id=nope")
    assert code == 404

    # --- decisions, diff, tree, files, report, export
    d = ok(api, "POST", f"/api/jobs/{job}/decision", {"id": fid, "decision": "rejected"})
    assert d["functions"][0]["decision"] == "rejected"
    diff = ok(api, "GET", f"/api/jobs/{job}/file-diff?path=textlab/text/distance.py")
    assert "_pythia_accelerated(" in diff["modified"] and '"edit_distance"' not in diff["modified"]
    ok(api, "POST", f"/api/jobs/{job}/decision", {"id": "all", "decision": "accepted"})
    diff = ok(api, "GET", f"/api/jobs/{job}/file-diff?path=textlab/text/distance.py")
    assert '@_pythia_accelerated("pythia_' in diff["modified"] and "_pythia_accelerated" not in diff["original"]
    assert api.post(f"/api/jobs/{job}/decision", {"id": fid, "decision": "maybe"})[0] == 422
    tree = ok(api, "GET", f"/api/workspaces/{ws_id}/tree")
    assert tree and all({"path", "name", "type", "badges"} <= set(n) for n in tree)
    assert any(n["type"] == "dir" and n["children"] for n in tree)
    f = ok(api, "GET", f"/api/workspaces/{ws_id}/file?path=textlab/num/primes.py&version=work")
    assert {"path", "content", "language", "size"} <= set(f) and f["language"] == "python" and "_pythia_accelerated" in f["content"]
    orig = ok(api, "GET", f"/api/workspaces/{ws_id}/file?path=textlab/num/primes.py&version=original")
    assert "_pythia_accelerated" not in orig["content"]
    assert api.get(f"/api/workspaces/{ws_id}/file?path=../etc/passwd")[0] == 400
    rep = ok(api, "GET", f"/api/jobs/{job}/report")
    assert rep["markdown"].startswith("# PYTHIA report") and rep["json"]["summary"]["verified"] >= 3
    ex = ok(api, "POST", f"/api/jobs/{job}/export", {"dest": os.path.join(home, "exp"), "zip": False})
    assert (Path(ex["path"]) / "PYTHIA_REPORT.md").is_file() and (Path(ex["path"]) / "build_accel.sh").is_file()
    code, z = api.get(f"/api/jobs/{job}/export.zip")
    assert code == 200 and "PYTHIA_REPORT.md" in " ".join(zipfile.ZipFile(io.BytesIO(z)).namelist())
    assert any(e["type"] == "export.done" for e in ok(api, "GET", f"/api/jobs/{job}/events?after={len(evs)}")["events"])
    assert ok(api, "GET", "/api/workspaces/recent")[0]["workspace_id"]

    # --- fs picker
    ls = ok(api, "GET", "/api/fs/list?path=" + urllib.request.quote(home))
    assert {"path", "parent", "entries"} <= set(ls) and any(e["name"] == "jobs" and e["type"] == "dir" for e in ls["entries"])
    assert api.get("/api/fs/list?path=/definitely/not/here")[0] == 404

    # --- upload (multipart)
    b = "XBOUNDARYX"
    body = (f'--{b}\r\nContent-Disposition: form-data; name="options"\r\n\r\n{{"fast": true}}\r\n'
            f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="snippet.py"\r\nContent-Type: text/x-python\r\n\r\n'
            f'def f(x: int) -> int:\r\n    return x + 1\r\n--{b}--\r\n').encode()
    up = api.call("POST", "/api/upload", raw=body, ctype=f"multipart/form-data; boundary={b}")
    assert up[0] == 200 and up[1]["job_id"], up
    assert stream(port, up[1]["job_id"])[-1]["type"] == "job.done"

    # --- playground (degrades with a clear error if the compiler pieces are missing)
    src = "def f(n: int) -> int:\n    return n * 2\nprint(f(21))\n"
    c = ok(api, "POST", "/api/playground/compile", {"source": src})
    assert c["ok"] and "f_f" in c["cpp"] and {"diagnostics", "fidelity", "cpp_line_map"} <= set(c)
    bad = ok(api, "POST", "/api/playground/compile", {"source": "def f(x):\n    return x\n"})
    assert bad["ok"] is False and bad["diagnostics"]
    run = ok(api, "POST", "/api/playground/run", {"source": src})
    if run["ok"]:
        assert run["python"]["stdout"] == "42\n" and run["cpp"]["stdout"] == "42\n" and run["same"] is True, run
        print(f"ok  playground run: python {run['python']['time_ms']} ms, cpp {run['cpp']['time_ms']} ms")
    else:
        print("note playground run unavailable here:", run["error"])
    boom = ok(api, "POST", "/api/playground/run", {"source": "xs: list[int] = [1]\nprint(xs[5])\n"})
    if boom["ok"]:
        assert boom["python"]["exception"] == "IndexError" and boom["cpp"]["exception"] == "IndexError" and boom["same"], boom
    sd = ok(api, "POST", "/api/stages", {"source": src})
    assert {"ok", "diagnostics", "tokens", "ast", "typed_ast", "pir", "cpp", "fidelity"} <= set(sd) and sd["ok"] and sd["tokens"]
    assert api.call("POST", "/api/playground/compile", {"nosource": 1})[0] == 422

    # --- durability: a fresh server over the same home still serves the finished job
    srv.should_exit = True
    time.sleep(0.5)
    port2 = free_port()
    srv2 = serve(home, port2)
    api2 = Api(port2)
    assert any(x["job_id"] == job for x in ok(api2, "GET", "/api/jobs"))
    again = ok(api2, "GET", f"/api/jobs/{job}/events")
    assert again["events"][: len(evs)] == evs
    assert stream(port2, job)[: len(evs)] == evs
    assert len(ok(api2, "GET", f"/api/jobs/{job}/functions")) == len(funcs)
    srv2.should_exit = True
    print(f"ALL OK in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
