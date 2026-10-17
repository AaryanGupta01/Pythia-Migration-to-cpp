#!/usr/bin/env bash
# Create (or recreate) a local bare git repo of demo/textlab for the "Clone repository" path.
#   ./scripts/make_demo_repo.sh        ->  prints  file:///home/you/.pythia-studio/demo-remote/textlab.git
# Idempotent: the repo is rebuilt from scratch with a fixed author/date, so the commit hash is stable.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE="${PYTHIA_HOME:-$HOME/.pythia-studio}/demo-remote/textlab.git"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

mkdir -p "$(dirname "$REMOTE")"
rm -rf "$REMOTE"
git init -q --bare -b main "$REMOTE"

cp -r "$ROOT/demo/textlab/." "$WORK/"
find "$WORK" -name '__pycache__' -type d -prune -exec rm -rf {} +
printf '__pycache__/\n*.pyc\n' > "$WORK/.gitignore"

export GIT_AUTHOR_NAME="PYTHIA Demo" GIT_AUTHOR_EMAIL="demo@pythia.local"
export GIT_COMMITTER_NAME="PYTHIA Demo" GIT_COMMITTER_EMAIL="demo@pythia.local"
export GIT_AUTHOR_DATE="2026-01-01T00:00:00Z" GIT_COMMITTER_DATE="2026-01-01T00:00:00Z"
git -C "$WORK" init -q -b main
git -C "$WORK" add -A
git -C "$WORK" commit -q -m "textlab demo project"
git -C "$WORK" push -q "$REMOTE" main

echo "file://$REMOTE"
