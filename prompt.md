# PYTHIA Studio — build prompt for Claude Code

You are building **PYTHIA Studio**: a professional, IDE-grade desktop-feel web application that takes a Python codebase (typed snippet, dropped file, local folder path, or GitHub URL), finds the parts that are slow and convertible, compiles them to C++17 with our existing PYTHIA transpiler, splices the compiled versions back into the project, **proves** they behave identically, and shows every change in a Cursor-style diff view.

This is a course project (Compiler Design, VIT) that must also be a demo-ready product. The bar is: a stranger sits down, opens it, and within 3 minutes sees their Python project get measurably faster with verified, reviewable changes. Polish matters as much as function.

The repo is `github.com/Vishalvivek2007/Pythia`. Work inside it. Read it fully before planning.

---

## 0. Ground rules

1. **Read before you build.** Read every file in `pythia/`, `runtime/`, `tools/`, `tests/`, `docs/`, plus the README and Makefile. Learn the *actual* PySub subset from `typecheck.py` and `parser.py`; do not trust this prompt's summary of it over the code.
2. **Don't break the compiler.** The existing CLI (`python3 -m pythia.cli ...`) and `tools/oracle.py` must keep working exactly as before. Our course evaluation depends on them. New compiler capability is additive (new flags, new modules).
3. **Minimal testing.** Do not write unit-test suites per module. Do not spend turns writing tests for UI components or API endpoints. The only required checks are:
   - the existing `python3 tools/oracle.py` still passes after compiler changes, and
   - one end-to-end smoke script (`scripts/smoke.sh`) that runs the full pipeline on the demo project headlessly and asserts at least 3 functions come back verified with speedup > 1.
   Run those, fix what breaks, move on. Spend the saved time on the product and the demo.
4. **Never mutate the user's original project.** All output goes to a workspace copy. The user exports when they're happy.
5. **Python → C++ only.** Do not add other source languages. If asked in the UI, show "Python projects supported; architecture is source-language-agnostic past the IR."
6. **Work autonomously, end to end.** Do not stop to ask questions or wait for approval between phases. When something is ambiguous, pick the most reasonable option, note it in `studio/DECISIONS.md` (one line each), and keep going. Install whatever dependencies you need. The only reasons to stop are things you genuinely cannot do yourself (e.g. a missing `ANTHROPIC_API_KEY` when recording the offline cache, or pushing to a GitHub account): in that case finish everything else first, then list exactly what's needed in your final summary.
7. **Target platforms:** Linux and macOS natively, Windows via WSL. Detect the C++ compiler on startup and show a clear, friendly setup message if it's missing.

---

## 1. What the product does (the core loop)

```
input (snippet | file | folder path | git URL)
  → ingest into workspace copy
  → static scan: every function, eligibility, heuristic cost
  → optional trace run: real hotness + observed types + recorded calls
  → rank hotspots
  → classify each: VERIFIABLE / FIXABLE / NOT ELIGIBLE (with reason)
  → LLM rewrites FIXABLE functions into PySub → typechecker must accept
  → transpile eligible functions to a C++17 extension module (pybind11)
  → splice: original function replaced by import of compiled one
  → oracle replay: recorded calls through Python vs C++, compare outputs
  → benchmark per function + end-to-end
  → user reviews diffs, accepts/rejects per function
  → export accelerated project + report
```

The key idea to make visible everywhere in the UI: **the LLM suggests, the compiler proves.** The LLM never writes C++. It only rewrites Python into valid PySub. Every rewrite must pass our typechecker, and every compiled function must pass oracle replay before it can be marked verified.

---

## 2. Engine work (Python backend)

### 2.1 Compiler: library mode
Add a library-emission mode to the transpiler:
- Input: a set of PySub functions (and any PySub helper functions/classes they call), extracted from a user module.
- Output: a C++17 translation unit with **no `main`**, exposing those functions, plus a generated **pybind11 wrapper** that marshals arguments/returns:
  - `int ↔ int64_t`, `float ↔ double`, `bool`, `str ↔ pystr`, `list[T]` ↔ the runtime list types, `dict[K,V]` ↔ the runtime dict types, nested lists to the depth the compiler supports.
  - Runtime exceptions (IndexError, KeyError, ZeroDivisionError, OverflowError, etc.) must surface in Python as the same exception classes.
- Build with `c++ -std=c++17 -O3 -shared -fPIC $(python3 -m pybind11 --includes)` against `runtime/pyrt.cpp`, producing an importable `.so` per accelerated module. Cache builds by content hash.
- Expose this as `python3 -m pythia.cli <file> --lib <fn1,fn2,...> --out <dir>` so it's usable outside the UI too.
- Note: the runtime currently doesn't reclaim memory (divergence D7). Fine for the demo; just surface it as a fidelity note.

### 2.2 Analyzer (`pythia/studio/` package)
- **Ingest:** snippet → temp module; file → workspace; folder path → copy into workspace (respect `.gitignore`, skip `venv`, `node_modules`, `.git`, data files > 5 MB); git URL → `git clone --depth 1` into workspace. Stream progress.
- **Static scan:** parse every `.py` with Python's `ast`. For each function: location, size, loop nesting depth, arithmetic density, calls made, imports used. Run each function (with its PySub-eligible callees) through our real typechecker to decide eligibility. Collect the exact rejection reason in plain English ("uses a closure", "calls numpy", "variable `x` changes type from int to str", "missing annotations — fixable").
- **Trace run (optional, strongly encouraged in the UI):** user supplies an entry command (e.g. `python main.py --small`). Run it in a subprocess with a tracer using `sys.monitoring` (3.12+) or `sys.setprofile` fallback. Record per function: cumulative time, call count, observed argument/return types, and a sampled, size-capped set of real `(args, return)` pairs (e.g. up to 500 calls per function, skip any call whose args exceed a size cap). Timeout and kill cleanly.
- **Auto-annotation:** use observed types to synthesize PySub annotations for unannotated functions. This is what makes real-world code eligible without the user touching it.
- **Ranking:** score = (trace time share if available, else static heuristic) × eligibility × expected benefit, penalising functions with large marshalled inputs (crossing the Python/C++ boundary costs; a function called a million times on a 10k-element list may get slower). Show the score breakdown.
- **LLM fixer:** for FIXABLE functions, call the Anthropic API (model `claude-sonnet-5-5`, configurable; key from `ANTHROPIC_API_KEY`). Prompt it with the function, the PySub rules extracted from the typechecker, the exact typechecker error, and observed types. Ask for a semantically equivalent rewrite in PySub only. Loop up to 3 times feeding back typechecker errors. If it never passes, mark NOT ELIGIBLE with the reason. Without an API key, the app still works; the fixer is shown as disabled with a one-line hint.
- **Oracle replay:** for each compiled function, replay recorded calls through original Python and compiled C++. Compare return values and exception classes exactly (floats bitwise, matching our oracle's rules). Also run any fidelity notes for that function. Status: VERIFIED (all match), GUARDED (match, but has guarded divergence sites — e.g. overflow traps), FAILED (mismatch → auto-reject, show the first mismatching input as a counterexample).
- **Benchmark:** per function, time replayed calls Python vs C++ (repeat, take median). If a trace entry command exists, run it end-to-end before vs after splice and report total speedup.
- **Splice:** in the workspace copy, replace each accepted function's body with a thin dispatch to the compiled version, keeping the signature and docstring, e.g. a `@pythia.accelerated` decorator or a guarded import at the bottom of the module that rebinds the name. Must fall back to the original Python if the `.so` fails to import. Keep the original body in a comment block or `_pythia_original_<name>` so diffs are reviewable and reversible.
- **Export:** write the accelerated project to a chosen folder or a zip; include `PYTHIA_REPORT.md` (per-function status, speedups, fidelity notes, LLM rewrites) and a `build_accel.sh` that rebuilds the `.so` files on another machine.

### 2.3 API server
FastAPI + WebSockets. One long-running **job** per analysis with a typed event stream the UI renders live (`ingest.progress`, `scan.function`, `trace.progress`, `rank.done`, `fix.attempt`, `compile.done`, `verify.result`, `bench.result`, `splice.ready`, `log`, `error`). REST endpoints for: start job (any input type), file tree, file contents, per-function detail (original, rewritten PySub, generated C++, fidelity notes, replay results), accept/reject, export, playground compile/run, pipeline-stage dump (tokens, AST, typed AST, PIR, C++).

---

## 3. The UI — this is what wins the demo

Stack: **React + Vite + TypeScript + Tailwind**, **Monaco Editor** (incl. its diff editor), **xterm.js** for the terminal panel, **Framer Motion** used sparingly, **cmdk** for the command palette. Served locally by the FastAPI app; one command starts everything (`./studio.sh` → installs deps on first run → opens the browser).

### Look and feel
- Professional IDE, in the league of Cursor / VS Code / JetBrains. Dark by default, near-black surfaces, one accent colour, hairline borders, no gradients-everywhere, no emoji, no cartoonish illustrations. Clean and minimal.
- Inter for UI, JetBrains Mono for code. Dense but breathable. Every interaction ≤ 150 ms of feedback; skeletons instead of spinners.
- Keyboard-first: ⌘/Ctrl+K command palette, ⌘P quick-open file, ⌘Enter run, ⌘⇧A accept all.

### Layout
- **Activity bar** (far left icons): Explorer, Hotspots, Playground, Report, Settings.
- **Side panel:** file tree with per-file badges (number of hotspots, accelerated count); in Hotspots mode, the ranked function list with a horizontal time-share bar, status chip (Verified / Guarded / Fixable / Not eligible / Failed) and speedup.
- **Editor area:** tabs. Opening a function shows a **Monaco diff** (original Python vs accelerated Python), with a toggle to a **three-way view**: original Python | PySub rewrite (if LLM changed it) | generated C++. Gutter colours on the C++/Python lines by fidelity class (exact green, guarded amber, divergent red); hover a line to see the divergence class, explanation and mitigation. Inline accept/reject buttons per function, like Cursor.
- **Right panel — "PYTHIA agent":** a live, Cursor-composer-style feed of what the engine is doing ("Tracing `main.py`… 12,480 calls recorded", "`edit_distance` → PySub ✓ → C++ ✓ → 500/500 replays match → 38.2×"). Each step expandable. Ends with a summary card and **Accept all / Reject all / Export**.
- **Bottom panel tabs:** Terminal (raw build/trace logs via xterm), Problems (typechecker diagnostics with jump-to-line), Fidelity (all notes, filterable), Benchmarks (per-function bar chart Python vs C++ on a log scale, plus end-to-end before/after).
- **Status bar:** workspace name, compiler detected, LLM on/off, job state, total speedup.

### Step-by-step visibility (first-class feature, not an afterthought)
The user must be able to *see* every stage of the process, both for the whole project and for a single function. Three layers:

1. **Project pipeline stepper.** A slim horizontal stepper pinned at the top of the editor area: `Ingest → Scan → Trace → Rank → Fix → Compile → Verify → Benchmark → Splice → Export`. Each stage shows idle / running (subtle animated progress) / done (with a one-number result, e.g. "Scan · 84 functions", "Verify · 6/7") / failed. Clicking a stage opens a **stage inspector** in the editor area showing that stage's real output: files ingested, the full function table from the scan, the trace profile (flame-style or sorted bars), ranking score breakdowns, LLM fix attempts with the typechecker error each round, compiler build logs, replay results, benchmark charts, the splice diff, the export manifest.

2. **Function journey view.** Opening any function shows a vertical timeline of *that function's* path through the system, each node expandable to its artifact:
   `Original Python → observed types (from trace) → eligibility check (typechecker verdict) → LLM rewrite attempts (diff per attempt, error that triggered the retry) → final PySub → Tokens → AST → Typed AST → PIR (with fidelity notes) → generated C++ → pybind11 wrapper → build (.so, compile time) → oracle replay (N/N matched, first counterexample if any) → benchmark (Python vs C++ median, speedup) → splice diff → status`.
   Failed or skipped steps are shown greyed with the exact reason, so the user sees *where* and *why* a function stopped. This replaces a separate Pipeline explorer: the compiler-phase steps (Tokens → AST → Typed AST → PIR → C++) live inside the journey, with tree views and source highlighting synced to the selected node.

3. **Presenter mode.** A toggle (and `?presenter=1`) for live demos: the whole run plays stage by stage at a readable pace, auto-focuses the active stage inspector, auto-opens the journey of the top hotspot as it progresses, and shows a short caption per step ("Typechecker rejected: list comprehension → asking the LLM for a PySub rewrite"). Space pauses/resumes, → steps forward. Works in offline demo mode. Every completed job can also be **replayed** later from its saved event log, so the demo never depends on timing luck.

### Entry points (welcome screen)
Four large, quiet cards: **Open folder** (path input + native-feeling picker via backend), **Clone repository** (paste a GitHub URL), **Drop a file** (drag-and-drop anywhere in the window also works), **Playground**. Plus "Recent workspaces" and "Open demo project".

### Playground
Split view: type PySub/Python on the left, live C++ on the right (debounced compile), fidelity gutter on both, and a Run button that executes under CPython and the compiled binary side by side with an output diff and timing. Typechecker errors appear inline as squiggles.

### Report
A clean, printable page: headline speedup, table of functions with status/speedup/replays, fidelity summary, LLM rewrites shown as diffs, export buttons.

---

## 4. Demo setup (must be bulletproof)

1. **Demo project** at `demo/textlab/` — a realistic, pure-Python mini "ML/data" project (~400–600 lines, several modules, a `main.py` with `--small` flag finishing in ~10–20 s under CPython). Design it so the analysis has a mix of outcomes:
   - **Verified big wins** (compute-heavy, small I/O): e.g. `edit_distance(a: str, b: str) -> int` used for fuzzy dedup, an n-body or particle simulation step, a sieve / prime feature, a hand-written k-means inner loop, a BPE-style pair counter.
   - **Fixable** (LLM needed): same kind of function but unannotated, or using a list comprehension / `enumerate` / other construct outside PySub that has a straightforward PySub rewrite.
   - **Not eligible** with clear reasons: something using `numpy`, a closure, dynamic typing, file I/O.
   - **One boundary-cost case** where compilation is possible but the ranker correctly declines because marshalling would dominate — this shows the tool is smart, not just aggressive.
   Push the same project to a public GitHub repo (or prepare it for us to push) so the "Clone repository" path can be demoed; also support a local bare-repo fallback for offline demos.
2. **Offline demo mode:** a toggle (and env var) that replays cached LLM responses and pre-built `.so` files for the demo project, so the demo works with no internet and no API key. Record the cache by running the demo once online.
3. **`DEMO.md`:** a 3-minute script with exact clicks — open demo → start trace run in presenter mode → narrate as the stepper advances stage by stage → open the journey of the LLM-fixed function and walk its timeline (rejected → rewrite → PySub → AST → PIR → C++ → replay → speedup) → diff view with fidelity gutter → show the declined boundary-cost function and where its journey stopped → Benchmarks tab with end-to-end speedup → export. Also a 30-second version, and a viva section that drills into Tokens → AST → Typed AST → PIR for `edit_distance`.
4. **`scripts/smoke.sh`:** the one end-to-end check from §0.3.

---

## 5. How to run this build (use subagents)

**Phase 0 — you, alone (don't parallelise this):**
Read the whole repo. Then write `studio/CONTRACTS.md`: the job event schema, REST endpoints and payload shapes, the function-record data model (id, file, name, span, status, reason, score breakdown, original/pysub/cpp sources, fidelity notes, replay results, speedup), the library-mode CLI contract, and the folder layout. Every agent builds against this file. Keep it short and exact.

**Phase 1 — parallel subagents** (use separate git worktrees so they don't collide):
- **Agent A — Compiler library mode + pybind11 bridge** (§2.1). Must keep `tools/oracle.py` green.
- **Agent B — Analyzer** (§2.2: ingest, scan, trace, auto-annotate, rank, LLM fixer, replay, benchmark, splice, export). Can stub compilation via the contract until A lands.
- **Agent C — API server** (§2.3) wired to B, with mock events for the UI to develop against.
- **Agent D — Frontend** (§3). Builds against C's mock event stream first. Owns all visual polish.
- **Agent E — Demo** (§4: demo project, offline cache plumbing, DEMO.md, smoke script).

**Phase 2 — you:** merge worktrees, integrate end to end on the demo project, run `tools/oracle.py` and `scripts/smoke.sh`, fix integration bugs.

**Phase 3 — polish pass:** open the app, walk DEMO.md yourself click by click, and fix anything that looks unfinished: empty states, error states, loading states, alignment, overflow, contrast, copy. Then record the offline demo cache.

---

## 6. Definition of done

- `./studio.sh` on a fresh Linux/macOS/WSL machine with Python 3.12 and a C++ compiler brings the app up.
- All four entry points work: snippet, dropped file, local folder path, GitHub URL.
- On `demo/textlab`, the app finds hotspots, LLM-fixes at least one function, verifies at least 3 by oracle replay, declines at least one with a clear reason, shows per-function and end-to-end speedups, and exports a working accelerated project.
- Diff view, three-way view, fidelity gutter, agent feed, benchmarks and report all render with real data.
- The pipeline stepper, every stage inspector, and the per-function journey (including the compiler phases) show real artifacts; presenter mode plays a full run end to end and saved runs can be replayed.
- Offline demo mode runs the whole DEMO.md flow with no network.
- Existing `python3 -m pythia.cli` and `python3 tools/oracle.py` behave exactly as before.
- No sprawling test suites. One smoke script, the existing oracle, done.

When finished, give a short summary: what was built, how to launch it, what's stubbed or rough, and any limits we should mention to our evaluator.