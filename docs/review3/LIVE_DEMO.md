# PYTHIA live demo, Review 3

Everything below was run on 2026-10-24 on the team laptop (see report Table 5.1), zero-LLM path (no API key). Times are from that run; expect
the same shape, not the same digits.

## Picks

| | Project | Pinned commit | Entry command (type it in the *Entry command* box) | What it shows |
|---|---|---|---|---|
| **Main** | `dayyass/project-euler` (7 stars, no licence declared, about 1,300 lines, 28 files) <https://github.com/dayyass/project-euler> | `ad501f8` | `python solutions/problem_014.py` | one hot function found and compiled (21.3x, 500/500 replays match), the caller `problem_014` **declined** (0.81x), whole program 8.9 s to 0.8 s (11.6x), output identical |
| Backup 1 | same repository | `ad501f8` | `python solutions/problem_010.py` | `is_prime` compiled (1.8x), whole program 7.1 s to 1.3 s (5.4x), output identical |
| Backup 2 | **TextLab**, the demo bundled with the app (not a third-party repo) | in the repository | `python main.py --small` | many functions; see numbers below |

**Honest note on the hunt.** About twenty small public repositories were cloned and screened; five went through the real pipeline. Most small repos are class-based
(methods are not compiled in v1), use generators, read module-level mutable state, or need numpy, pygame or `input()`. `dayyass/project-euler` was the best small,
unknown, pure-Python project that ran end to end with identical output, but its main demo compiles **one** function and it has **no licence file**, so it is a weaker showpiece
than the bundled demos. A repository with several verified functions and a permissive licence was not found in the time available. Two other candidates produced nothing
worth compiling (`landsgevaer/euler.py`: generators and a global prime cache; `AshrithSagar/projecteuler`: its one hot function was correctly rejected by replay).
The GitHub-URL ingest path was **not** exercised on this repository; the demo used the local folder. Try "Clone repository" with the URL once before the review.

## Exact clicks (main demo, 2 to 3 minutes)

1. Start **PYTHIA Studio**. On the welcome screen choose **Open folder** and browse to `docs\review3\demo\repos\project-euler` (a local copy pinned to `ad501f8`), or **Clone repository** with the URL.
2. In **Entry command** type `python solutions/problem_014.py`, then press **Analyse** (Ctrl+Enter). Say: *"Ordinary Python, nobody annotated it. PYTHIA runs it once under a tracer."*
3. Watch the stepper. At **Trace** point at the call count (about 1,000,000). At **Rank**: *"It ranks by measured time, not by guesses."* Scan finds 102 functions.
4. When it finishes, click **collatz_sequence_len** in the Hotspots list. Header: **Guarded, 21.3x, 500/500 replays match**. In **Diff** show the one decorator line added and the original body untouched.
5. Click **Journey**: original, observed types, PySub, tokens, AST, typed AST, PIR, generated C++, build, replay, benchmark.
6. Click **problem_014** (the caller, 98% of time): chip **Declined 0.81x**. Say: *"It compiled this one too, measured it slower because copying the arguments costs more than it saves, so it never splices it. It is careful, not reckless."*
7. Point at the right panel: **End to end 11.6x, 8.9 s to 0.8 s, output identical**. Say: *"The original folder is untouched; this is a working copy."*
8. Optional: open **Fidelity** in the bottom panel (7 positioned notes for this function: which are exact, which guarded, such as integer overflow), then the **Report** page.

## 60-second version

Open the saved run (below), click `collatz_sequence_len`, show **Diff** (one decorator line), then the end-to-end card: **11.6x, output identical**; then `problem_014` **Declined 0.81x**.
Say: *"We found the slow function, compiled it, checked it on 500 real calls, and refused to compile the caller because it would be slower."*

## Backup plan (in this order)

1. **Replay a saved run (no network, no compile).** `python docs\review3\demo\install_saved_runs.py` copies three finished runs into the app's data folder. Start the app, then open
   `http://127.0.0.1:8765/?job=c45cc4b3&replay=1` (main), `?job=1eab5ef0&replay=1` (backup 1) or `?job=429050d0&replay=1` (TextLab), or click the project under *Recent*.
   The welcome screen's **Replay sample run** button plays the bundled sample the same way. (Checked on a fresh data folder: the saved runs load and serve their events.)
2. **Run the local folder** instead of the URL (step 1 above). First build takes about 51 s cold; faster when the build cache is warm.
3. **Switch to TextLab** (`python main.py --small`, about 232 s cold, or its saved run).

## Pre-demo checklist

- [ ] Laptop charged and plugged in; Windows updates paused.
- [ ] PYTHIA Studio installed from `PYTHIA-Studio-Setup-1.1.0.exe`, or the checkout starts with `python -m pythia_studio`. **Rebuild the installer** first: this session fixed `runtime/pyrt_bridge.hpp` (print inside compiled code) and `pythia/studio/_replay_worker.py` (sibling imports), and the installer in `dist/` was built on 19 Oct without them.
- [ ] No stale server: nothing listening on port 8765 (`Get-NetTCPConnection -LocalPort 8765`), and nothing in WSL (`ps aux | grep pythia_studio`).
- [ ] `python docs\review3\demo\install_saved_runs.py` run once.
- [ ] A full dry run done this morning: main demo end to end, once cold and once warm.
- [ ] Wi-Fi-off test: the local-folder path and the replay both work offline.
- [ ] Window at least 1440x900, light theme (sun/moon button), notifications off.
- [ ] No `GROQ_API_KEY` in the environment unless you want to show the optional LLM; the numbers here are the no-LLM path.

## Expected numbers

| Run | Functions | Accelerated | Declined | Not eligible | Whole program | Output |
|---|---|---|---|---|---|---|
| project-euler, problem 14 | 102 | 1 (21.3x) | 21 | 64 | 8.9 s to 0.8 s (11.6x) | identical |
| project-euler, problem 10 | 102 | 1 (1.8x) | 21 | 64 | 7.1 s to 1.3 s (5.4x) | identical |
| TextLab | 35 | 9 | 2 | 22 | 17.2 s to 6.5 s (2.6x) | identical |

Commit pin: `dayyass/project-euler` `ad501f8`; a local copy is in `docs/review3/demo/repos/project-euler` (`.git` removed). The e2e figure for problem 10 is larger than its single
function's speedup because the end-to-end run uses much larger arguments than the replayed sample; we report it as measured.
