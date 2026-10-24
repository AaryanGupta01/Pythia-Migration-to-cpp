"""Report content, part 4: appendices."""
from fig_common import FIG


def appendices(d, F):
    # ---------------------------------------------------------------- A
    d.appendix("A", "User manual")
    d.p("A condensed version of `USER_GUIDE.md`. Screens are in Appendix H.", after=3)
    d.numbered([
        "**Install.** Run `PYTHIA-Studio-Setup-1.1.0.exe` (per-user, no administrator rights). Start **PYTHIA Studio** from the Start menu. Python, the C++ compiler and the web UI are inside the installer.",
        "**First start.** A three-step setup checks the computer (Python, compiler, headers, data folder), offers an optional AI key (skip it: the in-house path needs none), and then offers *Replay sample run*, *Open the demo project* or the *Playground*.",
        "**Bring code in.** *Open folder*, *Clone repository* (a public GitHub URL), drop a `.py` file, or use the Playground. Give an **entry command** such as `python main.py` so PYTHIA can trace the program, rank functions by measured time and record real calls.",
        "**Watch the pipeline.** The stepper runs *Ingest, Scan, Trace, Rank, Fix, Compile, Verify, Benchmark, Splice, Export*. Click any stage for its raw output; the agent panel narrates each step.",
        "**Review.** Each function has a status chip (*Verified, Guarded, Fixable, Declined, Failed, Not eligible*). Open one for the **Diff** (original against accelerated file), the **three-way view** (Python, PySub, C++ with the fidelity gutter) or the **Journey** (sixteen steps from original source to splice).",
        "**Accept and export.** Accept or reject per function (or accept all verified ones), then **Export** a folder or zip: your project with `_pythia_accel/`, `PYTHIA_REPORT.md` and `build_accel.sh`. Your original folder is never modified.",
        "**Playground.** Type or paste a program; the C++ appears as you type. *Convert* turns plain Python into PySub with the in-house converter, and *Run* executes the original under CPython and the converted program compiled to C++ on the same input, reporting whether the output is identical.",
        "**Command line.** `python -m pythia.cli prog.py --run` (compile and run), `--fidelity` (divergence report), `--emit-only` (print C++), `--mode leetcode` (a solution class without `main`), `--lib f,g` (build an importable module).",
    ])
    # ---------------------------------------------------------------- B
    d.appendix("B", "Installation guide")
    d.table(["You have", "Do this"], [
        ["Windows 10 or 11", "Run `PYTHIA-Studio-Setup-1.1.0.exe` from `dist/` (or the GitHub release); or unzip `PYTHIA-Studio-1.1.0-portable.zip` and run the launcher. Nothing else to install."],
        ["Linux, macOS, WSL", "`./studio.sh` from a checkout, or the one-line installer `scripts/install.sh`, then `pythia-studio --app`. Needs Python 3.10 or newer, a C++17 compiler and `pip install pybind11`."],
        ["Docker", "`docker build -t pythia-studio .` and `docker run --rm -p 127.0.0.1:8765:8765 -v pythia-data:/data pythia-studio`"],
        ["Developers", "`python -m pythia_studio --no-open --port 8797` (set `PYTHIA_HOME` to isolate state). UI development: `cd studio/web && npm install && npm run build` (the built `dist/` is committed)."],
        ["Build the installer", "`python packaging/windows/build.py` downloads the pinned CPython, WinLibs GCC and Inno Setup, assembles the tree and writes `dist/PYTHIA-Studio-Setup-1.1.0.exe`."],
    ], "install", "Installation paths.", widths=[3.2, 13.4], size=8.6, first_col_bold=True)
    d.p("**Troubleshooting.** `pythia-studio --doctor` prints each check with its fix. If errors look impossible, check for a stale "
        "server: the doctor reports a build fingerprint and the launcher refuses a server with a different one; on this team's "
        "machines the usual culprit was an old server left running inside WSL and answering on the same port.", align="justify")
    # ---------------------------------------------------------------- C
    d.appendix("C", "Sample runs")
    d.p(F["sample_runs_intro"], align="justify")
    for title, cols, rows, key, cap, widths in F["sample_tables"]:
        d.h3(title)
        d.table(cols, rows, key, cap, widths=widths, size=8.0)
    # ---------------------------------------------------------------- D
    d.appendix("D", "Complete test table")
    d.p(f"All {F['n_pos']} positive and {F['n_neg']} negative oracle programs from the run logged in Appendix F. Time columns are single-run, whole-process "
        "times and include process start-up.", align="justify")
    d.table(["Positive program", "CPython", "PYTHIA", "Ratio", "Result"], F["pos_table"], "postable",
            "Positive corpus (`tests/positive`).", widths=[6.2, 2.4, 2.4, 2.2, 2.2], size=7.6, align=["l", "r", "r", "r", "c"])
    d.table(["Negative program", "Expected text", "Result"], F["neg_table"], "negtable",
            "Negative corpus (`tests/negative`): the compiler must reject each with a diagnostic containing the expected text.",
            widths=[6.6, 7.2, 2.8], size=7.6)
    # ---------------------------------------------------------------- E
    d.appendix("E", "Grammar specification and API specification")
    d.p("**Grammar.** `docs/grammar.ebnf` is reproduced as committed. It specifies the PySub v0.1 core; Section 11.4 explains how "
        "the implemented language extends it.", align="justify")
    d.code(F["grammar_text"], size=7.4)
    d.p("**Server API** (`pythia/studio/server/app.py`). All routes are served on 127.0.0.1 and reject foreign `Host` headers.", after=3)
    d.table(["Method and path", "Purpose"], F["api_rows"], "api", "REST and WebSocket interface of the Studio server.",
            widths=[6.4, 10.2], size=8.0)
    # ---------------------------------------------------------------- F
    d.appendix("F", "Evidence register")
    d.p("Every number in the report is traceable to a row here. Commands were run from the repository root at commit "
        f"`{F['git']['head']}` on the machine described in Table [[tab:env]]; raw logs are in `docs/review3/src/evidence/`.", align="justify")
    d.table(["#", "Claim", "Command", "Result", "Date"], F["evidence_rows"], "evidence", "Evidence register.",
            widths=[0.7, 4.5, 5.0, 4.9, 1.8], size=7.4)
    d.p("**Claims in the earlier draft that were corrected or removed.**", after=3)
    d.table(["Draft claim", "Finding", "Action"], F["draft_fix_rows"], "draftfix", "Corrections to the teammate's draft.",
            widths=[5.0, 8.4, 3.2], size=7.8)
    # ---------------------------------------------------------------- G
    d.appendix("G", "Contribution log")
    d.p("From `git log` and `git shortlog` at the commit above. Merge commits are listed where they are the only evidence.", after=3)
    d.table(["Date", "Commit", "Author", "What", "Member (by Review 1 matrix)"], F["contrib_rows"], "contrib",
            "Commits by teammates and the main milestones.", widths=[1.9, 1.5, 2.6, 7.4, 3.2], size=7.6)
    # ---------------------------------------------------------------- H
    d.appendix("H", "User-interface screenshots and additional diagrams")
    for path, cap, key, width in F["screens"]:
        d.figure(path, cap, key, width)
