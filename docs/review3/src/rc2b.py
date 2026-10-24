"""Report content, compact version of sections 6-9 (replaces rc2.sec6-9)."""
from fig_common import FIG


def sec6(d, F):
    d.h1("System design")
    d.p("PYTHIA has two tiers. The **compiler** (`pythia/`) turns PySub into C++17. **Studio** (`pythia/studio/`) wraps it in a ten-stage pipeline that works on whole "
        "projects, with a web interface that shows each stage. [[fig:arch]] draws the system in six layers; the numbered arrows are explained below it.", align="justify")
    d.landscape_section()
    d.figure(FIG / "fig_architecture.png", "PYTHIA architecture. Arrows 1 to 8 are described in the text; stage numbers 01 to 10 are the pipeline order.", "arch", 24.6)
    d.portrait_section()
    d.numbered([
        "**Input.** A snippet, file, folder, GitHub URL, demo or saved run reaches the FastAPI server as a job.",
        "**Ingest.** The project is copied to an isolated workspace (`original/` and `work/`); GitHub URLs are fetched as a zip, so git is not needed.",
        "**Compiler as judge and builder.** Scan, Fix and Compile call the compiler core: the real parser and type checker decide eligibility, the converter adds missing annotations, and the lowering, guard elision, emitter and `libmode.py` produce C++17 and pybind11 glue.",
        "**Build.** g++ builds a `.so` or `.pyd` against the runtime; builds are cached by content.",
        "**Replay.** A worker process feeds the recorded calls to the original and the compiled function.",
        "**Verdict.** Agreement and a speedup of at least 1.1x keep the function; anything else is rejected or declined with the numbers.",
        "**Outputs.** Accepted functions get a one-line decorator in the working copy; the diff, fidelity report, `PYTHIA_REPORT.md`, C++ and modules are exported. The original folder is never modified.",
        "**Interface.** Every stage emits sequenced events on a WebSocket bus, so the UI can play a run live, replay a saved one, or step through it.",
    ])
    d.h2("6.1 Modules")
    d.table(["Module", "Files (lines of code)", "Responsibility"], [r[:3] for r in F["module_rows"]], "modules",
            "Main modules; line counts are non-blank lines (`collect_facts.py`).", widths=[2.6, 6.4, 8.0], size=8.2)
    d.h2("6.2 Key data structures and decisions")
    d.bullets([
        "**Token, AST, `Ty`:** tokens carry line and column; every AST node has a `ty` slot the type checker fills, so the typed tree is the same tree. Types widen bool, int, float (`widens_to`, `typecheck.py:54`).",
        "**FidelityNote** (`lower.py:26`): position, divergence class, detail, mitigation, severity (exact, guarded or divergent).",
        "**FunctionRecord** (`studio/models.py`): one per function, with eligibility, status (`verified`, `guarded`, `fixable`, `not_eligible`, `declined`, `failed`), trace, every source form, build, replay, benchmark, splice and the 16-step journey the UI shows.",
        "**The compiler is the judge.** `scan.py` does not list PySub's features; it extracts each function and asks the real parser and type checker.",
        "**Splice by decorator, never by rewrite.** The original body stays; if the compiled module is missing or raises `FallbackError`, Python runs.",
        "**Never splice a slowdown.** Below 1.1x measured, a function is `declined`; functions under 0.2% of run time are not even built.",
        "**CPython-exact or rejected.** Accepted code gives identical stdout and exception type and message, or the compiler refuses it with a reason.",
    ])


def sec7(d, F):
    d.h1("Algorithms and methodology")
    d.p("For each stage: what it does, the algorithm, its cost and the trade-off we accepted. [[fig:journey]] follows one real function through the stages; the numbers are from Section 10.4.", align="justify", keep=True)
    d.figure(FIG / "fig_journey.png", "One function's journey: dayyass/project-euler, collatz_sequence_len, from Python to a replay-verified speedup.", "journey", 16.0)
    d.h2("7.1 Lexing and the off-side rule (`lexer.py`)")
    d.p("A stack of indentation widths starts as `[0]`. At the start of a logical line a larger indent pushes and emits INDENT; a smaller one pops and emits one DEDENT per level, "
        "and must land on a width still on the stack. Blank and comment lines carry no layout, brackets suppress it, `;` separates statements, and operators match longest-first. "
        "**Cost:** O(n). **Trade-off:** tabs are expanded to four spaces by the converter, not interpreted by the lexer.", align="justify")
    d.h2("7.2 Parsing (`parser.py`)")
    d.p("Statements use recursive descent; expressions use a Pratt loop (`parse_expr`, line 512) over a binding-power table (`or` 1 up to `**` 16, right associative). "
        "Chained comparisons desugar to `a < b and b < c`. Syntax errors use panic-mode recovery: `synchronize()` skips to the next statement boundary and always consumes a token, "
        "so one run reports several errors and cannot loop. **Cost:** O(n). **Trade-off:** hand-written, so each new construct is a hand-added hook; the gain is exact diagnostics and no dependency.", align="justify")
    d.h2("7.3 Bidirectional type checking (`typecheck.py`)")
    d.p("`synth` computes a type bottom-up; `check_expr(e, expected)` pushes one inward. That is what types an empty `[]` from its annotation, and widens `[1, 2.5]` against `list[float]`. "
        "Signatures are collected before bodies, so mutual recursion works; scopes are a parent-linked chain. **Cost:** O(n) visits with O(depth) lookups. "
        "**Trade-off:** one fixed type per variable, which gives unboxed fast code and rejects code that rebinds a name to another type.", align="justify")
    d.h2("7.4 In-house type inference for untyped Python (`pythia/convert/`)")
    d.numbered([
        "**Observe** (`observe.py`): run the program once under `sys.setprofile` and record the runtime types of arguments and locals.",
        "**Fixpoint** (`infer.py`, `Engine`): every variable, return, attribute and record field is a slot; evidence from assignments, calls, returns and iteration is joined on a type lattice until nothing changes. Conflicts become an absorbing `bad`; int-or-float becomes `num`, which is refused where it would change printed output.",
        "**Search** (`search.py`): for parameters nobody calls, try up to 400 type assignments ordered by syntactic hints; the first that makes the whole program type-check wins.",
        "**Judge:** the real PySub checker accepts or rejects the result; rejections come back with a plain-English reason.",
    ])
    d.p("**Cost:** linear passes, finite lattice height (nesting cut at depth 5), so it terminates. **Trade-off:** soundness over coverage; `coin_change` is refused because converting it would print `3.0 -1.0` where Python prints `3 -1` (Section 9.2). [[fig:ladder]] shows the ladder applied to each function.", align="justify")
    d.figure(FIG / "fig_ladder.png", "The fix-and-verify ladder. Every rung is deterministic except the optional last one, and none can bypass the compiler or the replay.", "ladder", 15.0)
    d.h2("7.5 Lowering and the divergence catalogue (`lower.py`)")
    d.p(f"`Lowerer` rewrites the typed tree into PIR: every implicit conversion becomes an explicit `Coerce`, and every risky site gets a `FidelityNote`. [[tab:div]] lists the fourteen classes. "
        f"On the {F['n_pos']} positive programs the compiler emitted {F['fid_total']} notes ({F['fid_exact']} exact, {F['fid_guarded']} guarded, {F['fid_divergent']} divergent); Section 10.3 breaks them down.", keep=True)
    d.table(["Class", "Divergence", "Treatment"], F["div_rows"], "div", "The divergence catalogue (D1 to D14) as implemented.", widths=[1.0, 6.4, 9.6], size=8.0)
    d.h2("7.6 Guard elision by interval analysis (`optimize.py`)")
    d.p("Python ints do not overflow; int64 does. PYTHIA compiles `+ - *` as checked calls (`py_add_i64` and friends) that throw `OverflowError`, and removes a check only where an interval proof shows it cannot fire. "
        "Literals give point intervals, `range` and `len()` bound indices, results must stay within plus or minus 2^62, and loop-carried accumulators are widened to *unknown* before the body is analysed, "
        "which is why one forward pass is sound. It may keep an unneeded check, never drop a needed one. **Cost:** O(n). **Measured effect:** none we can demonstrate (Section 10.2).", align="justify")
    d.h2("7.7 C++17 emission (`emit_c.py`)")
    d.p("One syntax-directed walk of PIR. Primitive lists map to monomorphic runtime types (`PyListI64`, `PyListF64`, ...), scalar dicts to specialised dict types, classes to `std::shared_ptr`. "
        "A `for ... in range` loop runs on a hidden counter so reassigning the loop variable cannot change the iteration; expressions that must evaluate an operand once use immediately invoked lambdas. "
        "Listing 7.1 is real output.", align="justify")
    d.code(F["emit_listing"], size=7.4)
    d.p("*Listing 7.1. `python -m pythia.cli e.py --emit-only` for a three-line kernel. The loop-carried `p_s` keeps its checks.*", size=8.6)
    d.h2("7.8 Library mode and marshalling (`libmode.py`, `pyrt_bridge.hpp`)")
    d.p("A module without `main()` gets a generated pybind11 wrapper. Arguments are copied in, results copied out, and mutated lists and dicts are written back. What cannot be represented faithfully "
        "(non-ASCII string, wrong-typed argument) raises `FallbackError` and the original Python runs; an int beyond int64 raises `OverflowError`. Each call runs in an arena that frees everything it allocated, "
        "and `print` inside compiled code is routed to Python's `sys.stdout` so output order matches. Builds are cached by content. **Trade-off:** copying makes large arguments expensive; the ranker accounts for it.", align="justify")
    d.h2("7.9 Tracing and ranking (`_tracer_boot.py`, `rank.py`)")
    d.p("The entry command runs with a tracer injected as `sitecustomize`: `sys.monitoring` on Python 3.12+, `sys.setprofile` before. It records calls, time, argument and return types and sampled call records. "
        "The ranker scores `trace_share x eligibility x expected_benefit x (1 - boundary_penalty)`, with `marshal = calls x (1.5 us + 4 ns x elements)`; a function with negative predicted net saving is declined, "
        "and those under 0.2% of run time are marked cold. The two constants are calibration knobs.", align="justify")
    d.h2("7.10 Oracle and replay verification (`tools/oracle.py`, `replay.py`)")
    d.p("The **oracle** checks the compiler: each positive program runs under CPython and as a binary and must give byte-identical stdout and exception class; each negative program must be rejected with the `# expect:` text. "
        "The **replay** checks one conversion: at least 50 calls (recorded, topped up and labelled) go through original and compiled function in a worker process; return value, exception and mutated arguments must match, floats by bit pattern. "
        "A match is then benchmarked and kept only if at least 1.1x faster. **Limit:** agreement on the replayed calls is evidence, not proof.", align="justify")


def sec8(d, F):
    d.h1("Implementation details")
    d.code(F["tree"], size=7.2)
    d.p("*Listing 8.1. Repository layout (selected).*", size=8.6)
    d.bullets([
        "**Front end and type system** grew by small extension modules registered on a few dispatch chains (`parse_ext.py`, `types_ext.py`, `classes_ext.py`, `tuples.py`, `comprehensions.py`, `builtins_ext.py`); those chains are where parallel work conflicted most.",
        "**Back end.** `emit_c.py` kept its Review 1 name through the C++17 migration; `emit_cpp.py` is an eight-line alias. The old C11 runtime (`pyrt.c/.h`) stays in the tree and is unused.",
        "**Studio.** `pipeline.py` runs the ten stages; `scan.py` extracts each function with its helpers; `replay.py`, `_replay_worker.py` and `codec.py` verify; `splice.py` and `export.py` produce the accelerated copy. The React UI is bundled with its fonts and committed as `dist/`.",
    ])
    d.p(f"**Build and packaging.** `python -m pythia.cli prog.py --run` parses, checks, lowers, emits and calls g++; `--fidelity` prints the report and `--lib f,g` builds a module. "
        f"`packaging/windows/build.py` assembles a relocatable CPython 3.13, a pruned MinGW-w64 GCC 16.2 toolchain, the compiler, the UI and prebuilt demo modules, then Inno Setup 6.7.3 writes the installer "
        f"({F['installer_mib']} MiB, per-user, no administrator rights) and a {F['zip_mib']} MiB portable zip. **CI** (`.github/workflows/ci.yml`) runs the oracle, a library-mode check and a packaging check on every push; we did not run CI in this session.", align="justify")


def sec9(d, F):
    d.h1("Testing strategy and test cases")
    d.p("Each layer catches a different kind of error. Suites are in [[tab:suites]]; representative cases with expected and actual results are in [[tab:cases]].", align="justify")
    d.table(["Suite", "What it checks", "Size", "Result (this session)"], F["suite_rows"], "suites", "Test suites.", widths=[3.6, 6.0, 2.4, 5.0], size=8.2)
    d.h2("9.1 Representative cases")
    d.table(["ID", "Category", "Input / description", "Expected", "Actual", "Status"], F["case_rows"], "cases",
            "Representative cases; actual values are from the logged runs (Appendix F). LIMIT rows are documented limits, not failures.",
            widths=[1.0, 1.6, 5.0, 3.4, 4.4, 1.4], size=7.8)
    d.h2("9.2 A regression we found and kept honest")
    d.p("`check_snippets.py` reported 21 of 22 snippets, not the 22 of 22 in `STATUS.md`. Bisecting with `git worktree` traced it to commit `210a599`. `coin_change` starts `dp` at `float('inf')` and returns `-1` when unreachable. "
        "Before the commit the converter typed it as returning `float`, which compiles but prints `3.0 -1.0` where CPython prints `3 -1`; now the converter reports conflicting types and refuses. "
        "The refusal is the CPython-exact behaviour, so we corrected the number, not the code.", align="justify")
    d.p("**Two bugs found while preparing the demo, fixed in commit `bd7e8ca`:** `print` inside a compiled function bypassed Python's stdout (reordered and wrong newlines when piped, so a whole-program output hash differed), "
        "and replay failed on scripts that import siblings by bare name.", align="justify")
    d.h2("9.3 Stress")
    d.p("`scripts/stress.py` pushes every file of a public repository through converter, checker, build and run. It was **not re-run** for this report, so we make no stress claim.", align="justify")
