#!/usr/bin/env bash
# Re-record the offline demo cache with a real model (GROQ_API_KEY, free tier, or ANTHROPIC_API_KEY; a key in ./.env works too):
#   LLM replies -> demo/offline_cache/llm/<key>.json   (provenance "recorded", written by PYTHIA_RECORD_LLM_DIR)
#   built .so   -> demo/offline_cache/so/               (+ .meta.json, only the modules this run built)
# Runs the whole pipeline online on a demo (default quanta; pass --demo textlab for the small one) in a fresh
# PYTHIA_HOME so every rewrite really goes to the API and every .so really gets built.  Free-tier rate limits are
# handled by the client (it waits and retries on 429).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [ -z "${GROQ_API_KEY:-}" ] && [ -z "${ANTHROPIC_API_KEY:-}" ] && ! grep -qE '^(GROQ|ANTHROPIC)_API_KEY=' .env 2>/dev/null; then
  echo "Neither GROQ_API_KEY nor ANTHROPIC_API_KEY is set. Get a free Groq key at https://console.groq.com and run:" >&2
  echo "  GROQ_API_KEY=gsk_... ./scripts/record_offline_cache.sh" >&2
  echo "(The cache already committed under demo/offline_cache keeps the offline demo working meanwhile.)" >&2
  exit 2
fi

PY=""
for cand in "${PYTHIA_VENV:+$PYTHIA_VENV/bin/python}" "$ROOT/.venv/bin/python" "$HOME/pythia-venv/bin/python" "$(command -v python3 || true)"; do
  if [ -n "$cand" ] && [ -x "$cand" ]; then PY="$cand"; break; fi
done
[ -n "$PY" ] || { echo "no python found; run ./studio.sh once to create the venv" >&2; exit 2; }

export PYTHIA_HOME="${PYTHIA_HOME:-$(mktemp -d)}"
"$PY" scripts/demo_job.py record "$@"
echo "Review with: git status demo/offline_cache && git add demo/offline_cache"
