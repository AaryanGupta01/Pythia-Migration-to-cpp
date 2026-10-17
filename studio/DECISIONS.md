# DECISIONS (one line each)

- Runs in WSL Ubuntu (Python 3.14, g++ 15) on this Windows host; native Windows toolchain (MinGW 6.3) cannot build C++17.
- Python package for the backend is `pythia/studio/`; `studio/` holds docs and the web app.
- Splice uses a decorator (`@_pythia_accelerated`) and keeps the original body untouched, so the diff stays small and reversible.
- Compiled modules raise `FallbackError` for inputs they cannot represent faithfully (e.g. non-ASCII str); the shim then runs the original Python.
- Declined (boundary-cost) functions are compiled and benchmarked as a probe only, never spliced, so the decision is backed by a measured number.
- No ANTHROPIC_API_KEY here: offline LLM cache entries are marked `provenance: "authored"` until re-recorded with a real key.
- Frontend `dist/` is committed so the app runs without Node on the evaluator's machine.
- Oracle baseline is 16/17 on CPython 3.14 (t15 message text differs from 3.12); not touched.
- (C) Server adds `mock_data.py` (demo project text + per-function outcomes) next to `mock_engine.py`; mock C++/fidelity come from the real front-end (`pythia.cli.compile_source`) when importable, so they are real, not invented.
- (C) Event `seq` starts at 1 and is contiguous per job; the bus (not the engine) writes `events.jsonl`, buffering events emitted before `start_job` returns the job id.
- (C) Mock export is user-triggered (`export.done` after POST /export); pass `options.export=true` to make the scripted stream cover every §4 event type.
- (C) `/api/upload` parses multipart with the stdlib `email` parser (no python-multipart dependency); `/api/stages` falls back to a stdlib tokenize/ast dump flagged `"mock": true` when `pythia.stages` is absent.
- (C) Server answers only requests whose Host header is localhost/127.0.0.1 (DNS-rebinding guard) and binds 127.0.0.1.
