"""Turn the PySub compiler's own diagnostics into plain-English, user-facing reasons.

`explain(diags) -> (eligibility, reason, fix_kind)`:
  * not_eligible: a limit no rewrite of this function can remove (changes of type, no first-class functions ...)
  * fixable: the function might be rewritten into PySub (by hand or by the optional LLM step)
Messages come straight from the type checker, so new compiler features need no edit here: a construct that
becomes supported simply stops producing a diagnostic.
"""
from __future__ import annotations

import re
from typing import Callable, List, Optional, Tuple

_Rule = Tuple[str, str, Callable]          # (regex, class 'hard'|'soft', formatter(match, diag) -> text)

_RULES: List[_Rule] = [
    (r"variable '(\w+)' was inferred as ([^;]+); cannot rebind to (.+?)\.",
     "hard", lambda m, d: f"variable `{m[1]}` changes type from {m[2].strip()} to {m[3].strip()} (dynamic typing)"),
    (r"'(\w+)' has static type ([^;]+); cannot assign (.+)",
     "hard", lambda m, d: f"variable `{m[1]}` changes type from {m[2].strip()} to {m[3].strip()} (dynamic typing)"),
    (r"unknown type '(\w+)'", "hard", lambda m, d: f"uses type `{m[1]}`, which PySub does not have"),
    (r"name '(\w+)' is not defined", "hard",
     lambda m, d: f"uses name `{m[1]}` that is not visible inside a PySub function (module state is invisible)"),
    (r"function '(\w+)' is not defined", "hard", lambda m, d: f"calls `{m[1]}`, which is not a PySub function"),
    (r"first-class functions|nested function definitions", "hard", lambda m, d: "uses a closure / first-class function"),
    (r"cannot infer element type of empty|cannot infer key/value type", "soft",
     lambda m, d: f"empty list/dict literal needs a type annotation (line {d['line']})"),
    (r"bare 'list'|bare 'dict'", "soft", lambda m, d: f"bare list/dict annotation needs element types (line {d['line']})"),
]


def _one(d: dict) -> Tuple[str, str]:
    msg = d["msg"]
    if d.get("kind") == "Eligibility":
        return "hard", msg
    for pat, cls, fmt in _RULES:
        m = re.search(pat, msg)
        if m:
            return cls, fmt(m, d)
    return "soft", f"line {d['line']}: {msg}"


def explain(diags: List[dict]) -> Tuple[str, str, str]:
    hard: List[str] = []
    soft: List[str] = []
    kind = "rewrite"
    for d in diags:
        cls, text = _one(d)
        if cls == "hard":
            if text not in hard:
                hard.append(text)
        elif text not in soft:
            soft.append(text)
            if "annotation" in text:
                kind = "annotations"
    from .scan import _short
    if hard:
        return "not_eligible", _short(hard, 2), kind
    return "fixable", _short(soft, 2) or "the type checker rejected the function", kind
