"""Viva guide, part B: sections 5-7 (HTML strings)."""
import re
from pathlib import Path

from fig_common import FIG, ROOT


def L(path, pat, nth=1):
    """Line number of the nth line matching `pat` in `path` (relative to the repo root); raises if absent."""
    txt = (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
    n = 0
    for i, l in enumerate(txt, 1):
        if re.search(pat, l):
            n += 1
            if n == nth:
                return i
    raise KeyError(f"{path}: {pat}")


def ref(path, pat, label=None, nth=1):
    return f"<code>{label or Path(path).name}:{L(path, pat, nth)}</code>"


def entry(path, pat, what, nth=1):
    return f"<tr><td>{ref(path, pat, nth=nth)}</td><td>{what}</td></tr>"


def sec5(F, D):
    def block(color, name, rows, talk, newfiles=""):
        return f"""
<div class="member" style="--c:{color}">
<div class="mh"><span class="dot"></span><h3>{name}</h3></div>
<table class="open"><tr><th style="width:26%">Open</th><th>Point at this</th></tr>{''.join(rows)}</table>
<div class="say"><span class="tag">30-second talk track</span>{talk}</div>
</div>"""
    v = block("#2563eb", "Vishal: front end and Studio shell", [
        entry("pythia/lexer.py", r"class Lexer", "The lexer class. The indentation stack lives in <code>self.indents</code>."),
        entry("pythia/lexer.py", r"def tokenize", "The main loop: layout at line start, comments, NEWLINE, strings, operators, then end-of-file DEDENTs."),
        entry("pythia/parser.py", r"^BP = ", "The binding-power table. One line per precedence level; <code>**</code> is the only right-associative operator."),
        entry("pythia/parser.py", r"def parse_expr", "The Pratt loop: parse a unary, then keep folding operators while their binding power is high enough."),
        entry("pythia/parser.py", r"def synchronize", "Panic-mode recovery. Read the docstring: it explains the infinite-loop bug it avoids."),
        entry("pythia/cli.py", r"def compile_source", "The whole compiler in six lines: parse, typecheck, lower, elide guards, emit."),
        entry("pythia/studio/pipeline.py", r"def _run", "The ten stages in order, with cancellation checks between them."),
        entry("pythia/studio/server/app.py", r"def create_app|app = FastAPI", "The server: REST routes plus the WebSocket that streams events."),
        entry("pythia/studio/launcher.py", r"def _probe", "How the app refuses to reuse a stale server (build fingerprint check)."),
    ], "“Python marks blocks with indentation, which a grammar cannot see. My lexer keeps a stack of indent widths and turns changes into INDENT and DEDENT tokens, so after that the parser sees ordinary braces-like blocks. Statements are recursive descent; expressions use Pratt parsing with the binding-power table here, so adding an operator is one table line. When there is a syntax error the parser skips to the next statement boundary and carries on, so one run reports several errors. For Review 3 I built the pipeline that runs the ten stages and the server and app around it.”")
    r = block("#059669", "Rujuta: type system", [
        entry("pythia/typecheck.py", r"^class Ty\b", "The type representation: a name plus element, key or tuple parts."),
        entry("pythia/typecheck.py", r"^def widens_to", "The implicit-conversion lattice: bool to int to float, plus subclass and optional rules."),
        entry("pythia/typecheck.py", r"^def join", "How two branch types are combined; <code>[]</code> next to <code>[1,2]</code> becomes <code>list[int]</code>."),
        entry("pythia/typecheck.py", r"^class Scope", "Parent-linked scope chain."),
        entry("pythia/typecheck.py", r"    def check_expr", "Checking mode: the expected type is pushed inward, which is how empty lists get typed."),
        entry("pythia/typecheck.py", r"    def synth\(", "Synthesis mode: the type is computed from the expression itself."),
        entry("tests/negative/n02_badarg.py", r"expect", "A negative test: the first line says what the message must contain."),
        entry("runtime/pydict.hpp", r"class PyDict|struct PyDict", "The dictionary runtime (pull request #2)."),
        entry("pythia/convert/infer.py", r"^class Engine", "<b>Studio, proposed:</b> the whole-program type inference engine."),
        entry("pythia/convert/types.py", r"^def join", "<b>Studio, proposed:</b> the lattice the inference joins evidence on."),
        entry("pythia/convert/search.py", r"^def best_assignment", "<b>Studio, proposed:</b> guessing types for parameters nobody calls."),
    ], "“The type checker has two modes. In synthesis mode it works a type out from the expression, like <code>1 + 2.5</code> being float. In checking mode it already knows what it expects, like a list annotated <code>list[int]</code>, and pushes that inward, which is the only way <code>[]</code> can be typed. Each variable keeps one type for life, which is what lets us emit unboxed C++. For Studio the same idea runs on untyped code: we collect evidence about every variable until nothing changes, and then let the real type checker accept or reject the result.”")
    j = block("#d97706", "Jahnavi: lowering, fidelity, runtime, guard elision", [
        entry("pythia/lower.py", r"^class FidelityNote", "One fidelity note: position, class, detail, mitigation, severity."),
        entry("pythia/lower.py", r"^D_INTWIDTH", "The catalogue of divergence classes D1 to D13 (D14 is added in two extension modules)."),
        entry("pythia/lower.py", r"    def check_binop", "Where each operator is examined and tagged."),
        entry("pythia/optimize.py", r"^SAFE_LO", "The safety margin: stay inside plus or minus 2<sup>62</sup>."),
        entry("pythia/optimize.py", r"^class GuardElider", "The interval analysis. <code>eval</code> computes ranges; <code>block</code> widens loop-carried variables."),
        entry("runtime/pyrt.cpp", r"^int64_t py_add_i64", "A checked addition: throws <code>OverflowError</code> instead of wrapping."),
        entry("runtime/pyrt.hpp", r"arena_begin", "The per-call arena that frees memory in library mode."),
        entry("runtime/pyset.hpp", r"class PySet|struct PySet", "The set runtime (pull request #3)."),
        entry("runtime/pyrt_bridge.hpp", r"struct Arena", "<b>Studio, proposed:</b> the boundary: copy in, copy out, write back, <code>FallbackError</code>."),
        entry("pythia/libmode.py", r"^def build_library", "<b>Studio, proposed:</b> generate the pybind11 wrapper and build the module."),
    ], "“Python and C++ disagree on small things that change output: floor division, the sign of modulo, integer overflow. My lowering pass finds every such spot and records a note with its position, its class and what we did. That is the Semantic Fidelity Report. Overflow checks cost time, so the interval pass proves where they cannot fire and removes them, but it is conservative: it may keep a check it did not need, never drop one it did. The runtime gives C++ Python’s behaviour.”")
    a = block("#7c3aed", "Aaryan: emitter, oracle, verification", [
        entry("pythia/emit_c.py", r"^class Emitter", "The emitter class."),
        entry("pythia/emit_c.py", r"    def emit_module", "Walks the module and writes the translation unit."),
        entry("pythia/emit_c.py", r"py_add_i64", "Where a guarded or unguarded <code>+</code> is chosen (look for <code>no_guard</code> just above).", nth=1),
        entry("tools/oracle.py", r"^def run_positive", "The oracle: CPython versus the compiled binary, stdout and exception class."),
        entry("tools/oracle.py", r"^def run_negative", "The negative suite: the diagnostic must contain the <code>expect:</code> text."),
        entry("tools/fuzz.py", r"^class Var", "The grammar-directed program generator keeps a live type environment."),
        entry(".github/workflows/ci.yml", r"oracle", "CI: three jobs on every push."),
        entry("pythia/studio/replay.py", r"^MIN_CALLS", "<b>Studio, proposed:</b> at least 50 calls per function, topped up when too few were recorded."),
        entry("pythia/studio/codec.py", r"^def same", "<b>Studio, proposed:</b> the comparison; floats are compared bit for bit."),
        entry("pythia/studio/bench.py", r"^def bench_e2e", "<b>Studio, proposed:</b> end-to-end timing before and after the splice, with an output hash."),
        entry("scripts/stress.py", r"^ap = ", "<b>Studio, proposed:</b> the stress harness over public repositories."),
    ], "“Same behaviour is a claim, so we built the thing that tries to break it. The oracle runs every program under CPython and as a compiled binary and compares the output byte for byte, plus the exception class. A second suite checks that bad programs are rejected with the right message. A generator makes new programs from the grammar so we find bugs we did not think of. In Studio the same idea runs on your own function’s recorded calls, and anything that disagrees is rejected.”")
    tree = F["tree"].replace("<", "&lt;")
    return f"""
<section class="chap" id="s5">
<h1><span class="no">5</span>“Open the codebase” cheat sheet</h1>
<p>Line numbers are from commit <code>{F['git']['head']}</code>; they were looked up by the build script, so they match the code you open. If someone edits those files, regenerate this guide.</p>
{v}{r}{j}{a}
<h2>Repository tree, one line per folder</h2>
<pre class="tree">{tree}</pre>
<h2>Files added since Review 2</h2>
<p>Everything below was added after commit <code>533f875</code> (10 September 2026, “Final Cleanup Before Review 2”).</p>
<table class="open"><tr><th style="width:30%">Where</th><th>What was added</th></tr>
<tr><td><code>pythia/convert/</code> (7 files)</td><td>The in-house untyped-Python converter: inference engine, type lattice, observer, search, preparation.</td></tr>
<tr><td><code>pythia/studio/</code> (40 files)</td><td>The Studio back end: ingest, scan, trace, rank, fix, compile, verify, benchmark, splice, export, server, LLM fixer (optional), playground converter.</td></tr>
<tr><td><code>pythia/libmode.py</code>, <code>classes_lib.py</code>, <code>lib_ext.py</code>, <code>toolchain.py</code>, <code>paths.py</code></td><td>pybind11 library mode, class marshalling, toolchain discovery.</td></tr>
<tr><td><code>pythia/*_ext.py</code>, <code>tuples.py</code>, <code>comprehensions.py</code>, <code>classes_ext.py</code>, <code>parse_*.py</code>, <code>driver.py</code>, <code>stages.py</code></td><td>Language growth: types, classes, tuples, comprehensions, built-ins, parsing hooks.</td></tr>
<tr><td><code>runtime/pyrt_bridge.hpp</code>, <code>runtime/pythia_accel/</code></td><td>Python/C++ marshalling and the loader shim.</td></tr>
<tr><td><code>studio/web/</code> (46 source files)</td><td>The React, TypeScript and Monaco application.</td></tr>
<tr><td><code>packaging/windows/</code></td><td>Installer assembly, launcher, Inno Setup script.</td></tr>
<tr><td><code>scripts/</code></td><td>check_basics, check_snippets, check_libmode, check_project, check_installed, property_test, stress, measure_coverage, install scripts, corpora.</td></tr>
<tr><td><code>studio/DECISIONS.md</code>, <code>CONTRACTS.md</code>, <code>README.md</code>, <code>USER_GUIDE.md</code>, <code>INSTALL.md</code>, <code>DEMO.md</code>, <code>STATUS.md</code></td><td>Design decisions, interface contracts, user and install guides, demo script, hand-over status.</td></tr>
<tr><td><code>demo/</code>, <code>docs/review3/</code></td><td>Two bundled demo projects with an offline cache; this review’s documents and sources.</td></tr>
</table>
</section>
"""


def sec6(F, D):
    rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td></tr>" for a, b, c in [
        ("Python for the compiler", "The compiler works on trees and text, not hot loops, and Studio has to import and run the user’s code. Python is quick to change.", "C++ or Rust: faster compiler, but slower to write and awkward to call into user code."),
        ("Hand-written lexer and parser", "We needed to control the indentation rule and give precise error positions, with no extra dependency.", "ANTLR, Lark, PLY: less code, but harder to get Python’s layout and friendly errors."),
        ("C++17 as the target", "pybind11 needs C++. Templates give typed lists. The output is readable. g++ does the optimising.", "C11 (what we started with; needed GNU tricks) and LLVM IR (not readable, needs LLVM)."),
        ("pybind11", "Converts types and exceptions for us, one header, same compiler.", "ctypes/cffi (hand-written marshalling), raw C-API (long). nanobind: we did not evaluate it."),
        ("Differential testing", "Our spec is “behaves like CPython”; running both is the cheapest executable spec.", "Unit tests (only what we thought of) or a formal proof (out of reach)."),
        ("In-house type inference", "Deterministic, free, offline. We <b>tried</b> an LLM first (Groq free tier: about 200,000 tokens a day, answers vary, needs internet) and kept it only as an optional fallback.", "LLM translation."),
        ("FastAPI + WebSockets", "Live event stream is a first-class feature.", "Flask, Django."),
        ("React + Vite + TypeScript + Monaco in an app window", "A real diff editor, runs in any browser, no second runtime to ship.", "Tkinter, Qt, Electron."),
        ("Bundled MinGW-w64 GCC", "A zip we can put inside the installer; the build flags target GCC.", "MSVC (a separate big install)."),
        ("Inno Setup", "One script, per-user install, no admin rights.", "WiX/MSI, NSIS."),
        ("sys.monitoring tracing", "Cheap per-function events on Python 3.12+; falls back to setprofile. We never use settrace.", "sys.settrace (line-level, slower)."),
    ])
    return f"""
<section class="chap" id="s6">
<h1><span class="no">6</span>Tools we chose, and why</h1>
<table class="open"><tr><th style="width:24%">We chose</th><th>Why</th><th style="width:26%">Instead of</th></tr>{rows}</table>
<div class="say"><span class="tag">Be careful</span>The “instead of” column is our reasoning, not benchmarks. If asked “did you measure nanobind or Electron?”, answer “no, we chose on maturity and simplicity”.</div>
</section>
"""


def sec7(F, D):
    ec = F["edge"] or {"lib": {}}
    lib = ec.get("lib", {})
    mem = lib.get("mem", {})
    def lim(title, honest, comeback):
        return f"""<div class="lim"><h4>{title}</h4>
<div class="two"><div class="h"><span class="tag">Honest answer</span>{honest}</div><div class="c"><span class="tag">Confident comeback</span>{comeback}</div></div></div>"""
    items = [
        lim("“What about NumPy, pandas, PyTorch, OpenCV?”",
            "PYTHIA cannot transpile functions that call those libraries. The scanner marks them “not eligible” and says why.",
            "Those libraries are already C and C++ inside, so the maths is not where Python is slow. The time goes in the pure-Python code around them. PYTHIA compiles that glue and leaves the library calls in Python. Next steps: call the libraries from compiled code through the CPython C-API, map a NumPy subset onto Eigen or xtensor, or use LibTorch’s C++ API directly instead of transpiling."),
        lim("“What if the code is dynamic: <code>eval</code>, monkey-patching, a variable that changes type?”",
            "Those are rejected with a reason, not guessed at. Our own snippet <code>coin_change</code> is refused because it returns an int on one path and a float on another.",
            "Refusing is the safe answer: the old version of the converter widened it to float and printed <code>3.0 -1.0</code> where Python prints <code>3 -1</code>, and we caught that. To cover more, compile one specialised version per observed type signature, or use <code>std::variant</code> for union types."),
        lim("“Python ints are unbounded. What happens on overflow?”",
            f"Compiled code uses 64-bit ints. Operations that might overflow are checked and raise <code>OverflowError</code>; an int beyond 64 bits passed into a compiled function also raises it. We measured both ({'2**62 * 2 raises OverflowError' if ec else 'see report'}).",
            "It fails loudly instead of silently wrapping, and the fidelity report lists every site (class D1). The remedy is bignum promotion on overflow: fall back to an arbitrary-precision type only when a check fires."),
        lim("“Strings and Unicode?”",
            "Compiled strings are ASCII bytes. A non-ASCII argument makes the wrapper raise <code>FallbackError</code>, and the original Python function runs instead, so nothing breaks, you just do not get the speedup.",
            "It is a safe fallback by design. The fix is UTF-8-aware strings with code-point indexing, which is a runtime change, not a compiler redesign."),
        lim("“Memory: does it leak?”",
            f"Standalone binaries never free memory (class D7). In library mode, which is what Studio uses, everything allocated during a call is freed when the call ends. We checked: memory did not grow over {mem.get('calls', 'many')} calls ({mem.get('rss_before_kb', '?')} KB before, {mem.get('rss_after_kb', '?')} KB after), and the repo’s own check shows no growth over 3,000 calls.",
            "So the Studio path is safe. For standalone programs the next step is a region allocator or reference counting."),
        lim("“Isn’t crossing between Python and C++ expensive?”",
            f"Yes. Arguments are copied in and out. For a trivial function the call costs about {lib.get('call_overhead_us', '?')} µs against {lib.get('py_len_us', '?')} µs for Python’s own <code>len</code>, and a 100,000-element list costs about {lib.get('marshal_100k_ms', '?')} ms per call to copy.",
            "That is exactly why the ranker exists: it predicts marshalling cost, and a function whose measured speedup is under 1.1x is “declined” and never spliced. Remedies: zero-copy buffers, keep data on the C++ side across calls, fuse neighbouring hot functions."),
        lim("“Testing is not proof.”",
            "Correct. Verification is differential testing on recorded and generated calls. It shows agreement on those calls, not on all inputs. Untraced code paths are untested, which is why the entry command matters.",
            "It is evidence about <i>your</i> program, which a generic proof would not give, and anything that disagrees is rejected. Stronger forms exist and are future work: translation validation per pass, property-based fuzzing around the recorded inputs, and formally proving one pass in the style of CompCert."),
        lim("“Only Python?”",
            "Yes: Python in, C++ out.",
            "Everything after the front end works on the typed tree and the IR, which do not know about Python syntax. A new front end is the only addition needed for another source language; a new emitter would give another target."),
        lim("“Are dictionaries fast?”",
            "No. Our benchmark with a string-keyed dictionary and about 2,000 keys ran about 29 times <i>slower</i> than CPython. The cause is in <code>runtime/pyrt.cpp</code> line 131: the specialised dictionaries scan a vector for every lookup.",
            "Correct and slow is a fixable kind of wrong: a hash index in that one macro removes it, and the ranker would already decline such a function when the measured speedup is below 1.1x, so Studio would not splice it."),
        lim("“Generators, threads, files, regex, <code>random</code>?”",
            "Not supported: generators are rejected, and I/O, threads, regex and unseeded randomness are refused with a reason (<code>explain.py</code>).",
            "Most hot numeric code does not need them. Seeded randomness is the one we would add first, because a generator with a known algorithm can be reproduced exactly."),
        lim("“It takes a long time to compile.”",
            f"The first build of a module is slow: {F['libmode']['cold']} s cold in our library check, {F['libmode']['tu']} s for a new module with the runtime already built, and {F['libmode']['cached']} ms when the build cache hits. A whole cold project run takes minutes (Section 10.4 of the report).",
            "Builds are content-addressed, so a second run of the same project is fast, and the demo ships prebuilt modules. The bundled compiler means nothing is installed."),
    ]
    return f"""
<section class="chap" id="s7">
<h1><span class="no">7</span>Limitations and comebacks</h1>
<p>Say the honest answer first, then the comeback. A panel trusts you more if you name the limit before they do.</p>
{''.join(items)}
</section>
"""
