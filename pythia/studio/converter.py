"""Whole-program Python -> PySub conversion for the Playground: the LLM suggests, the compiler decides.

The model sees the program, the PySub rules (from pysub_rules) and the exact type-checker errors; it answers with
one complete program. Every answer is type-checked, then run under CPython next to the original on the user's
input: a type error or any difference in the output goes back to the model for another round (<= 4).
Programs that no rewrite can keep identical (random numbers, files, third-party libraries, ...) are refused up
front with the reasons (explain.blockers), instead of spending attempts on them.
"""
from __future__ import annotations

import difflib
import re
import time
from typing import Any, Dict, List, Optional

from . import explain, llm
from .pysub_rules import rules_text

MAX_ATTEMPTS = 4

GUIDE = """You convert ordinary Python programs into PySub, a statically typed subset of Python that compiles to C++.

{rules}

How to convert (keep the program's observable behaviour IDENTICAL: same prompts, same printed text, same
exceptions for the same input):
1. Annotate every parameter and return type; annotate empty containers (`students: list[Student] = []`).
2. A dict used as a record with mixed value types becomes a small class with typed fields and an __init__.
3. Module-level state used inside functions becomes a parameter: create it at module level (or in main) and
   pass it to every function that reads or changes it. Lists passed this way are shared, so changes are seen.
4. enumerate/zip -> `for i in range(len(xs))`; comprehensions/generators -> loops with append;
   lambda + key= (sort/max/min) -> explicit loops
   (e.g. a loop that tracks the best record, replacing only on a strictly better value, like max()).
   Python's sort is STABLE: emulate sort(key=..., reverse=...) with an insertion sort that moves an item past
   another only when its key is strictly smaller (strictly larger for reverse=True), never a selection sort.
5. `if __name__ == "__main__": main()` may stay. Keep f-strings; keep every printed string byte-for-byte.
6. A dict whose values are lists or records (dict[str, list[str]], defaultdict(list), dict of objects) becomes
   parallel lists: `keys: list[str] = []` and `groups: list[list[str]] = []` (or list[Record]), looked up with
   `if k in keys: i = keys.index(k)`; keep first-insertion order exactly as the dict would.
   Tuples become separate variables or a small class; a set becomes a list with `if x not in xs` before append.
   Counter / defaultdict(int) become dict[str, int] with d.get(k, 0); math.sqrt(x) can be x ** 0.5.
7. Printed text must be byte-for-byte identical. An int prints as 83 and a float as 83.0: if a value is an int on
   one path and a float on another (e.g. a median), keep separate int and float variables, or build the printed
   str in each branch. Printing an object prints its __str__: call a method that returns the str instead.
8. Do not add explanations inside the code. Do not print anything the original does not print.
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


def _out_diff(a: Dict[str, Any], b: Dict[str, Any]) -> Optional[str]:
    """None when two CPython runs behave the same (stdout and exception), else a short diff for the model."""
    if a.get("stdout") == b.get("stdout") and a.get("exception") == b.get("exception"):
        return None
    d = list(difflib.unified_diff((a.get("stdout") or "").splitlines(), (b.get("stdout") or "").splitlines(),
                                  "original", "converted", lineterm="", n=1))
    text = "\n".join(d[:40]) + ("\n..." if len(d) > 40 else "")
    if a.get("exception") != b.get("exception"):
        text += f"\noriginal raised: {a.get('exception') or 'nothing'}; converted raised: {b.get('exception') or 'nothing'}"
    return text


def status(settings: Optional[dict]) -> Dict[str, Any]:
    st = llm.llm_status((settings or {}).get("model"), False, None, settings=settings or {})
    return {"enabled": st["enabled"], "provider": st.get("provider"), "model": st.get("model"), "hint": st.get("hint")}


def convert(source: str, settings: Optional[dict], compile_fn, stdin: str = "", run_fn=None) -> Dict[str, Any]:
    """compile_fn(source) -> {ok, diagnostics, ...} (the Playground's compile); run_fn(source, stdin) -> CPython run
    {stdout, exception, timed_out?} used to check that the conversion prints what the original prints."""
    first = compile_fn(source)
    if first.get("ok"):
        return {"ok": True, "already": True, "source": source, "attempts": [], "provider": None, "model": None}
    bad = explain.syntax_error(source)
    if bad:
        return {"ok": False, "error": bad, "attempts": [], "provider": None, "model": None}
    blocks = explain.blockers(source)
    if blocks:
        return {"ok": False, "blockers": blocks, "attempts": [], "provider": None, "model": None,
                "error": "This program can't be compiled to C++ as a whole: " + "; ".join(str(b["what"]) for b in blocks)
                         + ". It still runs under Python (press Run)."}
    client = llm.make_client((settings or {}).get("model"), None, settings=settings or {})
    st = status(settings)
    if client is None:
        return {"ok": False, "error": "The AI converter is off. Add a free Groq API key in Settings (console.groq.com) "
                                      "or set ANTHROPIC_API_KEY.", "attempts": [], **st}
    ref = run_fn(source, stdin) if run_fn else None
    if ref is not None and ref.get("timed_out"):
        ref = None                                       # can't compare against a run that didn't finish
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
            return {"ok": False, "error": str(ex), "attempts": attempts, **st, "model": getattr(client, "last_model", None) or st.get("model")}
        latency = round((time.perf_counter() - t0) * 1000)
        code = _code(reply)
        if code is None:
            attempts.append({"attempt": n, "ok": False, "source": None, "diagnostics": [], "latency_ms": latency,
                             "error": "the model did not return a ```python block"})
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "Return the complete program in one ```python block only."}]
            continue
        res = compile_fn(code)
        att = {"attempt": n, "ok": bool(res.get("ok")), "source": code,
               "diagnostics": res.get("diagnostics") or [], "latency_ms": latency, "error": None}
        attempts.append(att)
        if res.get("ok"):
            diff = _out_diff(ref, run_fn(code, stdin)) if ref is not None else None
            if diff is None:
                return {"ok": True, "already": False, "source": code, "attempts": attempts,
                        "behaviour_checked": ref is not None, **st, "model": getattr(client, "last_model", None) or st.get("model")}
            att["ok"], att["behaviour"] = False, diff
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "That version type-checks, but run under Python on the same input "
                                                     "it prints something different from the original:\n" + diff +
                                                     "\nFix the behaviour (keep it valid PySub) and return the complete "
                                                     "program again in one ```python block."}]
            continue
        messages += [{"role": "assistant", "content": reply},
                     {"role": "user", "content": "The PySub type checker rejected that version:\n"
                                                 + _diag_text(res["diagnostics"])
                                                 + "\nFix exactly these problems (keep everything else) and return the "
                                                   "complete program again in one ```python block."}]
    behaved = any(a.get("behaviour") for a in attempts)
    return {"ok": False, "attempts": attempts, **st, "model": getattr(client, "last_model", None) or st.get("model"),
            "error": (f"No conversion that behaves exactly like your program after {MAX_ATTEMPTS} attempts"
                      if behaved else f"No valid PySub after {MAX_ATTEMPTS} attempts")
                     + "; the last problems are shown. Your program still runs under Python (press Run), or try again."}
