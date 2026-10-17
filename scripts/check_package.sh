#!/usr/bin/env bash
# Packaging self-check (not a test suite): build the wheel, install it into a fresh venv OUTSIDE the repo,
# boot `pythia-studio`, hit /api/env and /api/doctor, run an offline demo job, assert >=3 accelerated functions.
#
#   scripts/check_package.sh                 # PYTHON=python3.12 scripts/check_package.sh to pick an interpreter
#   WHEEL=dist/pythia_studio-1.0.0-py3-none-any.whl scripts/check_package.sh   # test an existing wheel
#   KEEP=1 scripts/check_package.sh          # keep the scratch dir
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/pythia-pkg.XXXXXX")"
PORT="${PORT:-$((20000 + RANDOM % 20000))}"
JOB_TIMEOUT="${JOB_TIMEOUT:-900}"
SERVER_PID=""

say() { printf '\033[1m[check_package]\033[0m %s\n' "$*"; }
die() { printf '\033[31m[check_package] FAIL: %s\033[0m\n' "$*" >&2; [ -f "$WORK/server.log" ] && tail -n 30 "$WORK/server.log" >&2; exit 1; }
cleanup() {
  [ -n "$SERVER_PID" ] && kill -INT "$SERVER_PID" 2>/dev/null && wait "$SERVER_PID" 2>/dev/null || true
  if [ "${KEEP:-0}" = 1 ]; then say "kept $WORK"; else rm -rf "$WORK"; fi
}
trap cleanup EXIT

# 1. wheel ---------------------------------------------------------------------------------------
if [ -n "${WHEEL:-}" ]; then
  WHL="$(cd "$(dirname "$WHEEL")" && pwd)/$(basename "$WHEEL")"
else
  say "building the wheel"
  "$PYTHON" -m pip wheel --quiet --no-deps --wheel-dir "$WORK/dist" "$ROOT" || die "wheel build failed"
  WHL="$(ls "$WORK"/dist/*.whl)"
fi
say "wheel: $(basename "$WHL")"
"$PYTHON" - "$WHL" <<'EOF' || die "wheel is missing bundled resources"
import sys, zipfile
names = set(zipfile.ZipFile(sys.argv[1]).namelist())
need = ["pythia/_runtime/pyrt.cpp", "pythia/_runtime/pyrt_bridge.hpp", "pythia/_runtime/pythia_accel/__init__.py",
        "pythia/studio/web_dist/index.html", "pythia/studio/demo_data/textlab/main.py",
        "pythia/studio/demo_data/offline_cache/authored_rewrites.json", "pythia_studio/__main__.py"]
missing = [n for n in need if n not in names]
sys.exit("missing: %s" % missing if missing else 0)
EOF

# 2. fresh venv, install -------------------------------------------------------------------------
say "installing into a fresh venv"
"$PYTHON" -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install --quiet "$WHL" || die "pip install failed"
VPY="$WORK/venv/bin/python"

# 3. boot from a neutral directory (nothing from the checkout on sys.path) -------------------------
cd "$WORK"
export PYTHIA_HOME="$WORK/home"
say "pythia-studio --doctor"
"$WORK/venv/bin/pythia-studio" --doctor || say "(doctor reported missing pieces; continuing)"
"$WORK/venv/bin/pythia-studio" --no-open --offline --port "$PORT" >"$WORK/server.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 1 100); do
  curl -fsS "http://127.0.0.1:$PORT/api/env" >/dev/null 2>&1 && break
  kill -0 "$SERVER_PID" 2>/dev/null || die "server exited early"
  sleep 0.2
done

"$VPY" -I - "$PORT" "$JOB_TIMEOUT" <<'EOF' || die "API check failed"
import json, sys, time, urllib.error, urllib.request
port, timeout = sys.argv[1], float(sys.argv[2])
base = f"http://127.0.0.1:{port}"

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
EOF

say "OK: installed wheel boots, serves the UI, passes the doctor and accelerates the demo project"
