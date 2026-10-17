#!/usr/bin/env bash
# PYTHIA Studio installer for Linux, macOS and WSL.
#
#   curl -fsSL https://raw.githubusercontent.com/Vishalvivek2007/Pythia/main/scripts/install.sh | bash
#   scripts/install.sh --from-source .          # install the checkout you are standing in
#
# What it does (nothing outside $PREFIX and ~/.local is touched, except the system packages you approve):
#   1. checks Python >= 3.10, a C++17 compiler, Python.h and venv support; offers to install what is missing (apt/dnf/pacman/zypper/brew)
#   2. creates an isolated virtualenv in $PREFIX/venv and installs pythia-studio into it
#   3. links `pythia-studio` and `pythia` into ~/.local/bin
#   4. adds a launcher: a .desktop entry (Linux) or a small .app bundle (macOS) that opens the chromeless app window
#
# Options:
#   --from-source DIR   install from a source checkout        --from-wheel FILE   install a built wheel
#   --spec SPEC         any pip requirement (default: PYTHIA_SPEC or the GitHub repo)
#   --prefix DIR        install root (default ~/.pythia-studio; the venv is DIR/venv)
#   --yes               do not prompt, answer yes (needed when piped without a terminal)
#   --no-system-deps    never touch system packages      --no-launcher   skip the desktop launcher
#   -h, --help
set -euo pipefail

PREFIX="${PYTHIA_PREFIX:-$HOME/.pythia-studio}"
SPEC="${PYTHIA_SPEC:-git+https://github.com/Vishalvivek2007/Pythia.git}"
BIN_DIR="${XDG_BIN_HOME:-$HOME/.local/bin}"
ASSUME_YES=0
SYSTEM_DEPS=1
LAUNCHER=1

say()  { printf '\033[1m[pythia-install]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[pythia-install] %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[31m[pythia-install] ERROR: %s\033[0m\n' "$*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --from-source) [ -n "${2:-}" ] || die "--from-source needs a directory"; SPEC="$(cd "$2" && pwd)"; shift ;;
    --from-wheel)  [ -n "${2:-}" ] || die "--from-wheel needs a file"; SPEC="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"; shift ;;
    --spec)        [ -n "${2:-}" ] || die "--spec needs a value"; SPEC="$2"; shift ;;
    --prefix)      [ -n "${2:-}" ] || die "--prefix needs a directory"; PREFIX="$2"; shift ;;
    --yes|-y) ASSUME_YES=1 ;;
    --no-system-deps) SYSTEM_DEPS=0 ;;
    --no-launcher) LAUNCHER=0 ;;
    -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option: $1 (try --help)" ;;
  esac
  shift
done

# ask "question" -> 0 for yes. Reads the terminal even when the script itself is piped (curl | bash).
ask() {
  [ "$ASSUME_YES" = 1 ] && return 0
  if [ -r /dev/tty ] && : </dev/tty 2>/dev/null; then
    printf '%s [Y/n] ' "$1" >/dev/tty
    local a; read -r a </dev/tty || a=""
    case "$a" in n|N|no|NO) return 1 ;; *) return 0 ;; esac
  fi
  die "no terminal to ask '$1'. Re-run with --yes to accept, or --no-system-deps to skip."
}

# ---- platform -------------------------------------------------------------------------------------
OS="$(uname -s)"
case "$OS" in
  Linux|Darwin) ;;
  *) die "unsupported system '$OS'. On Windows run scripts/install.ps1 (it sets up WSL and calls this script)." ;;
esac
WSL=0; grep -qi microsoft /proc/version 2>/dev/null && WSL=1

PM=""
if [ "$OS" = Darwin ]; then command -v brew >/dev/null 2>&1 && PM=brew
elif command -v apt-get >/dev/null 2>&1; then PM=apt
elif command -v dnf >/dev/null 2>&1; then PM=dnf
elif command -v pacman >/dev/null 2>&1; then PM=pacman
elif command -v zypper >/dev/null 2>&1; then PM=zypper
fi

SUDO=""
if [ "$(id -u)" != 0 ] && [ "$OS" = Linux ]; then
  command -v sudo >/dev/null 2>&1 && SUDO="sudo"
fi

pm_install() {          # pm_install pkg...
  case "$PM" in
    apt)    $SUDO apt-get update -qq && $SUDO apt-get install -y "$@" ;;
    dnf)    $SUDO dnf install -y "$@" ;;
    pacman) $SUDO pacman -S --needed --noconfirm "$@" ;;
    zypper) $SUDO zypper --non-interactive install "$@" ;;
    brew)   brew install "$@" ;;
    *)      return 1 ;;
  esac
}

need_pkgs() {           # need_pkgs "<why>" apt-pkgs... -- dnf-pkgs... -- pacman-pkgs... -- zypper-pkgs... -- brew-pkgs...
  local why="$1"; shift
  local -a groups=() cur=()
  local a
  for a in "$@"; do
    if [ "$a" = "--" ]; then groups+=("${cur[*]:-}"); cur=(); else cur+=("$a"); fi
  done
  groups+=("${cur[*]:-}")
  local pick=""
  case "$PM" in apt) pick="${groups[0]}" ;; dnf) pick="${groups[1]:-}" ;; pacman) pick="${groups[2]:-}" ;;
                zypper) pick="${groups[3]:-}" ;; brew) pick="${groups[4]:-}" ;; esac
  if [ "$SYSTEM_DEPS" = 0 ] || [ -z "$PM" ] || [ -z "$pick" ]; then
    warn "missing: $why. Install it with your package manager (apt: ${groups[0]})."
    return 1
  fi
  say "missing: $why  ->  ${PM} install $pick"
  ask "Install '$pick' now?" || { warn "skipped; $why stays missing"; return 1; }
  # shellcheck disable=SC2086
  pm_install $pick
}

# ---- Python >= 3.10 ---------------------------------------------------------------------------------
find_python() {
  local c
  for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      command -v "$c"; return 0
    fi
  done
  return 1
}

PY="$(find_python || true)"
if [ -z "$PY" ]; then
  need_pkgs "Python 3.10+" python3 python3-venv python3-dev -- python3 python3-devel -- python -- python3 -- python || true
  PY="$(find_python || true)"
fi
[ -n "$PY" ] || die "Python 3.10 or newer is required (https://www.python.org/downloads/)."
say "Python: $PY ($("$PY" -c 'import platform; print(platform.python_version())'))"

has_header() { "$PY" -c 'import os, sys, sysconfig; sys.exit(0 if os.path.isfile(os.path.join(sysconfig.get_paths()["include"], "Python.h")) else 1)'; }

if ! command -v c++ >/dev/null 2>&1 && ! command -v g++ >/dev/null 2>&1 && ! command -v clang++ >/dev/null 2>&1; then
  if [ "$OS" = Darwin ]; then
    warn "No C++ compiler. Run: xcode-select --install   (then re-run this installer)"
  else
    need_pkgs "a C++17 compiler" build-essential -- gcc-c++ make -- base-devel -- gcc-c++ make -- gcc || true
  fi
fi
command -v c++ >/dev/null 2>&1 || command -v g++ >/dev/null 2>&1 || command -v clang++ >/dev/null 2>&1 \
  || warn "No C++ compiler found: the UI will start, but nothing can be compiled until you install one."

if ! has_header; then
  need_pkgs "Python headers (Python.h)" python3-dev -- python3-devel -- python -- python3-devel -- python || true
  has_header || warn "Python.h still missing: compiled modules cannot be built. Debian/Ubuntu: sudo apt install python3-dev"
fi

# ---- venv + package -----------------------------------------------------------------------------------
VENV="$PREFIX/venv"
mkdir -p "$PREFIX"
make_venv() { rm -rf "$VENV"; "$PY" -m venv "$VENV" >/dev/null 2>&1 && [ -x "$VENV/bin/pip" ]; }
if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
  say "creating virtualenv in $VENV"
  if ! make_venv; then
    need_pkgs "python venv support" python3-venv -- python3 -- python -- python3 -- python || true
    make_venv || die "could not create a virtualenv with $PY (Debian/Ubuntu: sudo apt install python3-venv)"
  fi
fi

say "installing pythia-studio from: $SPEC"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet --upgrade "$SPEC" || die "pip install failed (see the error above)"
VERSION="$("$VENV/bin/pythia-studio" --version 2>/dev/null || echo '?')"
say "installed PYTHIA Studio $VERSION"

# ---- commands on PATH -------------------------------------------------------------------------------------
mkdir -p "$BIN_DIR"
for exe in pythia-studio pythia; do
  ln -sf "$VENV/bin/$exe" "$BIN_DIR/$exe"
done
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR is not on your PATH. Add this line to ~/.bashrc or ~/.zshrc:   export PATH=\"$BIN_DIR:\$PATH\"" ;;
esac

# uninstaller next to the venv (copied from the checkout, or fetched when run via curl | bash)
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
if [ -f "$SELF_DIR/uninstall.sh" ]; then cp "$SELF_DIR/uninstall.sh" "$PREFIX/uninstall.sh"
else curl -fsSL "https://raw.githubusercontent.com/Vishalvivek2007/Pythia/main/scripts/uninstall.sh" -o "$PREFIX/uninstall.sh" 2>/dev/null || true; fi
chmod +x "$PREFIX/uninstall.sh" 2>/dev/null || true

# ---- launcher ------------------------------------------------------------------------------------------------
if [ "$LAUNCHER" = 1 ]; then
  ICON="$PREFIX/icon.png"
  "$VENV/bin/pythia-studio" --export-icon "$ICON" 2>/dev/null || ICON=""
  if [ "$OS" = Linux ]; then
    APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
    mkdir -p "$APPS"
    cat >"$APPS/pythia-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=PYTHIA Studio
Comment=Accelerate Python hotspots with verified C++
Exec=$VENV/bin/pythia-studio --app
Icon=${ICON:-utilities-terminal}
Terminal=false
Categories=Development;
StartupWMClass=PYTHIA Studio
EOF
    chmod +x "$APPS/pythia-studio.desktop"
    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" >/dev/null 2>&1 || true
    say "launcher: $APPS/pythia-studio.desktop (search 'PYTHIA Studio' in your app menu)"
  else
    APP="$HOME/Applications/PYTHIA Studio.app"
    mkdir -p "$APP/Contents/MacOS"
    cat >"$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>PYTHIA Studio</string>
<key>CFBundleIdentifier</key><string>dev.pythia.studio</string>
<key>CFBundleExecutable</key><string>pythia-studio</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleVersion</key><string>1.0.0</string>
</dict></plist>
EOF
    printf '#!/bin/sh\nexec "%s/bin/pythia-studio" --app\n' "$VENV" >"$APP/Contents/MacOS/pythia-studio"
    chmod +x "$APP/Contents/MacOS/pythia-studio"
    say "launcher: $APP (double-click, or drag to the Dock)"
  fi
fi

# ---- verdict ---------------------------------------------------------------------------------------------------
echo
"$VENV/bin/pythia-studio" --doctor || warn "Some requirements are missing (see above). The fix hints show the exact commands."
echo
say "uninstall later with:  $PREFIX/uninstall.sh"
say "done. Start it with:   pythia-studio --app        (add --offline to run the bundled demo without an API key)"
[ "$WSL" = 1 ] && say "WSL: the window opens in your Windows Edge/Chrome; the server runs inside Linux."
exit 0
