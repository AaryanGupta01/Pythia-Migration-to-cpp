"""Report content, part 1: cover, abstract, sections 2-5."""
from fig_common import FIG


def cover(d, F):
    doc = d.doc
    d.p("VIT VELLORE  ·  SCHOOL OF COMPUTER SCIENCE AND ENGINEERING", align="center", size=10, color=None, after=2)
    d.p("**BCSE307L – Compiler Design**", align="center", size=13, after=26)
    d.p("**FINAL PROJECT REPORT  ·  REVIEW 3**", align="center", size=11, after=18)
    d.p("**PYTHIA and PYTHIA Studio**", align="center", size=27, after=2)
    d.p("A verified source-to-source accelerator that converts the slow parts of a Python project to C++17, "
        "checks every conversion against CPython, and splices it back in", align="center", size=12.5, after=22, italic=True)
    rows = [["Course", "BCSE307L – Compiler Design"],
            ["Project ID and title", "A15 – Typed Source-to-Source Transpiler"],
            ["Team number", "Team 2"],
            ["Review", "Review 3 (final), October 2026"],
            ["Faculty", "Shalini L"],
            ["Repository state", f"branch `main`, commit `{F['git']['head']}` ({F['git']['commits']} commits)"]]
    _plain_table(d, ["Item", "Details"], rows, [4.2, 12.4])
    d.p("", after=6)
    _plain_table(d, ["Team member", "Register number", "Role"],
                 [["Vishal Vivek (team lead)", "24BCE2377", "Front end, integration, repository, Studio application"],
                  ["Rujuta Mangesh Kulkarni", "24BDS0459", "Type checker, semantic analysis, dictionary support, negative corpus"],
                  ["Koliparthy Venkata Jahnavi", "24BDS0132", "Lowering, divergence catalogue, runtime, guard elision, PySet"],
                  ["Aaryan Gupta", "24BDS0134", "C++ emitter, C11 to C++17 migration, differential oracle, CI, corpus"]],
                 [5.2, 3.2, 8.2])
    d.p("", after=6)
    d.p("**Declaration.** We declare that this report and the project it describes are the work of the team named above. "
        "Where we reused open-source software, documentation or AI coding assistants, we have said so in Section 14. "
        "Every number in this report comes from a command we ran on the machine described in Section 5; "
        "Appendix F lists each claim with its command, result and date.", size=9.5, after=22)
    d.p("Signatures:   ______________   ______________   ______________   ______________", size=9.5, align="center")
    d.pagebreak()


def _plain_table(d, header, rows, widths):
    d.table_plain(header, rows, widths)


def abstract(d, F):
    d.h1("Abstract")
    d.p(F["abstract"], align="justify")


def sec2(d, F):
    d.h1("Introduction and motivation")
    d.h2("2.1 Context")
    d.p("Python is the default language for scripting, teaching and prototyping, and its speed on loop-heavy, "
        "numeric and text-processing code is a well-known cost: the CPython interpreter evaluates every operation on "
        "heap-allocated, reference-counted objects, so an integer addition is a pointer chase, a type check and an "
        "allocation rather than one machine instruction. Developers who hit this wall have four options today: rewrite "
        "the hot code in C or C++, port it to an annotated dialect such as Cython, adopt a JIT such as Numba or PyPy, "
        "or ask a language model to translate it. Each option moves the problem rather than solving it. A rewrite "
        "costs a second codebase; a dialect costs a new syntax; a JIT constrains the types or the interpreter; and a "
        "translation from a model comes with no evidence that it behaves like the original.", align="justify")
    d.h2("2.2 The need")
    d.p("What a working developer actually has is an existing, untyped Python project and a profiler output that says "
        "three functions take most of the time. What they want is for those three functions to be fast without "
        "rewriting the project, without trusting a black box, and without breaking behaviour. That is a compiler "
        "problem in the strict sense: it needs a front end (to read the code), a type system (to know what the code "
        "means), an intermediate form (to make Python's implicit behaviour explicit), a back end (to produce native "
        "code), and a correctness argument (to say why the output can replace the input). PYTHIA is built around that "
        "last point: the conversion is accepted only if it reproduces the original's behaviour on real calls.", align="justify")
    d.h2("2.3 Beneficiaries")
    d.bullets([
        "**Developers with an existing Python code base** who want measured speedups on their hot spots, with a diff they can review and a one-line way to undo it.",
        "**Teams porting or auditing legacy Python**, who get a source-positioned list of every place where Python and C++ semantics could differ (the Semantic Fidelity Report).",
        "**Students and instructors of compiler design**, because every classical phase is present, small enough to read, and visible in the Studio application.",
    ])
    d.h2("2.4 Relevance to compiler design")
    d.p("The project exercises each phase of the course: lexical analysis with the off-side rule (Section 7.1), "
        "recursive-descent and Pratt parsing (7.2), scoped symbol tables and bidirectional type checking (7.3), "
        "type inference over a lattice with a fixpoint (7.4), lowering to an explicit intermediate form (7.5), "
        "interval-based abstract interpretation for check elision (7.6), syntax-directed code generation (7.7), and "
        "translation validation by differential testing (7.10). It also touches the part of compiler engineering that "
        "textbooks skip: interfacing generated code with a host runtime (pybind11), caching builds, and shipping the "
        "result as an installable product.", align="justify")


def sec3(d, F):
    d.h1("Problem statement, objectives, scope and limitations")
    d.h2("3.1 Problem statement")
    d.p("*Given a Python project, find the functions on which its run time is spent, translate each one that can be "
        "translated into C++17, prove on the program's own recorded calls that the translation behaves identically to "
        "CPython, install only the translations that pass and are actually faster, and report every place where the "
        "two languages' semantics could differ.* Functions that cannot be translated are left running in Python, "
        "with a plain-English reason.", align="justify")
    d.p("This is the Review 1 problem (a typed Python subset to readable native code, with a differential oracle and a "
        "divergence report) lifted from single files to whole projects, and from typed input to ordinary, untyped input.", align="justify")
    d.h2("3.2 Final approved scope")
    d.bullets([
        "**In scope:** the PySub language (a statically typed Python subset that has grown from the Review 1 core to include classes, dictionaries, sets, tuples, comprehensions, exceptions, f-strings and a part of the standard library); an in-house converter from untyped Python to PySub; the C++17 back end and its runtime; library mode (pybind11 extension modules); the Studio application (scan, trace, rank, fix, compile, verify, benchmark, splice, export); a Windows installer.",
        "**Out of scope, by design:** third-party C-extension libraries (NumPy, pandas, PyTorch, OpenCV), generators, `eval`/`exec`, threads, file and network I/O, regular expressions, unseeded randomness, non-ASCII text, and any back end other than C++17.",
    ])
    d.h2("3.3 Objective-compliance table")
    d.p("[[tab:obj]] compares each measurable objective set in Reviews 1 and 2 with what was achieved. Where a target was missed or changed, the status says so.", keep=True)
    d.table(["#", "Objective", "Target (Review 1/2)", "Achieved (Review 3)", "Status"], F["obj_rows"], "obj",
            "Objective compliance. Evidence for every value is in Appendix F.",
            widths=[0.8, 3.0, 4.0, 6.6, 2.0], size=8.4)
    d.h2("3.4 Review 2 to Review 3: what changed and why")
    d.p("The faculty asked specifically for improvement since Review 2. [[fig:changed]] shows the change in one picture "
        "and [[tab:r2r3]] lists it item by item.", keep=True)
    d.figure(FIG / "fig_whatchanged.png", "From a command-line transpiler (Review 2) to the Studio application (Review 3).", "changed", 16.4)
    d.table(["Area", "At Review 2", "At Review 3", "Why"], F["r2r3_rows"], "r2r3",
            "Review 2 compared with Review 3.", widths=[2.4, 4.6, 5.8, 4.2], size=8.4)
    d.p("**Why we pivoted.** A transpiler that takes a hand-annotated subset is a good compiler exercise, but it is not "
        "how anyone would use the idea. A developer does not have a PySub program; they have a project. The question "
        "that matters to them is not \"can this subset compile?\" but \"which of my functions can be sped up, how do "
        "I know the fast version is right, and what do I do about the rest?\". Answering it needed three things the "
        "Review 2 tool did not have: a way to find the hot functions (tracing and ranking), a way to type untyped code "
        "(in-house inference), and a way to establish trust (replay on the program's own calls). The compiler "
        "core is unchanged in kind and reused; the new work sits around it.", align="justify")
    d.p("**Targets that changed.** (1) The WebAssembly text back end promised for Review 3 was **dropped**. A second "
        "back end would have demonstrated retargetability but would not have helped a developer speed up a Python "
        "project, and the team's remaining time went to the Studio pipeline. (2) The oracle corpus target of 120 "
        "positive and 60 negative programs was met for the negative suite (88) and not for the positive oracle suite "
        f"({F['n_pos']}); the positive count is supplemented by an independent {F['n_basics']}-program untyped gate "
        "and a grammar-directed generator (Section 9). (3) Region-based reclamation was delivered only for library mode "
        "(a per-call arena); standalone binaries still never free memory (divergence D7).", align="justify")
    d.h2("3.5 Limitations (summary)")
    d.p("The full list, with measured impact, is Section 11. In one sentence: PYTHIA converts pure-Python computation "
        "over ints, floats, bools, ASCII strings, lists, dicts, sets, tuples and simple classes; it will not touch "
        "code that depends on C-extension libraries, dynamic features or I/O, and its verification is differential testing "
        "on recorded inputs, not a proof.", align="justify")


def sec4(d, F):
    d.h1("Background and related work")
    d.h2("4.1 Concepts")
    d.p("**Off-side rule and layout tokens.** Python's block structure is indentation, so the token stream is not "
        "context-free until the lexer turns indentation changes into explicit INDENT and DEDENT tokens. "
        "**Pratt parsing** (top-down operator precedence) handles expressions with a binding-power table instead of one "
        "grammar rule per precedence level. **Bidirectional type checking** (Pierce and Turner, local type inference) "
        "pushes an expected type inward where one is known and synthesises a type bottom-up where it is not. "
        "**Abstract interpretation with intervals** (Cousot and Cousot) computes a sound range for each integer "
        "expression and is used here to remove overflow checks that cannot fire. **Differential testing** "
        "(McKeeman) runs two implementations on the same input and compares behaviour; applied to a translator it is a "
        "form of **translation validation**: the translation is checked per program, not proved correct for all programs.", align="justify")
    d.h2("4.2 Prior tools and comparison")
    d.p("Nine existing systems address part of the problem. [[fig:matrix]] compares them with PYTHIA on the criteria "
        "that matter for this project; the sources for each cell are the tools' own documentation, listed in "
        "Section 14. We tried to say what each tool does better than PYTHIA, and the list is not short.", keep=True)
    d.figure(FIG / "fig_matrix.png", "Comparison with existing tools. Filled circle: yes; half: partly or with caveats; empty: no. "
             "Cells reflect each tool's official documentation (Section 14); \"readable output\" is the team's own assessment.", "matrix", 16.6)
    d.bullets([
        "**Numba** needs no annotations and is excellent on NumPy-style numeric code, but it is a JIT aimed at array-oriented, math-heavy code and needs a decorator per function; it gives no per-function check against CPython and no divergence report.",
        "**PyPy** runs unmodified programs with full Python semantics (including unbounded integers) at about 4x CPython on average according to its own site, with no setup at all. It is a different interpreter, so it needs no conversion and produces no code to read; it also does not give a C++ artefact.",
        "**Cython** and **mypyc** compile real Python (with optional static declarations or standard type hints) to C extension modules that keep Python semantics; they are more complete than PYTHIA and handle arbitrary imports. They do not verify or report divergence, and the user supplies the types.",
        "**Nuitka** compiles whole programs to C linked against libpython, claiming every Python construct; its speed-ups are modest, and the output depends on CPython.",
        "**Codon**, **Pythran**, **Shed Skin** and **LPython** compile a Python-like language or subset to native code (LLVM or C++) and can be faster than PYTHIA's output because they own their whole runtime. They require code that fits their subset or typing model: Codon's low-level documentation describes its standard `int` as a 64-bit signed integer, and it presents itself as a Python-like language rather than a drop-in replacement (we could not retrieve its \"differences\" page, so the second point is the team's reading); Shed Skin says existing code may need a lot of work; LPython is alpha.",
        "**LLM translation** (asking a chat model to rewrite Python as C++) handles any code and gives readable output, but nothing checks that the result behaves like the original, results differ between runs, and it needs an online service.",
    ])
    d.h2("4.3 The identified gap and our novelty")
    d.p("Read across [[fig:matrix]]: tools that handle untyped code (Numba, PyPy, Nuitka) do not give an auditable, readable "
        "artefact; tools that give readable native code (Codon, Pythran, Shed Skin, LPython) need code written for them; "
        "and none of the nine checks its output against CPython or tells the user where the semantics may differ. "
        "PYTHIA's contribution is the combination, and each part is stated here only as far as the evidence in Section 10 supports:", align="justify")
    d.numbered([
        "**Verified, not asserted.** Every converted function is run against CPython on calls recorded from the user's own program (topped up with generated inputs when too few were recorded, and labelled as such); results, mutated arguments and exception types must match, floats bitwise. A function that disagrees is rejected automatically. This is differential testing, not a proof (Section 11).",
        "**The Semantic Fidelity Report.** A machine-generated, source-positioned list of every site where Python and C++ semantics could differ, each with its divergence class (D1 to D14) and mitigation. None of the surveyed tools documents a per-site report of this kind.",
        "**Whole project, hands-off.** Point it at a folder or a GitHub URL; it scans every function, traces the program, ranks hot spots, converts what it can, explains in plain English why the rest was left alone, and splices compiled code back so the project keeps running.",
        "**In-house type inference for untyped code, with no language model.** Deterministic, free, offline and reproducible: the same input always gives the same annotations. An optional LLM fallback exists, is off unless a key is configured, and cannot bypass the compiler or the replay check.",
        "**Readable, exportable C++17 and an IDE-style application** that shows every stage, with a diff for every change.",
    ])
    d.p("What we do not claim: PYTHIA is not faster than Codon or Pythran on code those tools accept, it does not cover as much of "
        "Python as PyPy, Cython or Nuitka, and its \"verified\" label means \"agreed with CPython on the calls we replayed\".", align="justify")


def sec5(d, F):
    d.h1("Requirements and technology stack")
    d.h2("5.1 Environment used for every measurement in this report")
    d.table(["Item", "Value (detected on the machine that produced the results)"], F["env_rows"], "env",
            "Hardware and software environment.", widths=[4.2, 12.4], size=8.6, first_col_bold=True)
    d.h2("5.2 Software and libraries")
    d.table(["Layer", "Choice (version used)", "Role"], F["stack_rows"], "stack", "Technology stack.",
            widths=[3.0, 6.0, 7.6], size=8.4)
    d.h2("5.3 Test programs and corpora")
    d.p(f"The project needs no external data set. Its inputs are self-authored: {F['n_pos']} positive and {F['n_neg']} negative "
        f"PySub programs (`tests/positive`, `tests/negative`), {F['n_basics']} untyped everyday programs (`scripts/basics`), "
        f"{F['n_snippets']} LeetCode- and GfG-style snippets (`scripts/snippets`), two bundled demo projects "
        "(`demo/textlab`, `demo/quanta`), a grammar-directed program generator (`tools/fuzz.py`), a property-based "
        "differential harness (`scripts/property_test.py`), and a stress harness that downloads public GitHub repositories "
        "(`scripts/stress.py`). Section 9 describes each.", align="justify")
    d.h2("5.4 Why this, not that")
    d.p("[[tab:why]] records each major technology choice, the alternative we considered, and the reason. Where the "
        "repository records the reason (in `studio/DECISIONS.md` or a commit message) we cite it; where the reason is "
        "our own engineering judgement we say so.", keep=True)
    d.table(["Decision", "Chosen", "Considered", "Why"], F["why_rows"], "why", "Technology choices and their alternatives.",
            widths=[2.4, 3.2, 3.4, 7.6], size=8.1)
