# Installing PYTHIA Studio

PYTHIA Studio is a local app: a Python server plus a web UI that opens in its own window. It compiles your Python hotspots to C++ on your machine, so it needs a **C++17 compiler, Python 3.10+ and the Python headers**. The installers below take care of that, and `pythia-studio --doctor` tells you exactly what is missing and how to fix it.

| You have | Use |
|---|---|
| Linux, macOS or WSL | [Path 1: one-liner](#1-one-liner-linux-macos-wsl) |
| Windows | [Path 1b: install.ps1](#1b-windows-through-wsl2) (sets up WSL2 for you) |
| Python and pip already | [Path 2: pip / pipx](#2-pip-or-pipx) |
| Docker | [Path 3: Docker](#3-docker) |

## 1. One-liner (Linux, macOS, WSL)

```bash
curl -fsSL https://raw.githubusercontent.com/Vishalvivek2007/Pythia/main/scripts/install.sh | bash
```

or from a checkout: `scripts/install.sh --from-source .`

It checks Python, a compiler, `Python.h` and venv support, offers to install what is missing (`apt`, `dnf`, `pacman`, `zypper`, `brew`; it asks first, `--yes` to skip the prompt), creates `~/.pythia-studio/venv`, links `pythia-studio` and `pythia` into `~/.local/bin`, and adds an app-menu launcher (a `.desktop` entry on Linux, `~/Applications/PYTHIA Studio.app` on macOS). macOS needs the Xcode command line tools (`xcode-select --install`) for the compiler.

```bash
pythia-studio --app            # app window
pythia-studio --app --offline  # bundled demo with cached LLM answers, no API key needed
~/.pythia-studio/uninstall.sh  # remove it (add --purge to delete your data too)
```

### 1b. Windows (through WSL2)

PYTHIA needs a Linux toolchain, so on Windows the server runs in WSL2 and the window opens in your normal Edge or Chrome.

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1            # downloads install.sh from GitHub
powershell -ExecutionPolicy Bypass -File scripts\install.ps1 -FromSource # installs this checkout
```

It installs WSL2 + Ubuntu if needed (`wsl --install -d Ubuntu`; Windows may ask for a restart, then run it again), runs `install.sh` inside Ubuntu, and creates a Start-Menu and Desktop shortcut "PYTHIA Studio" plus `pythia-studio.cmd` on your PATH. Closing the app window stops the server.

## 2. pip or pipx

```bash
pipx install "git+https://github.com/Vishalvivek2007/Pythia.git"     # isolated, recommended
# or: python -m venv .venv && . .venv/bin/activate && pip install .
sudo apt install build-essential python3-dev                          # compiler + headers (Linux)
pythia-studio --doctor                                                # verify
pythia-studio --app
```

The wheel is self-contained: compiler sources, C++ runtime, prebuilt web UI, the demo project and the offline cache are all inside it. From a checkout, build one with `make wheel` (`dist/pythia_studio-1.0.0-py3-none-any.whl`). `python -m pythia_studio` is the same as `pythia-studio`.

## 3. Docker

```bash
docker build -t pythia-studio .
docker run --rm -p 127.0.0.1:8765:8765 -v pythia-data:/data pythia-studio
# or, with your projects browsable in the "Open folder" dialog (read-only) and an LLM key:
PROJECTS=~/code GROQ_API_KEY=gsk_... docker compose up
```

Open <http://localhost:8765>. In the folder picker type `/projects` (also available as `~/projects`). Data (workspaces, jobs, build cache) lives in the `/data` volume. Use "Offline" in the UI or `PYTHIA_OFFLINE=1` for the bundled demo without a key. Published images: `ghcr.io/vishalvivek2007/pythia-studio` (pushed on version tags).

The container binds `0.0.0.0` internally; the compose file publishes it on loopback only. The UI can read any folder you mount, so do not publish it to a network you do not trust. To reach it by another name, add the name to `PYTHIA_ALLOWED_HOSTS` (comma separated); other `Host` headers get a 403 (DNS-rebinding guard).

## Using it

```text
pythia-studio [--app] [--no-open] [--offline] [--port 8765] [--host 127.0.0.1] [--home DIR] [--doctor]
```

* `--app` opens a chromeless window with its own browser profile (Edge, Chrome, Chromium or Brave; set `PYTHIA_BROWSER=/path/to/browser` to choose). Closing the window shuts the server down; Ctrl+C does too. Without `--app` it opens a normal tab.
* Starting a second copy on the same port just opens another window.
* The page is also an installable PWA: in Chrome/Edge use the "Install PYTHIA Studio" icon in the address bar.
* An LLM is optional. Put `GROQ_API_KEY=...` (free) or `ANTHROPIC_API_KEY=...` in `~/.pythia-studio/.env` or the environment. Without a key everything except the LLM rewrite step works, and `--offline` replays recorded answers for the demo.
* Environment: `PYTHIA_HOME` (data, default `~/.pythia-studio`), `PYTHIA_PORT`, `PYTHIA_HOST`, `PYTHIA_ALLOWED_HOSTS`, `PYTHIA_OFFLINE=1`, `PYTHIA_BROWSER`.
* `GET /api/doctor` returns the same environment report as `--doctor`.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| Doctor says `C++17 compiler` missing | Ubuntu/Debian/WSL: `sudo apt install build-essential`. Fedora: `sudo dnf install gcc-c++`. macOS: `xcode-select --install`. |
| Doctor says `Python.h` missing | `sudo apt install python3-dev` (Fedora `python3-devel`). With pyenv/uv Pythons the headers ship with Python; with Homebrew run `brew reinstall python`. |
| `ensurepip is not available` / venv creation fails | `sudo apt install python3-venv`. |
| `pythia-studio: command not found` | Add `~/.local/bin` to PATH: `export PATH="$HOME/.local/bin:$PATH"`. On Windows open a new terminal, or use the Start-Menu shortcut. |
| Port already in use | Another program owns 8765: `pythia-studio --port 8800`. If it is PYTHIA itself, the launcher just opens a window. |
| `--app` opens a normal tab | No Chromium-family browser found. Install Chrome/Edge/Brave or set `PYTHIA_BROWSER`. |
| WSL: window does not open | The server is still running: browse to <http://localhost:8765>. Needs WSL2 with localhost forwarding (the default). |
| Windows: `wsl --install` finished but nothing happened | Restart Windows, open "Ubuntu" once to create your Linux user, then run `install.ps1` again. |
| First compile takes 10-20 s, first demo run a few minutes | One-time: the C++ runtime and a precompiled header are built into `~/.pythia-studio/build-cache` (about 400 MB). Later builds are cached. |
| Everything is slow under Python 3.10/3.11 | The tracer uses `sys.monitoring` on 3.12+ and a slower profiler hook before. Use 3.12+. |
| `403 this server only answers requests addressed to localhost` | You reached it through another hostname or IP. Add it to `PYTHIA_ALLOWED_HOSTS`. |
| Docker: "Open folder" shows an empty list | Mount a folder: `PROJECTS=/path/to/code docker compose up`, then browse `/projects`. |
| LLM step says disabled | Set `GROQ_API_KEY` or `ANTHROPIC_API_KEY`, or use Offline mode for the demo. |

Verify an install end to end (builds the wheel, installs it into a throwaway venv, boots the server, runs the demo job): `scripts/check_package.sh`.
