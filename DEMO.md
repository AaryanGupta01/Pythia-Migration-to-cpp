# PYTHIA Studio: demo script

Tagline for the whole demo: **the LLM suggests, the compiler proves.** The LLM only ever rewrites Python into PySub (our typed subset). It never writes C++, and nothing is called verified until the compiled code has reproduced the recorded calls exactly.

UI labels below follow the layout in `prompt.md` section 3 and may shift slightly. Click targets are given as **bold names**.

## 0. Before you go on stage (5 minutes, once)

```bash
./scripts/make_demo_repo.sh          # local bare repo for the "Clone repository" card (prints a file:// URL)
python scripts/check_demo.py         # every demo function is in its intended class; prints CPython time shares
./studio.sh --offline                # cached LLM answers + prebuilt .so files, no network, no API key
```

1. Open `http://127.0.0.1:8765/?presenter=1` in a 1080p window at 110% zoom, dark theme.
2. **Dry run once** (steps below), then note the job id in the status bar. If anything stalls on stage, open `http://127.0.0.1:8765/?presenter=1&job=<id>` and the whole run replays from its saved event log.
3. With a real key (`ANTHROPIC_API_KEY=... ./studio.sh`) the same flow works online; the attempt/rewrite pictures are the same shape, the text will differ.
4. `python demo/textlab/main.py --small` takes about 10 s under CPython 3.14 (about 25 to 40 s when traced). Its output is deterministic: no clock, fixed LCG seeds.

## 1. What the demo project is

`demo/textlab/`: about 550 lines, a text and numerics workbench. `main.py --small` runs four stages (text, sim, ml, features). Numbers are from this machine; the Hotspots list shows yours.

| Function (file under `textlab/`) | Intended outcome | CPython time share | Expected speedup | Why |
|---|---|---|---|---|
| `edit_distance` (text/distance.py) | Guarded win | 14% | 4 to 10x | fuzzy de-dup; two short strings in, an int out; 15 D1 `+`/`-` sites stay guarded |
| `simulate_energy` (sim/nbody.py) | Verified win (no D1 sites) | 16% | 9 to 13x | n-body over `list[float]`, pure float math |
| `prime_square_sum` (features/primes.py) | Guarded win, has a callee | 5% | 10 to 12x | calls same-module helper `is_prime`, so the callee is compiled with it |
| `assign_clusters` (ml/kmeans.py) | Verified win (no D1 sites) | 10% | 9 to 19x | k-means assignment over `list[list[float]]` (two-level list) |
| `count_pairs` (text/bpe.py) | Guarded win, the modest one | 3% | about 2.5x | BPE pair counts; 60k ints in, 16k ints out, so marshalling eats most of the gain |
| `monte_carlo_pi` (sim/montecarlo.py) | Guarded win, the big one | 20% | 14 to 23x | inline LCG; `state * 1103515245` cannot be proven non-overflowing, so it is trapped, not wrapped |
| `knn_vote` (ml/knn.py) | Fixable: LLM retry story | 6% | 5 to 6x after rewrite | comprehension, generator, `zip`, `sorted`, tuple unpacking, `max(x)`; **attempt 1 is rejected, attempt 2 passes** |
| `life_generations` (sim/life.py) | Fixable: LLM | 7% | 5 to 10x after rewrite | tuple loops, ternary, `enumerate`, `[row[:]...]`, `sum` |
| `collatz_longest` (features/collatz.py) | Fixable: types from the trace | 8% | 5 to 27x after annotation | no annotations; observed types `int -> int` fill them in, no LLM needed |
| `window_energy` (signal/window.py) | **Declined (boundary cost)** | 7% | below 1x (about 0.4x probe) | compiles fine, but ~220k calls each marshal a 5000-float list for 128 multiply-adds: 3.5 us in Python vs about 50 us to cross the boundary |
| `normalize_rows` (ml/embed.py) | Not eligible | ~0% | n/a | reads module-level `np` (numpy, guarded import) |
| `make_lr_schedule` (ml/schedule.py) | Not eligible | ~0% | n/a | returns a closure (nested function) |
| `parse_number` (util/parse.py) | Not eligible | ~0% | n/a | `value` changes type str to int (dynamic typing) |
| `summarize` (util/parse.py) | Not eligible | ~0% | n/a | `*args` |
| `load_corpus`, `write_corpus` (text/corpus.py) | Not eligible | small | n/a | file I/O (`open`, `with`, `os.remove`) |
| `Vocab.train/merge`, `Rng.*`, `KMeans.*`, `CorpusBuilder.*` | Not eligible | ~5% (BPE merge) | n/a | methods of classes: v1 analyses module-level functions only |
| `main.py::*`, `energy_profile` | Not eligible | glue | n/a | cross-module callees / generator |

The six "win" rows together are about 68% of runtime, the three "fixable" rows about 21%. The end-to-end speedup is therefore capped by what stays in Python (Amdahl): expect roughly **2.5x** with only the wins and **about 4x** once the LLM-fixed functions are in. That honest ceiling is a good talking point.

## 2. The 3-minute script

| Time | Click | Say |
|---|---|---|
| 0:00 | Welcome screen. Point at the four cards, then click **Open demo project** (bottom). | "A stranger gets a Python project. Four ways in: folder, GitHub URL, dropped file, playground. I'll use the bundled demo, a 550-line text and numerics workbench." |
| 0:15 | In the run dialog check **Trace command** = `python main.py --small`, **Offline** on, **Presenter mode** on. Press **Run** (Ctrl+Enter). | "We give it an entry command so it can watch the program run. Offline means cached LLM answers, but everything else is real: real compiler, real C++ build, real replay." |
| 0:25 | Watch the **pipeline stepper** at the top of the editor. As **Ingest** and **Scan** complete, read the captions. | "Ingest copies the project, we never touch the original. Scan parses every function and runs our real typechecker on each: about 35 functions, a handful eligible as written." |
| 0:40 | Stepper reaches **Trace**: the stage inspector shows calls counting up and the sorted profile bars. | "Now it runs `main.py` under a sys.monitoring tracer: call counts, time, observed types, and it samples real argument/return pairs. Those samples become the proof obligations later." |
| 0:55 | **Rank**: click the stage to open the score breakdown. Hover one row. | "Score is trace share times eligibility times expected benefit, minus a boundary penalty. Ten hotspots between 3% and 20% each: this is where the time actually goes." |
| 1:05 | **Fix** starts. The right **PYTHIA agent** panel shows `knn_vote`: "typechecker rejected: loop over tuples, list comprehension, max() with 1 argument". Pause with **Space** here. | "Three functions need help: a comprehension, a ternary, no annotations. The rewrite is the only thing the LLM does. Watch what the checker does to its first answer." |
| 1:15 | Press **right arrow**. Attempt 1 appears red: `line 5: expected ')' but found 'for'`; then attempt 2 green. | "First attempt kept a generator expression: our parser rejects it, the error goes back to the model, second attempt passes the typechecker. The compiler is the judge, not the model." |
| 1:30 | Click the function **`knn_vote`** in **Hotspots** (activity bar) to open its **journey**. Expand nodes in order: Original, Observed types, Eligibility, Rewrite attempts, Final PySub, then Tokens, AST, Typed AST, PIR, C++. Spend about 3 s each; show the source-highlight link. | "This is that one function's whole path: original, what we saw at runtime, why it was rejected, the retry, the PySub, then our compiler phases, tokens, AST, typed AST, IR with the fidelity notes, and finally C++. Failed or skipped steps would be greyed out with the exact reason." |
| 1:55 | Keep scrolling: **wrapper**, **build**, **oracle replay**, **benchmark**, **splice**. Land on the replay node ("N/N matched") and the speedup. | "Built into a pybind11 module, then the proof: the recorded calls replayed through Python and through C++, floats compared bitwise, exceptions compared by class. N of N match. Then the benchmark." |
| 2:10 | Open the **diff** (button at the top of the journey, or double-click the function in the file tree). Toggle **three-way view**. Hover a coloured gutter mark. | "Cursor-style diff: the original function is untouched, a one-line decorator is added; the shim falls back to Python if the `.so` is missing. Three-way: Python, the PySub rewrite, the C++. Gutter colours are fidelity: green exact, amber guarded, red divergent. Hover shows the class and the mitigation." |
| 2:25 | Hotspots list: click **`window_energy`** (status chip **Declined**). Show the journey stopping at benchmark/splice. | "This is the one it refuses. It compiles and passes replay, but it is called 220,000 times on a 5000-element list to do 128 multiply-adds. Crossing the boundary costs more than the work: the probe measured below 1x. The ranker declined it before it could make your program slower." |
| 2:40 | Bottom panel: **Benchmarks** tab. Point at the log-scale bars, then the end-to-end before/after. | "Per-function Python vs C++ on a log scale, and the number that matters: the whole program before and after, output identical." |
| 2:50 | Agent panel summary card: **Export**. Pick a folder, tick zip. Mention `PYTHIA_REPORT.md` and `build_accel.sh`. Press **Accept all** first if some are still pending (Ctrl+Shift+A). | "Accept or reject per function, export the project with the report and a script that rebuilds the `.so` on any machine. Python in, verified faster Python out." |

If you are ahead of time, run `python main.py --small` in the exported folder and show the same output lines as the original.

## 3. The 30-second version

1. (0:00) **Open demo project**, Presenter mode on, **Run**. "Python project in, we trace it to find the hot functions."
2. (0:10) Space to pause on the Fix stage, right arrow through `knn_vote`: attempt 1 rejected, attempt 2 passes. "The LLM only rewrites into PySub; our typechecker is the judge."
3. (0:18) Open its journey, jump to the replay node: "N/N recorded calls match, then C++, then speedup."
4. (0:24) **Benchmarks** tab: "Whole program before and after, identical output. And it declined one function because the boundary cost would have made it slower."

## 4. Viva: Tokens, AST, Typed AST, PIR for `edit_distance`

Open the journey of `edit_distance` (27 lines of PySub after const-inlining) and walk the nodes. The source, with the lines used below:

```
12    for i in range(1, n + 1):
13        ca: str = a[i - 1]
15        for j in range(1, m + 1):
16            cost: int = 1
17            if ca == bc[j - 1]:
18                cost = 0
19            best: int = prev[j] + 1
```

**Tokens** (hand-written lexer, `pythia/lexer.py`). Line 13 becomes `NAME(ca) OP(:) NAME(str) OP(=) NAME(a) OP([) NAME(i) OP(-) INT(1) OP(]) NEWLINE`. Say: the lexer implements Python's off-side rule: leading whitespace turns into explicit `INDENT`/`DEDENT` tokens, so the parser can use an ordinary block grammar. `range`, `in`, `None`, `try`... are keywords (22 of them), which is why `for ... in range(...)` can be parsed straight into a loop node. Longest-match operators (`**=` before `**` before `*`).

**AST** (recursive descent for statements, Pratt parser for expressions, `pythia/parser.py`). The function body is five annotated `Assign` nodes, three `ForRange` nodes, then `Return`. Line 19 is `Assign(target=Name best, ann=int, value=BinOp('+', Subscript(Name prev, Name j), IntLit 1))`. Say: precedence comes from binding powers (`*` 8 beats `+` 6 beats comparisons 4 beats `and`/`or`), `**` is right associative, and panic-mode recovery means one run reports several syntax errors.

**Typed AST** (`pythia/typecheck.py`). Every expression node now carries a static type: `a[i - 1]` is `str`, `ca == bc[j - 1]` is `bool`, `prev[j] + 1` is `int`. Say: bidirectional checking; locals need no annotation because the first binding fixes the type, and rebinding to another type is an error ("variable 'value' was inferred as str; cannot rebind to int"); the only implicit conversion is bool to int to float; function bodies are closed, module globals are invisible (the analyzer inlines literal constants such as `MODULUS`). This is the stage that rejects `knn_vote` in the fixable story.

**PIR and fidelity** (`pythia/lower.py`, `pythia/optimize.py`). Lowering makes every implicit coercion an explicit `Coerce` node (none are needed in `edit_distance`, everything is already `int`/`str`; for a visible one type `def g(i: int) -> float:` / `return i + 0.5` in the Playground and watch `i` get wrapped in `Coerce(int to float)`) and records a **Semantic Fidelity Report**: for `edit_distance` that is 25 sites: 15 **D1** `+`/`-` (amber, guarded), 10 **D5** indexing (green, exact), plus the global D7 note. Then guard elision runs an interval analysis: `0 of 15` guards are removed here because the bounds come from `len()` and parameters, which are unknown. To show it working, paste this into the **Playground**:

```python
def f(n: int) -> int:
    total: int = 0
    for i in range(100):
        y: int = i * i + 7
        total = total + n
    return y + total
```

`i * i + 7` is proven to be at most 9808 so both guards are removed (2 of 4); `total + n` and `y + total` stay guarded because `n` is a parameter.

**C++** (`py_add_i64`, `PyListI64_get/set`, `pystr_index`): the generated loop is a plain `for` with Python's `range` semantics, every list access goes through the runtime so negative indices and `IndexError` behave like Python, and `+`/`-` call overflow-checked helpers that raise `OverflowError` instead of wrapping.

### Likely questions and crisp answers

**What are D1 to D9?** Divergence classes, places where a C++ image of Python could silently differ, each reported with a mitigation. D1 unbounded int vs int64 (guarded: overflow raises `OverflowError`, never wraps). D2 floor division rounds toward minus infinity (exact). D3 modulo sign follows the divisor (exact). D4 `/` always returns float (exact). D5 negative indexing and bounds checks (exact: same `IndexError`). D6 `int ** negative int` yields a float in Python (the one **divergent** class: reported, not hidden). D7 object lifetime: the runtime never frees (guarded). D8 exception propagation across calls (exact, via setjmp/longjmp handler stack). D9 class fields zero-initialised before `__init__` (guarded). Severity colours the gutter: exact green, guarded amber, divergent red.

**Why does interval analysis let you drop a guard, and is that safe?** A guard only needs to exist where overflow is possible. A forward pass computes a conservative `[lo, hi]` for every int expression (constants, `range` loop variables, results of `+ - *` on known intervals) and removes the guard only if the result provably stays within +/-2^62, which leaves two bits of headroom so a following operation cannot be the one that overflows. Anything loop-carried (accumulators), read from a parameter or returned from a call is "unknown" and keeps its guard. It may be incomplete (keeps guards it did not need), it must never be wrong. That is why `edit_distance` keeps all 15 and `i * i + 7` loses both.

**Why can the LLM not break correctness?** Three independent gates, none of which trusts the model. (1) Its output has to be valid PySub text and must pass our typechecker, otherwise the error goes back to it (3 attempts, then the function is simply marked not eligible). (2) The C++ comes from our deterministic transpiler, not from the model. (3) The compiled function must reproduce up to 500 recorded real calls: return values (floats compared bitwise), exception class, and post-call state of list/dict arguments. A mismatch auto-rejects the function and shows the first counterexample. At run time the splice layer falls back to the original Python if the `.so` is missing or an input cannot be represented (`FallbackError`, e.g. non-ASCII strings). Be honest about the limit: replay is testing on observed inputs, not a proof of equivalence, which is why fidelity classes and overflow traps exist and why the original function stays in the file.

**What is the boundary cost and how do you predict it?** Calling compiled code means copying arguments into runtime containers and copying results back (copy semantics, with write-back for mutated lists). That is O(size of arguments) per call. If a call does little work per element, the copy dominates: `window_energy` costs about 3.5 us in Python and about 50 us through the boundary because it marshals 5000 floats to read 128. The ranker multiplies trace share by expected benefit and subtracts a penalty that grows with `avg_arg_elems` (observed from the trace) relative to the work per call; for a declined function the pipeline still builds and times a probe so the number on screen is measured, not guessed.

**What is the memory model (D7)?** The original runtime allocates strings, lists and dicts and never frees them (fine for a short-lived CLI binary, flagged as D7). In library mode every wrapper opens an arena after marshalling the arguments and frees everything allocated during the call once the result has been copied back, so long-running Python processes do not leak. Outside library mode the behaviour is unchanged.

**What are the limits of PySub?** Types `int float bool str`, `list[T]` up to two levels, `dict[int|str, scalar]`, classes with typed fields and an `__init__`. Statements: `if/while/for-range/for-each`, `try/except` with six named exceptions, `raise`. No tuples, sets, comprehensions, generators, lambdas or closures, no slices, no `sum/zip/enumerate/sorted`, `min`/`max` take exactly two arguments, only `.append`/`.pop()`, `.get(k, d)`, `.upper/.lower`; no default arguments or `*args`; no imports; strings are ASCII; module globals invisible except literal constants. Classes and methods can be used inside compiled code but cannot cross the boundary. Everything outside the subset is the LLM's job to rewrite, or stays Python.

**Why not just Cython or Numba?** Different goal: source-visible, auditable output (read the C++), a written fidelity contract with a report per construct, a replay oracle and splice that preserves the original, and a pipeline whose stages (tokens, AST, typed AST, PIR) are inspectable. It is a compiler course project first and a product second.

**What does a rejected function look like in the UI?** `parse_number` (journey stops at Eligibility, reason: "variable `value` changes type from str to int"), `normalize_rows` ("reads module-level variable `np`"), `make_lr_schedule` (closure), `load_corpus` (file I/O), `Vocab.train` (method of a class). The greyed nodes after the stop carry the same reason text.

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| Fixer shows "disabled" | You are not in offline mode and have no key. Restart with `./studio.sh --offline`, or `export ANTHROPIC_API_KEY=...`. |
| Offline run says "no cached reply" for a rewrite | `python scripts/author_offline_cache.py` regenerates `demo/offline_cache/llm/` from `authored_rewrites.json`. The cache key hashes the function source, so re-run it after editing a demo function. |
| Builds take about 5 s each | First run without `demo/offline_cache/so/` (or after a compiler upgrade). Run once before the demo; the build cache then makes it instant. |
| Trace times out | Raise **Timeout** in the run dialog (default 60 s) or keep `--small`. |
| Clone repository path | `./scripts/make_demo_repo.sh` prints a `file://...` URL; paste it into the **Clone repository** card. |
| Wi-Fi / projector hiccup | Replay the saved job: `?presenter=1&job=<id>`. |
| Want to refresh the cache with a real key | `ANTHROPIC_API_KEY=... ./scripts/record_offline_cache.sh`, then commit `demo/offline_cache/`. |
| Headless sanity check | `./scripts/smoke.sh` (prints the table, asserts at least 3 accelerated, 1 declined, 1 not eligible). |
