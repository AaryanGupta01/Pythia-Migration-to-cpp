"""Viva guide, part C: sections 8-11 (HTML strings)."""


def sec8(F, D):
    return f"""
<section class="chap" id="s8">
<h1><span class="no">8</span>The value this adds</h1>
<h2>Who would use it</h2>
<ul>
<li><b>A developer with a slow Python project</b> who wants the hot functions faster without a rewrite, and wants to review the change as a diff.</li>
<li><b>A team that must justify a port.</b> The Fidelity Report is an audit trail: here is every place the behaviour could differ, and what we did.</li>
<li><b>Students and teachers of compilers.</b> Every phase is small enough to read and the app shows each one.</li>
</ul>
<h2>What it saves</h2>
<p>The time to find the hot spots (the tracer does it), the time to hand-annotate (the inference does it), the time to write bindings (pybind11 glue is generated), and the time to convince yourself the fast version is right (replay does it). On the bundled TextLab demo a whole program went from {D['textlab_before']} s to {D['textlab_after']} s with no source edits beyond decorator lines.</p>
<h2>Why verified matters more than raw speed</h2>
<p>A fast wrong answer is worse than a slow right one. Tools that translate quietly change behaviour (a 64-bit integer, a different rounding rule), and the problem shows up months later. PYTHIA’s promise is smaller and checkable: whatever it splices in agreed with CPython on the calls we replayed, and anything doubtful is reported or refused.</p>
<h2>Where it could go</h2>
<ul>
<li><b>A research paper</b> on the divergence report as a first-class output of a source-to-source compiler, paired with replay verification. It needs a bigger independent corpus and a comparison with Cython, mypyc and Codon on the same programs.</li>
<li><b>A VS Code extension</b> that shows the gutter and diff inside the editor.</li>
<li><b>CI integration</b> that fails a build when a converted function stops matching.</li>
<li><b>Bignum promotion, UTF-8 strings, zero-copy buffers, type-specialised versions</b> (Section 7).</li>
</ul>
</section>
"""


def make_qa(F, D):
    return [
    ("Isn’t this just Cython?",
     "No. Cython needs you to write C type declarations (or pure-Python mode annotations) and gives you a C extension with Python semantics; it does not check the result against CPython or tell you where behaviour differs. PYTHIA takes untyped code, works out the types, produces readable C++17, and checks every conversion on real calls. Cython is more complete: it handles arbitrary Python and C libraries, and we say so."),
    ("Why not just ask ChatGPT to convert it?",
     "We tried an LLM first (commit <code>dfe6942</code>). Three problems: the free tier ran out (about 200,000 tokens a day), answers change between runs, and nothing proves the answer is right. PYTHIA’s in-house inference is deterministic and free, and everything it produces is checked. An optional LLM fallback still exists, but its output has to pass the type checker and the replay like anything else."),
    ("How do you know the C++ is correct?",
     "Two checks. The oracle compiles 78 programs and compares output and exception class with CPython byte for byte, and rejects 88 invalid programs with the right message. In Studio, every converted function is replayed on at least 50 calls (recorded, topped up with generated ones, and labelled) and the return value, exception and mutated arguments must match; floats are compared bit for bit. It is differential testing, not a proof, and we say so."),
    ("Why are the speedups different from Review 1?",
     f"Review 1 reported a median of 9.4x (range 3.3x to 13.8x) on 14 programs with generated C11. The oracle now reports a median of {F['oracle_speed'][0]}x (range {F['oracle_speed'][1]}x to {F['oracle_speed'][2]}x) on 78 programs with C++17 and <code>-O2 -flto</code>. We did not isolate each cause: the backend changed, more programs are in the set, guard elision exists, and those timings are single runs of whole processes. For performance claims we use a separate benchmark: ten fixed kernels, medians of {F['bench_runs']} runs, median {F['bench_median']:.0f}x."),
    ("What happens if someone passes NumPy code?",
     "Functions that use NumPy are marked not eligible, with the reason “uses numpy (a C-extension library)”, and keep running in Python. NumPy’s own loops are already native, so the time is usually in the Python around them, which PYTHIA can compile."),
    ("What did <i>you</i> personally build?",
     "Answer from Section 4 and 5: name your files, the hardest problem, and one function to open. If it is Studio work, say which part you understood and wrote or reviewed, and be straight that AI coding assistants were used and are credited in the repository history."),
    ("Why C++ and not LLVM?",
     "Readable output, and pybind11 needs C++. g++ already optimises well, and we can bundle it on Windows. LLVM IR would not be readable and would need LLVM at run time. The cost: we depend on a C++ compiler, which we ship in the installer."),
    ("What happens on integer overflow?",
     "Checked arithmetic raises <code>OverflowError</code> instead of wrapping (class D1). Where interval analysis proves a result stays within plus or minus 2<sup>62</sup>, the check is removed. An int beyond 64 bits passed into compiled code also raises. Python would have kept going with a big integer, so this is a documented divergence."),
    ("Why did you drop the WebAssembly backend?",
     "It was promised at Review 2. A second back end shows retargetability but does not help a developer speed up a Python project, and the time went to the Studio pipeline. The IR does not depend on Python syntax, so adding it later is an addition."),
    ("What’s a DEDENT token?",
     "Python marks blocks by indentation. When a line is indented less than the previous one, the lexer emits one DEDENT for each block that just ended, so the parser can treat blocks like braces. INDENT is the opposite. The lexer keeps a stack of indentation widths to know how many to emit."),
    ("Explain bidirectional type checking.",
     "Two modes. Synthesis works a type out from the expression (<code>1 + 2.5</code> is float). Checking is given an expected type and pushes it inward (<code>xs: list[int] = []</code> types the empty list as <code>list[int]</code>). Alone, <code>[]</code> has no type; with an expected type it does."),
    ("Is the type system Hindley–Milner?",
     "No. The compiler uses bidirectional local inference with one fixed type per variable. The converter for untyped code uses a whole-program fixpoint over a type lattice (join evidence until nothing changes), which is simpler than HM unification and gives up on conflicts instead of generalising."),
    ("Why Pratt parsing?",
     "Expressions have many precedence levels. A Pratt parser uses one loop and a binding-power table, so adding an operator is one line, and right-associativity (<code>**</code>) is a small tweak. A cascade of grammar functions would need one function per level."),
    ("What is the Semantic Fidelity Report?",
     f"A list, produced by the compiler, of every place where C++ could behave differently from Python: position, class (D1 to D14), what could differ, what we did, and a severity (exact, guarded, divergent). On our corpus it has {F['fid_total']} notes: {F['fid_exact_pct']}% exact, {F['fid_guarded_pct']}% guarded, {F['fid_divergent_pct']}% divergent. We did not find a surveyed tool whose documentation describes a per-site report like this."),
    ("What is PIR?",
     "The typed tree after lowering. It uses the same node classes, but every implicit conversion (bool to int to float) is an explicit Coerce node and every risky site carries a fidelity note, so the emitter never has to infer anything."),
    ("What does guard elision do, and is it sound?",
     "Every int <code>+ - *</code> is a checked call by default. Interval analysis computes a range for each integer expression; where the range provably fits, it marks the operation unguarded. It is sound by construction: unknown means keep the check, and loop-carried variables are treated as unknown. Measured gain on our kernels is real but modest, and it does nothing for accumulators."),
    ("What does “verified” versus “guarded” mean?",
     "Both mean every replayed call matched. “Guarded” also means the function contains sites we cannot prove safe, such as integer addition that could overflow int64, which raises instead of wrapping. “Verified” has none of those."),
    ("Why a 1.1x threshold?",
     "Compiling a function does not make it faster if copying its arguments across the boundary costs more than it saves. We measure each function and keep it only if the median speedup is at least 1.1x. Below that it is “declined” and the number is shown."),
    ("What if the traced run does not cover a code path?",
     "Then that path is untested. Replay only checks the calls the program made (plus generated inputs, labelled). That is why the entry command should exercise the hot code, and why we call it differential testing."),
    ("Does it change my code?",
     "Not your folder. It works on a copy. In the copy, each accepted function gets one decorator line and the original body stays, so it is reversible, and if the compiled module cannot run, the Python body does."),
    ("Is it safe to run on unknown code?",
     "No. Tracing and replay execute your project. The server listens only on 127.0.0.1 and rejects foreign Host headers, but you should only run it on code you trust."),
    ("How does it find the hot functions?",
     "It runs your entry command with a tracer that uses <code>sys.monitoring</code> on Python 3.12 or later (<code>sys.setprofile</code> before that) and records calls and time per function. The ranker combines time share, eligibility and a predicted marshalling cost."),
    ("How does type inference work without an LLM?",
     "Four steps: observe runtime types by running the program once; collect evidence from assignments, calls and returns into a lattice until nothing changes; for parameters nobody calls, try plausible type combinations; then let the real type checker accept or reject the whole result. If anything is ambiguous, such as int on some paths and float on others, it refuses."),
    ("Did you use AI to build this?",
     f"Yes, and the repository says so: Claude (Opus 5.5 and Sonnet 5.5) and GitHub Copilot appear as co-authors on {F['ai_commits']} of {F['git']['commits']} commits, including the dictionary library. The product itself does not need an LLM to run. We are responsible for what we submit, and you should be able to explain any file you claim."),
    ("What does “the compiler is the judge” mean?",
     "The scanner does not keep a list of supported features. It extracts each function into a standalone module and runs the real parser and type checker on it. If it passes, the function is eligible. So when the compiler gains a feature, the scanner needs no change."),
    ("What are the time complexities?",
     "Lexing, parsing, type checking, lowering, interval analysis and emission are linear in the size of the unit. Inference iterates passes of linear cost until the lattice stops changing (it has finite height). The search tries at most 400 type assignments, each a full check. Build time is dominated by g++."),
    ("Why is the end-to-end speedup smaller than the per-function speedup?",
     f"Amdahl’s law: only the converted functions get faster. On TextLab, functions are 4x to 44x faster but the whole program is {D['textlab_e2e']}x, because the rest still runs in Python and the program has other costs."),
    ("What are the known bugs?",
     "Honest list: the snippet <code>coin_change</code> is refused (21 of 22 snippets); the grammar file is the v0.1 core and has not been regenerated for the later language; some fidelity-note text is stale (D8 still mentions <code>setjmp</code>); and STATUS.md lists three stress-harness cases found earlier that we did not re-investigate."),
    ("What would you do with another month?",
     "Bignum promotion and UTF-8 strings, zero-copy buffers, type-specialised versions so int-or-float functions convert, a VS Code extension, and a larger independent corpus with a comparison against Cython, mypyc and Codon so the novelty claim could become a paper."),
    ("Can I see it work?",
     "Yes. Section 10 is the demo script: it runs the app on a small public repository, shows the pipeline, one diff, and one function it correctly leaves alone, in under three minutes."),
]


def sec9(F, D):
    QA = make_qa(F, D)
    items = "".join(f'<div class="qa"><div class="q"><span class="n">{i}</span>{q}</div><div class="a">{a}</div></div>' for i, (q, a) in enumerate(QA, 1))
    return f"""
<section class="chap" id="s9">
<h1><span class="no">9</span>Likely viva questions, with short answers</h1>
<p>{len(QA)} questions. Learn the shape of each answer, not the words. Numbers are from this session’s runs (report, Appendix F).</p>
{items}
</section>
"""


def sec10(F, D):
    return f"""
<section class="chap" id="s10">
<h1><span class="no">10</span>Live demo script and backup plan</h1>
{D['demo_html']}
</section>
"""


GLOSSARY = [
    ("AST", "Abstract syntax tree: the program as a tree of statements and expressions."),
    ("Arena", "Memory region freed in one go when a library call ends."),
    ("Bidirectional type checking", "Synthesise a type from an expression, or check it against an expected type pushed inward."),
    ("Boundary / marshalling", "Copying values between Python objects and C++ objects when a compiled function is called."),
    ("DEDENT / INDENT", "Tokens the lexer invents when indentation decreases or increases."),
    ("Differential testing", "Run two implementations on the same input and compare their behaviour."),
    ("Divergence (D1 to D14)", "A place where C++ could behave differently from Python; each class has a mitigation."),
    ("Fidelity note / report", "A positioned record of one divergence; the report is the full list."),
    ("Guard", "A runtime check, for example for integer overflow."),
    ("Guard elision", "Removing a guard that analysis proves can never fire."),
    ("Hotspot", "A function where a program spends much of its time."),
    ("Interval analysis", "Tracking a (low, high) range for each integer expression."),
    ("IR / PIR", "Intermediate representation; PIR is our typed tree with explicit conversions."),
    ("Library mode", "Compiling functions into a Python extension module instead of a standalone program."),
    ("Lattice", "A set of types with a “join” that combines evidence; bool, int, float is a tiny one."),
    ("Off-side rule", "Block structure carried by indentation."),
    ("Oracle", "The test harness that compares compiled output to CPython’s."),
    ("pybind11", "A C++ library that builds Python extension modules."),
    ("Pratt parsing", "Expression parsing with a binding-power table."),
    ("PySub", "The typed Python subset PYTHIA compiles."),
    ("Replay", "Feeding recorded calls to both the original and the compiled function and comparing."),
    ("Splice", "Adding a decorator so the compiled function is used, keeping the original body."),
    ("Declined", "Compiled and measured, but not spliced because it was not at least 1.1x faster."),
    ("Translation validation", "Checking each translation, instead of proving the translator correct."),
]


def sec11(F, D):
    rows = "".join(f"<tr><td><b>{a}</b></td><td>{b}</td></tr>" for a, b in GLOSSARY)
    return f"""
<section class="chap" id="s11">
<h1><span class="no">11</span>One-page glossary</h1>
<table class="open gl"><tr><th style="width:28%">Term</th><th>Meaning</th></tr>{rows}</table>
</section>
"""
