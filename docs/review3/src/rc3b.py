"""Report content, compact version of sections 10-13 (replaces rc3.sec10-13)."""
from fig_common import FIG


def sec10(d, F):
    d.h1("Results and evaluation")
    d.h2("10.1 Correctness")
    d.table(["Gate", "Result", "What it shows"], F["correct_rows"], "correct", "Correctness results from this session (Appendix F has commands and dates).",
            widths=[4.4, 3.2, 9.4], size=8.4)
    d.p(F["correct_text"], align="justify")
    d.h2("10.2 Performance on ten fixed kernels")
    d.p(f"Ten kernels were fixed before measuring (`docs/review3/src/kernels/`): integer loops, sieve, matrix multiply, recursion, dynamic programming, floating-point iteration, sorting and a dictionary count. "
        f"Each ran {F['bench_runs']} times under CPython and as a native binary; the table gives the **median whole-process time** (CPython start-up is {F['bench_startup']} ms of every Python figure). "
        "Outputs were byte-identical in every run.", align="justify")
    d.table(["Kernel", "CPython (ms)", "PYTHIA (ms)", "Speedup", "No guard elision (ms)", "Elision ratio", "Elided / kept"],
            F["bench_rows"], "bench", "Kernel benchmark (medians; min and max are in `evidence/bench_kernels.json`).",
            widths=[3.0, 2.0, 2.0, 1.8, 3.0, 1.8, 2.4], size=8.4, align=["l", "r", "r", "r", "r", "r", "r"])
    d.figure(FIG / "chart_bench.png", "Speedup per kernel (left, log scale) and the effect of guard elision (right).", "bench", 15.6)
    for part in F["bench_text"].split("**Guard elision.**"):
        d.p(part if part is F["bench_text"].split("**Guard elision.**")[0] else "**Guard elision.** " + part.strip(), align="justify")
    d.h2("10.3 Semantic Fidelity Report statistics")
    d.p(f"Over the {F['n_pos']} positive programs the compiler emitted {F['fid_total']} positioned notes (median {F['fid_median']} per program): {F['fid_exact_pct']}% exact, {F['fid_guarded_pct']}% guarded, "
        f"{F['fid_divergent_pct']}% divergent. The divergent ones are all D6 (`int ** negative int` changes the type), which is reported at compile time and refused at run time. "
        "D1 (integer width) and D5 (indexing and bounds) dominate because every integer operation and subscript is a site ([[fig:fid]]).", align="justify")
    d.figure(FIG / "chart_fidelity.png", "Fidelity notes by divergence class (left) and severity (right).", "fid", 14.6)
    d.h2("10.4 Studio on whole projects")
    d.p(F["studio_intro"], align="justify")
    d.bullets(F["studio_parts"], size=9.5)
    d.table(["Project", "Funcs found", "Verified / guarded", "Declined", "Not eligible", "Geomean fn speedup", "End-to-end"],
            F["studio_rows"], "studio", "Studio runs, zero-LLM path, build cache cold.",
            widths=[4.0, 1.7, 2.3, 1.7, 1.9, 2.5, 2.9], size=8.2, align=["l", "r", "r", "r", "r", "r", "r"])
    d.figure(FIG / "chart_studio.png", "Per-function speedups from the Studio runs (replay-verified, log scale).", "studio", 14.6)
    d.h2("10.5 Reading the results")
    d.bullets([
        "**Where the speedup comes from:** unboxed int64 and double, contiguous monomorphic lists, no interpreter dispatch. The dictionary kernel shows what a slow runtime structure does to that.",
        "**Amdahl applies:** per-function gains exceed whole-program gains because the rest keeps running in Python.",
        "**The boundary can erase the gain:** the ranker declines such functions, and the replay's measured number is the final judge.",
        f"**Threats to validity:** one laptop ({F['env']['cpu']}) and one toolchain family; whole-process timing; verification covers only replayed calls; most test programs were written by the team and its AI assistants, so they may share our blind spots.",
    ])


def sec11(d, F):
    d.h1("Error handling, limitations and known issues")
    d.p("Compile-time problems print `line:col: Kind: message` with the source line and a caret; panic-mode recovery lets one run report several syntax errors. "
        "Compiled programs print Python's exception name and message (`IndexError`, `ZeroDivisionError`, `OverflowError`, `RecursionError`) so the oracle can compare them. "
        "In Studio a stage failure fails one function, never the job, and a compiled-code exception reaches Python as the matching exception or as `FallbackError`, which makes the shim run the original body.", align="justify")
    d.h2("11.1 Limitations with measured impact")
    d.table(["Limitation", "What happens", "Observed impact", "Remedy"], F["limit_rows"], "limits", "Limitations, their observed effect and the way forward.",
            widths=[2.7, 4.2, 5.7, 4.4], size=7.9)
    d.h2("11.2 Known issues")
    d.bullets(F["known_issues"])


def sec12(d, F):
    d.h1("Member-wise contribution")
    d.p("The first commit (`84f1251`, 4 Sept 2026) already holds the Review 2 code base as one commit, so git cannot attribute Review 1 and 2 modules to people; "
        "ownership follows the Review 1 responsibility matrix and the `Owner:` headers in the files. "
        f"What git does show: {F['git']['shortlog_text']}. Three pull requests from teammates' forks are the only non-owner work. "
        "The Studio work (17 to 19 Oct) was committed by the owner with AI coding assistants (Section 14); its split below is **proposed** and must be agreed by the team.", align="justify")
    d.table(["Member", "Ownership (Reviews 1 and 2)", "Evidence", "Integration and testing"], F["member_rows"], "members", "Member-wise contribution.", widths=[2.6, 4.8, 6.0, 3.6], size=7.9)
    d.table(["Member", "Proposed ownership of the Studio work (to be agreed)"], F["studio_split_rows"], "studio_split",
            "PROPOSED split of the Studio work by compiler phase; not evidenced by git.", widths=[3.2, 13.8], size=8.2)


def sec13(d, F):
    d.h1("Conclusion and future work")
    d.p(F["conclusion"], align="justify")
    d.h2("13.1 What we learned")
    d.bullets([
        "A transpiler's front end is the easy half; the hard half is the contract with the host language: the boundary, overflow, changing types, and showing the output is right.",
        "Reporting beats hiding: making every divergence a positioned note turned an unanswerable question into a list, and caught a regression in this very session.",
        "A measurement harness is part of the product: the ranker, the 1.1x threshold and the cold cut-off exist because a function that compiles is not always worth compiling. Measuring also exposed our slow dictionaries and the unproven guard elision.",
    ])
    d.h2("13.2 Future work")
    d.bullets([
        "**Hash-indexed dictionaries** (fixes the 29x slowdown), **bignum promotion** on overflow and **UTF-8 strings** to remove D1 and D13.",
        "**Boundary cost:** zero-copy buffers, data kept on the C++ side, fusing neighbouring hot functions.",
        "**Specialisation:** one compiled version per observed type signature, so int-or-float functions convert instead of being refused.",
        "**Verification depth:** fuzzing around recorded inputs, per-pass translation validation, a machine-checked proof of one pass.",
        "**Ecosystem:** call CPython from compiled code, a NumPy subset on Eigen, a VS Code extension, a CI mode that fails when a converted function stops matching, and the dropped WebAssembly back end.",
    ])
    d.p("**Publication potential.** The Semantic Fidelity Report, a positioned account of where a translation could differ, treated as a first-class output of a source-to-source compiler and paired with "
        "replay on recorded calls, is the publishable part. It would need a larger independent corpus, a comparison with Cython, mypyc and Codon on the same programs, and a study of replay's false-accept rate (for example by mutation testing).", align="justify")
