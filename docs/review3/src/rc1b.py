"""Report content, compact version of sections 2-5 (replaces rc1.sec2-5)."""
from fig_common import FIG


def sec2(d, F):
    d.h1("Introduction and motivation")
    d.p("Python is easy to write and slow on loop-heavy code, because CPython handles every value as a heap object. The usual remedies each move "
        "the problem: a rewrite in C++ costs a second code base, a dialect such as Cython costs a new syntax, a JIT constrains the code, and an LLM translation "
        "comes with no evidence that it behaves like the original.", align="justify")
    d.p("What a working developer actually has is an untyped project and a profile saying three functions take most of the time. They want those functions "
        "faster, without a rewrite and without trusting a black box. That is a compiler problem: read the code (front end), know what it means (types), make Python's "
        "implicit behaviour explicit (IR), produce native code (back end), and argue why the output may replace the input (verification).", align="justify")
    d.bullets([
        "**Beneficiaries:** developers with a slow Python project; teams auditing a port (the Fidelity Report is the audit trail); students of compiler design.",
        "**Relevance to the course:** lexing with the off-side rule, Pratt parsing, scoped symbol tables and bidirectional type checking, type inference over a lattice, "
        "lowering, interval analysis, syntax-directed code generation and translation validation, plus the practical parts textbooks skip "
        "(host-runtime interfacing, build caching, packaging).",
    ])


def sec3(d, F):
    d.h1("Problem statement, objectives, scope and limitations")
    d.p("**Problem.** *Given a Python project, find where its time goes, translate each function that can be translated into C++17, prove on the program's own recorded calls "
        "that the translation behaves like CPython, install only the translations that pass and are actually faster, and report every place where the two languages could differ.* "
        "Functions that cannot be translated keep running in Python, with a plain-English reason.", align="justify")
    d.p("**Scope.** In: the PySub language (a typed Python subset grown to classes, dicts, sets, tuples, comprehensions, exceptions, f-strings and part of the standard library), "
        "an in-house converter from untyped Python, the C++17 back end and runtime, pybind11 library mode, the Studio application and a Windows installer. "
        "Out, by design: C-extension libraries (NumPy, pandas, PyTorch), generators, `eval`/`exec`, threads, file and network I/O, regex, unseeded randomness, non-ASCII text, and any back end other than C++17.", align="justify")
    d.h2("3.1 Objective compliance")
    d.table(["#", "Objective", "Target (Review 1/2)", "Achieved (Review 3)", "Status"], F["obj_rows"], "obj",
            "Objective compliance. Evidence for every value is in Appendix F.",
            widths=[0.8, 3.0, 3.8, 6.9, 2.1], size=8.2)
    d.h2("3.2 Review 2 to Review 3: what changed")
    d.figure(FIG / "fig_whatchanged.png", "Review 2 (a command-line transpiler) and Review 3 (the Studio application).", "changed", 16.0)
    d.table(["", "Review 2", "Review 3"], F["r2r3_rows"], "r2r3", "What changed since Review 2.", widths=[2.2, 5.6, 9.2], size=8.6, first_col_bold=True)
    d.p("**Why we changed direction.** A transpiler that takes hand-annotated PySub is a good compiler exercise, but nobody has a PySub program; they have a project. "
        "They need to find the hot functions, type untyped code, and trust the result. So the compiler core stayed and the new work sits around it: "
        "scan, trace and rank, in-house inference, replay verification, splice, and an application that shows every step.", align="justify")
    d.p("**Targets that changed.**", after=1)
    d.bullets([
        "**WebAssembly back end: dropped.** It would show retargetability but not help a developer speed up a Python project; the time went to Studio.",
        f"**Oracle corpus:** target 120 positive and 60 negative. Negative met (88); positive is {F['n_pos']}, backed by an independent {F['n_basics']}-program untyped gate and a generator (Section 9).",
        "**Reclamation:** delivered for library mode (a per-call arena); standalone binaries still never free memory (D7).",
    ])


def sec4(d, F):
    d.h1("Background and related work")
    d.p("**Concepts.** The off-side rule turns indentation into INDENT/DEDENT tokens. Pratt parsing handles expressions with a binding-power table. Bidirectional type checking "
        "pushes an expected type inward and synthesises types bottom-up. Interval abstract interpretation (Cousot and Cousot) gives sound integer ranges. "
        "Differential testing (McKeeman) compares two implementations on the same input; applied to a translator it is a form of translation validation: the output is checked per program, not proved correct for all programs.", align="justify")
    d.h2("4.1 Prior tools")
    d.p("[[fig:matrix]] compares nine existing systems with PYTHIA on the criteria that matter here; each cell follows the tool's own documentation (Section 14). Several of them beat PYTHIA in ways that matter:", keep=True)
    d.figure(FIG / "fig_matrix.png", "Comparison with existing tools. Filled circle: yes; half: partly or with caveats; empty: no; dash: not applicable. "
             "\"Readable output\" is the team's own assessment.", "matrix", 15.0)
    d.bullets([
        "**PyPy** runs unmodified programs with high compatibility at about 4x CPython on average (its own site); **Numba** needs only a decorator and excels on array code.",
        "**Cython, mypyc, Nuitka** handle far more of Python and its libraries; none checks its output or reports divergence.",
        "**Codon, Pythran, Shed Skin, LPython** compile a subset to native code and can beat our output, but need code written for them.",
        "**LLM translation** accepts any code and gives readable output, but nothing checks it, results vary between runs, and it needs a network.",
    ])
    d.h2("4.2 The gap and our novelty")
    d.p("Tools that accept untyped code do not give a readable, auditable artefact; tools that give readable native code need code written for them; none checks its output against CPython "
        "or reports where semantics may differ. PYTHIA's contribution is the combination, stated only as far as Section 10 supports:", align="justify")
    d.numbered([
        "**Verified, not asserted.** Each converted function is replayed against CPython on calls recorded from the user's own program (topped up with labelled generated inputs); a function that disagrees is rejected automatically. It is differential testing, not a proof.",
        "**Semantic Fidelity Report.** A positioned list of every site where Python and C++ could differ, with class (D1 to D14) and mitigation; we found no surveyed tool documenting one.",
        "**Whole project, hands-off.** Scan, rank, convert what can be converted, explain the rest in plain English, splice back while the project keeps running.",
        "**In-house type inference, no LLM.** Deterministic, free, offline. An optional LLM fallback exists, is off without a key, and cannot bypass the compiler or the replay.",
        "**Readable, exportable C++17** and an application that shows every stage.",
    ])
    d.p("We do not claim to be faster than Codon or Pythran on code they accept, to cover as much of Python as PyPy, Cython or Nuitka, or that \"verified\" means more than \"agreed with CPython on the calls we replayed\".", align="justify")


def sec5(d, F):
    d.h1("Requirements and technology stack")
    d.table(["Item", "Value (detected on the machine that produced the results)"], F["env_rows"], "env",
            "Environment used for every measurement in this report.", widths=[3.4, 13.6], size=8.4, first_col_bold=True)
    d.table(["Layer", "Choice (version used)", "Role"], F["stack_rows"], "stack", "Technology stack.", widths=[2.8, 6.4, 7.8], size=8.2)
    d.p(f"**Test inputs.** All self-authored: {F['n_pos']} positive and {F['n_neg']} negative PySub programs, {F['n_basics']} untyped everyday programs, {F['n_snippets']} LeetCode-style snippets, "
        "two bundled demo projects, a grammar-directed generator, a property-test harness and a stress harness (Section 9).", align="justify")
    d.h2("5.1 Why this, not that")
    d.table(["Decision", "Chosen", "Considered", "Why"], F["why_rows"], "why", "Technology choices. Where the reason is our own judgement, we say so.",
            widths=[2.2, 3.2, 3.0, 8.6], size=7.9)
