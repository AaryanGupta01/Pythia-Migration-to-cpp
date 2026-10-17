#!/usr/bin/env python3
"""Turn demo/offline_cache/authored_rewrites.json into demo/offline_cache/llm/<key>.json files.

    python scripts/author_offline_cache.py

key = sha256(f"{sha256(function_source)}|{attempt}") as in studio/CONTRACTS.md section 7. `function_source`
must be exactly the text the fixer hashes: the function as it appears in the file (def line to last line,
no trailing newline) after auto-annotation. For knn_vote and life_generations the annotator adds nothing, so the
key is the verbatim source. collatz_longest needs only annotations from the trace (llm_needed=false), so no
entry is written for it. Replies are wrapped in a fenced python block like a real model reply.
Entries are written with provenance "authored"; scripts/record_offline_cache.sh replaces them with
"recorded" ones.
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DEMO = ROOT / "demo" / "textlab"
CACHE = ROOT / "demo" / "offline_cache"


def function_source(rel: str, name: str) -> str:
    text = (DEMO / rel).read_text(encoding="utf-8")
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(text.splitlines()[node.lineno - 1:node.end_lineno])
    raise SystemExit(f"{name} not found in {rel}")


def key_for(src: str, attempt: int) -> str:
    try:                                                   # prefer B1's implementation when it exists
        from pythia.studio.fixer import cache_key
        return cache_key(src, attempt)
    except ImportError:
        return hashlib.sha256(f"{hashlib.sha256(src.encode()).hexdigest()}|{attempt}".encode()).hexdigest()


def main() -> None:
    data = json.loads((CACHE / "authored_rewrites.json").read_text(encoding="utf-8"))
    out = CACHE / "llm"
    out.mkdir(parents=True, exist_ok=True)
    n = 0
    for name, spec in data["functions"].items():
        if spec.get("llm_needed") is False:          # annotation from the trace is enough: the fixer never asks
            continue
        src = function_source(spec["file"], name)
        for att in spec["attempts"]:
            # the fixer extracts the fenced python block, exactly like from a real model reply
            reply = f"Here is a PySub version of `{name}`:\n\n```python\n{att['pysub'].rstrip()}\n```\n"
            entry = {"model": "authored", "attempt": att["attempt"],
                     "function_sha": hashlib.sha256(src.encode()).hexdigest(),
                     "response": reply, "provenance": "authored"}
            (out / f"{key_for(src, att['attempt'])}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
            n += 1
    print(f"wrote {n} authored cache entries to {out}")


if __name__ == "__main__":
    main()
