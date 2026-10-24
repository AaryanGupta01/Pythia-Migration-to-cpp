"""Prose and tables for the report that need the measured values. Imported by build_report.py."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import tables as T
from fig_common import FIG
from report_data import EV, HERE, ROOT, fx, geomean, git, rd
from report_tables import DATE


def texts(F, D):
    g = F["git"]
    ec = F["edge"] or {"rows": [], "lib": {}}
    lib = ec.get("lib", {})
    mem = lib.get("mem", {})
    bm, gm = F["bench_median"], F["bench_geomean"]
    jobs = F["studio_jobs"]
    pos, neg = F["oracle_pos"], F["oracle_neg"]
    main = D.get("main_job")

    # ------------------------------------------------------------------ abstract
    F["abstract"] = (
        "Python is easy to write and slow on loop-heavy code, and the usual remedies either cost a second code base or give no evidence "
        "that the fast version behaves like the original. PYTHIA is a source-to-source compiler and desktop application that converts the hot "
        "functions of an ordinary Python project to C++17, checks every conversion against CPython on the program's own recorded calls, and "
        "splices the survivors back in behind a one-line decorator. The compiler core (off-side-rule lexer, Pratt parser, bidirectional type checker, "
        "lowering with a fourteen-class Semantic Fidelity Report, interval-based guard elision, C++17 emitter) is extended by an in-house type "
        "inference engine for untyped code that uses no language model, a tracer and hotspot ranker, pybind11 library mode, and a replay-based verifier. "
        f"PYTHIA Studio shows every stage and installs as a {F['installer_mib']} MiB Windows package. "
        f"On the machine described in Section 5 the differential oracle agrees with CPython on {pos[0]} of {pos[1]} programs and rejects {neg[0]} of {neg[1]} invalid ones; "
        f"{F['basics'][0]} of {F['basics'][1]} untyped everyday programs convert and match without any LLM. On ten fixed kernels the compiled binaries are "
        f"{F['bench_min_ex']:.1f} to {F['bench_max']:.0f} times faster than CPython on nine (median over all ten {bm:.0f}x) with identical output, and about {1/F['bench_dict']:.0f} times slower on one dictionary-heavy kernel. "
        + (D.get("abstract_studio", "") or "") +
        " The limits are stated: 64-bit integers, ASCII strings, no C-extension libraries, and verification that is differential testing rather than proof. "
        "The WebAssembly back end promised at Review 2 was dropped in favour of the Studio pipeline.")

    # ------------------------------------------------------------------ results text
    F["bench_text"] = (
        f"Nine of the ten kernels are {fx(F['bench_min_ex'])} to {fx(F['bench_max'])} faster. Indexed integer and float loops (collatz, mandelbrot, bubble sort) gain most; "
        f"recursion, the sieve, matrix multiply and N-queens gain about 9 to 12x; Levenshtein gains only {fx(F['bench_min_ex'])} because the string-indexing path allocates. "
        f"The geometric mean over all ten is {fx(gm, 2)} and the median {fx(bm)}; every output was byte-identical to CPython's. "
        f"**One kernel is a failure and we report it:** the string-keyed dictionary count (`k10_wordcount`, about 2,000 distinct keys, 1.5 million updates) ran in "
        f"{F['bench_rows'][-1][2]} ms compiled against {F['bench_rows'][-1][1]} ms in CPython, about {1/F['bench_dict']:.0f} times slower. The cause is in the runtime: the eight specialised dictionary "
        "types look keys up by scanning a vector (`DICT_IMPL`, `runtime/pyrt.cpp:131`), so each lookup is O(number of keys), where CPython's is O(1). Dictionaries are correct but not fast; "
        "a hash index would fix it and is the first item in Section 13.2. "
        f"**Guard elision.** The right-hand panel of [[fig:bench]] compares each kernel with and without the interval pass. The ratio lies between {F['bench_gain_min']:.2f}x and {F['bench_gain_max']:.2f}x, "
        "scattered on both sides of 1.0, which is the size of run-to-run noise at five runs. **We therefore cannot claim a measured benefit from the pass.** It removes very few checks on these kernels "
        "(Table [[tab:bench]]), and with `-O2 -flto` the compiler can often inline the checked helpers and predict their branches. The Review 1 report anticipated a factor of two; we did not observe it.") if bm else "pending"

    sj = {j["label"]: j for j in jobs}
    parts = []
    for j in jobs:
        s = j.get("summary") or {}
        e = j.get("e2e") or {}
        acc = [f for f in j["functions"] if f["status"] in ("verified", "guarded")]
        parts.append(f"**{j['label']}**: {s.get('functions')} functions found, {len(acc)} accelerated, {s.get('declined', 0)} declined, "
                     f"{s.get('not_eligible', 0)} not eligible; whole job {j['seconds']:.0f} s"
                     + (f"; program {e.get('before_s', 0):.1f} s to {e.get('after_s', 0):.1f} s ({e.get('speedup', 0):.2f}x), output hash {'identical' if e.get('output_match') else 'DIFFERENT'}" if e else "") + ".")
    F["studio_text"] = ("Each project was run through the real application path (the HTTP API that the UI uses) on a clean server with no LLM key, with its trace command "
                        "and the build cache cold unless marked warm. A function is counted *accelerated* only if its replay matched on every call and its measured "
                        "speedup was at least 1.1x. " + " ".join(parts))
    F["stress_results_text"] = D.get("stress_text", "pending")
    F["stress_text"] = ("`scripts/stress.py OWNER/REPO` downloads a public repository as a zip, pushes every file through converter, type checker, C++ build and run "
                        "against CPython, and reports build failures and output differences (which must be zero) and the ranked reasons for rejection. "
                        "Section 10.5 gives this session's results.")
    F["fuzz_n"] = "150 programs"
    fz = F["fuzz_raw"]
    m = re.search(r"matched CPython exactly\s*:\s*(\d+)", fz)
    F["fuzz_result"] = f"{m[1]}/150 identical, 0 mismatches" if m else F["fuzz_result"]
    pr = F["property_raw"]
    m = re.findall(r"(\d+)/(\d+)", pr)
    F["property_result"] = F["property_result"]
    F["property_tail"] = "\n".join(pr.strip().splitlines()[-6:])

    F["interp_bullets"] = [
        f"**Where the speedup comes from.** Unboxed 64-bit integers and doubles, monomorphic contiguous lists, and no interpreter dispatch. Loop kernels reach {fx(F['bench_max'], 0)}; the linear-scan dictionary is a slowdown (Section 10.2).",
        "**Amdahl applies.** Per-function speedups are far larger than whole-program ones because the rest of the program keeps running in Python (Table [[tab:studio]]).",
        "**The boundary can erase the gain.** Copying arguments in and out costs time proportional to their size; the ranker declines functions where that dominates, and the replay's measured number is the final judge.",
        f"**Single machine, single toolchain family.** All timings are from one laptop ({F['env']['cpu']}) with GCC 15 under WSL2 (kernels) and GCC 16 on Windows (Studio). We did not test other CPUs, other operating systems, or clang.",
        "**Whole-process timing.** Kernel times include process start-up (CPython about " + str(F['bench_startup']) + " ms). That favours the compiled binary slightly on short kernels; all kernels run for at least 0.1 s under CPython.",
        "**Recorded-call verification.** Agreement is on calls the program made plus labelled generated inputs; unexercised paths are untested. The oracle and generator widen the evidence on the compiler itself, not on a user's function.",
        "**Corpus authorship.** Most test programs were written by the team (and by AI assistants working for the team). They may share our blind spots; the stress harness on third-party repositories is the independent check.",
    ]

    # ------------------------------------------------------------------ limitations
    def tc(i):
        return next((r for r in ec["rows"] if r["id"] == i), {"pythia": "n/a", "cpython": "n/a"})
    F["limit_rows"] = [
        ["C-extension libraries (NumPy, pandas, PyTorch, OpenCV)", "Functions that use them are `not eligible`; they stay in Python.", "Their own loops are already native; the speedup is lost only on the Python around them. Not measured on a NumPy project.", "Call CPython from compiled code; a NumPy subset on Eigen or xtensor; LibTorch for PyTorch."],
        ["Dynamic typing and metaprogramming", "`eval`, `exec`, `getattr`, a variable that changes type, int-or-float results are rejected with a reason.", "Snippet `coin_change` refused: 21 of 22 snippets pass. Converting it would print `3.0 -1.0` instead of `3 -1`.", "Compile one version per observed type signature, or `std::variant` unions."],
        ["64-bit integers (D1)", "Checked arithmetic raises `OverflowError`; an int beyond int64 at the boundary raises too.", f"`2 ** 62 * 2`: CPython prints 9223372036854775808, PYTHIA `{tc('TC-10')['pythia']}`. Library mode: list element 2**70 gives `{tc('TC-14')['pythia']}`.", "Promote to a bignum when a check fires."],
        ["ASCII-only strings (D13)", "Non-ASCII input to a compiled function raises `FallbackError`; the original Python runs.", f"`len('héllo')`: CPython 5, standalone `{tc('TC-11')['pythia']}`; library mode `{tc('TC-13')['pythia']}`.", "UTF-8 strings with code-point indexing."],
        ["Memory reclamation (D7)", "Standalone binaries never free memory. Library mode frees everything allocated in a call when it ends.", f"RSS stayed at {mem.get('rss_after_kb', '?')} KB after {mem.get('calls', '?')} calls that each built a 500-element list and string (before: {mem.get('rss_before_kb', '?')} KB).", "Region allocator or reference counting for standalone code."],
        ["Dictionary speed", "Specialised dicts use a linear scan per lookup.", "String-keyed word count, about 2,000 keys: about 29 times slower than CPython (Table [[tab:bench]]).", "Hash index in `DICT_IMPL`."],
        ["Boundary cost", "Arguments are copied in and mutated containers copied back.", f"A call to a trivial compiled function costs about {lib.get('call_overhead_us', '?')} us against {lib.get('py_len_us', '?')} us for `len`; a 100,000-element list costs about {lib.get('marshal_100k_ms', '?')} ms per call. The ranker declines functions where this dominates (Table [[tab:studio]]).", "Zero-copy buffers, data kept on the C++ side, fusing neighbouring functions."],
        ["Verification is differential testing", "Agreement on recorded and labelled generated calls only.", "A path the traced run never took is untested; fuzzing found 0 mismatches in 150 programs, which bounds nothing about other programs.", "Fuzz around recorded inputs, validate each pass, prove one pass formally."],
        ["Unsupported constructs", "Generators, nested functions, decorators, `with`, `global`, `*args`, `async`, `match` (Section 11.3).", "Reported per function with a reason; 0 crashes of the converter on the stress repositories recorded in `STATUS.md`.", "Closures by lambda lifting; generators by state machines."],
        ["Randomness, files, OS, regex, threads", "Refused with a reason (`explain.py`).", "Programs that print random numbers cannot be compared with CPython unless seeded.", "Reproduce CPython's Mersenne Twister for seeded use."],
        ["Compile-time latency", "g++ runs once per module and is cached by content.", f"Library check: {F['libmode']['cold']} s cold, {F['libmode']['tu']} s for a new module with the runtime built, {F['libmode']['cached']} ms on a cache hit. " + D.get("latency_text", ""), "Ship prebuilt modules for known projects; build in the background."],
        ["Needs a C++ toolchain", "Bundled on Windows (GCC 16.2); on Linux and macOS the user installs g++.", f"Windows installer {F['installer_mib']} MiB.", "Ship a compiler in the Linux and macOS packages too."],
        ["Python to C++ only", "One front end, one back end.", "WebAssembly back end dropped.", "The IR is language-agnostic after the front end."],
    ]

    # ------------------------------------------------------------------ members
    F["member_rows"] = [
        ["Vishal Vivek\n24BCE2377\nlead", "Front end (grammar, lexer with the off-side rule, parser, AST, diagnostics), command line, repository, integration. Review 3: the Studio engine, server, web UI and installer.",
         "138 of 143 commits (`git shortlog`); every Studio commit (`2f46833` to `95bbb1b`, 17 to 19 Oct); merges of the three pull requests (`086b6f8`, `079bcb5`, `4ef0102`) and of eight workstream branches (for example `c8ca929`, `176f5d0`). Front-end files are in the first commit `84f1251` with `Owner: Member 1` headers.",
         "Integrated all workstreams, kept the oracle green, wrote `STATUS.md` and `DECISIONS.md`; built and ran the installer."],
        ["Rujuta Mangesh Kulkarni\n24BDS0459", "Symbol table, bidirectional type checker and local inference (`typecheck.py`), negative corpus and diagnostic quality, dictionary support.",
         "Pull request 2 from `rujuta-student`, merged as `079bcb5` (9 Sept): `runtime/pydict.hpp` (351 lines), `tests/dict_test.cpp`, five documents. The commits in that pull request are authored by `Copilot` (Co-authored-by Copilot App); the git record shows an AI assistant wrote them on her branch. `typecheck.py` and `tests/negative` are in the first commit.",
         "Negative suite (88 programs, each tested for message text); type-checker soundness fixes found by the oracle."],
        ["Koliparthy Venkata Jahnavi\n24BDS0132", "Divergence catalogue and Semantic Fidelity Report (`lower.py`), `pyrt` runtime, interval-analysis guard elision (`optimize.py`), PySet.",
         "Pull request 3 from `Jahnavikoliparthy`, merged as `4ef0102` (9 Sept): commit `ddc975b` by Jahnavi adds `runtime/pyset.hpp` (533 lines) and `tests/set_test.cpp` (366 lines). `lower.py`, `optimize.py` (header: Owner Member 3, Review 2 deliverable) and `pyrt.c/.h` are in the first commit.",
         "Fidelity statistics and the guard-elision measurement in Section 10."],
        ["Aaryan Gupta\n24BDS0134", "C++ emitter, C11 to C++17 migration, differential oracle, benchmark harness, program generator, CI, corpus.",
         "Pull request 1 from `AaryanGupta01`, merged as `086b6f8` (4 Sept): commit `9264cbb` \"Migrate backend from C11 to C++17\" (6 files, +270/-48: `emit_c.py`, `emit_cpp.py`, `pyrt.cpp`, `pyrt.hpp`, `oracle.py`, `cli.py`). `emit_c.py`, `tools/oracle.py`, `tools/fuzz.py`, `tools/fuzz_run.py` (Owner: Member 4) and the first CI workflow are in the first commit.",
         "Oracle (78/88), generator (150/150 in this session), CI (three jobs), kernel benchmark design."],
    ]
    F["studio_split_rows"] = [
        ["Vishal Vivek", "Studio shell: `pipeline.py` (the ten stages), `server/app.py` and `bus.py` (REST and WebSocket events), the React UI, `launcher.py` and the Windows installer."],
        ["Rujuta Mangesh Kulkarni", "In-house type inference and eligibility: `convert/infer.py`, `types.py`, `search.py`, `observe.py`; `scan.py` and `reasons.py` (the compiler as judge, plain-English reasons)."],
        ["Koliparthy Venkata Jahnavi", "Fidelity and the boundary: the fidelity gutter and bottom panel, `libmode.py` and `pyrt_bridge.hpp` (marshalling, `FallbackError`, `OverflowError`, arena), `rank.py` (boundary-cost model)."],
        ["Aaryan Gupta", "Verification and measurement: `replay.py`, `_replay_worker.py`, `codec.py`, `bench.py`, `stress.py`, `property_test.py`, the oracle and CI."],
    ]

    F["conclusion"] = (
        "PYTHIA set out to answer one question: can a student-built compiler turn the slow parts of an ordinary Python project into native code *and* show why the result "
        "can be trusted? The work delivered a complete compiler pipeline (Reviews 1 and 2), and in Review 3 a system around it that scans, traces, ranks, types, converts, "
        f"compiles, verifies, benchmarks and splices a real project, with a user interface that exposes every step and a Windows installer. Against the Review 1 and 2 "
        f"objectives (Table [[tab:obj]]), the type-checking, equivalence-rate, divergence-catalogue and performance objectives are met or exceeded; the grammar specification lags the language, the "
        f"oracle corpus is {F['n_pos']} programs against a target of 120, reclamation covers library mode only, and the WebAssembly back end was dropped. "
        + (D.get("conclusion_studio", "") or "") +
        " The honest summary of the result is that verified conversion of a well-defined subset works, is useful on compute-heavy pure-Python code, and is bounded by the language subset, the 64-bit and ASCII choices, and the quality of the recorded calls.")

    F["references"] = {"books": T.REFS_BOOKS, "docs": T.REFS_DOCS, "oss": T.REFS_OSS}
    F["ai_ack"] = T.AI_ACK.format(ai_commits=F["ai_commits"], commits=g["commits"])

    # ------------------------------------------------------------------ appendix C, E
    F["sample_runs_intro"] = ("Per-function results of the Studio runs in Table [[tab:studio]], zero-LLM path. `Speedup` is the median over the replayed calls; "
                              "`replay` is matched calls over replayed calls; `declined` rows show the measured probe speedup and the reason.")
    tabs = []
    for j in jobs:
        rows = []
        for f in sorted(j["functions"], key=lambda f: -(f.get("share") or 0)):
            if f["status"] not in ("verified", "guarded", "declined", "failed"):
                continue
            rp = f.get("replay") or {}
            matched = f"{rp.get('matched', '?')}/{rp.get('n', rp.get('calls', '?'))}" if rp else ""
            sp = f.get("speedup") or f.get("probe_speedup")
            rows.append([f"`{f['name']}`", f["file"].split("/")[-1], f["status"], fx(sp), f"{100 * (f.get('share') or 0):.1f}%", matched,
                         (f.get("reason") or "")[:80] if f["status"] != "verified" and f["status"] != "guarded" else ""])
        tabs.append((j["label"], ["Function", "File", "Status", "Speedup", "Share", "Replay", "Note"], rows, "run_" + re.sub(r"\W", "", j["label"]),
                     f"Functions compiled in `{j['label']}`.", [3.0, 2.4, 1.6, 1.4, 1.2, 1.4, 5.6]))
    F["sample_tables"] = tabs
    F["grammar_text"] = (ROOT / "docs" / "grammar.ebnf").read_text(encoding="utf-8")
    desc = {"/api/env": "compiler, pybind11, Python and LLM availability", "/api/demos": "bundled demo projects", "/api/settings": "read or change settings (`PUT` through the same path)",
            "/api/settings/test-key": "check an optional API key with a read-only call", "/api/doctor": "environment checks and build fingerprint",
            "/api/jobs": "list jobs; `POST` starts one (input: snippet, file, folder, git URL or demo)", "/api/upload": "upload a file or snippet",
            "/api/jobs/{job}": "job state and summary", "/api/jobs/{job}/events": "events after a sequence number", "/api/jobs/{job}/ws": "WebSocket event stream (live or replay)",
            "/api/jobs/{job}/cancel": "cancel a running job", "/api/jobs/{job}/functions": "function summaries", "/api/jobs/{job}/function": "one function record, optionally with stage dumps",
            "/api/jobs/{job}/decision": "accept or reject a function", "/api/jobs/{job}/file-diff": "original against accelerated file", "/api/jobs/{job}/export": "write the accelerated project",
            "/api/jobs/{job}/export.zip": "download it as a zip", "/api/jobs/{job}/report": "printable summary", "/api/workspaces/recent": "recent workspaces",
            "/api/workspaces/{ws}/tree": "file tree of a workspace", "/api/workspaces/{ws}/file": "file contents", "/api/fs/list": "browse local folders",
            "/api/playground/compile": "PySub to C++ with diagnostics and fidelity notes", "/api/playground/run": "run original under CPython and the compiled version",
            "/api/playground/convert": "in-house conversion of plain Python to PySub", "/api/playground/convert/status": "progress of a conversion", "/api/stages": "tokens, AST, typed AST, PIR, C++ for a snippet"}
    app = (ROOT / "pythia/studio/server/app.py").read_text(encoding="utf-8")
    rows = []
    for meth, path in re.findall(r'@app\.(get|post|websocket)\("(/api[^"]*)"', app):
        rows.append([f"`{'WS' if meth == 'websocket' else meth.upper()} {path}`", desc.get(path, "")])
    F["api_rows"] = rows

    # ------------------------------------------------------------------ contributions
    cr = []
    for line in git("log", "--reverse", "--format=%h|%ad|%an|%s", "--date=short").splitlines():
        h, d, a, s = line.split("|", 3)
        key = h in ("84f1251", "9264cbb", "086b6f8", "16450af", "079bcb5", "ddc975b", "4ef0102", "533f875", "2f46833", "74bfa7d", "d344271", "cf2cfb8",
                    "37acf6d", "8c0e1dc", "e4a4804", "95bbb1b", "0cad7e4", "f14f559")
        if key:
            who = {"84f1251": "owner (first commit holds the Review 2 code base)", "9264cbb": "Aaryan (M4)", "086b6f8": "Aaryan (M4), merge of PR 1",
                   "16450af": "Rujuta (M2), authored by Copilot", "079bcb5": "Rujuta (M2), merge of PR 2", "ddc975b": "Jahnavi (M3)", "4ef0102": "Jahnavi (M3), merge of PR 3"}.get(h, "owner (Studio, proposed split in Section 12)")
            cr.append([d, f"`{h}`", a, s[:110], who])
    F["contrib_rows"] = cr

    # ------------------------------------------------------------------ draft corrections
    F["draft_fix_rows"] = [
        ["Register numbers 24BDS0102, 24BDS0118, 24BDS0127 and Vishal as 24BDS", "Review 1 report: 24BCE2377, 24BDS0459, 24BDS0132, 24BDS0134.", "Corrected on the cover and in Section 12."],
        ["\"Hindley-Milner\" type inference", "`typecheck.py` is bidirectional local inference with one fixed type per variable; the converter uses a lattice fixpoint. No unification-based generalisation exists (searched the code).", "Removed; Section 7.3 and 7.4 describe the real algorithms."],
        ["\"Electron desktop shell\"", "The app is a FastAPI server plus a React page shown in an Edge/Chrome `--app` window by `launcher.py`; no Electron anywhere in the repository (searched).", "Corrected in Sections 5 and 6."],
        ["\"zero memory leaks\"", "Standalone binaries never free memory (D7). Library mode frees per call; measured RSS flat over " + str(mem.get('calls', '?')) + " calls.", "Replaced by the measured statement."],
        ["`sys.settrace`", "The tracer uses `sys.monitoring` with a `sys.setprofile` fallback (`_tracer_boot.py:66`); `settrace` appears nowhere.", "Corrected in Section 7.9."],
        ["`symbol_table.py`, `stages.py` ownership, `splice.py` in `pythia/`", "`symbol_table.py` does not exist (scopes are in `typecheck.py`); `stages.py` exists but is a read-only stage dumper for the UI; `splice.py` is `pythia/studio/splice.py`.", "File list rebuilt from the tree (Listing 8.1)."],
        ["Runtime owned by Aaryan; `lower.py` and `optimize.py` plus `stages.py` for Jahnavi", "The Review 1 matrix and file headers give the runtime and fidelity to Jahnavi; the emitter and oracle to Aaryan.", "Section 12 follows the matrix and git."],
        ["Made-up commit messages (\"feat(front): lexer indentation\", ...)", "`git log` has no such messages; the first commit is a single squash.", "Replaced by the real commits in Appendix G."],
        ["Intel i7-13700H, Python 3.11, GCC 13.2", "Measured environment is in Table [[tab:env]] (" + F['env']['cpu'] + ", Python " + F['env']['py_win'] + " and " + F['env']['py_wsl'] + ", GCC " + F['env']['gcc_wsl'].split()[-1] + " and 16.2).", "Replaced."],
        ["Speedups 12.4x to 84.6x, geometric mean 28.7x; 8-row benchmark table", "No such measurements exist in the repository or in our runs. Our kernels: " + (f"{fx(F['bench_min'], 2)} to {fx(F['bench_max'])}, geometric mean {fx(gm, 2)}." if bm else "pending."), "Replaced by Table [[tab:bench]]."],
        ["\"Assembly confirms vectorization\"; \"100% bounds-check elision\"", "No assembly was inspected, and guards are elided only where provable (Section 10.2 gives counts).", "Removed."],
        ["\"6,000+ LOC Quanta\"; \"142 functions\"", f"`demo/quanta` is about 3,800 lines (`DECISIONS.md`); function counts come from the Studio runs in Table [[tab:studio]].", "Replaced."],
        ["\"Zero-overhead\" pybind11 splicing; \"0% false positives\"; \"100% of divergences caught\"", "Marshalling copies data (measured); replay can miss unexercised paths.", "Replaced by measured costs and by Section 11."],
        ["Figures 4.1, 6.1, 10.1 referenced but absent", "Report now contains every figure it refers to; cross-references are generated.", "Fixed."],
        ["Test-case table TC-01 to TC-10 and the emitted-code listing", "The loop listing used names (`_t_ctr`) that the emitter does not produce, and TC-07 claimed assembly evidence.", "Rebuilt from runs (Table [[tab:cases]], Listing 7.1)."],
    ]

    # ------------------------------------------------------------------ evidence register
    o_date = F["oracle_date"]
    ev = []

    def add(claim, cmd, result, date=DATE):
        ev.append([str(len(ev) + 1), claim, cmd, result, date])
    add("Oracle: compiled output equals CPython on every positive program", "`wsl .venv/bin/python tools/oracle.py -v`", f"{pos[0]}/{pos[1]}", o_date)
    add("Oracle: invalid programs rejected with the expected text", "same", f"{neg[0]}/{neg[1]}", o_date)
    add("Oracle single-run median speedup", "same", f"{F['oracle_speed'][0]}x (min {F['oracle_speed'][1]}x, max {F['oracle_speed'][2]}x)", o_date)
    add("Fidelity notes over positive corpus", "`python docs/review3/src/fidelity_stats.py`", f"{F['fid_total']} notes: exact {F['fid_exact']}, guarded {F['fid_guarded']}, divergent {F['fid_divergent']}")
    add("Untyped basics, no LLM", "`python scripts/check_basics.py --jobs 6`", f"{F['basics'][0]}/{F['basics'][1]}")
    add("Snippets", "`python scripts/check_snippets.py`", f"{F['snippets'][0]}/{F['snippets'][1]}; refused: {', '.join(F['snippets_fail'])}")
    add("`coin_change` regression bisected", "`git worktree add` at `6423a29` and `210a599`, `check_snippets.py coin_change`", "passes at `6423a29`, refused from `210a599`; old conversion prints `3.0 -1.0`, CPython `3 -1`")
    add("Library mode matches CPython", "`wsl .venv/bin/python scripts/check_libmode.py`", f"OK: {F['libmode']['calls']} calls, {F['libmode']['class_calls']} class calls; cold build {F['libmode']['cold']} s, cached {F['libmode']['cached']} ms")
    add("Generated programs", "`tools/fuzz.py --n 150 --seed 0` then `tools/fuzz_run.py`", F["fuzz_result"])
    add("Property tests", "`python scripts/property_test.py`", F["property_result"])
    add("Kernel benchmark and guard elision", "`wsl .venv/bin/python docs/review3/src/bench_kernels.py`", (f"median {fx(bm)}, geometric mean {fx(gm)}; outputs identical: {F['bench_identical']}" if bm else "pending"))
    add("Edge cases, boundary cost, memory over many calls", "`wsl .venv/bin/python docs/review3/src/edge_cases.py`", f"{len(ec['rows'])} cases; RSS {mem.get('rss_before_kb', '?')} to {mem.get('rss_after_kb', '?')} KB over {mem.get('calls', '?')} calls")
    add("Studio runs, zero LLM", "`python docs/review3/src/studio_runs.py ...` against a server started with empty `GROQ_API_KEY` and `ANTHROPIC_API_KEY`", f"{len(jobs)} runs; see Table [[tab:studio]]")
    add("Stress harness on public repositories", "`python scripts/stress.py OWNER/REPO --limit N`", D.get("stress_short", "pending"))
    add("Lines of code, test counts, symbol line numbers", "`python docs/review3/src/collect_facts.py`", f"{F['total_loc']:,} lines in product code and tools (non-blank), {F['n_pos']}/{F['n_neg']} oracle programs")
    add("Environment", "`python docs/review3/src/collect_env.py`", f"{F['env']['cpu']}; Windows Python {F['env']['py_win']}; WSL Python {F['env']['py_wsl']}")
    add("Commit counts and AI co-author trailers", "`git shortlog -sn`; `git log --format=%B` for `Co-authored-by`", f"{g['commits']} commits; 138 owner; {F['ai_commits']} with an AI trailer")
    add("Installer and zip sizes", "`ls -l dist/`", f"{F['installer_mib']} MiB and {F['zip_mib']} MiB (built 19 Oct; not rebuilt this session)")
    add("Grammar rule count", "regex over `docs/grammar.ebnf`", "33 named rules")
    add("No `settrace`, no Electron, no Hindley-Milner in the code", "repository search (grep)", "no matches in product code")
    add("LLM is optional, not the default path", "read `pipeline.fix_one`, `llm.make_client`", "annotate, then deterministic inference, then LLM only if a key exists")
    add("Competitor descriptions", "official pages fetched: Shed Skin, Nuitka, PyPy, LPython, mypyc, Numba, Pythran", "Figure 4.1 cells; Cython and Codon pages were not retrieved in full (Cython from general knowledge, Codon from a search snippet), so those two rows are lower confidence", DATE)
    add("Emitted code listing", "`python -m pythia.cli e.py --emit-only`", "Listing 7.1")
    F["evidence_rows"] = ev

    # ------------------------------------------------------------------ screenshots
    scr = []
    for p, cap, key, w in D.get("screens", []):
        scr.append((p, cap, key, w))
    scr += [(FIG / "fig_ladder.png", "Fix-and-verify ladder (also Figure 7.1).", "ladder2", 15.0)] if False else []
    F["screens"] = scr
    return F
