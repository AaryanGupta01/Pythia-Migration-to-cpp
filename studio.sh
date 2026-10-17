#!/usr/bin/env bash
# PYTHIA Studio launcher: sets up a venv on first run, then starts the server and opens the browser.
#
#   ./studio.sh                  # normal start (http://127.0.0.1:8765)
#   ./studio.sh --offline        # replay cached LLM answers + prebuilt .so files for the demo project
#   ./studio.sh --port 9000      # different port
#   ./studio.sh --no-open        # do not launch the browser
#
# Env: PYTHIA_VENV=<dir> reuse/create that venv (default ./.venv), PYTHIA_PORT, PYTHIA_HOME, ANTHROPIC_API_KEY.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PORT="${PYTHIA_PORT:-8765}"
OPEN="--open"
OFFLINE="${PYTHIA_OFFLINE:-0}"

while [ $# -gt 0 ]; do
  case "$1" in
    --offline) OFFLINE=1 ;;
    --port) PORT="${2:?--port needs a number}"; shift ;;
    --port=*) PORT="${1#--port=}" ;;
    --no-open) OPEN="" ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

say()  { printf '\033[1m[pythia]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[pythia] %s\033[0m\n' "$*" >&2; }

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    warn "Windows: PYTHIA Studio needs a Unix toolchain. Install WSL (wsl --install), open an Ubuntu shell and run ./studio.sh there."
    exit 1 ;;
esac

# --- Python + venv -----------------------------------------------------------------------
BASE_PY="$(command -v python3 || command -v python || true)"
if [ -z "$BASE_PY" ]; then
  warn "Python 3 not found. Install Python 3.12+ (Ubuntu: sudo apt install python3 python3-venv python3-pip; macOS: brew install python)."
  exit 1
fi
"$BASE_PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
  || warn "Python $("$BASE_PY" -c 'import platform; print(platform.python_version())') found; 3.12+ recommended (older versions use the slower sys.setprofile tracer)."

VENV="${PYTHIA_VENV:-$ROOT/.venv}"
if [ ! -x "$VENV/bin/python" ]; then
  say "creating virtualenv in $VENV"
  "$BASE_PY" -m venv "$VENV" || { warn "venv creation failed. Ubuntu: sudo apt install python3-venv"; exit 1; }
fi
PY="$VENV/bin/python"

REQ="$ROOT/requirements-studio.txt"
STAMP="$VENV/.studio-requirements.sha"
REQ_SUM="$(cksum < "$REQ" | cut -d' ' -f1)"
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$REQ_SUM" ]; then
  say "installing Python dependencies (first run only)"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet -r "$REQ"
  echo "$REQ_SUM" > "$STAMP"
fi

# --- C++ toolchain -----------------------------------------------------------------------
CXX_BIN="$(command -v "${CXX:-}" 2>/dev/null || command -v c++ || command -v g++ || command -v clang++ || true)"
if [ -z "$CXX_BIN" ]; then
  warn "No C++ compiler found. PYTHIA compiles hotspots to C++17, so you need one:"
  warn "  Ubuntu/Debian/WSL: sudo apt install build-essential"
  warn "  macOS:             xcode-select --install"
  warn "  Fedora:            sudo dnf install gcc-c++"
  warn "The app will still start; scan, trace and rank work, but compile/verify are disabled."
else
  say "C++ compiler: $("$CXX_BIN" --version | head -n1)"
fi
if ! "$PY" -c 'import pybind11' 2>/dev/null; then
  warn "pybind11 is missing from the venv (pip install pybind11). Python headers may also be needed: sudo apt install python3-dev"
fi

# --- Frontend ----------------------------------------------------------------------------
DIST="$ROOT/studio/web/dist"
if [ ! -f "$DIST/index.html" ]; then
  if command -v npm >/dev/null 2>&1 && [ -f "$ROOT/studio/web/package.json" ]; then
    say "building the web UI (studio/web/dist is missing)"
    (cd "$ROOT/studio/web" && npm install --no-audit --no-fund && npm run build)
  else
    warn "studio/web/dist is missing and npm was not found. Install Node 20+ (https://nodejs.org) or use a checkout that includes the built UI."
  fi
fi

# --- Go ----------------------------------------------------------------------------------
export PYTHIA_PORT="$PORT"
if [ "$OFFLINE" = "1" ]; then
  export PYTHIA_OFFLINE=1
  say "offline mode: cached LLM answers and prebuilt .so files from demo/offline_cache"
elif [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  say "no ANTHROPIC_API_KEY set: the LLM fixer is disabled (use --offline for the cached demo rewrites)"
fi
say "starting PYTHIA Studio on http://127.0.0.1:$PORT"
# shellcheck disable=SC2086
exec "$PY" -m pythia.studio.server $OPEN
