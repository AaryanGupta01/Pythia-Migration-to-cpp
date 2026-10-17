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

"$VPY" -I "$ROOT/scripts/check_api.py" "$PORT" "$JOB_TIMEOUT" || die "API check failed"

say "OK: installed wheel boots, serves the UI, passes the doctor and accelerates the demo project"
