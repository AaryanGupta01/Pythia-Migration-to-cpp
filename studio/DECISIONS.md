# DECISIONS (one line each)

- Runs in WSL Ubuntu (Python 3.14, g++ 15) on this Windows host; native Windows toolchain (MinGW 6.3) cannot build C++17.
- Python package for the backend is `pythia/studio/`; `studio/` holds docs and the web app.
- Splice uses a decorator (`@_pythia_accelerated`) and keeps the original body untouched, so the diff stays small and reversible.
- Compiled modules raise `FallbackError` for inputs they cannot represent faithfully (e.g. non-ASCII str); the shim then runs the original Python.
- Declined (boundary-cost) functions are compiled and benchmarked as a probe only, never spliced, so the decision is backed by a measured number.
- No ANTHROPIC_API_KEY here: offline LLM cache entries are marked `provenance: "authored"` until re-recorded with a real key.
- Frontend `dist/` is committed so the app runs without Node on the evaluator's machine.
- Oracle baseline is 16/17 on CPython 3.14 (t15 message text differs from 3.12); not touched.
- Demo project root is `demo/textlab/` (main.py + package `textlab/`), so fids look like `textlab/text/distance.py::edit_distance`; scale factor 1 for `--small`, 4 otherwise.
- Demo "guarded" vs "verified": expected by D1 (int +,-,* not provable) sites; the global D7 note (line 0) appears on every list/str function and is ignored for that split. Interval analysis elides 0 guards in the demo wins (bounds come from len()/params), so n-body and k-means are the fully exact ones.
- Authored offline rewrites live in `demo/offline_cache/authored_rewrites.json` (keyed by function name, provenance "authored"); `scripts/author_offline_cache.py` converts them to `llm/<key>.json`.
