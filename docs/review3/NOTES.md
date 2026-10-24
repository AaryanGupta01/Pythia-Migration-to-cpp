# Review 3 documentation: judgment calls and open decisions

Written while producing `PYTHIA_Final_Report.docx/.pdf`, `PYTHIA_Viva_Guide.pdf` and `LIVE_DEMO.md`. Sources and logs are in `src/`
(`src/evidence/` holds the raw command output behind every number).

## Judgment calls

1. **Review 1/2 ownership.** The repository's first commit (`84f1251`, 4 Sept 2026) already contains the Review 2 code base as one commit by the
   repository owner, so git cannot attribute Review 1/2 modules. I used the Review 1 responsibility matrix, `CONTRIBUTIONS.md` and the `Owner:`
   headers in the files, and said so in the report (Section 12) and viva guide (Section 4). The three teammate pull requests (`086b6f8`, `079bcb5`,
   `4ef0102`) are the only non-owner evidence. The dictionary pull request's commits are authored by `Copilot`; I wrote that down rather than hide it.
2. **Studio ownership is a proposal.** All Studio work (17 to 19 Oct) is committed by the owner. The proposed split follows each person's compiler phase and
   is marked "proposed, agree before the viva" everywhere.
3. **Snippets are 21/22, not 22/22.** `check_snippets.py` fails `coin_change` because commit `210a599` made the converter refuse an int-or-float function.
   I bisected it, re-ran the old conversion (it printed `3.0 -1.0` instead of `3 -1`) and kept the refusal. I did not change compiler code.
4. **Grammar.** `docs/grammar.ebnf` has 33 named rules, not the 41 "productions" quoted in Review 1, and covers only the v0.1 core. Reported as "partly met".
5. **Oracle speed column.** The oracle's own speedup column is one run of a whole process; the report uses a separate ten-kernel benchmark
   (`src/bench_kernels.py`, medians) for performance claims, and shows both.
6. **LLM wording.** The default path is LLM-free; an optional LLM fixer still exists and is off without a key (`pipeline.fix_one`, `llm.make_client`). The report
   says "no language model" for the type inference and does not claim the product contains no LLM code. Zero-LLM measurements were taken on a server started with
   empty `GROQ_API_KEY`/`ANTHROPIC_API_KEY` (the repo `.env` contains a key; I never printed it).
7. **Competitor matrix.** Cells follow each tool's official documentation fetched this session (sources in Section 14). "Readable output" is the team's own
   assessment and is marked as such; where a doc did not settle a cell it is "not assessed".
8. **Installer.** Sizes come from `dist/` (built 19 Oct). I did not rebuild or re-run the installer in this session, and the report says so.
9. **CI.** I did not run GitHub Actions (no `gh` CLI); the report says the three CI jobs exist and that the equivalent checks were run locally.
10. **Stale text found, not fixed:** the D8 note still describes `setjmp`/`longjmp`; the D7 note still calls reclamation "the Review 3 target"; `STATUS.md` quotes oracle 72/72 and
    88/88 and median 8.6x, while this session measured 78/78, 88/88 and 15.2x (single-run timing).

## Findings made while measuring (all in the report)

11. **Dictionary kernel is ~29x slower compiled** (`k10_wordcount`): the eight specialised dict types do a linear scan per lookup (`runtime/pyrt.cpp:131`, `DICT_IMPL`). Reported, not fixed.
12. **Guard elision shows no consistent measured gain** (ratios 0.85x to 1.17x on ten kernels, 5 runs). Reported as "benefit not demonstrated".
13. **Two small general fixes made** (outside `docs/review3`, in a separate commit): (a) `runtime/pyrt_bridge.hpp` routes C++ `print` inside compiled functions to Python's `sys.stdout`
    (before: output reordered and LF instead of CRLF when piped, so TextLab's end-to-end output hash differed; after: identical; new check `scripts/check_print.py`);
    (b) `pythia/studio/_replay_worker.py` puts a script's own folder on `sys.path` so `from utils import f` works during replay (before: a replay failed with NameError on `dayyass/project-euler`).
    Gates after the fixes: oracle 78/78 and 88/88, snippets 21/22, library check OK, print check OK. `check_basics.py` was run before the fixes (91/91) and not re-run after them.
14. **Stress harness not re-run**; the report makes no stress-test claim. **GitHub-URL ingest was not tried** on the demo repo (local folder used).
15. **Demo repo is weak**: `dayyass/project-euler` (7 stars, no licence file) has one compiled function in the main demo. No better small repo was found in the time available.
16. **Report length**: body (abstract to references) is about 26 pages, one over the 25-page limit if the source listings are counted; trim Section 7 or the tables if the faculty counts strictly.
17. **Competitor matrix**: pages for Shed Skin, Nuitka, PyPy, LPython, mypyc, Numba and Pythran were fetched; Cython and Codon were not (Codon from a search snippet), lower confidence.

## Decisions the team must make

- **Studio ownership split** (report Section 12 proposed table, viva guide Section 4).
- **AI-assistant acknowledgement wording** (report Section 14, last paragraph; viva Q&A "Did you use AI to build this?"). Current wording is factual:
  Claude (Opus 5.5, Sonnet 5.5) and GitHub Copilot as co-authors on 99 of 143 commits.
- **Which demo to run** (see `LIVE_DEMO.md`) and whether to run it from the installed app or from the repository.
- **Whether to rebuild and re-test the installer before the review.**
