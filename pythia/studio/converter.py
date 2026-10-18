"""Whole-program Python -> PySub conversion for the Playground: the LLM suggests, the compiler decides.

The model sees the program, the PySub rules (from pysub_rules) and the exact type-checker errors; it answers with
one complete program. Every answer is type-checked; on failure the errors go back for another round (<= 3).
A converted program can then be run against the ORIGINAL under CPython with the same stdin, so the user sees
that behaviour was preserved, not just that it compiles.
"""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

from . import llm
from .pysub_rules import rules_text

MAX_ATTEMPTS = 3

GUIDE = """You convert ordinary Python programs into PySub, a statically typed subset of Python that compiles to C++.

{rules}

How to convert (keep the program's observable behaviour IDENTICAL: same prompts, same printed text, same
exceptions for the same input):
1. Annotate every parameter and return type; annotate empty containers (`students: list[Student] = []`).
2. A dict used as a record with mixed value types becomes a small class with typed fields and an __init__.
3. Module-level state used inside functions becomes a parameter: create it at module level (or in main) and
   pass it to every function that reads or changes it. Lists passed this way are shared, so changes are seen.
4. enumerate/zip -> `for i in range(len(xs))`; comprehensions/generators -> loops with append;
   `x if c else y` -> an if/else statement; lambda + key= (sort/max/min) -> explicit loops
   (e.g. a loop that tracks the best record, replacing only on a strictly better value, like max()).
   Python's sort is STABLE: emulate sort(key=..., reverse=...) with an insertion sort that moves an item past
   another only when its key is strictly smaller (strictly larger for reverse=True), never a selection sort.
5. `if __name__ == "__main__": main()` may stay. Keep f-strings; keep every printed string byte-for-byte.
6. Do not add explanations inside the code. Do not print anything the original does not print.
Answer with the COMPLETE converted program in exactly one ```python fenced block and nothing else."""

_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


def _code(text: str) -> Optional[str]:
    blocks = _BLOCK.findall(text or "")
    if not blocks:
        return None
    return max(blocks, key=len).strip() + "\n"


def _diag_text(diags: List[Dict[str, Any]], limit: int = 12) -> str:
    lines = [f"line {d['line']}:{d['col']}: {d['kind']}: {d['msg']}" for d in diags[:limit]]
    if len(diags) > limit:
        lines.append(f"... and {len(diags) - limit} more")
    return "\n".join(lines)


def status(settings: Optional[dict]) -> Dict[str, Any]:
    st = llm.llm_status((settings or {}).get("model"), False, None, settings=settings or {})
    return {"enabled": st["enabled"], "provider": st.get("provider"), "model": st.get("model"), "hint": st.get("hint")}


def convert(source: str, settings: Optional[dict], compile_fn) -> Dict[str, Any]:
    """compile_fn(source) -> {ok, diagnostics, ...} (the Playground's compile)."""
    first = compile_fn(source)
    if first.get("ok"):
        return {"ok": True, "already": True, "source": source, "attempts": [], "provider": None, "model": None}
    client = llm.make_client((settings or {}).get("model"), None, settings=settings or {})
    st = status(settings)
    if client is None:
        return {"ok": False, "error": "The AI converter is off. Add a free Groq API key in Settings (console.groq.com) "
                                      "or set ANTHROPIC_API_KEY.", "attempts": [], **st}
    system = GUIDE.format(rules=rules_text())
    messages = [{"role": "user", "content": (
        "Convert this Python program to PySub.\n\n```python\n" + source.rstrip() + "\n```\n\n"
        "The PySub type checker reports these problems with it as written:\n" + _diag_text(first["diagnostics"]))}]
    attempts: List[Dict[str, Any]] = []
    for n in range(1, MAX_ATTEMPTS + 1):
        t0 = time.perf_counter()
        try:
            reply = client.complete(system, messages, function_source=source + "\n#program", attempt=n)
        except llm.LLMError as ex:
            attempts.append({"attempt": n, "ok": False, "source": None, "diagnostics": [],
                             "error": str(ex), "latency_ms": round((time.perf_counter() - t0) * 1000)})
            return {"ok": False, "error": str(ex), "attempts": attempts, **st}
        latency = round((time.perf_counter() - t0) * 1000)
        code = _code(reply)
        if code is None:
            attempts.append({"attempt": n, "ok": False, "source": None, "diagnostics": [], "latency_ms": latency,
                             "error": "the model did not return a ```python block"})
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "Return the complete program in one ```python block only."}]
            continue
        res = compile_fn(code)
        attempts.append({"attempt": n, "ok": bool(res.get("ok")), "source": code,
                         "diagnostics": res.get("diagnostics") or [], "latency_ms": latency, "error": None})
        if res.get("ok"):
            return {"ok": True, "already": False, "source": code, "attempts": attempts, **st}
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "The PySub type checker rejected that version:\n"
                                                 + _diag_text(res["diagnostics"])
                                                 + "\nFix exactly these problems (keep everything else) and return the "
                                                   "complete program again in one ```python block."}]
    return {"ok": False, "error": f"no valid PySub after {MAX_ATTEMPTS} attempts; the last errors are shown",
            "attempts": attempts, **st}
