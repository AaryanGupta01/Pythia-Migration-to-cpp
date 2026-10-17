#!/usr/bin/env bash
# Re-record the offline demo cache with a real API key:
#   LLM replies -> demo/offline_cache/llm/<key>.json   (provenance "recorded", replaces "authored")
#   built .so   -> demo/offline_cache/so/
# Runs the whole pipeline online on demo/textlab. Fails clearly without ANTHROPIC_API_KEY.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY is not set. Export it and re-run: ANTHROPIC_API_KEY=sk-ant-... ./scripts/record_offline_cache.sh" >&2
  echo "(The authored cache from scripts/author_offline_cache.py keeps the offline demo working meanwhile.)" >&2
  exit 2
fi

PY=""
for cand in "${PYTHIA_VENV:+$PYTHIA_VENV/bin/python}" "$ROOT/.venv/bin/python" "$HOME/pythia-venv/bin/python" "$(command -v python3 || true)"; do
  if [ -n "$cand" ] && [ -x "$cand" ]; then PY="$cand"; break; fi
done
[ -n "$PY" ] || { echo "no python found; run ./studio.sh once to create the venv" >&2; exit 2; }

# Fresh home so every rewrite really goes to the API and every .so really gets built.
export PYTHIA_HOME="$(mktemp -d)"
trap 'rm -rf "$PYTHIA_HOME"' EXIT
"$PY" scripts/demo_job.py record --online "$@"
echo "Review with: git status demo/offline_cache && git add demo/offline_cache"
