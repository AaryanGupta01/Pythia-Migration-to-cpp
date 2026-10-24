"""Report content, part 3: sections 10-14."""
from fig_common import FIG


def sec10(d, F):
    d.h1("Results and evaluation")
    d.h2("10.1 Correctness")
    d.table(["Gate", "Result", "What it demonstrates"], F["correct_rows"], "correct",
            "Correctness results, all produced in this session (Appendix F gives commands and dates).",
            widths=[4.6, 3.8, 8.2], size=8.4)
    d.p(F["correct_text"], align="justify")
    d.h2("10.2 Compiler performance on a fixed set of kernels")
    d.p(f"To avoid cherry-picking, ten kernels were fixed before measuring (`docs/review3/src/kernels/`): integer loops, a "
        "sieve, dense matrix multiply, recursion, dynamic programming on strings and arrays, floating-point iteration, "
        "sorting, and a string-keyed dictionary count. Each was compiled with the oracle's flags, run "
        f"{F['bench_runs']} times under CPython and as a native binary, and the **median whole-process wall time** is reported "
        f"(CPython start-up is {F['bench_startup']} ms of every Python figure; the native binaries start in about a millisecond). "
        "Outputs were byte-identical in every run. [[tab:bench]] gives the numbers and [[fig:bench]] plots them.", align="justify")
    d.table(["Kernel", "CPython (ms)", "PYTHIA (ms)", "Speedup", "Without guard elision (ms)", "Elision gain", "Guards elided / kept"],
            F["bench_rows"], "bench", "Kernel benchmark. Medians of the runs shown above; min and max are in `evidence/bench_kernels.json`.",
            widths=[3.0, 2.0, 2.0, 1.8, 3.0, 1.8, 3.0], size=8.4, align=["l", "r", "r", "r", "r", "r", "r"])
    d.figure(FIG / "chart_bench.png", "Speedup of the PYTHIA binary over CPython per kernel (left, log scale) and the effect of interval-based guard elision (right).", "bench", 16.4)
    d.p(F["bench_text"], align="justify")
    d.h2("10.3 Semantic Fidelity Report statistics")
    d.p(f"Across the {F['n_pos']} positive programs the compiler emitted {F['fid_total']} positioned notes, a median of "
        f"{F['fid_median']} per program. {F['fid_exact_pct']}% are *exact* (the runtime reproduces CPython's rule), "
        f"{F['fid_guarded_pct']}% *guarded* (identical unless a documented condition occurs, for example an integer beyond int64) and "
        f"{F['fid_divergent_pct']}% *divergent*; the divergent ones are all D6 (`int ** negative int` changes the result type), which the "
        "compiler reports and refuses at run time. [[fig:fid]] shows the distribution by class. D1 (integer width) and D5 "
        "(negative indexing and bounds) dominate because every integer operation and every subscript is a site.", align="justify")
    d.figure(FIG / "chart_fidelity.png", "Fidelity notes over the positive corpus, by divergence class (left) and severity (right).", "fid", 15.6)
    d.h2("10.4 Studio on whole projects")
    d.p(F["studio_text"], align="justify")
    d.table(["Project", "Funcs found", "Verified / guarded", "Declined", "Not eligible", "Geomean fn speedup", "End-to-end"],
            F["studio_rows"], "studio", "Studio runs, zero-LLM path, build cache cold unless noted.",
            widths=[3.6, 1.8, 2.4, 1.8, 2.0, 2.6, 2.4], size=8.4, align=["l", "r", "r", "r", "r", "r", "r"])
    d.figure(FIG / "chart_studio.png", "Per-function speedups from the Studio runs (replay-verified, log scale).", "studio", 16.0)
    d.h2("10.5 Stress test on public repositories")
    d.p(F["stress_results_text"], align="justify")
    d.h2("10.6 Interpretation and threats to validity")
    d.bullets(F["interp_bullets"])


def sec11(d, F):
    d.h1("Error handling, limitations and known issues")
    d.h2("11.1 Error handling")
    d.p("Compile-time problems are reported as `line:col: Kind: message` with the source line and a caret, from the lexer, "
        "parser and type checker; one run reports several syntax errors thanks to panic-mode recovery. At run time the "
        "emitted program wraps `main` in a handler that prints Python's exception name and message "
        "(`IndexError: list index out of range`, `ZeroDivisionError`, `OverflowError`, `RecursionError`) so that the "
        "oracle can compare exception classes; message text follows the minor version of the CPython that runs the "
        "comparison, because 3.11 to 3.14 word some errors differently. In Studio, every stage failure is a typed event "
        "that fails one function (never the job), and an exception inside compiled code reaches Python as the matching "
        "Python exception or as `FallbackError`, which the shim catches to run the original body.", align="justify")
    d.h2("11.2 Limitations with measured impact")
    d.table(["Limitation", "What happens", "Observed impact", "Remedy (future work)"], F["limit_rows"], "limits",
            "Limitations, their observed effect and the way forward.",
            widths=[2.7, 4.5, 5.0, 4.4], size=8.0)
    d.h2("11.3 Unsupported constructs today")
    d.p("The Studio scanner rejects, with a plain-English reason, any function that is `async` or uses `await`; is decorated; "
        "takes `*args` or `**kwargs`; defines a nested function; is a generator (`yield`); uses `global` or `nonlocal`, "
        "`with`, `match`, an import inside the function, the `@` operator, bytes or complex literals, or an integer "
        "literal beyond 64 bits; calls dynamic built-ins (`type`, `getattr`, `setattr`, `eval`, `exec`, `open`, `input` and "
        "similar); or reaches a module it cannot compile (third-party packages, `os`, `sys` I/O, `json`, `random`, `re`, "
        "threads). The Playground's converter is more permissive about lambdas and some closures, but verification applies "
        "there too. This list is taken from `scan.analyze()` (line 940) and `explain.py`.", align="justify")
    d.h2("11.4 Known issues")
    d.bullets(F["known_issues"])


def sec12(d, F):
    d.h1("Member-wise contribution")
    d.p("**How to read this section.** The repository's first commit (`84f1251`, 4 September 2026) already holds the Review 2 "
        "code base as a single commit by the repository owner, so git cannot attribute the Review 1 and 2 modules to individuals. "
        "Their ownership below follows the Review 1 responsibility matrix and the team's contribution log "
        "(`CONTRIBUTIONS.md`). What git *can* show is recorded as evidence: `git shortlog` gives "
        f"{F['git']['shortlog_text']}. Three pull requests from teammates' forks are the only non-owner work in history. "
        "The Studio work (17 to 19 October 2026) was committed by the owner, using AI coding assistants "
        "(Section 14); its ownership split below is **proposed** and must be agreed by the team.", align="justify")
    d.table(["Member", "Technical ownership (Reviews 1 and 2)", "Evidence", "Integration and testing"], F["member_rows"], "members",
            "Member-wise contribution.", widths=[2.6, 5.3, 4.9, 3.8], size=8.0)
    d.table(["Member", "Proposed ownership of the Studio work (to be agreed)"], F["studio_split_rows"], "studio_split",
            "PROPOSED ownership split for the Review 3 Studio work, aligned with each member's compiler phase. Not evidenced by git; the team must confirm it.",
            widths=[3.2, 13.4], size=8.4)


def sec13(d, F):
    d.h1("Conclusion and future work")
    d.p(F["conclusion"], align="justify")
    d.h2("13.1 What we learned")
    d.bullets([
        "A compiler's *front end* is the easy half of a transpiler. The hard half is the contract with the host language: what happens at the boundary, on overflow, on a type that changes, and how to *show* that the output is right.",
        "Reporting beats hiding. Making every divergence a positioned note turned an unanswerable question (\"is it faithful?\") into a list the team could shrink, and it caught a regression in this very session (Section 9.4).",
        "A measurement harness is part of the product. The ranker's constants, the 1.1x threshold and the cold-code cut-off exist because a function that compiles is not the same as a function worth compiling.",
        "Parallel work on shared dispatch chains needs one integrator and a green oracle; the hook-order merge conflicts recorded in `STATUS.md` are the cost of skipping either.",
    ])
    d.h2("13.2 Future work")
    d.bullets([
        "**Bignum promotion** on overflow instead of `OverflowError`, and UTF-8-aware strings with code-point indexing, to remove the two largest semantic gaps (D1, D13).",
        "**Boundary cost.** Zero-copy buffers (the buffer protocol for lists of ints and floats), keeping data on the C++ side across calls, and fusing neighbouring hot functions into one compiled unit.",
        "**Specialisation.** Compile one version per observed type signature, or `std::variant` unions, so that functions that see both int and float are converted instead of refused.",
        "**Reclamation for standalone binaries** (regions or reference counting), so D7 can be closed outside library mode.",
        "**Verification depth.** Property-based fuzzing of each converted function around the recorded inputs, translation validation per pass, and a machine-checked proof of one pass in the style of CompCert.",
        "**Ecosystem.** NumPy subset mapped to Eigen or xtensor, calls from compiled code back into CPython for library calls, a VS Code extension and a CI mode that fails a build when a converted function stops matching.",
        "**Retargeting.** The IR is language-agnostic past the front end, so a second front end (or the WebAssembly back end dropped from this cycle) is an addition, not a rewrite.",
    ])
    d.h2("13.3 Publication potential")
    d.p("The Semantic Fidelity Report, a positioned, machine-generated account of where a translation could differ, treated as a "
        "first-class output of a source-to-source compiler and paired with replay verification on recorded production calls, is the "
        "part we believe is publishable. To make it a paper rather than a project the team would need a larger, independent "
        "corpus than ours, a comparison against Cython, mypyc and Codon on the same programs, and a proper study of the "
        "false-accept rate of replay verification (for example by mutation testing the compiler).", align="justify")


def sec14(d, F):
    d.h1("References")
    refs = F["references"]
    d.numbered(refs["books"])
    d.p("**Official documentation consulted for the comparison (accessed October 2026).**", after=2)
    d.numbered(refs["docs"], start=len(refs["books"]) + 1)
    d.p("**Reused open-source components.**", after=2)
    d.numbered(refs["oss"], start=len(refs["books"]) + len(refs["docs"]) + 1)
    d.p("**AI coding assistants.** " + F["ai_ack"], align="justify")
