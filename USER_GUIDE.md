# PYTHIA Studio — User Guide

PYTHIA Studio finds the slow, compilable parts of a Python project, compiles them to C++17, **proves** the compiled versions behave identically to your Python, and shows every change as a reviewable diff. Your original project is never modified; you review, accept or reject each function, then export.

> **The LLM suggests, the compiler proves.** The LLM (optional) only rewrites Python into PySub, the typed Python subset PYTHIA compiles. Every rewrite must pass the type checker, and every compiled function must reproduce the real calls of your program before it can be called *verified*.

---

## 1. Install and start (2 minutes)

Pick one path (details and troubleshooting in [INSTALL.md](INSTALL.md)):

| You have | Do this |
|---|---|
| Linux, macOS or WSL | `curl -fsSL https://raw.githubusercontent.com/Vishalvivek2007/Pythia/main/scripts/install.sh \| bash` then `pythia-studio --app` |
| Windows | `powershell -ExecutionPolicy Bypass -File scripts\install.ps1` (sets up WSL2 + Ubuntu for you), then use the **PYTHIA Studio** Start-Menu shortcut |
| Docker | `docker build -t pythia-studio . && docker run --rm -p 127.0.0.1:8765:8765 -v pythia-data:/data pythia-studio`, then open <http://127.0.0.1:8765> |
| This repository checkout (Linux/macOS/WSL) | `./studio.sh` (creates a virtualenv on first run, installs dependencies, opens the browser; `--offline` for the cached demo, `--app` for a chromeless window) |
| This repository checkout (Windows) | double-click **`studio.cmd`** (or run it from a terminal). It starts PYTHIA inside WSL2, which provides the Linux C++ toolchain, and opens your browser. Running `python -m pythia_studio` on Windows does the same hand-off automatically. |

You need a **C++ compiler** (g++/clang) and Python 3.10+ (3.12+ recommended). `pythia-studio --doctor` checks everything and prints the exact fix for anything missing.

**Optional — turn on the LLM fixer for free.** Create a free key at <https://console.groq.com>, then either put `GROQ_API_KEY=your_key` in a file named `.env` next to where you launch PYTHIA (or in `~/.pythia-studio/.env`), or paste it in **Settings → LLM key** inside the app. PYTHIA uses the free `openai/gpt-oss-120b` model on Groq. An `ANTHROPIC_API_KEY` works too. Without any key everything still works; the LLM fixer is simply off (functions that need a rewrite stay "Fixable").

---

## 2. Your first run: the demo project (3 minutes)

1. Start the app. On the **welcome screen** click **Open the demo project** (Quanta, a 3,800-line analytics toolkit; a full run takes a few minutes on a cold machine, mostly benchmarking — the TextLab demo under *Demo projects* takes about 90 seconds).
2. Watch the **pipeline stepper** along the top fill in left to right: *Ingest → Scan → Trace → Rank → Fix → Compile → Verify → Benchmark → Splice → Export*. Each stage shows a one-number result. Click any stage to see its real output.
3. The right-hand **PYTHIA agent** panel narrates what the engine is doing, one line per step ("Traced `python main.py --small` · 523,953 calls", "`edit_distance` → PySub ✓ → C++ ✓ → 500/500 replays match → 10×").
4. When it finishes, the summary card shows the **end-to-end speedup** of the whole program (output hash must be identical) and the status counts.
5. Click a function in the **Hotspots** list (left) to review it — see §4.
6. Click **Accept all** (or accept functions one by one), then **Export**.

**Want it instantly?** Click **Replay sample run** next to the demo button: a finished run of the same project is bundled with the app and plays back in about a minute without compiling anything (browse everything; Export needs a real run).

To see it as a guided show instead, click **Presenter** (top right): the run plays stage by stage with captions; **Space** pauses, **→** steps.

---

## 3. Analysing your own code

On the welcome screen choose how to bring code in:

* **Open folder** — type or **Browse** to a project folder on this machine. The folder is *copied* into a private workspace (it respects `.gitignore`, skips `venv`, `node_modules`, `.git`, caches and files over 5 MB).
* **Clone repository** — paste a public Git URL (`https://github.com/user/repo`, or a `file://` path). A shallow clone is analysed.
* **Drop a file** — drag a `.py` file anywhere into the window.
* **Playground** — type code and see the generated C++ live (§7).

### The entry command (strongly recommended)

Under the cards there is an **Entry command** box, e.g. `python main.py --small`. When you give one, PYTHIA runs your program once under a tracer to learn:

* **where the time really goes** (so the hot spots are ranked by real measurements, not guesses),
* **what types** your functions actually receive (this lets it annotate unannotated code automatically), and
* **real calls** (up to 500 per function) that are replayed through both the Python and the compiled version to prove they match.

Without a command PYTHIA still scans and ranks statically and checks the compiled code with generated inputs, but results are less meaningful. Use a command that finishes in under a minute and exercises your hot code; the command runs inside the workspace copy, so file paths relative to the project root work.

### Offline mode

The **Offline mode** switch makes PYTHIA replay recorded LLM answers and prebuilt modules for the bundled demo project, so the demo runs with no network and no key. For your own projects leave it off.

---

## 4. Reading and reviewing the results

### Status chips

| Chip | Meaning |
|---|---|
| **Verified** | Compiled, and every replayed call matched Python exactly (return value, exception class, and the post-call state of list/dict arguments; floats bitwise). No risky arithmetic sites. |
| **Guarded** | Matched, **and** the function has guarded sites — e.g. integer `+`/`*` that can't be proven free of int64 overflow (PYTHIA raises `OverflowError` instead of silently wrapping, where Python would grow a big integer). Usually fine; read the fidelity notes. |
| **Fixable** | Not valid PySub as written, but a rewrite or annotation may fix it (needs the trace or the LLM). |
| **Declined** | Compiles, but crossing the Python/C++ boundary would cost more than it saves (large lists passed many times). PYTHIA measured it as a *probe* and shows the number (< 1×); it is never spliced in. |
| **Failed** | Compiled but a replay mismatched. It is auto-rejected, and the **first counterexample** is shown. |
| **Not eligible** | Can't be compiled, with the exact reason ("uses a closure", "calls `numpy`", "variable `x` changes type from str to int", "method of class `Vocab`"…). |

Use the filter tabs **All / Accelerated / Fixable / Stopped** above the list. Each row shows the function's share of runtime (bar), status and measured speedup.

### Opening a function

Click it. The header shows status, speedup, runtime share, call count and how many replays matched. Three views:

* **Diff** — your original file vs the accelerated file. The change is deliberately tiny and reversible: the original function body is untouched and a one-line decorator is added; the compiled module is used when available and the original Python runs as a fallback.
* **Three-way** — original Python | PySub (the typed version actually compiled; differs from your code only if the LLM or annotator changed it) | generated C++. Gutter colours mark **fidelity**: green = exact, amber = guarded, red = divergent. Hover a line for the divergence class, why it matters and how PYTHIA mitigates it.
* **Journey** — the function's whole path through the system as a timeline: *Original → observed types → eligibility → LLM rewrite attempts (each with the type-checker error that triggered the retry) → final PySub → Tokens → AST → Typed AST → PIR → C++ → pybind11 wrapper → build → oracle replay → benchmark → splice → status*. Steps that were skipped or failed are greyed with the exact reason, so you can see *where* and *why* a function stopped.

### Accept or reject

Every function has **Accept** and **Reject** buttons (and a right-click menu in the list). Rejecting removes that function's acceleration from the workspace immediately. **Accept all** / **Reject all** act on every verified/guarded function. Nothing touches your original project until you export.

### Bottom panel

* **Terminal** — raw trace/build/system logs.
* **Problems** — type-checker errors with jump-to-line.
* **Fidelity** — every divergence note, filterable by class and severity.
* **Benchmarks** — per-function Python vs C++ on a log scale, plus the end-to-end before/after and whether program output stayed identical.

### Stage inspectors

Click any stage in the stepper: the file list that was ingested, the full sortable function table from the scan, the trace profile (flame/icicle chart of where time went), the ranking with the score breakdown (trace share × eligibility × expected benefit − boundary cost), LLM attempts with model and latency, compiler logs, replay matrices (one dot per recorded call), benchmark charts, the splice diff and the export manifest.

---

## 5. Exporting and using the faster project

Click **Export** (agent panel) and choose a folder or a zip. You get:

* your project with the accepted functions accelerated (`_pythia_accel/` holds the compiled `.so` files and a tiny loader),
* `PYTHIA_REPORT.md` — per-function status, speedup, replay counts, fidelity notes and every LLM rewrite,
* `build_accel.sh` — rebuilds the `.so` files on another machine of the same OS family (needs a C++ compiler, Python headers and `pybind11`).

Run the exported project exactly as before (`python main.py …`). If a compiled module is missing or can't be loaded, or an input can't be represented faithfully (for example non-ASCII strings), the original Python runs instead — the project never breaks. Set `PYTHIA_ACCEL=0` to disable acceleration entirely. To undo a single function, delete its `@_pythia_accelerated(...)` line.

The **Report** page (activity bar) is a printable summary you can save as PDF.

---

## 6. The LLM fixer

Functions that nearly qualify — missing annotations, list comprehensions, `enumerate`, conditional expressions — are marked *Fixable*. With a key configured, PYTHIA asks the model for a PySub rewrite, feeding back the **exact type-checker errors** for up to three attempts. A rewrite is only used if it type-checks, compiles and then passes replay against your original function. You can read each attempt (diffed against the original, with the error that rejected it) in the function's **Journey** and in the **Fix** inspector.

Choose the provider in **Settings** (Auto / Groq / Anthropic / Offline). Your key is stored locally (`~/.pythia-studio/settings.json`, mode 600), is write-only in the UI and is only ever sent to the provider you selected.

---

## 7. Playground

Open the **Playground** (activity bar). Type PySub/Python on the left; the generated C++ appears on the right, debounced as you type, with the fidelity gutter on both sides and type errors as inline squiggles. **Run** (`Ctrl/⌘+Enter`) executes the program under CPython and as compiled C++ side by side, with an output diff and timings. It is the fastest way to learn what PYTHIA accepts.

**What PySub is:** a typed subset of Python — `int`, `float`, `bool`, `str`, `list[T]` (two levels deep), `dict[int|str, int|float|bool|str]`, classes with typed fields, `if/while/for-in-range/for-in-list`, `try/except` for the five common exceptions, and a handful of builtins (`len`, `abs`, `min`/`max` of two, `int/float/str/bool`). Every variable keeps one type. No comprehensions, closures, generators, imports or `print` formatting beyond plain values. The Studio shows the precise reason whenever something falls outside it.

---

## 8. Keyboard shortcuts

Press `?` in the app for the full sheet. Key ones (`Ctrl` on Linux/Windows, `⌘` on macOS):

| Keys | Action |
|---|---|
| `Ctrl/⌘ + K` | Command palette (functions, files, actions) |
| `Ctrl/⌘ + P` | Quick-open a file or function |
| `Ctrl/⌘ + Enter` | Run the analysis (or Run in the Playground) |
| `Ctrl/⌘ + Shift + A` | Accept every verified function |
| `Space` / `→` | Pause / step in Presenter mode |
| `Esc` | Close dialogs and menus |

---

## 9. Command-line use (no UI)

The compiler is also a plain tool:

```bash
# compile a typed Python file to C++17 and run it
python -m pythia.cli prog.py --run
# show the fidelity report
python -m pythia.cli prog.py --fidelity
# build an importable Python extension exposing chosen functions
python -m pythia.cli mymodule.py --lib fn1,fn2 --out build/lib
# the whole analysis pipeline headlessly (what scripts/smoke.sh does)
./scripts/smoke.sh
```

Launch options: `pythia-studio [--app] [--port N] [--host H] [--no-open] [--offline] [--home DIR] [--doctor]`.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| Red "No C++ compiler" banner | Install one: Ubuntu/WSL `sudo apt install build-essential python3-dev`, macOS `xcode-select --install`, Fedora `sudo dnf install gcc-c++ python3-devel`. Then restart. |
| Build fails with `Python.h not found` | Install the Python headers (`python3-dev` / `python3-devel`). |
| Everything is "Guarded" | Normal for integer-heavy code: any `+`/`-`/`*` on `int` that can't be proven to stay within 64 bits is guarded. It still matched on every replayed call. |
| A function is "Not eligible" but should work | Open its Journey → Eligibility for the exact reason; common fixes: add type annotations, move a nested helper to module level, replace a comprehension with a loop (or enable the LLM fixer). |
| Speedup is < 1× or "Declined" | The function is cheap relative to the data copied across the boundary on each call. Compile the *caller* (the loop) instead, or pass less data. |
| Whole-program speedup is small | Amdahl: only the compiled share of runtime gets faster. Look at the trace chart — the rest is glue, I/O or code PySub can't express. |
| "LLM: off" | No key found. Add `GROQ_API_KEY` (free) in `.env` or Settings. |
| First run is slow (minutes) | The first builds compile the C++ runtime and a precompiled header (~10 s) and each new function takes ~5 s; later runs reuse the cache in `~/.pythia-studio/build-cache`. |
| Port already in use | `pythia-studio --port 8800`. A second launch on the same port just opens a window to the running instance. |
| Browser can't reach WSL app | Open <http://localhost:8765> from Windows; or use `pythia-studio --app`. |

---

## 11. Know the limits (tell this to your reviewers too)

* **"Verified" = differential testing on recorded real inputs**, not a proof for all inputs. Code paths your trace command never exercises are untested; choose the entry command accordingly.
* Integers are 64-bit; overflow raises instead of promoting to big ints. Strings are ASCII bytes in compiled code (non-ASCII falls back to Python).
* Arguments are copied across the boundary; list/dict mutations are written back; tuples and aliasing between arguments are not preserved.
* v1 compiles **module-level functions** only (no methods, closures, third-party calls, I/O, default arguments, tuple returns).
* The compiled runtime frees memory per call but dict lookups are linear scans, so keep dictionaries small in hot code.
* PYTHIA executes your code (tracing/replay) as your user: analyse code you trust.
* Python → C++ only; the architecture is source-language-agnostic past the IR.

More technical detail: [studio/README.md](studio/README.md) (architecture) and [DEMO.md](DEMO.md) (3-minute demo script and viva Q&A).
