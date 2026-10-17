#!/usr/bin/env bash
# End-to-end smoke test: full Studio pipeline on the bundled demos (Quanta, then TextLab), headless, through the
# Engine facade.  Per demo it asserts: >=N accelerated functions with speedup>1, LLM-fixed functions verified,
# a boundary-cost decline measured below 1x, not-eligible functions with reasons, an end-to-end speedup with
# identical stdout, and (Quanta) that `python -m unittest` passes in the exported, accelerated project.
#   ./scripts/smoke.sh                  # both demos, offline replay of the cached LLM answers unless a key is set
#   ./scripts/smoke.sh --offline        # force offline (no key, no network needed)
#   ./scripts/smoke.sh --online         # force the real LLM
#   ./scripts/smoke.sh --demo quanta    # one demo only
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
echo "== full pipeline on the demo projects"
exec "$PY" scripts/demo_job.py smoke "$@"
