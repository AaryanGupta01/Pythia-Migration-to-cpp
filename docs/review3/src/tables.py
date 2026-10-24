"""Static tables for the report (facts that do not depend on this session's measurements)."""

R2R3_ROWS = [
    ["Input", "Hand-annotated PySub", "Ordinary Python: snippet, file, folder or GitHub URL; types inferred"],
    ["Unit", "One whole program", "One function at a time inside a project, spliced back behind a decorator"],
    ["Types", "Written by the author", "In-house inference (observe, fixpoint, search); no LLM needed"],
    ["Evidence", "Oracle: 17 positive, 20 negative programs", "Oracle 78 and 88, plus replay of the program's own calls for every converted function"],
    ["Language", "Scalars, lists, PyDict, PySet", "Plus classes, tuples, comprehensions, try/except, f-strings, a standard-library subset"],
    ["Interface", "Command line", "Studio: pipeline stepper, diff with fidelity gutter, function journey, playground, report"],
    ["Delivery", "Clone and run", "Windows installer, portable zip, wheel, Docker image"],
    ["Back ends", "C++17 (WebAssembly promised)", "C++17 only; **WebAssembly dropped**"],
]

WHY_ROWS = [
    ["Compiler language", "Python 3", "C++, Rust", "The compiler manipulates trees and strings, not hot loops, and Studio must import and run the user's modules in process (tracing, replay). Our judgement."],
    ["Lexer and parser", "Hand-written (`lexer.py`, `parser.py`)", "ANTLR, Lark, PLY", "Full control of the off-side rule and of positioned error recovery, and no third-party import in the compiler core. Cost: each new construct is a hand-written hook."],
    ["Target", "C++17 (migrated from C11 on 4 Sept 2026, pull request 1)", "C11, LLVM IR", "pybind11 needs C++; templates give monomorphic containers; lambdas give single evaluation; the output stays readable source and g++ does the optimisation. C11 had needed GNU statement expressions at three sites (Review 1, Section 5.4). LLVM IR would not be readable and would need LLVM at run time."],
    ["Python bridge", "pybind11 3.1.0", "ctypes, cffi, raw C-API, nanobind", "Automatic conversions and exception translation with one header-only dependency built by the same g++. ctypes and cffi need a C ABI and hand-written list and string marshalling; the raw C-API is long. We did not evaluate nanobind."],
    ["Correctness evidence", "Differential testing (oracle and replay)", "Unit tests, formal proof", "The specification of a translator is \"behaves like CPython\", and the cheapest executable form of that is to run both. A proof of the whole pipeline was out of reach; we say so (Section 11)."],
    ["Type source", "In-house inference", "LLM translation", "We tried it first: a Groq/Anthropic fixer and an LLM Playground converter (commits `dfe6942`, `cf2cfb8`). The free tier is about 200,000 tokens per day per model (`STATUS.md`), answers vary between runs, it needs a network, and every answer still has to pass the compiler and the replay. The LLM path remains as an optional fallback (commit `e4a4804`)."],
    ["Server", "FastAPI with WebSockets", "Flask, Django", "First-class async WebSockets for the event stream, Pydantic models, and one small ASGI app that serves the UI bundle too."],
    ["Desktop UI", "React, Vite, TypeScript, Monaco in an Edge/Chrome `--app` window", "Tkinter, Qt, Electron", "Monaco gives a real diff editor; the same UI runs in any browser and as a PWA; no second runtime to ship, so the installer is {installer_mib} MiB with Python and a compiler inside. We did not benchmark Electron."],
    ["Windows toolchain", "Bundled MinGW-w64 GCC 16.2 (WinLibs, UCRT)", "MSVC", "The build flags (`-O3 -flto -fvisibility=hidden`) and the runtime are developed against GCC, and a redistributable zip can be shipped inside the installer; MSVC Build Tools are a separate installation. Our judgement."],
    ["Installer", "Inno Setup 6.7.3", "WiX / MSI, NSIS", "One scripted `.iss`, per-user install without administrator rights, free."],
    ["Tracing", "`sys.monitoring` (3.12+), `sys.setprofile` fallback", "`sys.settrace`", "Per-function call events at lower cost than line tracing; `settrace` is not used anywhere in the repository (`_tracer_boot.py:66`, `observe.py`)."],
    ["Accept rule", "Measured replay speedup of at least 1.1x", "Static heuristics only", "A function that compiles is not necessarily faster; the number decides (`DECISIONS.md`, B2)."],
]

DIV_ROWS = [
    ["D1", "Unbounded `int` against `int64_t`", "Guarded: checked `+ - *` raise `OverflowError`; guards removed where interval analysis proves them unreachable; ints beyond int64 at the boundary raise `OverflowError`."],
    ["D2", "`//` floors toward minus infinity, C++ truncates", "Exact: `py_floordiv_i64` and the float form."],
    ["D3", "`%` takes the sign of the divisor", "Exact: `py_mod_i64`, including signed zero for floats."],
    ["D4", "`/` is always true division", "Exact: operands widened to double, `ZeroDivisionError` preserved."],
    ["D5", "Negative indexing and bounds checks", "Exact: index normalised and checked in the runtime; `IndexError` reproduced."],
    ["D6", "`int ** negative int` changes the result type", "Divergent: cannot be typed statically; reported at compile time, refused at run time."],
    ["D7", "Object lifetime and reclamation", "Guarded: standalone binaries never free; library mode frees everything allocated in a call when the call ends."],
    ["D8", "Exception propagation across calls", "Exact: C++ exceptions of one type (`PythonException`) caught in `main`. The note text in `lower.py` still describes the Review 1 `setjmp`/`longjmp` mechanism and is stale."],
    ["D9", "Class fields zero-initialised before `__init__`", "Guarded: an unset field reads as zero instead of raising `AttributeError`."],
    ["D10", "`sum()` of an empty `list[float]`", "Guarded: CPython returns int 0, compiled code 0.0; non-empty sums use the same compensated summation."],
    ["D11", "Ordering of NaN in sort, min, max", "Guarded: merge sort and timsort may place NaN differently."],
    ["D12", "Interactive `input()`", "Exact: prompt to stdout, one line from stdin, `EOFError` at end."],
    ["D13", "Characters are ASCII", "Guarded: non-ASCII input raises `FallbackError` at the boundary; `ord`/`chr` above 127 raise `PythiaSemanticError`."],
    ["D14", "libm last-bit differences; user-defined ordering", "Guarded: math functions call the toolchain's libm; sorting objects by `__lt__` calls it in a different order."],
]

KNOWN_ISSUES = [
    "**Snippet `coin_change`** is refused (int and float on different paths): 21 of 22 snippets pass, not the 22 of 22 in `STATUS.md` (Section 9.2).",
    "**`docs/grammar.ebnf` is the v0.1 core** (33 named rules; Review 1 reported 41). The language has grown past it; later constructs are described by prose rules generated from the compiler source.",
    "**Stale text:** the D8 note still describes `setjmp`/`longjmp`, and the D7 note calls reclamation \"the Review 3 target\".",
    "**Dictionaries use a linear scan** (`runtime/pyrt.cpp:131`), about 29 times slower than CPython on our dictionary kernel.",
    "**Stress harness not re-run;** `STATUS.md` lists three older stress-harness bugs that we did not re-investigate.",
    "**A stale server is the usual cause of impossible-looking errors;** the launcher checks a build fingerprint, but a forgotten WSL server on the same port can still answer first.",
]

REFS_BOOKS = [
    "Aho, A. V., Lam, M. S., Sethi, R. and Ullman, J. D. (2006). *Compilers: Principles, Techniques, and Tools*, 2nd ed. Addison-Wesley.",
    "Pierce, B. C. and Turner, D. N. (2000). Local type inference. *ACM Transactions on Programming Languages and Systems*, 22(1), 1-44.",
    "Pratt, V. R. (1973). Top down operator precedence. *Proc. 1st ACM Symposium on Principles of Programming Languages*, 41-51.",
    "Cousot, P. and Cousot, R. (1977). Abstract interpretation: a unified lattice model for static analysis of programs by construction or approximation of fixpoints. *Proc. 4th ACM POPL*, 238-252.",
    "McKeeman, W. M. (1998). Differential testing for software. *Digital Technical Journal*, 10(1), 100-107.",
    "Yang, X., Chen, Y., Eide, E. and Regehr, J. (2011). Finding and understanding bugs in C compilers (Csmith). *Proc. PLDI*, 283-294.",
    "Pnueli, A., Siegel, M. and Singerman, E. (1998). Translation validation. *Proc. TACAS*, LNCS 1384, 151-166.",
    "Leroy, X. (2009). Formal verification of a realistic compiler. *Communications of the ACM*, 52(7), 107-115.",
    "ISO/IEC (2017). *ISO/IEC 14882:2017, Programming languages: C++*.",
]

REFS_DOCS = [
    "Cython documentation, \"Cython - an overview\". https://cython.readthedocs.io/en/latest/src/quickstart/overview.html",
    "Numba documentation, \"Overview\" and \"Glossary\" (nopython mode, type inference). https://numba.readthedocs.io/en/stable/",
    "PyPy, project home page (speed and compatibility statements). https://pypy.org/",
    "mypyc documentation, \"Introduction\". https://mypyc.readthedocs.io/en/latest/introduction.html",
    "Nuitka project, README and user manual. https://github.com/Nuitka/Nuitka , https://nuitka.net/doc/user-manual.html",
    "Codon, README and documentation (Apache-2.0). https://github.com/exaloop/codon , https://docs.exaloop.io/",
    "Pythran documentation. https://pythran.readthedocs.io/en/latest/",
    "Shed Skin, README. https://github.com/shedskin/shedskin",
    "LPython, project page (alpha status, backends). https://lpython.org/",
    "Python documentation, `sys.monitoring` and `sys.setprofile`. https://docs.python.org/3/library/sys.monitoring.html",
]

REFS_OSS = [
    "pybind11 (BSD-3-Clause), seamless operability between C++11 and Python. https://github.com/pybind/pybind11",
    "FastAPI (MIT), Uvicorn (BSD-3-Clause), Starlette (BSD-3-Clause), Pydantic (MIT), websockets (BSD-3-Clause).",
    "React 18 (MIT), Vite 5 (MIT), TypeScript 5 (Apache-2.0), Tailwind CSS 3 (MIT), Zustand (MIT), Framer Motion (MIT), cmdk (MIT), xterm.js (MIT).",
    "Monaco Editor and @monaco-editor/react (MIT). Inter and JetBrains Mono fonts (SIL OFL 1.1) via Fontsource.",
    "Lucide icons, `lucide-react` 0.460.0 (ISC licence), used in the application and in the figures of this report.",
    "MinGW-w64 GCC 16.2 (UCRT build) distributed by WinLibs (GPL with runtime-library exception). https://winlibs.com/",
    "Inno Setup 6.7.3 (Jordan Russell and Martijn Laan; free licence). https://jrsoftware.org/isinfo.php",
    "CPython 3.13 relocatable distribution via the NuGet `python` package (PSF licence).",
    "Playwright for Python (Apache-2.0) and Matplotlib (PSF-based licence), used to produce this report's screenshots and charts; python-docx (MIT) to generate the .docx.",
]

AI_ACK = ("PYTHIA was developed with the help of AI coding assistants. The repository history records Anthropic Claude (Opus 5.5 and "
          "Sonnet 5.5, used through Claude Code) and GitHub Copilot as co-authors in `Co-authored-by` trailers on {ai_commits} of {commits} "
          "commits, including the dictionary-library pull request. This report and the viva guide were also drafted with such an assistant "
          "from the repository and from commands run on the team's machine. The team is responsible for the content.")
