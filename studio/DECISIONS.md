# DECISIONS (one line each)

- Runs in WSL Ubuntu (Python 3.14, g++ 15) on this Windows host; native Windows toolchain (MinGW 6.3) cannot build C++17.
- Python package for the backend is `pythia/studio/`; `studio/` holds docs and the web app.
- Splice uses a decorator (`@_pythia_accelerated`) and keeps the original body untouched, so the diff stays small and reversible.
- Compiled modules raise `FallbackError` for inputs they cannot represent faithfully (e.g. non-ASCII str); the shim then runs the original Python.
- Declined (boundary-cost) functions are compiled and benchmarked as a probe only, never spliced, so the decision is backed by a measured number.
- No ANTHROPIC_API_KEY here: offline LLM cache entries are marked `provenance: "authored"` until re-recorded with a real key.
- Frontend `dist/` is committed so the app runs without Node on the evaluator's machine.
- Oracle baseline is 16/17 on CPython 3.14 (t15 message text differs from 3.12); not touched.
- B2: ingest.ingest honours optional input["ws_id"] (one-line edit) so POST /jobs can return workspace_id immediately.
- B2: replay compares dict results order-insensitively; print() side effects inside functions are not compared; measured speedup <0.95 turns a verified function into `declined` (never splice a slowdown).
- B2: rec.sources.pysub = scan.Extract.source (standalone module incl. helpers); rec.build gains additive keys exposed, cpp_path; shim also falls back to Python on TypeError (unmarshallable arg); PYTHIA_ACCEL=0 disables the shim.
- B1: ingest copies project contents to the workspace ROOT (no extra top-level folder), so fids are project-relative and `trace_cmd` is relative to the project root.
- B1: only module-level *scalar* constants (int/float/bool/str/None, simple constant expressions) are inlined into PySub functions; list/dict globals make a function not_eligible (mutation + per-call rebuild cost).
- B1: not_eligible by design: bitwise ops, default parameter values, tuple returns, user classes, module/third-party calls, closures, I/O. Methods are listed as not_eligible ("method of class X"); nested defs are not listed separately.
- B1: any typechecker rejection of otherwise-clean code is `fixable` (LLM may fix), except type rebinding / unknown types / undefined names which are `not_eligible`.
- B1: `Extract.helpers` = names of pulled-in same-module callees; `Extract.uses` = names of inlined constants. Scratch state lives in `rec.private` (`modinfo`, `siblings`, `own`, `fix_kind` = "annotations"|"rewrite").
- B1: ranker declines (net saving < 0 from trace numbers) only verifiable functions and annotation-only fixable ones; rewrite-fixable ones just get a note. Constants MARSHAL_S_PER_ELEM / CALL_OVERHEAD_S in rank.py are the calibration knobs.
- B1: `llm.make_client(model, offline_cache_dir=None, *, offline=None)`: offline defaults to "cache dir given". Fixer sets `rec.rewrites`, and on success `rec.sources["pysub"]` + `line_map_ok=False`. Anthropic calls send no temperature (rejected by newer models).
