# PYTHIA Studio — CONTRACTS

Every agent builds against this file. If you must deviate, append a line to `studio/DECISIONS.md` and keep the *shape* below stable. All JSON is UTF-8, snake_case.

**The LLM suggests, the compiler proves.** The LLM only rewrites Python → valid PySub. Nothing is "verified" until oracle replay passes.

## 0. Environment recipe (read this)

* Host is Windows; **everything runs in WSL Ubuntu** (Python 3.14, g++ 15, pybind11). Git-Bash/PowerShell tools cannot build C++17.
  `wsl -e bash -lc 'cd /mnt/c/<repo or worktree path> && ~/pythia-venv/bin/python <args>'`
* venv `~/pythia-venv` already has: pybind11, fastapi, uvicorn[standard], websockets, anthropic, pathspec. `pip install` more there if needed (and list it in `requirements-studio.txt`).
* Frontend: Node 22 in WSL **and** on Windows. Prefer Windows `npm`/`node` from PowerShell for `npm install`/`build` (the repo lives on `/mnt/c`, which is slow from WSL). Output is committed at `studio/web/dist`.
* No `ANTHROPIC_API_KEY` in this environment. Anything needing it must degrade gracefully (§6).
* Do **not** run `git add -A` (the user has unrelated uncommitted files). Stage only your own paths.
* Existing CLI behaviour and `tools/oracle.py` must stay identical (baseline on this machine: 16/17 pass; `t15` fails only because CPython 3.14's ZeroDivisionError text differs from 3.12 — pre-existing, ignore).

## 1. Layout

```
pythia/                  compiler (existing) + additive:
  libmode.py             (A) library-mode emission + pybind11 bridge + build cache
  stages.py              (A) tokens/AST/typed AST/PIR/C++ dump
  cli.py                 (A) adds --lib etc.; existing flags unchanged
pythia/studio/           Python backend
  engine.py              (B) the Engine facade (§5) — the ONLY thing the server imports from B
  models.py ingest.py scan.py trace.py annotate.py rank.py fixer.py replay.py bench.py splice.py export.py pipeline.py ...   (B)
  server/                (C) FastAPI app, WS, event bus, mock engine, playground
    app.py  bus.py  mock_engine.py  playground.py  __main__.py
runtime/pyrt.cpp/.hpp    (A may extend additively: arena, etc.)
runtime/pythia_accel/    (B) shim package copied into accelerated workspaces (`_pythia_accel`)
studio/CONTRACTS.md DECISIONS.md
studio/web/              (D) React+Vite+TS app; build → studio/web/dist (served by server)
demo/textlab/            (E) demo project;  demo/offline_cache/ (E+B plumbing)
scripts/smoke.sh  studio.sh  DEMO.md        (E)
```
Runtime data root: `$PYTHIA_HOME` (default `~/.pythia-studio`):
```
workspaces/<ws_id>/original/    pristine copy (never edited)
workspaces/<ws_id>/work/        accelerated copy (splice target) ; work/_pythia_accel/{__init__.py,lib/*.so}
jobs/<job_id>/job.json  events.jsonl  functions/<fid_hash>.json  artifacts/…
build-cache/<sha256>.so   (+ .meta.json)
recent.json  settings.json
```
`ws_id`, `job_id`: 8-char lowercase hex. One workspace per ingest; one job per analysis run (re-running creates a new job on the same or a new workspace).

## 2. Function identity & record

`fid` = `"<relpath-with-forward-slashes>::<qualname>"`, e.g. `textlab/text/distance.py::edit_distance`. v1 analyses only **module-level functions** (methods/nested ⇒ `not_eligible`, reason "method of class X" / "nested function").

**Statuses** (`status`): `pending | verified | guarded | fixable | not_eligible | failed | declined`
* `fixable` — typechecker rejects as written but a rewrite/annotation may fix it. After a successful fix + compile + replay it becomes verified/guarded; if fixing fails ⇒ `not_eligible` with reason; if LLM disabled it stays `fixable` with reason "…(LLM fixer disabled)".
* `declined` — compiles & typechecks but the ranker predicts net loss (marshalling > saving). Compiled/benchmarked only as a *probe* (never spliced); `probe_speedup` shows the measured number.
* `failed` — compiled but replay mismatched (auto-rejected, counterexample kept).
* `guarded` — replay matched, function has guarded/divergent fidelity sites (e.g. int64 overflow traps).
**Decision** (`decision`): `pending | accepted | rejected`. Splice puts every verified/guarded function into `work/` immediately (proposal); `rejected` reverts that function in `work/`; export includes everything not rejected.

**FunctionRecord** (detail endpoint; `FunctionSummary` = the starred subset `*`):
```jsonc
{
 "id":"…", "file":"textlab/text/distance.py", "name":"edit_distance", "qualname":"edit_distance",   // *
 "line":12, "end_line":31, "col":0,                       // * 1-based lines of the `def`..last line
 "status":"verified", "eligibility":"verifiable",         // * eligibility: verifiable|fixable|not_eligible (static class)
 "reason":null,                                           // * plain English; REQUIRED for fixable/not_eligible/declined/failed
 "decision":"pending",                                    // *
 "score":{"total":0.83,"trace_share":0.41,"static_heuristic":0.6,"eligibility_factor":1.0,
          "expected_benefit":12.0,"boundary_penalty":0.0,"basis":"trace|static","notes":["…"]},   // * (summary carries score.total)
 "share":0.41,                                            // * trace time share, null if no trace
 "calls":1204,                                            // * trace call count, null if no trace
 "speedup":38.2,                                          // * median bench speedup (null until benchmarked); probe_speedup for declined
 "probe_speedup":null,
 "metrics":{"size_lines":20,"loop_depth":2,"arith_density":0.34,"calls":["len"],"imports":[],"uses_globals":["MAXLEN"]},
 "trace":{"calls":1204,"cum_s":3.2,"self_s":3.1,"share":0.41,"arg_types":["str","str"],"ret_type":"int",
          "samples":500,"avg_arg_elems":38.0,"avg_ret_elems":1.0}|null,
 "sources":{"original":"…","annotated":"…"|null,"pysub":"…"|null,"cpp":"…"|null,"wrapper_cpp":"…"|null},
   // original = function text verbatim from the file; annotated = after auto-annotation/const-inlining (line count preserved);
   // pysub = FINAL PySub that was compiled (== annotated if no LLM rewrite); cpp = transpiler output for it (functions only, no main);
   // wrapper_cpp = generated pybind11 glue
 "line_map_ok":true,        // true ⇒ pysub line k ↔ original file line (line + k − 1); false after an LLM rewrite
 "cpp_line_map":{"3":[41,42]},   // pysub line → generated cpp lines (for the gutter)
 "rewrites":[{"attempt":1,"source":"api|cache","pysub":"…","error":"line 3: …"|null,"ok":false}],
 "diagnostics":[{"line":3,"col":5,"kind":"TypeError","msg":"…","phase":"eligibility|fix|compile"}],   // pysub-relative lines
 "fidelity":[{"line":7,"col":9,"cls":"D1 unbounded-int vs int64","detail":"…","mitigation":"…","severity":"exact|guarded|divergent"}],
 "build":{"ok":true,"module":"pythia_ab12cd34","so":"…","cached":true,"compile_s":6.1,"log":"…"}|null,
 "replay":{"total":500,"matched":500,"exc_matches":3,"first_mismatch":{"args":"repr…","python":"repr…","cpp":"repr…","kind":"value|exception|mutation"}|null}|null,
 "bench":{"py_ms":410.2,"cpp_ms":10.7,"speedup":38.3,"calls_timed":200,"repeats":5}|null,
 "splice":{"applied":true,"diff":"unified diff of the file"}|null,
 "journey":[{"key":"original","title":"Original Python","state":"done|failed|skipped|pending","summary":"…","reason":null}]
}
```
`journey` is **always** these 16 keys in this order (state `skipped`/`failed` carries `reason`): `original, observed_types, eligibility, rewrites, pysub, tokens, ast, typed_ast, pir, cpp, wrapper, build, replay, benchmark, splice, status`. Artifacts for each node come from the record fields above; tokens/ast/typed_ast/pir come from the stage dump (§3.2), returned in `record.stages` when `?stages=1`.

## 3. Compiler contracts (Agent A)

### 3.1 Library mode
CLI: `python3 -m pythia.cli <file.py> --lib fn1,fn2 --out <dir> [--modname NAME] [--no-build] [--json]`
* `<file.py>` is a PySub module (functions, classes, helpers; no main needed). Every function/class in it is compiled; **only `fn1,fn2` are exposed** to Python. Others are internal helpers.
* Writes `<dir>/<modname>.cpp` (functions + wrapper, **no `main`**) and, unless `--no-build`, `<dir>/<modname><EXT_SUFFIX>` (via `c++ -std=c++17 -O3 -shared -fPIC $(python -m pybind11 --includes)` + `runtime/pyrt.cpp`). Default `modname` = `pythia_<first 8 hex of build hash>`. `--json` prints the `LibResult` below to stdout (human text otherwise). Exit 0 ok / 2 diagnostics / 3 C++ build failure.
* Python API (what B calls): `from pythia.libmode import build_library`
```python
build_library(src: str, funcs: list[str], out_dir: str, modname: str|None=None, filename="<mod>.py",
              build=True, cache_dir: str|None=None, extra_cache_dirs: list[str]=()) -> LibResult   # dataclass, .to_dict() JSON-safe
LibResult: ok, modname, cpp (transpiled TU, no main), wrapper_cpp (pybind glue), so_path|None, cached: bool, compile_s,
           build_log, build_hash, diagnostics[{line,col,kind,msg}], fidelity[{…as §2}], cpp_line_map, exposed[{name,params:[type str],ret:str}], error|None
```
* Cache: key = sha256(cpp + wrapper + runtime sources + EXT_SUFFIX + compiler id/version + flags). Hit ⇒ copy `.so`, `cached=true`. Look in `extra_cache_dirs` read-only too (offline demo cache). Build `pyrt.cpp` once to a cached object and reuse.
* **Marshalling** (copy semantics): `int↔int64_t`, `float↔double` (accept Python int), `bool`, `str↔PyStr` (ASCII only), `list[int|float|bool|str]`, `list[list[…]]` (2 levels), `dict[int|str, int|float|bool|str]`. Class-typed params/returns ⇒ not exposable (diagnostic "class marshalling not supported") but classes may be used internally.
* **Mutation fidelity:** if a callee may mutate a list/dict argument (subscript-assign, append/pop, passed on to a callee), the wrapper writes the final state back into the caller's Python object in place after the call. Tuples/aliasing between args are not preserved (documented as a fidelity note).
* **Exceptions:** `PythonException` names `IndexError, ZeroDivisionError, OverflowError, ValueError, KeyError` surface as the *same builtin* Python classes; `PythiaSemanticError` → `RuntimeError` subclass named `PythiaSemanticError`. Marshalling an int outside int64 ⇒ `OverflowError`.
* **Fallback:** each module exposes exception class `FallbackError`. The wrapper raises it (before running anything) for input it cannot represent faithfully — non-ASCII `str`, bool-vs-int ambiguity is fine — so the splice layer can run the original Python instead.
* **Memory:** the runtime never frees (D7). Add an *optional* arena in `runtime/pyrt.cpp(.hpp)`: when active (library wrappers call `arena_begin()`/`arena_end()` around each call, after marshalling the result back), all `PyStr`/list/dict allocations made in the call are freed. Inactive ⇒ exactly today's behaviour. Keep the non-arena CLI/oracle output byte-identical.

### 3.2 Stage dump
`from pythia.stages import dump_stages` → `dump_stages(src: str, filename="<input>") -> dict`:
```jsonc
{"ok":bool,"diagnostics":[{line,col,kind,msg}],
 "tokens":[{"kind":"NAME","value":"x","line":1,"col":1}],
 "ast":Node, "typed_ast":Node, "pir":Node,      // pir = after lower()+elide_guards() (Coerce nodes, no_guard flags)
 "cpp":"…", "fidelity":[…§2…], "guard_elision":{"elided":3,"kept":5}}
Node = {"t":"BinOp","line":3,"col":9,"ty":"int"|null,"attrs":{"op":"+","no_guard":false},"kids":{"left":Node,"body":[Node,…]}}
```
Snapshot `typed_ast` **before** `lower()` mutates the tree. Must not change any existing compiler behaviour.

## 4. Event stream (Agent B emits, C transports, D renders)

Envelope: `{"seq":int,"ts":float,"type":str,"stage":str|null,"caption":str|null,"data":{…}}`. `caption` = one-sentence presenter text (e.g. "Typechecker rejected: list comprehension → asking the LLM for a PySub rewrite"). Stage names: `ingest scan trace rank fix compile verify benchmark splice export`.

| type | data |
|---|---|
| `job.start` | `{job_id, workspace_id, name, input_kind, options}` |
| `stage` | `{stage, state:"idle\|running\|done\|failed\|skipped", summary:str\|null, progress:0..1\|null}` — summary = one-number result, e.g. "84 functions", "6/7" |
| `ingest.progress` | `{phase:"copy\|clone\|index", files, bytes, current:str\|null, message}` |
| `ingest.done` | `{workspace_id, name, files, py_files, skipped:[{path,reason}]}` |
| `scan.function` | `{function:FunctionSummary}` (one per function; re-sent with updated status later is allowed) |
| `scan.done` | `{functions, verifiable, fixable, not_eligible}` |
| `trace.progress` | `{calls, functions_seen, elapsed_s, stdout_tail:str}` |
| `trace.done` | `{total_s, exit_code, timed_out, calls, profile:[{id,calls,cum_s,share}]}` |
| `rank.done` | `{ranking:[{id,rank,score:{…§2},status,reason}]}` (all functions, best first) |
| `fix.attempt` | `{id, attempt:1..3, source:"api\|cache", ok, error:str\|null, pysub:str}` |
| `fix.done` | `{id, ok, reason:str\|null}` |
| `compile.done` | `{id, ok, cached, compile_s, module, error:str\|null, diagnostics}` |
| `verify.result` | `{id, status:"verified\|guarded\|failed", total, matched, first_mismatch\|null}` |
| `bench.result` | `{id, py_ms, cpp_ms, speedup, calls_timed, probe:bool}` |
| `bench.e2e` | `{cmd, before_s, after_s, speedup, output_match:bool, ok:bool}` |
| `splice.ready` | `{files:[{path,functions:[fid]}], functions:int}` |
| `export.done` | `{path, zip:bool, files:int}` |
| `agent.step` | `{step_id, fn_id\|null, title, state:"running\|done\|failed\|info", detail:str\|null}` — same `step_id` is re-sent to update a step in place |
| `log` | `{stream:"build\|trace\|system", level:"info\|warn\|error", text}` |
| `error` | `{where, message, fatal:bool}` |
| `job.done` | `{state:"done\|failed\|cancelled", summary:{functions,verified,guarded,fixable,not_eligible,failed,declined,e2e_speedup\|null,geomean_speedup\|null}}` |

Events are persisted verbatim to `jobs/<job_id>/events.jsonl`; a finished job is replayed by feeding that file back through the same UI reducer (client-side pacing).

## 5. Engine facade (B implements, C calls)

```python
# pythia/studio/engine.py
class Engine:
    def __init__(self, home: str|None=None)
    def env(self) -> dict                         # {compiler:{found,name,version,hint}, pybind11:bool, python, platform, llm:{enabled,model,hint}, offline_available:bool, offline:bool, wsl:bool}
    def start_job(self, input: dict, options: dict, emit) -> str   # creates ids, returns job_id immediately; runs pipeline on a background thread. emit(type, data, stage=None, caption=None)
    def cancel(self, job_id)
    def job(self, job_id) -> dict                 # {job_id, workspace_id, name, state, options, started, finished, summary}
    def jobs(self) -> list[dict]; def recent(self) -> list[dict]       # recent workspaces
    def functions(self, job_id) -> list[FunctionSummary]
    def function(self, job_id, fid, stages=False) -> FunctionRecord
    def decide(self, job_id, fid: str|"all", decision: "accepted|rejected|pending") -> dict   # applies/reverts splice for that function; returns updated summaries
    def tree(self, ws_id) -> list[TreeNode]       # {path,name,type:"dir|file",children?,badges:{hotspots:int,accelerated:int}}
    def read_file(self, ws_id, rel, version="work|original") -> {"path","content","language","size"}
    def file_diff(self, job_id, rel) -> {"original":str,"modified":str}
    def export(self, job_id, dest: str|None, zip: bool) -> str      # writes project + PYTHIA_REPORT.md + build_accel.sh ; returns path
    def report(self, job_id) -> {"markdown":str,"json":dict}
    def list_dir(self, path) -> {"path","parent","entries":[{name,type}]}     # for the folder picker
    def settings(self) -> dict; def update_settings(self, patch: dict) -> dict  # offline, model, api_key (write-only)
```
Input: `{"kind":"snippet","code":"…","name":"…"} | {"kind":"file","filename":"x.py","content_b64":"…"} | {"kind":"folder","path":"…"} | {"kind":"git","url":"…"} | {"kind":"demo"}`.
Options: `{"trace_cmd":"python main.py --small"|null, "trace_timeout_s":60, "offline":false, "llm":true, "model":"claude-sonnet-5-5", "pace_ms":0}` (`pace_ms` > 0 sleeps between events for live-demo pacing).

## 6. REST + WS (Agent C) — prefix `/api`, JSON, errors `{ "error": "…" }` with proper status

```
GET  /api/env                      → Engine.env()
GET/PUT /api/settings
POST /api/jobs                     body {input, options} → {job_id, workspace_id}
GET  /api/jobs                     → list ;  GET /api/jobs/{job}  → Engine.job
GET  /api/jobs/{job}/events?after=<seq>   → {events:[…], last_seq}      (full log; used for replay)
WS   /api/jobs/{job}/ws?after=<seq>       → backlog from `after` then live; one JSON event per message; closes after job.done
POST /api/jobs/{job}/cancel
GET  /api/jobs/{job}/functions             → [FunctionSummary]
GET  /api/jobs/{job}/function?id=<fid>&stages=0|1   → FunctionRecord   (fid via query: it contains slashes)
POST /api/jobs/{job}/decision      body {id:"<fid>|all", decision}  → {functions:[FunctionSummary]}
GET  /api/jobs/{job}/file-diff?path=<rel>  → {original, modified}
POST /api/jobs/{job}/export        body {dest?:str, zip?:bool} → {path}
GET  /api/jobs/{job}/export.zip            → zip download
GET  /api/jobs/{job}/report                → {markdown, json}
GET  /api/workspaces/recent
GET  /api/workspaces/{ws}/tree
GET  /api/workspaces/{ws}/file?path=<rel>&version=work|original
GET  /api/fs/list?path=<abs>               → folder picker
POST /api/playground/compile  body {source}            → {ok,cpp,diagnostics,fidelity,cpp_line_map}
POST /api/playground/run      body {source}            → {ok, python:{stdout,exception,time_ms}, cpp:{stdout,exception,time_ms}, same:bool, error?}
POST /api/stages              body {source}            → stages.dump_stages(source)
POST /api/upload              multipart file → {job_id,…}   (drag-drop convenience; same as input.kind=file)
```
* Static: serve `studio/web/dist` at `/` with SPA fallback; `PYTHIA_PORT` default `8765`; bind 127.0.0.1.
* `PYTHIA_ENGINE=mock` swaps in `mock_engine.py` — same facade, scripted realistic data + events (used for UI dev and tests).
* The WS never drops events: backlog + live merge by `seq`.

## 7. LLM fixer, offline cache (B)

* Model default `claude-sonnet-5-5` (`options.model`/settings), key `ANTHROPIC_API_KEY`. Prompt = function source, PySub rules (extracted from `typecheck.py`/`parser.py`, not hand-copied), exact typechecker diagnostics, observed types. Reply = PySub function(s) only. ≤3 attempts, feeding diagnostics back. Every candidate must pass `typecheck` and then **replay**; failure at any point ⇒ `not_eligible`/`failed` with reason.
* No key and no offline cache entry ⇒ fixer disabled: functions stay `fixable`, `env().llm = {enabled:false, hint:"Set ANTHROPIC_API_KEY to enable the LLM fixer"}`; everything else works.
* **Offline mode** (`options.offline` or `PYTHIA_OFFLINE=1`): LLM replies come from `demo/offline_cache/llm/<key>.json` where `key = sha256(f"{sha256(function_source_after_annotation)}|{attempt}")`, content `{"model":…,"attempt":n,"function_sha":…,"response":"…","provenance":"recorded|authored"}`. Prebuilt `.so` files are looked up in `demo/offline_cache/so/` via `extra_cache_dirs` (rebuilt locally from source on miss — never needs network). `scripts/record_offline_cache.sh` re-records the LLM cache with a real key.
* **Replay/oracle rules:** calls come from the trace (`≤500` per function, args exceeding a size cap skipped). Run original Python (imported from `original/`) and compiled `.so` on a deep copy of the recorded args; compare return value, **exception class**, and post-call state of list/dict args. Floats compare **bitwise** (`struct.pack('<d')`, NaN==NaN by bits). Without a trace, synthesize inputs from observed/annotated types (small random generator) — still must match.
* **Splice:** in `work/<file>.py`, keep the original function unchanged and prepend the decorator `@_pythia_accelerated("<modname>", "<fn>")`; insert one guarded import near the top:
  `try: from _pythia_accel import accelerated as _pythia_accelerated` / `except ImportError: def _pythia_accelerated(*_a, **_k): return lambda f: f`.
  The shim (`runtime/pythia_accel/`, installed as `work/_pythia_accel/`) loads `lib/<modname>*.so` by path; on any import failure returns the original function; on `FallbackError` calls the original. Reversible = delete the decorator line.
* Export: project folder or zip with `_pythia_accel/` + `.so`s, `PYTHIA_REPORT.md`, `build_accel.sh` (rebuilds the `.so`s from the saved `.cpp`s with `c++ … $(python3 -m pybind11 --includes)`).

## 8. Frontend (D) must-haves, pointers only
Design/behaviour is in `prompt.md` §3. Routes via hash (`#/…`). Query flags: `?presenter=1` (presenter mode), `?mock=1` (self-contained scripted event stream so the UI runs with no backend), `?job=<id>` (open/replay a saved job). Dark default, Inter + JetBrains Mono, one accent colour, no emoji. Reducer is a pure function `(state, event) → state` so live, mock and replay share it.
