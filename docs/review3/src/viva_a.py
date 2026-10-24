"""Viva guide, part A: sections 1-4 (HTML strings)."""
from fig_common import FIG


def sec1(F, D):
    sp = F["bench_median"]
    return f"""
<section class="chap" id="s1">
<h1><span class="no">1</span>PYTHIA in 60 seconds</h1>
<p class="lead">PYTHIA speeds up the slow parts of your Python project, and it <b>proves</b>, using your own program's calls, that the fast version gives the same answers as the original.</p>

<h2>The problem</h2>
<p>Python is easy to write and slow to run. Loops that add numbers, compare strings or fill tables can be 10 to 100 times slower than the same loop in C++.</p>
<p>People fix this in four ways: rewrite the code in C++, learn a special dialect (Cython), use a JIT (Numba, PyPy), or ask ChatGPT to translate it. Every one of these either costs a second codebase or gives you <i>no evidence</i> that the fast version behaves like the old one.</p>

<h2>What we built</h2>
<p>Two things, one inside the other.</p>
<ul>
<li><b>PYTHIA, the compiler.</b> It reads a typed subset of Python (we call it <b>PySub</b>) and writes readable C++17. This is what you built in Reviews 1 and 2.</li>
<li><b>PYTHIA Studio, the app.</b> You give it a snippet, a file, a folder or a GitHub link. It finds the slow functions, works out their types, converts them, compiles them, checks them against real Python, and swaps them in. You see every step and every diff.</li>
</ul>

<h2>What is special</h2>
<div class="cards">
<div class="card"><h4>Verified</h4><p>Each converted function is run against CPython on the calls your program really made. Different answer? It is thrown away automatically.</p></div>
<div class="card"><h4>Fidelity Report</h4><p>A list of every spot where Python and C++ could behave differently, with the line number and what we did about it.</p></div>
<div class="card"><h4>Whole project</h4><p>Point it at a repo. It scans, ranks, converts what it can, and tells you in plain English why it left the rest.</p></div>
<div class="card"><h4>No LLM needed</h4><p>Types are worked out by our own code. Same input, same output, free, works offline.</p></div>
<div class="card"><h4>Readable</h4><p>The C++ is something a person can open and read. The app shows it next to your Python.</p></div>
</div>

<div class="say"><span class="tag">Say it</span><b>One-line pitch.</b> “PYTHIA is a compiler plus an app that makes the slow parts of a Python project faster, and proves on your own program’s calls that the fast version is correct.”</div>

<h2>The 60-second version, out loud</h2>
<p class="script">Python is slow on loop-heavy code. The usual fixes cost you a rewrite, or they ask you to trust a black box. PYTHIA takes an ordinary Python project, runs it once to see where the time goes, converts the hot functions to C++17 using our own type inference, and then replays the function’s real calls through both versions. If even one answer differs, the conversion is rejected. What survives is spliced in behind a one-line decorator, so the original code is still there. On our benchmark kernels the C++ is a median of {sp:.0f} times faster, and every output matches CPython. It is a compiler, so we built every phase: lexer, parser, type checker, lowering, optimiser and emitter. Where Python and C++ can differ, PYTHIA says so, line by line.</p>

<h2>Numbers to remember</h2>
<table class="nums">
<tr><td class="big">{F['oracle_pos'][0]}/{F['oracle_pos'][1]}</td><td>valid programs where compiled output equals CPython’s (the oracle)</td></tr>
<tr><td class="big">{F['oracle_neg'][0]}/{F['oracle_neg'][1]}</td><td>invalid programs correctly rejected, each with the right message</td></tr>
<tr><td class="big">{F['basics'][0]}/{F['basics'][1]}</td><td>everyday untyped programs converted <i>without any LLM</i> and matching CPython</td></tr>
<tr><td class="big">{F['snippets'][0]}/{F['snippets'][1]}</td><td>LeetCode-style snippets (one is refused on purpose: <code>coin_change</code>)</td></tr>
<tr><td class="big">14</td><td>divergence classes (D1 to D14), {F['fid_total']} positioned notes across the corpus</td></tr>
<tr><td class="big">{sp:.0f}x</td><td>median speedup on our ten fixed kernels (nine kernels {F['bench_min_ex']:.1f}x to {F['bench_max']:.1f}x; one dictionary kernel is about {1/F['bench_dict']:.0f}x <i>slower</i>)</td></tr>
{D['numbers_row']}
</table>
</section>
"""


def sec2(F, D):
    return f"""
<section class="chap" id="s2">
<h1><span class="no">2</span>The whole flow, one function at a time</h1>
<p class="lead">We follow one real function, <code>{D['fn_name']}</code> from <code>{D['repo_name']}</code>, through every stage. Everything below is real output from the app, not a mock-up.</p>
{D['journey_html']}
</section>
"""


def sec3(F, D):
    return f"""
<section class="chap" id="s3">
<h1><span class="no">3</span>What changed since Review 2, and why</h1>
<p>At Review 2 you could type a PySub program and get C++ out. It worked: 17 valid programs matched CPython, 20 invalid ones were rejected, and we had added the dictionary and set libraries and moved from C11 to C++17.</p>
<p>But think about who would use that. Nobody has a PySub program. They have a Python project that is a bit slow. So we asked: <i>what would a real developer need?</i></p>
<ol class="steps">
<li><b>Find the slow parts.</b> Run the program once under a tracer and rank functions by time. (Trace and Rank stages.)</li>
<li><b>Work out the types.</b> Real code has no annotations, so we infer them ourselves from what the tracer saw and from how values are used. (Fix stage.)</li>
<li><b>Prove it still works.</b> Replay the real calls through both versions and compare. (Verify stage.)</li>
<li><b>Put it back without breaking anything.</b> Add one decorator line and keep the original function; if the fast version cannot run, Python runs. (Splice stage.)</li>
<li><b>Show everything.</b> A desktop app that displays each stage, the diff and the fidelity notes, installable with one click.</li>
</ol>
<div class="fig"><img src="{FIG.as_uri()}/fig_whatchanged.png"><div class="cap"><b>Figure 3.1.</b> Review 2 (top) and Review 3 (bottom). “Reused” means the compiler core carried over; everything marked “new” is Review 3 work.</div></div>
<div class="warn"><span class="tag">Be ready</span><b>We dropped the WebAssembly back end.</b> It was promised for Review 3. A second back end would show retargetability but would not help a developer speed up a Python project, and the time went into the Studio pipeline. Say this first, before they ask. Also say: the compiler’s IR is language-agnostic after the front end, so adding it later is an addition, not a rewrite.</div>
<p><b>Other targets that moved:</b> the positive oracle corpus is {F['n_pos']}, not 120 (we added an independent {F['n_basics']}-program gate, snippets and a generator instead); memory is reclaimed per call in library mode but standalone binaries still never free memory.</p>
</section>
"""


def sec4(F, D):
    S = D["studio_notes"]
    def member(color, name, reg, own, built, hard, feeds, evidence, studio):
        return f"""
<div class="member" style="--c:{color}">
<div class="mh"><span class="dot"></span><h3>{name}</h3><span class="reg">{reg}</span></div>
<div class="grid2">
<div><h5>What they own</h5><p>{own}</p><h5>What they built</h5><ul>{''.join(f'<li>{x}</li>' for x in built)}</ul></div>
<div><h5>Hardest problem they solved</h5><p>{hard}</p><h5>How it feeds the next person</h5><p>{feeds}</p>
<h5>Git evidence</h5><p class="small">{evidence}</p></div>
</div>
<div class="proposed"><span class="tag">You explain this in the viva (proposed, agree it first)</span>{studio}</div>
</div>"""
    ms = [
        member("#2563eb", "Vishal Vivek", "24BCE2377 · team lead",
               "The <b>front end</b>: grammar, lexer, parser, AST, diagnostics; the command line, the repository and integration.",
               ["<b>Lexer</b> with the off-side rule: turns indentation into INDENT and DEDENT tokens.",
                "<b>Parser</b>: recursive descent for statements, Pratt for expressions, panic-mode error recovery.",
                "<b>AST</b> nodes (every node has line, column and a type slot).",
                "Review 3: the whole <b>Studio</b> engine, server, web app, packaging, and merging parallel work."],
               "Panic-mode recovery. The parser’s <code>synchronize()</code> must always eat at least one token, or a parser parked on a bad token calls it forever. The code comment explains the bug. Also: merging eight parallel feature branches that all touched the same few dispatch functions without breaking the oracle.",
               "The parser hands an <b>AST</b> to the type checker. If the AST were wrong or missing positions, Rujuta’s error messages would point at the wrong line.",
               f"138 of {F['git']['commits']} commits are under the owner’s name, including every Studio commit and all merges. The Review 1/2 front-end files arrive in the first commit (<code>84f1251</code>), so git cannot split Review 1 work between people; ownership of those files follows the Review 1 matrix and each file’s “Owner:” header.",
               S["V"]),
        member("#059669", "Rujuta Mangesh Kulkarni", "24BDS0459",
               "The <b>type system</b>: symbol table, scopes, the bidirectional type checker, local inference, the negative test corpus, and dictionary support.",
               ["<b>Type checker</b>: types every expression, keeps one type per variable, widens bool, int, float.",
                "<b>Negative corpus</b>: 88 invalid programs, each with an <code>expect:</code> marker for the message it must produce.",
                "<b>PyDict</b>: a Python-compatible dictionary runtime (merged as pull request #2)."],
               "Typing things that have no type yet. <code>xs = []</code> cannot be typed alone, but <code>xs: list[int] = []</code> can, because the expected type is pushed inward. That is what “bidirectional” means.",
               "The type checker puts a type on every AST node. Jahnavi’s lowering pass reads those types to decide where a conversion or a guard is needed.",
               "Pull request #2 (merged as <code>079bcb5</code>) added <code>runtime/pydict.hpp</code> (351 lines), a 20-case C++ test and five documents. Its commits are authored as “Copilot”, so say plainly that an AI assistant helped write the dictionary library. The type checker itself is in the first commit.",
               S["R"]),
        member("#d97706", "Koliparthy Venkata Jahnavi", "24BDS0132",
               "<b>Lowering and the runtime</b>: the divergence catalogue, the Semantic Fidelity Report, the <code>pyrt</code> runtime, guard elision by interval analysis, and PySet.",
               ["<b>Lowering</b>: makes every hidden Python conversion explicit and tags each risky spot.",
                "<b>Fidelity catalogue</b>: D1 to D14, each with a mitigation.",
                "<b>Interval analysis</b> (<code>optimize.py</code>): removes overflow checks that cannot fire.",
                "<b>PySet</b>: Python-compatible sets (pull request #3)."],
               "Being sound. The interval pass may <i>keep</i> a check it did not need, but must never <i>remove</i> one it did. Accumulators that feed back into themselves are widened to “unknown” before the loop body is analysed, so one pass is enough.",
               "Lowering gives Aaryan an IR in which every conversion is explicit, so the emitter never has to guess.",
               "Pull request #3 (merged as <code>4ef0102</code>): <code>runtime/pyset.hpp</code> (533 lines) and a 366-line test, authored by Jahnavi (<code>ddc975b</code>). <code>lower.py</code>, <code>optimize.py</code> and the C runtime are in the first commit.",
               S["J"]),
        member("#7c3aed", "Aaryan Gupta", "24BDS0134",
               "The <b>back end and the safety net</b>: the C++ emitter, the C11 to C++17 migration, the differential oracle, the program generator, CI, the corpus and the benchmarks.",
               ["<b>Emitter</b> (<code>emit_c.py</code>): walks the IR and writes C++17.",
                "<b>C11 to C++17 migration</b> (pull request #1, 4 September 2026).",
                "<b>Oracle</b>: runs CPython and the compiled binary, compares output byte for byte.",
                "<b>Generator and CI</b>: samples programs from the grammar; runs everything on every push."],
               "Making “same behaviour” measurable. The oracle compares stdout and the exception class; the negative suite checks the <i>message</i>, not just failure. On its first run the oracle found four bugs that manual testing had missed (Review 1, section 11.4).",
               "Aaryan’s oracle is the gate everyone else ships through. If a change anywhere breaks equivalence, the oracle names the program.",
               "Pull request #1 (merged as <code>086b6f8</code>): commit <code>9264cbb</code> “Migrate backend from C11 to C++17”, six files, +270/−48 lines. The emitter, oracle, generator and workflow files carry “Owner: Member 4” headers and are in the first commit.",
               S["A"]),
    ]
    return f"""
<section class="chap" id="s4">
<h1><span class="no">4</span>Who did what, and how it fits</h1>
<div class="warn"><span class="tag">Read first</span><b>What git can and cannot prove.</b> The first commit already holds the Review 2 code base, and the whole Studio (17 to 19 October) was committed under one name. So the split below for Reviews 1 and 2 follows the Review 1 responsibility table and the “Owner:” headers in the files; the split for the Studio work is a <b>proposal</b> that follows each person’s compiler phase. Agree it as a team before the viva, and be honest if asked how the Studio was built: with AI coding assistants, recorded as co-authors on {F['ai_commits']} of {F['git']['commits']} commits.</div>
<div class="fig"><img src="{FIG.as_uri()}/fig_handoff.png"><div class="cap"><b>Figure 4.1.</b> What each person hands to the next. Solid cards are Reviews 1 and 2; dashed cards are the proposed Studio split.</div></div>
{''.join(ms)}
</section>
"""
