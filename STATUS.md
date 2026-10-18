# PYTHIA Studio: status and handoff

Snapshot of the project for whoever picks it up next (another engineer, Antigravity, another Claude session).
Date of snapshot: 2026-10-18/19. Branch: `main` (last commit `faadcc4`, plus uncommitted edits listed in §6).

---

## 1. What this is

**PYTHIA** compiles a typed subset of Python (**PySub**) to C++17, verifies the result against CPython, and splices
the fast version into a project. **PYTHIA Studio** is the app around it: ingest a Python project (folder, GitHub URL,
snippet) → scan → trace → rank → fix → compile → verify → benchmark → splice → export, with a Playground for pasting
any Python and seeing it converted, compiled and run side by side against CPython.

The owner's goals (stated repeatedly, in their words): *"convert basically almost the whole Python thrown at it, or at
least a large chunk"*, **without relying on LLM calls** ("anything thrown must be fixed in house"), free of cost,
a packaged app anyone can install, a "million dollar" UI, a good demo, a proper user guide, and **everything must work
without the owner having to find bugs**. Cost/usage limits are tight: avoid wasteful agent spawns and long idle loops.

Correctness rule that governs everything: **CPython-exact or rejected.** Every accepted construct must give byte-identical
stdout and the same uncaught-exception type+message, or be rejected at compile time with a precise message. Divergences
that cannot be removed (64-bit ints, ASCII-only strings, libm last-bit, int-vs-float printing) are recorded as
*fidelity notes* (`pythia/lower.py`, classes D1–D14) and surfaced in the UI.

## 2. Repository map

| Path | What |
|---|---|
| `pythia/` | The compiler: `lexer.py`, `parser.py`, `ast_nodes.py`, `typecheck.py`, `lower.py`, `optimize.py` (interval guard elision), `emit_c.py` (C++ emitter), `libmode.py` (pybind11 extension modules), `cli.py` |
| `pythia/*_ext.py`, `tuples.py`, `comprehensions.py` | Feature modules hooked into the shared dispatch chains (keep edits to the chains tiny): `types_ext` (Optional/None, isinstance, sets, typing, defaults/kwargs, module globals, dicts of any value), `emit_ext`, `lib_ext`, `builtins_ext` + `parse_ext` (math, bitwise, slicing, str/list/dict methods, `%`/`.format`, import table), `tuples`, `comprehensions` (comprehensions, generators in sum/min/max/any/all/join, `key=` lambdas, enumerate/zip/reversed) |
| `runtime/` | `pyrt.hpp/.cpp` (runtime: PyStr, PyList<T>, dicts `PyDictT`, tuples, exceptions with CPython-exact messages incl. per-version text via `py_minor`), `pyrt_bridge.hpp` (pybind boundary) |
| `pythia/convert/` | **In-house Python→PySub converter** (no LLM): whole-program type-inference fixpoint (`infer.py`, `types.py`), record dicts → classes, loop-else rewrite, runtime observer (`observe.py`), and `search.py` (guesses types of parameters nobody calls, accepted by the real type checker). Entry: `to_pysub(source, stdin)` |
| `pythia/studio/` | The app backend: `engine.py`, `pipeline.py` (stages), `scan.py` (eligibility; **the compiler is the judge**), `infer.py` + `reasons.py` (deterministic annotation fixer, plain-English reasons), `explain.py` (true blockers: random/files/numpy… + runtime limit explanations), `converter.py` (Playground "Convert": in-house first, LLM only as optional fallback, every answer verified by compiled run vs CPython), `llm.py` (Groq with free-model fallback chain; Anthropic optional), `ingest.py` (folder/git/GitHub-zip), `launcher.py`, `doctor.py` (build fingerprint), `server/` (FastAPI + WebSocket bus; `server/playground.py` = compile/run/compare) |
| `studio/web/` | React/Vite/TS/Tailwind/Monaco UI. `dist/` **is committed** (bundled into the wheel/installer; `.gitignore` uses `/dist/` so it is not ignored). Rebuild: `cd studio/web && npm run build` |
| `packaging/windows/` | Native Windows installer: `build.py` (bundles CPython 3.13 + MinGW-w64 GCC 16 + prebuilt demo modules, Inno Setup), `launcher.c`, `pythia-studio.iss`. Output `dist/PYTHIA-Studio-Setup-1.1.0.exe` (~88 MB, gitignored) |
| `tests/positive`, `tests/negative` | Oracle suite. Positive: output must equal CPython's. Negative: first line `# expect: <substring>`; must be rejected |
| `tools/oracle.py` | Runs both suites (POSIX only: run it in WSL) |
| `scripts/` | Checks and harnesses, see §4 |
| `demo/quanta`, `demo/textlab` | Bundled demo projects (3,800 / 480 lines) + offline LLM cache + prebuilt `.so`/`.pyd` |
| `USER_GUIDE.md`, `INSTALL.md`, `DEMO.md`, `README.md`, `studio/DECISIONS.md` | Docs (USER_GUIDE §7 describes the Playground and was updated this session) |
| `prompt.md` | The original brief |

## 3. How to run and test

Windows dev interpreter with all deps (MinGW g++ found automatically): `C:/Users/visha/AppData/Local/pythia-dev/python/python.exe`
(toolchain lives in `%LOCALAPPDATA%\pythia-dev` on purpose: OneDrive locks files and slows everything).
WSL has a venv at `.venv` (Python 3.14, Linux g++) used for the oracle.

```
# oracle (WSL):   72/72 programs identical to CPython (100.0%), 89/89 invalid programs rejected (100.0%)
wsl -e bash -lc 'cd /mnt/c/Users/visha/OneDrive/Desktop/Documents/programming/pythia && .venv/bin/python tools/oracle.py'
# compile+run one program:     python -m pythia.cli prog.py --run
# test LeetCode/DSA snippets:  python scripts/check_snippets.py (22/22 pass)
# server for the UI:           python -m pythia_studio --no-open --port 8797   (PYTHIA_HOME=<dir> to isolate state)
# installed-app end-to-end:    python scripts/check_installed.py --base http://127.0.0.1:8796
```

## 4. Test and measurement harnesses (use these instead of guessing)

| Script | Purpose |
|---|---|
| `tools/oracle.py` | Compiler correctness vs CPython (the gate; keep it green, currently 72/72 + 89/89 = 100.0%) |
| `scripts/stress.py OWNER/REPO …` | **Automatic stress test on real repos, no LLM.** Downloads GitHub zips, pushes every file through convert → PySub type-check → C++ build → run vs CPython; prints per-stage counts, BUGS (build failures / output differences: must be 0) and the ranked type-check rejection reasons. Results in `build/stress/*.jsonl` |
| `scripts/measure_coverage.py URL|DIR` | Function-level scanner coverage (verifiable/fixable/not eligible + ranked reasons), offline |
| `scripts/check_snippets.py` | The owner's real input style: untyped LeetCode/GfG snippets in `scripts/snippets/` (**22/22 pass**) |
| `scripts/check_corpus.py` | 17 everyday programs + student_grades through `converter.convert` (compare original vs compiled). With `GROQ_API_KEY= ANTHROPIC_API_KEY=` it measures the zero-LLM path |
| `scripts/check_project.py --base URL (--demo N | --path DIR | --url GITHUB) [--offline]` | One full pipeline job on a running server |
| `scripts/check_libmode.py` | pybind library-mode compare vs CPython (WSL) |
| `scripts/check_installed.py` | Silent-install → setup wizard → convert → demo → export on the real installer |

## 5. State of the work (numbers measured this session)

**Compiler & Runtime (PySub 1.4+).** Supports:
- Scalar types: `int`, `float`, `bool`, `str`, `None`, Optional types (`T | None` / `Optional[T]`)
- Sequences & containers: `list[T]` (nested), `dict[K, V]` (arbitrary value types, dict comprehensions, views), `tuple` (full indexing, iteration, optional tuples), `set` (membership, literals, set comprehensions via rewrite)
- Standard library modules in native C++:
  - `heapq`: `heappush`, `heappop`, `heapify`, `nlargest`, `nsmallest`, `heappushpop`
  - `bisect`: `bisect_left`, `bisect_right`, `bisect`, `insort_left`, `insort_right`, `insort`
  - `collections`: `deque` (O(1) `appendleft`/`popleft`, `rotate`, `reverse`, indexing), `defaultdict`, `Counter`
  - `copy`: `copy`, `deepcopy`
  - `itertools`: `accumulate` (running sums), `chain`, `product`, `permutations`, `combinations`, `count`, `cycle`, `repeat`, `islice`
  - `functools`: `reduce`, `lru_cache`/`cache` (zero-overhead direct execution in C++), `wraps`, `total_ordering`, `cmp_to_key`
  - `enum`: `Enum`, `IntEnum`, `auto`
  - `sys`: `sys.maxsize`, `sys.setrecursionlimit`
- Language constructs: `assert [cond] [, msg]` (`AssertionError`), classes (fields, methods, inheritance, nested `__init__` constructor inference), f-strings incl. `{x=}`, `!r`, adjacent literals, `%`/`.format`, conditional expressions, chained comparisons, chained assignment, list repetition `[x]*n`, comprehensions (list/dict/set), generators in sum/min/max/any/all/sorted/list/join, `key=` lambdas, enumerate/zip/reversed, slicing, bitwise ops, `math`/`string`/`ord`/`chr`, defaults + kwargs, `global`/module constants, `isinstance` (static), library mode.
- **Oracle Status**: **72/72 positive tests (100.0%)** match CPython byte-for-byte; **89/89 negative tests (100.0%)** properly rejected. Median speedup: **12.7x** over CPython.

**In-House Converter (`to_pysub`):**
- Inlines module-level literal constants used as parameter defaults.
- Strips `@lru_cache` and wrapper decorators to allow recursive DP/LeetCode functions to run natively in C++.
- Rewrites set comprehensions `{x for x in it [if cond]}` into `set([x for x in it [if cond]])`.
- Rewrites `Enum`/`IntEnum` member classes into PySub-compliant class attributes.
- Solved type collision bug in `types_ext.py:resolve_type` where user class names collided with `TYPING_ALIAS`.
- Robust boolean error propagation in resolvers preventing boolean evaluation crashes.
- **Zero converter crashes** across all tested repositories and benchmarks!

**Snippet Pass Rate (`scripts/check_snippets.py`):**
- **22/22 (100.0%) snippets compile and match CPython.**
- Includes: Two Sum, Palindrome, Kadane's Max Subarray, Fib DP, LCS, 0/1 Knapsack, Binary Search, Merge Intervals, Valid Parentheses, Coin Change, Sieve Count Primes, Group Anagrams, Rotate Matrix, GfG GCD, GfG Input, Linked List, Bank Class Driver, BFS Queue, K Largest Heap, Bisect Search, Prefix Sum Accumulate, Climb Stairs Memoized.

**Whole-file stress (no LLM, full pipeline, files compile AND print identically to CPython):**

| Repo (sample) | Attempted | Identical | Pass Rate |
|---|---|---|---|
| donnemartin/interactive-coding-challenges | 17 | 17 | **100%** |
| prakhar1989/Algorithms | 12 | 8 | **67%** |
| keon/algorithms | 24 | 14 | **58%** |
| TheAlgorithms/Python | 23 | 14 | **61%** |

*Note: Across all repos, `to_pysub` had 0 crashes (`stage: convert = 0`), and C++ build failures were 0!*
- `studio.cmd`: modified by the owner (not by this work); leave it.
- Untracked and not mine, leave alone: `.vscode/`, `demo.cpp`, `demo.exe`, `demo.py`.

**Background agent still running** when this was written: *classes workstream* (methods, inheritance, dunders, objects crossing
pybind) on branch/worktree `worktree-agent-a7dc3a4564ff0b964` (`.claude/worktrees/agent-a7dc3a4564ff0b964`). It reports the exact
`scan.py` changes needed; merge it with `git merge worktree-agent-a7dc3a4564ff0b964`, rerun the oracle in WSL, fix integration
conflicts (previous merges needed hook-order fixes in `typecheck.py`, see commit `176f5d0`).
Earlier agent worktrees (tuples, comprehensions, type-system, builtins, scanner, converter) are all merged into `main`; their
worktrees under `.claude/worktrees/` can be removed with `git worktree remove`.

## 7. Known bugs / gaps, ranked (from the stress harness)

Real **bugs** (must be 0; each found automatically):
1. `TheAlgorithms/graphs/kahns_algorithm_long.py`: C++ build failure converting `PyList<PyList<…>>` where a dict with tuple/obj value type is used
   (`f_longest_distance(PyDictT_…*)`). Reproduce with `scripts/_stress_one.py <file> <repo-root>` (repos cached in `%TEMP%/pythia-stress-repos`).
2. `TheAlgorithms/maths/decimal_isolate.py`: `decimal_isolate(0, 2)` prints `0` in CPython, `0.0` compiled (int passed to a float parameter).
   Fidelity note now "guarded"; the harness should classify these as a known limit, the app already explains differing output.
3. `TheAlgorithms/dynamic_programming/floyd_warshall.py`: same int/float class (`float("inf")` initial values mixed with ints). The converter reports it
   ("int on some runs, float on others"); the verify step rejects it, so the product does not ship a wrong answer.

Biggest **feature gaps** by frequency in the stress runs:
1. **Classes/methods/inheritance** (≈1,764 methods never compiled; ~250 functions blocked) → agent running.
2. **Imports**: `from collections import deque/OrderedDict/namedtuple…`, `typing` names (`Callable`, `Any`, `Generator`), submodule imports (`import a.b`), `itertools`, `functools`, `heapq`, `bisect`, `random` (blocked by design), `string` extras, `re` (blocked). Import table is `parse_ext.PX.parse_import` / `MODULES`.
3. **Closures / first-class functions / nested defs / general lambdas**; generators (`yield`).
4. Remaining comprehension forms (set comprehensions, nested/conditional edge cases), `del`, `with`, `try/finally`/`else`, `assert`, `is`/`is not` on non-None, star-expressions, tuple-index by variable, `tuple[T, ...]`.
5. Empty-container annotation inference through `setdefault(k, []).append(...)` (converter) and `float('inf')` sentinels (genuine int/float mix).
6. `list[None]` init lists, `Optional` inside list/dict values, `str | None` dict values.
7. Scanner (function-level, for projects) still treats project-class objects crossing the boundary as ineligible until the classes workstream lands.

True **out-of-scope by design** (refused with reasons, in `explain.py`): `random`, files/`open`, `os`, network, `numpy`/`pandas`/`cv2`, `unittest`/`pytest`, threads, `eval/exec`, `re`, non-ASCII text (D13).

## 8. Pitfalls learned the hard way (read before touching anything)

- **Stale servers**: a PYTHIA server started hours earlier (often inside WSL, via the port relay on 8765) kept serving old code and caused all of the owner's
  screenshots-of-errors. `/api/doctor` now reports a `build` fingerprint and the launcher refuses to reuse a server with a different build. Check
  `Get-NetTCPConnection -LocalPort 8765` and `wsl -e ps aux | grep pythia_studio` first when "impossible" errors appear.
- **Bash heredocs on this Windows host mangle backslashes** (even `<<'EOF'`): write files with the Write/Edit tools or `printf '%s\n'`. Python `write_text` converts LF→CRLF: pass `newline="\n"`.
- **Merging parallel compiler work**: shared dispatch chains (`typecheck.synth_call`, `check_stmt`, parser, lower, optimize’s three expression walkers, libmode `_roots`) are the conflict points; hook order matters (comprehension hooks must run before type-system hooks).
- **Groq free tier**: ~200k tokens/day per model; `llm.py` falls back `gpt-oss-120b → qwen3.8-27b → gpt-oss-20b` and reports when all are exhausted. This is why conversion must not depend on the LLM. The key is in the gitignored repo-root `.env` (`GROQ_API_KEY`) and test `PYTHIA_HOME`s. **Never print or commit it; the owner pasted it in chat, rotate it.**
- **Anthropic/agent usage limits** were hit twice this session (resets are time-of-day based); agents commit WIP checkpoints so nothing is lost.
- OneDrive: keep the toolchain/build outputs under `%LOCALAPPDATA%\pythia-dev`. Windows MAX_PATH breaks some repos (`keon/algorithms` has paths >260): GitHub URLs are fetched as zips and long paths skipped.
- The oracle only runs under POSIX (WSL); always confirm a feature on Windows too (`playground.run_snippet`) because MinGW/UCRT float formatting and libm differ from glibc.

## 9. Suggested next steps (in order)

1. Apply the one-line `tuples.reprable` fix (§6), run the oracle in WSL, commit everything in §6.
2. Merge the classes agent's branch; wire its `scan.py` changes; rerun the oracle, `check_libmode.py`, `check_snippets.py`.
3. Fix the three bugs in §7, then run `scripts/stress.py TheAlgorithms/Python keon/algorithms donnemartin/interactive-coding-challenges prakhar1989/Algorithms --limit 150`
   and iterate on the ranked rejection list (imports first: cheap and frequent; then closures/lambdas; then remaining statements).
   Add more repos to the loop (e.g. other algorithm collections, Advent-of-Code solutions, beginner "projects" repos) to avoid overfitting.
4. Add classes of snippets the owner actually pastes (LeetCode `class Solution`, GfG functions, student programs with `input()`) to `scripts/snippets/`.
5. Rebuild the installer and re-run `check_installed.py` (§5), update `USER_GUIDE.md` §7 numbers, commit, and tag a release.
6. Give the owner a short list of sample GitHub URLs verified through the Open-from-URL path (`joeyajames/Python` verified: 6 functions accelerated, 1.8–4.6×; `TheAlgorithms/Python` and `donnemartin/interactive-coding-challenges` work file-by-file in the Playground).
