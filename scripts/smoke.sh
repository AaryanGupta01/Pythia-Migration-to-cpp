#!/usr/bin/env bash
# End-to-end smoke test: full Studio pipeline on demo/textlab, headless, through the Engine facade.
# Asserts >=3 verified/guarded functions with speedup>1, >=1 declined, >=1 not_eligible with a reason.
#   ./scripts/smoke.sh               # offline replay of the authored LLM cache unless ANTHROPIC_API_KEY is set
#   ./scripts/smoke.sh --offline     # force offline
#   ./scripts/smoke.sh --online      # force the real LLM
# Uses $PYTHIA_VENV or ./.venv or ~/pythia-venv, whichever has a python.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY=""
for cand in "${PYTHIA_VENV:+$PYTHIA_VENV/bin/python}" "$ROOT/.venv/bin/python" "$HOME/pythia-venv/bin/python" "$(command -v python3 || true)"; do
  if [ -n "$cand" ] && [ -x "$cand" ]; then PY="$cand"; break; fi
done
[ -n "$PY" ] || { echo "no python found; run ./studio.sh once to create the venv" >&2; exit 2; }

echo "== demo self-check (compiler front end on every demo function)"
"$PY" scripts/check_demo.py --no-run

echo
echo "== full pipeline on demo/textlab"
exec "$PY" scripts/demo_job.py smoke "$@"
