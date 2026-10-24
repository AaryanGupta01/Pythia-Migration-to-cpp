"""Report content, part 2: sections 6-9."""
from fig_common import FIG


def sec6(d, F):
    d.h1("System design")
    d.h2("6.1 Architecture and data flow")
    d.p("PYTHIA has two tiers. The **compiler** (`pythia/`) turns PySub source into C++17. **Studio** (`pythia/studio/`) "
        "wraps it in a pipeline that works on whole projects and a web user interface that shows each stage. "
        "[[fig:arch]] (next page) draws the complete system in six layers; the numbered arrows are walked through below.", align="justify")
    d.landscape_section()
    d.figure(FIG / "fig_architecture.png", "PYTHIA architecture. Arrows 1 to 8 are described in the text; stage numbers 01 to 10 in the Studio engine are the pipeline order.", "arch", 24.6)
    d.portrait_section()
    d.numbered([
        "**1. Input.** The user gives the UI a snippet, a file, a folder, a GitHub URL, or opens the bundled demo or a saved run. The server (FastAPI) accepts it as a job.",
        "**2. Ingest.** The project is copied into an isolated workspace with a pristine `original/` and a `work/` copy that receives the splice; GitHub URLs are fetched as a zip archive, so git is not required. Long Windows paths are skipped and recorded.",
        "**3. Compiler as judge and as builder.** *Scan*, *Fix* and *Compile* call the compiler core: the real PySub parser and type checker decide whether a function is eligible (`scan.py`), the converter adds missing annotations (`convert/`, `studio/infer.py`), and the lexer, parser, type checker, lowering, guard elision and emitter produce C++17 and pybind11 glue (`libmode.py`).",
        "**4. Build.** The C++ translation unit is compiled with the bundled or system g++ against the runtime (`pyrt.hpp/.cpp`, containers, `pyrt_bridge.hpp`) into a `.so` or `.pyd`. Builds are content-addressed so identical source is never rebuilt.",
        "**5. Replay.** A worker process imports the original function and the compiled module and feeds both the recorded calls.",
        "**6. Verdict.** Results come back to the Verify and Benchmark stages: agreement and a speedup of at least 1.1x keep the function, anything else is rejected or declined with the numbers.",
        "**7. Outputs.** Accepted functions get a one-line decorator in the `work/` copy; the diff, the Semantic Fidelity Report, `PYTHIA_REPORT.md`, the C++ source and the compiled modules are exported. The original folder is never modified.",
        "**8. Interface.** Every stage emits typed events on a WebSocket bus (contiguous sequence numbers, persisted to `events.jsonl`), so the UI can play a run live, replay a saved one, or step through it in presenter mode.",
    ])
    d.h2("6.2 Modules and interfaces")
    d.table(["Module", "Files (lines of code)", "Responsibility", "Interface"], F["module_rows"], "modules",
            "Main modules. Line counts are non-blank lines measured with `docs/review3/src/collect_facts.py`.",
            widths=[2.6, 3.7, 6.3, 4.0], size=8.2)
    d.h2("6.3 Key data structures")
    d.bullets([
        "**Token** (`lexer.py:32`): kind, value, line, column. Layout is explicit: INDENT, DEDENT, NEWLINE, EOF.",
        "**AST and typed AST** (`ast_nodes.py`): one dataclass per construct; every node carries `line`, `col` and a `ty` slot that the type checker fills, so the typed AST is the same tree.",
        "**Ty** (`typecheck.py:23`): `name` plus optional `elem`, `key`, `elts` (list, dict, tuple, optional, class, set). The widening order is bool < int < float (`widens_to`, line 54; `join`, line 71).",
        "**FidelityNote** (`lower.py:26`): line, column, divergence class, detail, mitigation, severity (exact, guarded or divergent).",
        "**Interval** (`optimize.py`): `None` for unknown or a `(lo, hi)` pair of Python ints, kept inside plus or minus 2^62.",
        "**FunctionRecord** (`studio/models.py`): one record per function, holding its eligibility, status (`pending`, `verified`, `guarded`, `fixable`, `not_eligible`, `declined`, `failed`), reason, trace, score, every source form (original, annotated, PySub, C++, wrapper), build, replay, benchmark and splice results, and the 16-step *journey* the UI shows.",
        "**Event** (`studio/server/bus.py`): typed, sequenced messages (`job.start`, `stage`, `step`, `fix.done`, `error`, ...). The reducer in the UI is a pure function over this stream, which is why live, replayed and mocked runs render identically.",
    ])
    d.h2("6.4 Design decisions")
    d.p("The decisions below are recorded in `studio/DECISIONS.md` and the commit history; [[tab:why]] covers technology choices.", keep=True)
    d.bullets([
        "**The compiler is the judge.** `scan.py` does not list PySub's features; it extracts each function into a standalone module and asks the real parser and type checker, then translates diagnostics into plain English. New compiler features therefore need no scanner change.",
        "**Splice by decorator, never by rewrite.** `@_pythia_accelerated` is added above the original `def`; the body stays, the diff is small and reversible, and if the compiled module is missing or raises `FallbackError` the Python body runs.",
        "**Never splice a slowdown.** A function whose measured speedup is below 1.1x is `declined` and kept as a measured probe, so the decision is backed by a number.",
        "**Cold code is skipped.** Functions below 0.2% of traced run time are neither built nor sent to any fixer; without this a 270-function project would build about 80 modules.",
        "**Copy semantics at the boundary.** Arguments are copied in and mutated lists and dicts are written back; anything not representable raises `FallbackError`; integers outside int64 raise `OverflowError`.",
        "**Correctness rule.** *CPython-exact or rejected*: an accepted construct reproduces byte-identical stdout and the same exception type and message, otherwise the compiler rejects it with a message that names the reason.",
    ])


def sec7(d, F):
    d.h1("Algorithms and methodology")
    d.p("For each stage this section states what it does, the algorithm, its complexity, and the trade-off we accepted. "
        "Source locations are from commit `" + F["git"]["head"] + "`. *n* is the number of tokens or AST nodes of the unit being processed.", align="justify")
    d.p("[[fig:journey]] follows one real function from a third-party repository through the stages this section describes; the numbers are from the run in Section 10.4.", keep=True)
    d.figure(FIG / "fig_journey.png", "One function's journey end to end: dayyass/project-euler, collatz_sequence_len (Python, trace, PySub, tokens, typed tree, guards, C++17, build, replay, speedup).", "journey", 16.4)
    d.h2("7.1 Lexing and the off-side rule (`lexer.py`)")
    d.p("The scanner keeps a stack of indentation widths, initially `[0]`. At the start of a logical line it measures the "
        "indentation: a larger value pushes the stack and emits INDENT; a smaller value pops and emits one DEDENT per "
        "popped level, and the new width must equal a width still on the stack. Blank lines and comment-only lines carry "
        "no layout, brackets suppress layout entirely (`paren_depth`), `\\` joins lines, and `;` acts as a statement "
        "separator. At end of file the lexer emits a final NEWLINE and one DEDENT per open block. Operators are matched "
        "longest-first (`**=` before `**` before `*`). **Cost:** one pass, O(n) time, O(depth) space. **Trade-off:** tabs "
        "are not interpreted by the lexer; the converter expands them to four spaces on entry to avoid mixed-indentation "
        "surprises (commit `125bd67`).", align="justify")
    d.h2("7.2 Parsing: recursive descent plus Pratt (`parser.py`)")
    d.p("Statements use one recursive procedure per construct. Expressions use a Pratt loop (`parse_expr`, line 512) over a "
        "binding-power table: `or` 1, `and` 2, comparisons 4, `|` 5, `^` 6, `&` 7, shifts 8, `+ -` 10, `* / // %` 12, "
        "`**` 16 (right associative, so `a ** b ** c` groups to the right). Chained comparisons are desugared as "
        "`a < b and b < c`; if the middle operand is not pure, the parser reports it rather than evaluate it twice. "
        "The conditional expression binds loosest. Syntax errors use **panic-mode recovery**: `synchronize()` skips to "
        "the next NEWLINE, DEDENT or statement keyword and always consumes at least one token, so a parse can report "
        "several errors and can never loop. **Cost:** O(n), one token of lookahead beyond the current token for `not in` "
        "and `is not`. **Trade-off:** hand-written, so each new construct (f-strings, comprehensions, slices) is a "
        "hook added by hand; the benefit is precise, friendly diagnostics and no dependency.", align="justify")
    d.h2("7.3 Bidirectional type checking (`typecheck.py`)")
    d.p("`synth` computes a type bottom-up; `check_expr(e, expected)` pushes an expected type inward. The distinction "
        "matters for exactly the cases that bottom-up alone cannot type: an empty `[]` or `{}` takes its element type "
        "from the annotation or parameter it flows into; `[1, 2.5]` is checked against `list[float]` and widened. "
        "Function signatures are collected before bodies are checked, so mutual recursion works. Scopes are a "
        "parent-linked chain (`Scope`, line 82). Implicit conversion follows the lattice bool, int, float, plus "
        "subclass-to-base and optional rules that the extension modules register. Every error carries line and column "
        "and, where it helps, both types in conflict. **Cost:** O(n) node visits, each doing an O(depth) scope lookup. "
        "**Trade-off:** each variable has one static type for its lifetime, which is what makes the output unboxed "
        "and fast and also what rejects Python code that rebinds a name to another type.", align="justify")
    d.h2("7.4 In-house type inference for untyped Python (`pythia/convert/`)")
    d.p("Most real Python has no annotations, so PYTHIA must supply them. It does so without a language model, in four steps, "
        "and edits only the original text (comments and strings never change).", align="justify")
    d.numbered([
        "**Observation** (`observe.py`). Run the program once on its stdin under `sys.setprofile` and record the runtime types of every function's arguments and locals and of module globals. This fills holes that static reasoning leaves open, and the program's own output is kept to compare against the converted program later.",
        "**Whole-program fixpoint** (`infer.py`, `Engine`, line 163). Every variable, return value, attribute and record field is a *slot*. Evidence from assignments, call sites, returns, method uses and iteration is *joined* into slots on the lattice of `types.py` (scalars, `list`, `set`, `dict`, `tuple`, `opt`, class instances, records) until no slot changes. Conflicting evidence becomes an absorbing `bad` element, and an int-on-some-paths, float-on-others slot becomes `num`, which is refused wherever it would change printed output.",
        "**Search** (`search.py`). Parameters that no call fixes (LeetCode-style `class Solution` methods) are tried against up to 400 candidate type assignments ordered by syntactic hints (a `.append` call suggests a list, `.lower()` a string); the first assignment that makes the *whole program* type-check wins.",
        "**The compiler decides.** The annotated program is parsed and type-checked by PySub's own checker; only then does it go on. Anything the checker rejects is reported with a plain-English reason, not guessed at.",
    ])
    d.p("**Cost:** each pass is O(n); the lattice has finite height (nested types are cut off at depth 5), so the "
        "iteration terminates. **Trade-off:** soundness over coverage. A function that returns `-1` on one path and a "
        "float on another is refused, because converting it would print `-1.0` where Python prints `-1`; the "
        "snippet `coin_change` in our own suite is rejected for exactly this reason (Section 9.4). Inside the Studio "
        "pipeline the same ladder runs per function: annotate from types observed by the tracer, then deterministic "
        "inference, and only then (if a key is configured) an optional LLM rewrite that must still pass the compiler and the replay.", align="justify")
    d.figure(FIG / "fig_ladder.png", "The fix-and-verify ladder applied to every function. Every rung is deterministic except the optional last one, and no rung can bypass the compiler or the replay.", "ladder", 16.4)
    d.h2("7.5 Lowering and the divergence catalogue (`lower.py`)")
    d.p("`Lowerer` walks the typed AST and rewrites it into PIR, which uses the same node classes but obeys two "
        "invariants: every implicit conversion is an explicit `Coerce` node, and every site where C++ could behave "
        "differently from Python carries a `FidelityNote`. The catalogue has fourteen classes; [[tab:div]] lists them.", keep=True)
    d.table(["Class", "Divergence", "Treatment"], F["div_rows"], "div", "The divergence catalogue (D1 to D14) as implemented.",
            widths=[1.0, 7.2, 8.4], size=8.2)
    d.p(f"On the {F['n_pos']} positive oracle programs the compiler emitted {F['fid_total']} positioned notes: "
        f"{F['fid_exact']} exact, {F['fid_guarded']} guarded and {F['fid_divergent']} divergent (Section 10.3). "
        "**Cost:** O(n). **Trade-off:** notes are emitted for every site, which is noisy; the UI folds the global notes and "
        "shows the rest as a gutter next to the diff.", align="justify")
    d.h2("7.6 Guard elision by interval analysis (`optimize.py`)")
    d.p("Python integers do not overflow; int64 does. PYTHIA keeps Python's meaning by compiling each `+`, `-`, `*` as a "
        "checked operation (`py_add_i64`, `py_sub_i64`, `py_mul_i64` in `pyrt.cpp`: explicit range tests) that throws `OverflowError`, and then removes "
        "the check where it provably cannot fire. The pass is abstract interpretation over intervals (Cousot and Cousot), "
        "run as a single forward pass. Literals give point intervals, `range(a, b)` bounds the induction variable, "
        "`len()` bounds indices, and results are kept only if they stay within plus or minus 2^62, which leaves two "
        "bits of headroom. A variable that is assigned in a loop and feeds back into itself (an accumulator) is "
        "widened to *unknown* before the body is analysed, which is what makes one pass sound without a fixpoint solver. "
        "For non-exposed functions, literal call-site arguments also bound parameters; exposed functions are "
        "called by Python with arbitrary ints, so that bound is dropped. **Soundness contract:** it may keep a guard "
        "that was not needed, never remove one that was. **Cost:** O(n). The measured effect is in Section 10.2; in short, "
        "it helps where indices and counters dominate and does nothing for accumulators.", align="justify")
    d.h2("7.7 C++17 emission (`emit_c.py`)")
    d.p("Emission is one syntax-directed walk of PIR. Parameters and locals are prefixed (`p_`), functions `f_`, "
        "temporaries `_tN`; primitive lists map to monomorphic runtime types (`PyListI64`, `PyListF64`, "
        "`PyListBool`, `PyListStr`), dictionaries with scalar key and value types to eight specialised dict types and "
        "otherwise to the generic `PyDictT`, and class instances to `std::shared_ptr`. Python's loop-variable rules are "
        "kept by driving `for ... in range` from a hidden counter and assigning the visible variable from it, so "
        "reassigning `i` inside the body cannot change the iteration. Expressions that must evaluate an operand once "
        "(`and`/`or` returning an operand, `min`, `max`) use immediately invoked lambdas. Listing 7.1 shows real output. "
        "**Cost:** O(n) for the walk; build time is dominated by g++.", align="justify")
    d.code(F["emit_listing"], size=7.6)
    d.p("*Listing 7.1. Output of `python -m pythia.cli e.py --emit-only` for a three-line kernel. The accumulator `p_s` "
        "keeps its guarded `py_add_i64`/`py_mul_i64` because it is loop-carried; the loop counter needs none.*", size=8.8, color=None)
    d.h2("7.8 Library mode and marshalling (`libmode.py`, `pyrt_bridge.hpp`)")
    d.p("Library mode compiles a module without `main()` and generates a pybind11 wrapper for the requested functions. "
        "Marshalling has *copy semantics*: arguments are converted to runtime objects, results converted back, and "
        "mutated lists and dicts are written back into the caller's object. What cannot be represented faithfully "
        "(a non-ASCII string, a float where an int is expected, a tuple for a list) raises `FallbackError` and the shim "
        "runs the original Python; an integer beyond int64 raises `OverflowError`. Each call runs inside a **per-call arena**: "
        "every runtime object allocated during the call is freed when it ends, which is the region-based reclamation "
        "planned in Review 1, delivered for library mode only. Builds are content-addressed on source and toolchain; the "
        "header `pyrt_bridge.hpp` is precompiled, which the repository records as cutting a cold build to about 9 s and "
        "a repeat build to about 4 s (cache hit about 20 ms). **Trade-off:** copying makes calls with large arguments "
        "expensive, which the ranker accounts for.", align="justify")
    d.h2("7.9 Tracing and hotspot ranking (`_tracer_boot.py`, `rank.py`)")
    d.p("The entry command (for example `python main.py`) runs with a tracer injected as `sitecustomize`. On Python 3.12 "
        "and later it uses `sys.monitoring`, which has much lower overhead than `sys.settrace`; earlier versions fall back "
        "to `sys.setprofile`. For each target function it records calls, cumulative and self time, observed argument and "
        "return types, element counts, and up to a bounded number of sampled (arguments, result) pairs. The ranker then "
        "scores `trace_share x eligibility x expected_benefit x (1 - boundary_penalty)`, where the penalty is "
        "`marshal / (marshal + saving)`, `marshal = calls x (1.5 us + 4 ns x elements)` and `saving = traced seconds x "
        "(1 - 1/benefit)`. A function whose predicted net saving is negative is declined with the numbers shown, and "
        "functions below 0.2% of run time are marked cold. The two constants are calibration knobs, not measurements "
        "of every machine.", align="justify")
    d.h2("7.10 Differential oracle and replay verification (`tools/oracle.py`, `replay.py`)")
    d.p("Two instruments check two different claims. The **oracle** checks the compiler: for every program in "
        "`tests/positive` it runs CPython and the compiled binary on the same stdin and demands byte-identical standard "
        "output and the same uncaught-exception class; for `tests/negative` it demands that the compiler reject the "
        "program with a diagnostic containing the text in the file's `# expect:` marker. The **replay** checks one "
        "conversion of one user function: the recorded calls (at least 50, topped up with synthesised inputs and then "
        "labelled as such) are run through the original and the compiled function in a worker process, and the return "
        "value, the exception class and the state of mutated arguments must match, with floats compared by bit pattern "
        "(`struct.pack('<d')`, so NaN equals NaN). A function that disagrees is rejected; one that agrees is benchmarked "
        "(median over repeats) and kept only if it is at least 1.1x faster. **Cost:** linear in the number of calls. "
        "**Limit:** agreement on the replayed calls is evidence, not proof.", align="justify")


def sec8(d, F):
    d.h1("Implementation details")
    d.h2("8.1 Code organisation")
    d.code(F["tree"], size=7.6)
    d.p("*Listing 8.1. Repository layout (selected). Counts are non-blank lines.*", size=8.8)
    d.h2("8.2 Module-wise notes")
    d.bullets([
        "**Front end.** The lexer and parser were written for Review 1; since then the parser grew hooks for slices, bitwise operators, f-strings, comprehensions, lambdas, tuples, classes and `try`, each in a small extension module (`parse_ext.py`, `parse_iter.py`, `parse_types.py`) so the core grammar function stays readable.",
        "**Type system.** `typecheck.py` is the core; `types_ext.py` (optional, isinstance, sets, defaults and keyword arguments, module globals), `classes_ext.py` (classes, inheritance, dunders, properties, dataclasses), `tuples.py`, `comprehensions.py` and `builtins_ext.py` register through a few dispatch chains. The shared chains are the places where parallel work conflicted most, and are recorded as such in `STATUS.md`.",
        "**Back end.** `emit_c.py` keeps its Review 1 file name (the C++17 migration reused it); `emit_cpp.py` is an eight-line public alias. The runtime is `pyrt.hpp/.cpp` plus `pydict.hpp`, `pyset.hpp` and `pyrt_bridge.hpp`; the C11 runtime (`pyrt.c/.h`) remains in the tree as the Review 1 artefact and is not used by the C++17 pipeline.",
        "**Studio back end.** `pipeline.py` runs the ten stages and emits events; `scan.py` (about 1,200 lines) extracts each function with its helpers and constants into a standalone module; `fixer.py` and `llm.py` hold the optional LLM path; `replay.py`, `_replay_worker.py` and `codec.py` implement verification; `splice.py` and `export.py` produce the accelerated copy.",
        "**Studio front end.** React 18 with TypeScript, Vite, Tailwind and Monaco, bundled with fonts and no CDN at run time; the compiled `dist/` is committed so the app runs without Node. A mock engine (`?mock=1`) serves the whole API in the browser for UI development.",
    ])
    d.h2("8.3 Build process")
    d.p("**Compiler pipeline.** `python -m pythia.cli prog.py --run` parses, type-checks, lowers, elides guards, emits C++17 and "
        "calls g++ (`-std=c++17 -O2 -flto` in the oracle; `-O3 -fPIC -fvisibility=hidden -shared` for extension modules) "
        "together with `runtime/pyrt.cpp`. `--fidelity` prints the divergence report; `--lib f,g` builds a pybind11 module.", align="justify")
    d.p(f"**Windows installer.** `packaging/windows/build.py` assembles a relocatable CPython (NuGet package, 3.13), a pruned "
        f"WinLibs MinGW-w64 GCC 16.2 toolchain (UCRT), the PYTHIA wheel contents, the UI bundle and the prebuilt demo modules, "
        f"then calls Inno Setup 6.7.3 to build `PYTHIA-Studio-Setup-1.1.0.exe` ({F['installer_mib']} MiB, per-user, no administrator rights) and a "
        f"portable zip ({F['zip_mib']} MiB). Extension modules link statically against `python3X.dll`, so a `.pyd` needs nothing else. "
        "GCC's default-manifest link spec breaks on install paths with spaces, so the bundled toolchain renames that object and PYTHIA passes it explicitly.", align="justify")
    d.h2("8.4 Integration")
    d.p("Three GitHub Actions jobs run on every push (`.github/workflows/ci.yml`): the differential oracle, the library-mode "
        "self-check against CPython, and a packaging check that builds the wheel, installs it into a fresh virtual environment, "
        "boots the server and runs the offline demo job. A second workflow builds the wheel, sdist and container image on a "
        "version tag. We did not run CI in this session; the oracle, basics, snippet and library checks were run locally (Section 9).", align="justify")


def sec9(d, F):
    d.h1("Testing strategy and test cases")
    d.p("Testing is layered so that each layer catches a different kind of error. [[tab:suites]] lists the suites; "
        "[[tab:cases]] gives representative cases with expected and actual results taken from runs in this session.", align="justify")
    d.table(["Suite", "What it checks", "Size", "Result (this session)"], F["suite_rows"], "suites", "Test suites.",
            widths=[3.4, 6.2, 2.4, 4.6], size=8.3)
    d.h2("9.1 Positive and negative corpora")
    d.p("Positive programs exercise each language feature and each divergence class; the oracle compares CPython and the "
        "compiled binary byte for byte, including the exception class for programs that are meant to fail "
        "(`t12_err_index`, `t13_err_zerodiv`, `t77` to `t82`). Negative programs each carry an `# expect:` marker and "
        "are rejected only if the diagnostic contains the expected text, so the suite tests message quality, not just rejection.", align="justify")
    d.h2("9.2 Untyped basics, snippets, property tests, generated programs")
    d.p("`scripts/check_basics.py` converts every untyped program in `scripts/basics` with the in-house converter and "
        "**no LLM** (the script blanks the API key variables), compiles it, and compares output and exception type with "
        "CPython on the same stdin. `scripts/check_snippets.py` does the same for LeetCode and GfG-style snippets. "
        "`scripts/property_test.py` runs ten algorithm categories on randomised inputs, and `tools/fuzz.py` samples "
        "well-typed programs from the grammar in the spirit of Csmith.", align="justify")
    d.h2("9.3 Representative test cases")
    d.table(["ID", "Category", "Input / description", "Expected", "Actual", "Status"], F["case_rows"], "cases",
            "Representative cases. `Actual` columns come from the logged runs in Appendix F.",
            widths=[1.0, 1.6, 5.0, 3.4, 4.2, 1.4], size=7.9)
    d.h2("9.4 Stress and regression")
    d.p(F["stress_text"], align="justify")
    d.p("**A regression we found and kept honest.** During this session `scripts/check_snippets.py` reported 21 of 22 snippets, "
        "not the 22 of 22 recorded in `STATUS.md`. Bisecting with `git worktree` showed the change arrived in commit "
        "`210a599` (\"Expand in-house conversion for lambdas and closures\"). `coin_change` initialises `dp` with "
        "`float('inf')` and returns `-1` when unreachable. Before the commit the converter typed the function as returning `float`, which compiles but prints `3.0 -1.0` where CPython prints `3 -1` (we re-ran the old conversion to confirm); after it, the converter reports conflicting types and refuses. The refusal is the CPython-exact behaviour, so we left it and corrected the number rather than the code.", align="justify")
