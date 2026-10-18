"""Turn the PySub compiler's own diagnostics into plain-English, user-facing reasons.

`explain(diags) -> (eligibility, reason, fix_kind)`:
  * not_eligible: a limit no rewrite of this function can remove (changes of type, no first-class functions ...)
  * fixable: the function might be rewritten into PySub (by hand or by the optional LLM step)
Messages come straight from the type checker, so new compiler features need no edit here: a construct that
becomes supported simply stops producing a diagnostic.
"""
from __future__ import annotations

import ast
import builtins
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
    (r"function '(\w+)' is not defined", "hard",
     lambda m, d: f"uses the Python builtin `{m[1]}`, which PySub does not provide" if hasattr(builtins, m[1])
     else f"calls `{m[1]}`, which is not a PySub function"),
    (r"declared -> (\w+) but control can reach the end", "soft",
     lambda m, d: f"promises a `{m[1]}` result but some path ends without returning a value (line {d['line']})"),
    (r"first-class functions|nested function definitions", "hard", lambda m, d: "uses a closure / first-class function"),
    (r"cannot infer element type of empty|cannot infer key/value type", "soft",
     lambda m, d: f"empty list/dict literal needs a type annotation (line {d['line']})"),
    (r"bare 'list'|bare 'dict'", "soft", lambda m, d: f"bare list/dict annotation needs element types (line {d['line']})"),
]


_PARSE = re.compile(r"^(expected .+ but found|unexpected token|unexpected character|unexpected end)")


def _constructs(n: ast.AST) -> List[str]:
    """Plain-English names of the Python construct at node `n` that PySub's parser has no rule for."""
    t = type(n)
    if t in (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp):
        return ["a comprehension (write an explicit loop with append)"]
    if t is ast.Lambda:
        return ["a lambda (define a normal function instead)"]
    if t is ast.Subscript and isinstance(n.slice, ast.Slice):
        return ["a slice like `a[i:j]` (loop over the range, or use a str method)"]
    if t is ast.Set:
        return ["a set literal (PySub has no sets; use a dict or a list)"]
    if t is ast.Tuple:
        if isinstance(n.ctx, ast.Store):
            return ["tuple unpacking like `a, b = ...` (assign each name separately)"]
        return ["a tuple (PySub has no tuples; use a list or separate values)"]
    if t is ast.NamedExpr:
        return ["an assignment expression (`:=`)"]
    if t is ast.Starred:
        return ["a star-expression (`*x`)"]
    if t is ast.Compare and any(isinstance(o, (ast.Is, ast.IsNot)) for o in n.ops):
        return ["`is` / `is not` (use `==` / `!=`)"]
    if t is ast.Assert:
        return ["an `assert` statement"]
    if t is ast.Delete:
        return ["a `del` statement"]
    if t in (ast.For, ast.While) and n.orelse:
        return [f"an `else` clause on a `{'for' if t is ast.For else 'while'}` loop"]
    if t is ast.Try and (n.finalbody or n.orelse):
        return ["a `finally` / `else` clause on `try`"]
    if t is ast.Dict and None in n.keys:
        return ["dict unpacking (`**d`)"]
    if t is ast.arguments and (n.defaults or any(k is not None for k in n.kw_defaults)):
        return ["a default parameter value (PySub functions need every argument)"]
    return []


def _find_constructs(source: str, line: int) -> List[str]:
    """Unsupported constructs starting on `line` of `source`, else the first one anywhere; [] if it will not parse."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    here, anywhere = [], []
    for n in ast.walk(tree):
        c = _constructs(n)
        if c:
            ln = getattr(n, "lineno", 10 ** 9)
            anywhere.append((ln, c[0]))
            if ln == line:
                here.append(c[0])
    return list(dict.fromkeys(here)) or [c for _, c in sorted(anywhere)][:1]


def _one(d: dict, source: Optional[str] = None) -> Tuple[str, str]:
    msg = d["msg"]
    if d.get("kind") == "Eligibility":
        return "hard", msg
    for pat, cls, fmt in _RULES:
        m = re.search(pat, msg)
        if m:
            return cls, fmt(m, d)
    if _PARSE.search(msg):                       # raw parser message -> the Python construct behind it
        found = _find_constructs(source, d["line"]) if source else []
        if found:
            return "soft", f"uses {found[0]}, which PySub does not support"
        if "';'" in msg:
            return "soft", f"line {d['line']}: a trailing semicolon (put each statement on its own line)"
        return "soft", f"line {d['line']}: syntax PySub's parser does not accept ({msg})"
    return "soft", f"line {d['line']}: {msg}"


def explain(diags: List[dict], source: Optional[str] = None) -> Tuple[str, str, str]:
    hard: List[str] = []
    soft: List[str] = []
    kind = "rewrite"
    for d in diags:
        cls, text = _one(d, source)
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
