# PYTHIA Studio: demo script

Tagline for the whole demo: **the LLM suggests, the compiler proves.** The LLM only ever rewrites Python into PySub (our typed subset). It never writes C++, and nothing is called verified until the compiled code has reproduced the recorded calls exactly.

UI labels below follow the layout in `prompt.md` section 3 and may shift slightly. Click targets are given as **bold names**. All numbers in this file were measured on the development machine (WSL2, CPython 3.14.4, g++ 15); the Hotspots list shows yours.

## 0. Before you go on stage (5 minutes, once)

```bash
python scripts/check_demo.py         # every demo function is in its intended class; prints CPython time shares
./scripts/smoke.sh --offline         # both demos end to end, no key, no network (about 15 minutes, run it once)
./studio.sh --offline                # cached LLM answers + prebuilt .so files
```

1. Open `http://127.0.0.1:8765/?presenter=1` in a 1080p window at 110% zoom, dark theme.
2. **Dry run once** (steps below), then note the job id in the status bar. If anything stalls on stage, open `http://127.0.0.1:8765/?presenter=1&job=<id>` and the whole run replays from its saved event log.
3. **Instant option:** on first start the app installs a saved, finished run of Quanta; click **Replay sample run** on the welcome screen (or open it under *Previous runs*) and it plays back from its event log in about a minute, identical every time. Browsing, diffs, journeys and benchmarks all work on it; Export asks you to run the demo for real (the sample carries no compiled modules). A full Quanta run takes about 3 minutes with the offline cache (trace 35 s, builds are cache hits, replay and benchmark about 2 minutes, two end-to-end runs 30 s each). For a live demo use the saved-job replay, or the 10-second `textlab` demo (**Demo projects** on the welcome screen, then *TextLab*, **Open**; or `{kind:"demo", name:"textlab"}` over the API).
4. With a key (`GROQ_API_KEY=... ./studio.sh`, free at console.groq.com, or `ANTHROPIC_API_KEY`) the same flow works online. The LLM answers in the offline cache were recorded from `openai/gpt-oss-120b` on Groq (provenance `recorded`), so online the pictures have the same shape and the text differs a little.
5. `python main.py --small` inside `demo/quanta` takes about 26 s under CPython 3.14 (32 to 38 s traced). Its output is deterministic: no clock, seeded LCG.

## 1. What the demo project is

`demo/quanta/`: **Quanta, a small analytics and simulation toolkit.** 3,772 lines of pure Python in 13 sub-packages (`sim`, `combinatorics`, `numtheory`, `text`, `graph`, `linalg`, `cluster`, `opt`, `signal`, `stats`, `io`, `util`, `cli`), a `pyproject.toml`, README, CHANGELOG, an argparse CLI with eleven sub-commands and 81 `unittest` tests that pass before **and** after acceleration. 24% of all lines (28% of the non-test code) sit in functions PYTHIA can use; the rest is the glue a real team writes: dataclasses, classes, I/O, closures, generators, `Optional`, `*args`, a guarded NumPy import.

`python main.py --small` runs seven jobs (simulation, puzzles, text, graph, linalg, optimisation, signals). Analysis result (offline run, 278 functions found, 123 of them methods, mostly the tests):

| Result | Count |
|---|---|
| accelerated (verified or guarded, replay matched, all faster) | 48 (3 verified, 45 guarded), geometric-mean 16x per function |
| LLM rewrite accepted and verified | 6 (+1 fixed by the LLM but then declined as slower) |
| annotated from the trace (no LLM) | 2 |
| declined | 5 measured below 1x, 3 predicted to lose that still measured above 1x, 30 cold (below 0.2% of runtime, not built) |
| not eligible, with a reason | 184 (123 of them methods of classes) |

CPython time shares (self time under the tracer; the 7 `job_*` functions are glue that call the kernels). Kernels together are **66 to 69%** of runtime, glue **31 to 34%**.

| Function (file under `quanta/`) | Intended | Actual | Share | Speedup | Why |
|---|---|---|---|---|---|
| `combinatorics/queens.py::count_queens` | win | guarded | 6.6-7.3% | 6.9x | backtracking, 3 bool tables; bounds checks on every access eat much of the gain |
| `sim/fractal.py::mandelbrot_row` | win | guarded | 4.0% | 31x | pure float escape-time loop |
| `sim/nbody.py::advance` | win | guarded | 3.9% | 19.6x | 7 `list[float]` mutated in place, written back after the call |
| `numtheory/collatz.py::longest_collatz` (+ callee `collatz_steps`) | win | guarded | 3.5% self / 4.2% cum | 26x | same-module callee compiled together |
| `linalg/spectral.py::spectral_norm` (+ `mult_av`, `mult_atv`) | win | guarded | 3.9% cum | 25x | power iteration, entries recomputed inline |
| `opt/routes.py::tour_length` | win | guarded | 3.0% | 4x | tiny lists, 167k calls: boundary cost eats most of the gain (modest win on purpose) |
| `graph/shortest.py::dijkstra_dense` | win | guarded | 3.0% | 6.4x | `list[list[int]]` 130x130 marshalled on each of 1,500 calls |
| `sim/montecarlo.py::estimate_pi` | win | guarded | 2.7% | 18x | inline LCG, `state * 1103515245` is trapped not wrapped |
| `text/distance.py::levenshtein` | win | guarded | 2.5% | 14-16x | two-row DP on `list[int]` symbol codes, 62k calls |
| `graph/shortest.py::floyd_warshall` | win | guarded | 2.2% | 19-20x | n^3 on an adjacency matrix |
| `numtheory/digits.py::digital_root_total`, `count_palindromes` | fixable (annotate) | guarded | 2.1%, 1.7% | 42x, 33x | **no annotations in the source**: observed types `int -> int` fill them in, no LLM |
| `cluster/kernels.py::assign_points` | win | verified | 1.9% | 18x | no int guards at all: fully exact |
| `linalg/dense.py::matmul` | win | verified | 1.7% | 29x | `list[list[float]]` x2 |
| `opt/dp.py::knapsack_01` | win | guarded | 1.5% | 27x | 1-D DP table |
| `numtheory/primes.py::sieve_primes` | win | guarded | 1.7% | 3.4x | the 400k-prime result list crosses the boundary |
| `opt/dp.py::grid_min_path` | **fixable (LLM)** | guarded | 1.0% | 11.5x | `row[:]`, ternaries, 3-argument `min`: rewritten in 1 attempt |
| `sim/life.py::life_population` | **fixable (LLM)** | guarded | 0.9% | 2.5x | comprehensions, `sum(genexpr)`, chained comparison: **attempt 1 rejected by the parser, attempt 2 passes** |
| `opt/dp.py::longest_increasing_subsequence` | fixable (LLM) | guarded | 0.7% | 13x | `[1] * n`, `max(list)` |
| `graph/traverse.py::bfs_levels` | fixable (LLM) | guarded | 0.55% | 2.8x | `[-1] * n`, `queue.pop(0)` |
| `signal/filters.py::exp_smooth` | fixable (LLM) | guarded | 0.4% | 2.4x | `enumerate`, slicing, ternary |
| `stats/descriptive.py::weighted_moments` | fixable (LLM) | guarded | 0.26% | 9.4x | `zip`, tuple loop. See the viva note: the rewrite is not equivalent on mismatched list lengths and replay never saw that input |
| `text/kmers.py::kmer_counts` | fixable (LLM) | **declined, 0.30x** | 0.9% | below 1x | the rewrite is valid and replays 250/250, but a `dict[str,int]` in the runtime is a linear scan and strings are copied: slower than CPython, so it is not spliced |
| `stats/drift.py::tail_variance` | boundary | **declined, 0.45x** | 0.74% | below 1x | a growing 12,000-float list marshalled for 143,232 calls, 24 samples of work each |
| `cluster/kernels.py::update_centroids` | win | declined, 0.16x | 0.21% | below 1x | nested lists copied in and out each call |
| `text/kmers.py::gc_content`, `longest_run` | win | declined, 0.35x and 0.74x | 0.3%, 0.2% | below 1x | 15,000-character strings marshalled 250 times |
| `opt/anneal.py::acceptance_probability` | boundary | declined (predicted) | 0.3% | probe 4.8x | the ranker predicted a loss from 144k scalar crossings; the probe measured a gain. A calibration miss, shown as is |
| `numtheory/primes.py::is_probable_prime` | win | declined (predicted) | 0.9% | probe 1.3x | 350k calls of a tiny function; it still gets compiled inside `prime_square_sum` (11x) |
| 30 more kernels (`rolling_std`, `histogram`, `convolve`, ...) | win | declined, **cold** | below 0.2% each | not built | "Cold: 0.03% of the traced runtime". No build, no LLM call |
| `util/iterutil.py::make_decay`, `combine_counts`, `coerce_cell`, `first_peak`, `chunked` | n/a | not eligible | small | n/a | closure, `*args`, function held in a variable, `Optional`/`Tuple`, generator |
| `linalg/accel.py::*` | n/a | not eligible | ~0 | n/a | reads module-level `np` (guarded NumPy import) |
| `text/corpus.py::*`, `sim/events.py::exponential`, `stats/resample.py::bootstrap_means`, `linalg/builders.py::random_matrix` | n/a | not eligible | 1.6% (`make_dna`) | n/a | "calls `.next_int()` on `rng`, an object of type `Lcg`": objects cannot cross into PySub |
| `io/csvio.py::read_table`, `io/jsonio.py::*`, `cli/*` | n/a | not eligible | 1-2% | n/a | file I/O, `with`, `csv`/`json`, cross-module callees, default arguments |
| `sim/events.py::simulate_queue`, `graph/sparse.py::*`, `text/index.py::*` | n/a | not eligible | 1.1% | n/a | `heapq`, constructs classes, module-level regex, `Counter` |
| 123 methods (`Lcg.*`, `Graph.*`, `SpellChecker.*`, `Test*.test_*`) | n/a | not eligible | glue | n/a | method of class: v1 analyses module-level functions only |

**End to end** (`python main.py --small`, same stdout hash before and after, `python -m unittest` green in the exported project):
about **26 s -> 5.7 s, 4.4 to 5.0x** across three runs (25.0 -> 5.6, 27.4 -> 5.7, and 4.95x in the last recording run). The ceiling is Amdahl: roughly a third of the time is glue that stays in Python, plus the declined and low-speedup kernels. That honest ceiling is a good talking point.

`demo/textlab/` stays as the 10-second demo (480 lines, 10 accelerated functions, 2 LLM-fixed, `window_energy` declined at 0.2x, 9.1 s -> 1.6 s = 5.7x).

## 2. The 3-minute script

| Time | Click | Say |
|---|---|---|
| 0:00 | Welcome screen. Point at the four cards, then click **Open demo project** (bottom). | "A stranger gets a Python project: a 3,800-line analytics toolkit, simulation, graphs, text, linear algebra, its own CLI and tests. Four ways in: folder, GitHub URL, dropped file, playground. I'll use the bundled demo." |
| 0:15 | In the run dialog check **Trace command** = `python main.py --small`, **Offline** on, **Presenter mode** on. Press **Run** (Ctrl+Enter). | "We give it an entry command so it can watch the program run. Offline means cached LLM answers recorded from a real model; everything else is real: real compiler, real C++ build, real replay." |
| 0:25 | Watch the **pipeline stepper**. As **Ingest** and **Scan** complete, read the captions. | "Scan parses every function and runs our real typechecker on each: 278 functions, about 90 that pass or can be fixed, 184 that can never be compiled, each with its reason." |
| 0:40 | **Trace**: calls count up (1.3 million) and the sorted profile bars grow. | "It runs `main.py` under a sys.monitoring tracer: call counts, time, observed types, and it samples real argument/return pairs. Those samples become the proof obligations later." |
| 0:55 | **Rank**: open the score breakdown, hover one row. | "Time share times eligibility times expected benefit, minus a boundary penalty. Look at the spread: `count_queens` 7%, `mandelbrot_row` 4%, `advance` 4%, ten more between 1 and 4%. The seven `job_*` functions at the top are glue: not eligible, but they show where the kernels are called from." |
| 1:05 | **Fix** starts. Agent panel: `life_population`, "typechecker rejected: list comprehension, `sum()`, generator expression". Pause with **Space**. | "Seven functions need help: comprehensions, `zip`, `pop(0)`, ternaries. Two more only lack annotations; those are fixed from the trace, no LLM. The rewrite is the only thing the model does. Watch what the checker does to its first answer." |
| 1:15 | Press **right arrow**: attempt 1 red (`expected ')' but found ','`), attempt 2 green. | "Attempt 1 kept a generator-style loop the parser can't read; the error goes back to the model, attempt 2 passes. The compiler is the judge, not the model." |
| 1:30 | In **Hotspots** open the journey of **`life_population`**. Expand Original, Observed types, Eligibility, Rewrite attempts, Final PySub, Tokens, AST, Typed AST, PIR, C++. About 3 s each. | "Original, what we saw at runtime, why it was rejected, the retry, the PySub, then our phases: tokens, AST, typed AST, IR with fidelity notes, C++." |
| 1:55 | Keep scrolling: **wrapper**, **build**, **oracle replay**, **benchmark**, **splice**. | "Built into a pybind11 module, then the proof: the recorded calls replayed through Python and C++, floats compared bitwise, exceptions by class. 50 of 50 match; 2.5x. Compare `mandelbrot_row`: 31x, nothing needed rewriting." |
| 2:10 | Open the **diff**; toggle **three-way view**; hover a gutter mark. | "The original function is untouched, a one-line decorator is added, and the shim falls back to Python if the `.so` is missing. Gutter colours are fidelity: green exact, amber guarded." |
| 2:25 | Hotspots: **`tail_variance`** (chip **Declined**), then **`kmer_counts`**. | "Two refusals. `tail_variance` compiles and replays fine but it is called 143,000 times on a list of thousands to do 24 samples of work; crossing the boundary measured 0.45x. And `kmer_counts` is the interesting one: the LLM rewrote it correctly, 250 of 250 replays match, and it is still slower, 0.30x, because strings and a string-keyed dict are expensive in our runtime. So it is not spliced. Proof is necessary, speed is measured." |
| 2:40 | Bottom panel: **Benchmarks**. Log-scale bars, then end-to-end. | "Per function Python vs C++ on a log scale, from 0.16x to 100x, and the number that matters: the whole program 26 seconds before, 5.7 after, output identical." |
| 2:50 | Summary card: **Export**, tick zip. Mention `PYTHIA_REPORT.md`, `build_accel.sh`. **Accept all** first (Ctrl+Shift+A). | "Export the project with the report and a script that rebuilds the `.so` anywhere. The exported project's 81 unit tests pass unchanged." |

If you are ahead of time, run `python main.py --small` and `python -m unittest` in the exported folder.

## 2b. Bonus minute: any Python program in the Playground

Use this when someone asks "does it work on *my* code?". It shows the whole thesis in one screen.

1. **Playground** (`{ }` in the activity bar) → **Examples…** → *Student grade manager*. It is ordinary beginner Python: a global list of dicts, `enumerate`, `max(key=lambda ...)`, `sort(key=..., reverse=True)`, f-strings and `input()`. The header shows typechecker errors, and the banner says "This is regular Python, not PySub yet."
2. **Convert to PySub with AI.** "The model gets the program, the PySub rules and the exact errors. Our type checker judges every answer." The answer typically comes back in 3 to 6 s on Groq's free tier: dicts became a `Student` class, the global list became a parameter, and `sort(key=...)` became a stable insertion sort. Show the diff.
3. **Use the PySub version**, then **Run**. The stdin box already holds a scripted session (add students, a bad number, out-of-range marks, search, topper, sort). "Left: the ORIGINAL program under CPython. Right: the conversion compiled to C++. Same input." The green line reads "Identical: the conversion behaves exactly like your original program."
4. The honest punchline: "It is not faster. This program waits on input, so the native binary's start-up dominates. Compiling pays off on compute, which is what the Studio's ranking finds." Then switch to the *Prime sieve* example to show a real speedup.

## 3. The 30-second version

1. (0:00) **Open demo project**, Presenter mode on, **Run**. "A 3,800-line Python project in, we trace it to find the hot functions."
2. (0:10) Space on the Fix stage, right arrow through `life_population`: attempt 1 rejected, attempt 2 passes. "The LLM only rewrites into PySub; our typechecker is the judge."
3. (0:18) Open its journey, jump to replay: "50 of 50 recorded calls match, then C++, then speedup."
4. (0:24) **Benchmarks**: "Whole program 26 s to 5.7 s, identical output. And it declined `tail_variance` and `kmer_counts` because the boundary would have made them slower."

## 4. Viva: Tokens, AST, Typed AST, PIR for `levenshtein`

Open the journey of `levenshtein` (`quanta/text/distance.py`, 18 lines of PySub after docstring stripping) and walk the nodes. The source, with the lines used below:

```
 4    prev: list[int] = []
 9    for i in range(1, n + 1):
11        for j in range(1, m + 1):
12            cost: int = 1
13            if a[i - 1] == b[j - 1]:
14                cost = 0
15            cur[j] = min(min(prev[j] + 1, cur[j - 1] + 1), prev[j - 1] + cost)
```

**Tokens** (hand-written lexer, `pythia/lexer.py`): 219 tokens for the whole function. Line 12 becomes `NAME(cost) OP(:) NAME(int) OP(=) INT(1) NEWLINE`. The lexer implements Python's off-side rule: leading whitespace turns into explicit `INDENT`/`DEDENT` tokens, so the parser can use an ordinary block grammar. `range`, `in`, `None`, `try`... are keywords, which is why `for ... in range(...)` parses straight into a loop node. Longest-match operators (`**=` before `**` before `*`).

**AST** (recursive descent for statements, Pratt parser for expressions, `pythia/parser.py`): 117 nodes. The body is annotated `Assign` nodes, `ForRange` nodes and one `Return`. Line 15 is `Assign(target=Subscript(cur, j), value=Call(min, [Call(min, [BinOp(+, Subscript(prev, j), 1), BinOp(+, Subscript(cur, j-1), 1)]), BinOp(+, Subscript(prev, j-1), Name cost)]))`. Say: precedence comes from binding powers (`*` 8 beats `+` 6 beats comparisons 4 beats `and`/`or`), `**` is right associative, and panic-mode recovery means one run reports several syntax errors. Note `min` takes exactly two arguments in PySub, which is why the source nests it; the 3-argument `min` in `grid_min_path` is one of the things the LLM had to rewrite.

**Typed AST** (`pythia/typecheck.py`): every expression carries a static type: `a[i - 1]` is `int`, `a[i - 1] == b[j - 1]` is `bool`, the whole of line 15 is `int`. Bidirectional checking; locals need no annotation because the first binding fixes the type, rebinding to another type is an error ("variable 'value' was inferred as str; cannot rebind to int"); the only implicit conversion is bool to int to float; function bodies are closed, module globals are invisible (the analyzer inlines literal constants such as `MODULUS` in `coin_ways`). This is the stage that rejects `life_population` in the fixable story.

**PIR and fidelity** (`pythia/lower.py`, `pythia/optimize.py`): lowering makes every implicit coercion an explicit `Coerce` node (none are needed in `levenshtein`, everything is `int`; for a visible one type `def g(i: int) -> float:` / `return i + 0.5` in the Playground and watch `i` get wrapped in `Coerce(int to float)`) and records a **Semantic Fidelity Report**: 19 notes here, 11 **D1** `+`/`-` sites (amber, guarded), 7 **D5** indexing sites (green, exact) and the global D7 note. Guard elision runs an interval analysis: `0 of 11` guards are removed because the bounds come from `len()` and parameters, which are unknown. To see it working paste into the **Playground**:

```python
def f(n: int) -> int:
    total: int = 0
    for i in range(100):
        y: int = i * i + 7
        total = total + n
    return y + total
```

`i * i + 7` is proven to be at most 9808 so both guards are removed (2 of 4); `total + n` and `y + total` stay guarded because `n` is a parameter. Another real example: `dft_power` in `signal/spectrum.py` has 8 of 9 guards elided because all its integer arithmetic is on `range` variables.

**C++** (`py_add_i64`, `PyListI64_get/set`): the generated loop (83 lines for `levenshtein`) is a plain `for` with Python's `range` semantics, every list access goes through the runtime so negative indices and `IndexError` behave like Python, and `+`/`-` call overflow-checked helpers that raise `OverflowError` instead of wrapping.

### Likely questions and crisp answers

**What are D1 to D9?** Divergence classes, places where a C++ image of Python could silently differ, each reported with a mitigation. D1 unbounded int vs int64 (guarded: overflow raises `OverflowError`, never wraps). D2 floor division rounds toward minus infinity (exact). D3 modulo sign follows the divisor (exact). D4 `/` always returns float (exact). D5 negative indexing and bounds checks (exact: same `IndexError`). D6 `int ** negative int` yields a float in Python (the one **divergent** class: reported, not hidden). D7 object lifetime: the runtime never frees outside library mode (guarded). D8 exception propagation across calls (exact, via setjmp/longjmp handler stack). D9 class fields zero-initialised before `__init__` (guarded). Severity colours the gutter: exact green, guarded amber, divergent red.

**Why does interval analysis let you drop a guard, and is that safe?** A guard only needs to exist where overflow is possible. A forward pass computes a conservative `[lo, hi]` for every int expression and removes the guard only if the result provably stays within +/-2^62, which leaves two bits of headroom. Anything loop-carried, read from a parameter or returned from a call is "unknown" and keeps its guard. It may be incomplete (keeps guards it did not need), it must never be wrong.

**Why can the LLM not break correctness?** Three independent gates, none of which trusts the model. (1) Its output must be valid PySub and pass our typechecker, otherwise the error goes back to it (3 attempts, then the function is marked not eligible). (2) The C++ comes from our deterministic transpiler, not from the model. (3) The compiled function must reproduce up to 500 recorded real calls: return values (floats bitwise), exception class, and post-call state of list/dict arguments. A mismatch auto-rejects the function and shows the first counterexample. At run time the splice layer falls back to the original Python if the `.so` is missing or an input cannot be represented (`FallbackError`).
**Be honest about the limit, with a real example:** the recorded rewrite of `weighted_moments` uses index loops where the original uses `zip`. On equal-length lists (all that the program ever passes) it matches 140 of 140 calls; on lists of different lengths `zip` silently stops early and the rewrite raises `IndexError`. Replay is testing on observed inputs, not a proof of equivalence. `scripts/check_demo.py` prints this as a note. That is why fidelity classes and overflow traps exist and why the original function stays in the file.

**What is the boundary cost and how do you predict it?** Calling compiled code means copying arguments into runtime containers and copying results back (copy semantics, write-back for mutated lists): O(size of arguments) per call. If a call does little work per element the copy dominates: `tail_variance` is 143,000 calls on lists averaging 1,200 elements for 24 samples of work. The ranker multiplies trace share by expected benefit and subtracts a penalty that grows with `avg_arg_elems` and call count; for a declined function the pipeline still builds and times a probe so the number on screen is measured. The probe can also disagree with the prediction: `acceptance_probability` was predicted to lose (144k scalar crossings) and measured 4.8x faster. We show both numbers.

**Why is `kmer_counts` slower after a correct rewrite?** Compiling is not free speed. The runtime copies every `str` into its own string type and `dict[str,int]` is a linear scan over keys, where CPython hashes. The benchmark catches it (0.30x) and the function is never spliced.

**Why do some kernels say "Cold"?** With a trace in hand, functions below 0.2% of the traced runtime get no build and no LLM call: 30 of Quanta's eligible functions. Otherwise every small helper in a real project would cost a 4-second build, and every glue function with an f-string an LLM call.

**What is the memory model (D7)?** The original runtime never frees. In library mode every wrapper opens an arena after marshalling the arguments and frees everything allocated during the call once the result has been copied back, so long-running Python processes do not leak.

**What are the limits of PySub (1.1)?**
- **Types:** `int float bool str`, `list[T]` up to two levels (including lists of your own classes), `dict[int|str, scalar]`, and classes with typed fields and an `__init__`.
- **Statements:** `if/while/for-range/for-each`, `try/except` with seven named exceptions (including `EOFError`), and `raise`.
- **Supported since 1.1:**
  - f-strings with format specs, `input()` and `print(sep=, end=)`
  - the common `str` methods (`strip`, `split`, `join`, `replace`, `find`, …) and `list` methods (`pop(i)`, `insert`, `remove`, `index`, `count`, `sort(reverse=)`, …)
  - `sum`, `sorted`, `round`, `format`, and `min`/`max` of many values or of a list
  - `if __name__ == "__main__":`
- **Still out:**
  - tuples, sets, comprehensions, generators, lambdas, closures and slices
  - `zip/enumerate/ord`, `key=` arguments, default arguments, `*args` and imports
  - strings are ASCII
- **Scoping:** module variables are invisible inside functions, so state is passed as parameters.
- **Classes and methods** can be used inside compiled code but cannot cross the Python/C++ boundary.
- **Everything else** is the LLM's job to rewrite (per function in the Studio, whole programs in the Playground), or it stays Python.

**Can it handle an ordinary program, not just numeric kernels?** Show the Playground's *Student grade manager*. The AI rewrites dicts into a class and the global list into a parameter. The type checker accepts it, and the compiled program's output is byte-identical to the original under CPython on a scripted session that includes invalid input. Point out that the run compares against the *original* source: if the model had changed behaviour (say, an unstable sort reordering tied marks), the diff would show it in red. We found exactly that case while building it, and the prompt now asks for a stable insertion sort.

**Why do exception messages match CPython exactly?** Three things make them match:
- **CPython wording changes by version.** 3.12 says `integer division or modulo by zero`, 3.13 says `integer modulo by zero` for `%`, and 3.14 says `division by zero`.
- **The runtime follows the comparing interpreter.** It uses the wording of the CPython minor version that runs the comparison: CLI programs get it from the compiling interpreter, and extension modules from `PY_MINOR_VERSION`.
- **Reprs match too.** `KeyError` carries `repr(key)`, and `ValueError` carries `repr` of the bad string.

`tests/positive/t19_error_messages.py` checks all of it, so the oracle is 19/19 on Python 3.13 (Windows) and 3.14 (Linux).

**Why does `levenshtein` take `list[int]` and not `str`?** Because strings are the slow path in the runtime (single-character indexing allocates). A str-based version measured 1.0 to 1.6x, the code-list version 14 to 16x. The caller encodes once with `[ord(c) for c in word]` (in a method, which is glue). It is a real design lesson the tool surfaces.

**Why not just Cython or Numba?** Different goal: source-visible, auditable output (read the C++), a written fidelity contract per construct, a replay oracle and splice that preserves the original, and a pipeline whose stages (tokens, AST, typed AST, PIR) are inspectable. It is a compiler course project first and a product second.

**What does a rejected function look like in the UI?** `exponential` ("calls `.next_float()` on `rng`, an object of type `Lcg`"), `coerce_cell` ("calls `convert`, a function held in a variable"), `make_decay` (closure), `matmul_fast` (reads module-level `np`), `read_table` (constructs a class, uses `with`), `Graph.shortest_paths` (method of a class). The journey stops at Eligibility and the greyed nodes after it carry the same reason text.

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| Fixer shows "disabled" | You are not in offline mode and have no key. Settings → paste a free Groq key → Test & save, or restart with `./studio.sh --offline`, or set `GROQ_API_KEY` / `ANTHROPIC_API_KEY` (a `.env` file in the repo root works). |
| Playground conversion is slow or fails | Groq's free tier is rate-limited; press **Try again** after a few seconds. For a guaranteed demo, rehearse once: the converted program stays in the editor (it is saved in the browser). |
| Offline run says "no cached reply" for a rewrite | The cache key hashes the function source, so editing a Quanta kernel invalidates its entry. Re-record: `./scripts/record_offline_cache.sh` (needs a key, about 12 minutes, free Groq tier is enough). |
| Builds take about 4 s each | First run without `demo/offline_cache/so/` (or after a compiler upgrade; the snapshot is for g++ 15 on x86-64 Linux/WSL, others rebuild locally from source). |
| Trace times out | The Quanta budget is 240 s (the run dialog value is raised to it). For a slow machine use `--small` and a bigger **Timeout**. |
| Clone repository path | `./scripts/make_demo_repo.sh` prints a `file://...` URL; paste it into the **Clone repository** card. |
| Wi-Fi / projector hiccup | Replay the saved job: `?presenter=1&job=<id>`. |
| Re-record the cache with a real model | `GROQ_API_KEY=... ./scripts/record_offline_cache.sh`, then commit `demo/offline_cache/`. |
| Headless sanity check | `./scripts/smoke.sh --offline` (both demos; asserts at least 6 accelerated, 3 LLM-fixed, 1 measured decline, 3 not eligible, end-to-end at least 2x with identical output, and `python -m unittest` green in the exported Quanta). |
