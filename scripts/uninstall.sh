#!/usr/bin/env bash
# Remove what scripts/install.sh created: the venv, the ~/.local/bin links and the launcher.
# Your data (workspaces, jobs, build cache in the prefix) is kept unless you pass --purge.
#
#   scripts/uninstall.sh [--prefix DIR] [--purge]
set -euo pipefail

PREFIX="${PYTHIA_PREFIX:-$HOME/.pythia-studio}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
PURGE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --prefix) [ -n "${2:-}" ] || { echo "--prefix needs a directory" >&2; exit 2; }; PREFIX="$2"; shift ;;
    --purge) PURGE=1 ;;
    -h|--help) sed -n '2,5p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

say() { printf '\033[1m[pythia-uninstall]\033[0m %s\n' "$*"; }

for exe in pythia-studio pythia; do         # only links that point into our venv
  link="$BIN_DIR/$exe"
  if [ -L "$link" ] && [ "$(readlink "$link")" = "$PREFIX/venv/bin/$exe" ]; then
    rm -f "$link"; say "removed $link"
  fi
done
DESKTOP="${XDG_DATA_HOME:-$HOME/.local/share}/applications/pythia-studio.desktop"
if [ -f "$DESKTOP" ] && grep -qF "$PREFIX/venv/" "$DESKTOP"; then rm -f "$DESKTOP"; fi
if grep -qF "$PREFIX/venv/" "$HOME/Applications/PYTHIA Studio.app/Contents/MacOS/pythia-studio" 2>/dev/null; then
  rm -rf "$HOME/Applications/PYTHIA Studio.app"
fi
rm -rf "$PREFIX/venv"; rm -f "$PREFIX/icon.png"
say "removed the virtualenv and launchers"

if [ "$PURGE" = 1 ]; then
  rm -rf "$PREFIX"; say "purged $PREFIX (all workspaces, jobs and the build cache)"
else
  say "kept your data in $PREFIX (rerun with --purge to delete it)"
fi
