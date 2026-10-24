#!/usr/bin/env python3
"""Writes ../LIVE_DEMO.md and evidence/demo_extra.json from evidence/studio_jobs.json (so the numbers cannot drift)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
jobs = {j["label"]: j for j in json.load(open(HERE / "evidence/studio_jobs.json"))}
e14, e10, e30, tl = (jobs[k] for k in ("project-euler (problem 14)", "project-euler (problem 10)", "project-euler (problem 30)", "textlab"))


def fn(j, name):
    return next(f for f in j["functions"] if f["id"].endswith("::" + name))


c = fn(e14, "collatz_sequence_len")
p14 = fn(e14, "problem_014")
s14, s10 = e14["e2e"], e10["e2e"]
iszero = fn(e10, "is_prime")
T = tl["e2e"]
BS = "\\"
md = f"""# PYTHIA live demo, Review 3

Everything below was run on 2026-10-24 on the team laptop (see report Table 5.1), zero-LLM path (no API key). Times are from that run; expect
the same shape, not the same digits.

## Picks

| | Project | Pinned commit | Entry command (type it in the *Entry command* box) | What it shows |
|---|---|---|---|---|
| **Main** | `dayyass/project-euler` (7 stars, no licence declared, about 1,300 lines, 28 files) <https://github.com/dayyass/project-euler> | `ad501f8` | `python solutions/problem_014.py` | one hot function found and compiled ({c['speedup']:.1f}x, {c['replay']['matched']}/{c['replay']['total']} replays match), the caller `problem_014` **declined** ({p14['probe_speedup']:.2f}x), whole program {s14['before_s']:.1f} s to {s14['after_s']:.1f} s ({s14['speedup']:.1f}x), output identical |
| Backup 1 | same repository | `ad501f8` | `python solutions/problem_010.py` | `is_prime` compiled ({iszero['speedup']:.1f}x), whole program {s10['before_s']:.1f} s to {s10['after_s']:.1f} s ({s10['speedup']:.1f}x), output identical |
| Backup 2 | **TextLab**, the demo bundled with the app (not a third-party repo) | in the repository | `python main.py --small` | many functions; see numbers below |

**Honest note on the hunt.** About twenty small public repositories were cloned and screened; five went through the real pipeline. Most small repos are class-based
(methods are not compiled in v1), use generators, read module-level mutable state, or need numpy, pygame or `input()`. `dayyass/project-euler` was the best small,
unknown, pure-Python project that ran end to end with identical output, but its main demo compiles **one** function and it has **no licence file**, so it is a weaker showpiece
than the bundled demos. A repository with several verified functions and a permissive licence was not found in the time available. Two other candidates produced nothing
worth compiling (`landsgevaer/euler.py`: generators and a global prime cache; `AshrithSagar/projecteuler`: its one hot function was correctly rejected by replay).
The GitHub-URL ingest path was **not** exercised on this repository; the demo used the local folder. Try "Clone repository" with the URL once before the review.

## Exact clicks (main demo, 2 to 3 minutes)

1. Start **PYTHIA Studio**. On the welcome screen choose **Open folder** and browse to `docs{BS}review3{BS}demo{BS}repos{BS}project-euler` (a local copy pinned to `ad501f8`), or **Clone repository** with the URL.
2. In **Entry command** type `python solutions/problem_014.py`, then press **Analyse** (Ctrl+Enter). Say: *"Ordinary Python, nobody annotated it. PYTHIA runs it once under a tracer."*
3. Watch the stepper. At **Trace** point at the call count (about 1,000,000). At **Rank**: *"It ranks by measured time, not by guesses."* Scan finds {e14['summary']['functions']} functions.
4. When it finishes, click **collatz_sequence_len** in the Hotspots list. Header: **Guarded, {c['speedup']:.1f}x, {c['replay']['matched']}/{c['replay']['total']} replays match**. In **Diff** show the one decorator line added and the original body untouched.
5. Click **Journey**: original, observed types, PySub, tokens, AST, typed AST, PIR, generated C++, build, replay, benchmark.
6. Click **problem_014** (the caller, 98% of time): chip **Declined {p14['probe_speedup']:.2f}x**. Say: *"It compiled this one too, measured it slower because copying the arguments costs more than it saves, so it never splices it. It is careful, not reckless."*
7. Point at the right panel: **End to end {s14['speedup']:.1f}x, {s14['before_s']:.1f} s to {s14['after_s']:.1f} s, output identical**. Say: *"The original folder is untouched; this is a working copy."*
8. Optional: open **Fidelity** in the bottom panel (7 positioned notes for this function: which are exact, which guarded, such as integer overflow), then the **Report** page.

## 60-second version

Open the saved run (below), click `collatz_sequence_len`, show **Diff** (one decorator line), then the end-to-end card: **{s14['speedup']:.1f}x, output identical**; then `problem_014` **Declined {p14['probe_speedup']:.2f}x**.
Say: *"We found the slow function, compiled it, checked it on 500 real calls, and refused to compile the caller because it would be slower."*

## Backup plan (in this order)

1. **Replay a saved run (no network, no compile).** `python docs{BS}review3{BS}demo{BS}install_saved_runs.py` copies three finished runs into the app's data folder. Start the app, then open
   `http://127.0.0.1:8765/?job={e14['job_id']}&replay=1` (main), `?job={e10['job_id']}&replay=1` (backup 1) or `?job={tl['job_id']}&replay=1` (TextLab), or click the project under *Recent*.
   The welcome screen's **Replay sample run** button plays the bundled sample the same way. (Checked on a fresh data folder: the saved runs load and serve their events.)
2. **Run the local folder** instead of the URL (step 1 above). First build takes about {e14['seconds']:.0f} s cold; faster when the build cache is warm.
3. **Switch to TextLab** (`python main.py --small`, about {tl['seconds']:.0f} s cold, or its saved run).

## Pre-demo checklist

- [ ] Laptop charged and plugged in; Windows updates paused.
- [ ] PYTHIA Studio installed from `PYTHIA-Studio-Setup-1.1.0.exe`, or the checkout starts with `python -m pythia_studio`. **Rebuild the installer** first: this session fixed `runtime/pyrt_bridge.hpp` (print inside compiled code) and `pythia/studio/_replay_worker.py` (sibling imports), and the installer in `dist/` was built on 19 Oct without them.
- [ ] No stale server: nothing listening on port 8765 (`Get-NetTCPConnection -LocalPort 8765`), and nothing in WSL (`ps aux | grep pythia_studio`).
- [ ] `python docs{BS}review3{BS}demo{BS}install_saved_runs.py` run once.
- [ ] A full dry run done this morning: main demo end to end, once cold and once warm.
- [ ] Wi-Fi-off test: the local-folder path and the replay both work offline.
- [ ] Window at least 1440x900, light theme (sun/moon button), notifications off.
- [ ] No `GROQ_API_KEY` in the environment unless you want to show the optional LLM; the numbers here are the no-LLM path.

## Expected numbers

| Run | Functions | Accelerated | Declined | Not eligible | Whole program | Output |
|---|---|---|---|---|---|---|
| project-euler, problem 14 | {e14['summary']['functions']} | 1 ({c['speedup']:.1f}x) | {e14['summary']['declined']} | {e14['summary']['not_eligible']} | {s14['before_s']:.1f} s to {s14['after_s']:.1f} s ({s14['speedup']:.1f}x) | identical |
| project-euler, problem 10 | {e10['summary']['functions']} | 1 ({iszero['speedup']:.1f}x) | {e10['summary']['declined']} | {e10['summary']['not_eligible']} | {s10['before_s']:.1f} s to {s10['after_s']:.1f} s ({s10['speedup']:.1f}x) | identical |
| TextLab | {tl['summary']['functions']} | {tl['summary']['verified'] + tl['summary']['guarded']} | {tl['summary']['declined']} | {tl['summary']['not_eligible']} | {T['before_s']:.1f} s to {T['after_s']:.1f} s ({T['speedup']:.1f}x) | {'identical' if T['output_match'] else 'DIFFERENT, see NOTES.md'} |

Commit pin: `dayyass/project-euler` `ad501f8`; a local copy is in `docs/review3/demo/repos/project-euler` (`.git` removed). The e2e figure for problem 10 is larger than its single
function's speedup because the end-to-end run uses much larger arguments than the replayed sample; we report it as measured.
"""
(HERE.parent / "LIVE_DEMO.md").write_text(md, encoding="utf-8")
FIG = HERE / "figures"
tab = "".join(f"<tr><td>{a}</td><td>{b}</td></tr>" for a, b in [
    ("Main", f"<b>dayyass/project-euler</b> @ <code>ad501f8</code>, command <code>python solutions/problem_014.py</code>. <code>collatz_sequence_len</code> {c['speedup']:.1f}x ({c['replay']['matched']}/{c['replay']['total']} replays), caller declined {p14['probe_speedup']:.2f}x, whole program {s14['before_s']:.1f} s to {s14['after_s']:.1f} s ({s14['speedup']:.1f}x), output identical."),
    ("Backup 1", f"Same repo, <code>python solutions/problem_010.py</code>: <code>is_prime</code> {iszero['speedup']:.1f}x, whole program {s10['speedup']:.1f}x."),
    ("Backup 2", f"TextLab (bundled): <code>python main.py --small</code>, {tl['summary']['verified'] + tl['summary']['guarded']} functions accelerated."),
])
steps = "".join(f"<li>{s}</li>" for s in [
    "Open folder (or clone the URL), type the entry command, press Analyse.",
    "Watch the stepper; at Trace say “about a million calls”; at Rank say “measured, not guessed”.",
    f"Click <code>collatz_sequence_len</code>: Guarded, {c['speedup']:.1f}x, {c['replay']['matched']}/{c['replay']['total']} replays match. Diff: one decorator line.",
    "Journey tab: walk the stages (Section 2).",
    f"Click <code>problem_014</code>: Declined {p14['probe_speedup']:.2f}x. “Careful, not reckless.”",
    f"End-to-end card: {s14['speedup']:.1f}x, output identical; original folder untouched."])
demo_html = f"""<table class="open"><tr><th style="width:16%">Pick</th><th>Detail</th></tr>{tab}</table>
<h2>Clicks, about 2 to 3 minutes</h2><ol class="steps">{steps}</ol>
<h2>If something fails</h2><ol class="steps"><li><b>Replay a saved run</b> (no network): run <code>docs{BS}review3{BS}demo{BS}install_saved_runs.py</code>, open <code>/?job={e14['job_id']}&amp;replay=1</code>.</li><li><b>Local folder</b> instead of the URL.</li><li><b>TextLab</b> (<code>python main.py --small</code>) or its saved run.</li></ol>
<h2>Before you go on stage</h2><ul class="checklist"><li>Laptop charged and plugged in</li><li>Installer rebuilt after this session’s runtime fixes (the one in <code>dist/</code> is from 19 Oct)</li><li>No stale server on port 8765 (also check WSL)</li><li>Saved runs installed; dry run done this morning, cold and warm</li><li>Wi-Fi-off test passed; light theme; window at least 1440x900</li></ul>
<div class="warn"><span class="tag">Be honest</span>The main demo compiles <b>one</b> function and the repo has no licence file. If asked “why this repo”: it was the best small, unknown, pure-Python project that went through the real pipeline with identical output; most small repos use classes, generators or global state, which v1 declines with a stated reason.</div>
<div class="fig shot"><img src="{FIG.as_uri()}/shots/diff.png"><div class="cap"><b>Figure 10.1.</b> The diff for the main demo: one decorator added, original body untouched.</div></div>"""
extra = {"demo_html": demo_html,
         "numbers_row": f'<tr><td class="big">{s14["speedup"]:.1f}x</td><td>whole-program speedup on the demo repository (<code>dayyass/project-euler</code>, problem 14), output identical</td></tr>',
         "abstract_studio": f"Through the full Studio pipeline on a small public repository (dayyass/project-euler), a hot function ran {c['speedup']:.1f}x faster, verified on {c['replay']['matched']} of {c['replay']['total']} recorded calls, and the whole program went from {s14['before_s']:.1f} s to {s14['after_s']:.1f} s with identical output.",
         "conclusion_studio": f"On a third-party repository the system found the hot function, compiled it ({c['speedup']:.1f}x), declined its caller on a measured {p14['probe_speedup']:.2f}x, and sped the program up {s14['speedup']:.1f}x with identical output; on other candidates it found nothing worth compiling and said why, which is the intended behaviour.",
         "latency_text": f"A cold Studio run took {e14['seconds']:.0f} s on the demo repository and {tl['seconds']:.0f} s on TextLab.",
         "stress_text": "The stress harness (`scripts/stress.py`) was **not re-run in this session**. The figures in `STATUS.md` (for example 17 of 17 files on one repository and 58 to 67% on three others, with zero converter crashes) were measured earlier on repositories the team had tuned on and are not reproduced here, so we make no stress-test claim. The independent evidence from this session is the demo-repository screening in `LIVE_DEMO.md`: about twenty small public repositories were cloned, five went through the full pipeline, and every function that was spliced matched CPython.",
         "stress_short": "not run this session (cut)"}
(HERE / "evidence/demo_extra.json").write_text(json.dumps(extra, indent=1), encoding="utf-8")
print("ok")
