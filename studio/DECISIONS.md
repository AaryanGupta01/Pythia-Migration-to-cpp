# DECISIONS (one line each)

- Runs in WSL Ubuntu (Python 3.14, g++ 15) on this Windows host; native Windows toolchain (MinGW 6.3) cannot build C++17.
- Python package for the backend is `pythia/studio/`; `studio/` holds docs and the web app.
- Splice uses a decorator (`@_pythia_accelerated`) and keeps the original body untouched, so the diff stays small and reversible.
- Compiled modules raise `FallbackError` for inputs they cannot represent faithfully (e.g. non-ASCII str); the shim then runs the original Python.
- Declined (boundary-cost) functions are compiled and benchmarked as a probe only, never spliced, so the decision is backed by a measured number.
- No ANTHROPIC_API_KEY here: offline LLM cache entries are marked `provenance: "authored"` until re-recorded with a real key.
- Frontend `dist/` is committed so the app runs without Node on the evaluator's machine.
- Oracle baseline is 16/17 on CPython 3.14 (t15 message text differs from 3.12); not touched.
- Web UI (Agent D): `?mock=1` serves the whole API/event stream in-browser (src/mock); the reducer, player and views are identical for mock, live WS and saved-job replay.
- Web UI: events pass through a Player (instant or paced) before the pure reducer, so presenter mode, replay speed and Space/Arrow stepping work for every source.
- Web UI: Monaco is bundled (edcore + python/cpp tokenizers + one worker); fonts via @fontsource; no CDN at runtime.
- Web UI: the diff view shows the whole file (original vs spliced work copy) with unchanged regions folded; a toggle compares the original function to the PySub rewrite.
