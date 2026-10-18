"""Triage of PySub compiler diagnostics on converted programs: is this a construct the compiler is gaining natively
(tuples, comprehensions, lambdas, imports, module globals, defaults, Optional, ...) or a real gap of the converter?
Used by the corpus check and the tests while those compiler features are being merged."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

_RULES = [
    (r"\bimport\b", "imports (math / typing / collections)"),
    (r"\blambda\b", "lambda"),
    (r"\bglobal\b", "module globals / global"),
    (r"!r\}|!r:", "f-string !r"),
    (r"\b(enumerate|zip|any|all)\(", "enumerate / zip / any / all"),
    (r"Optional\[|\bNone\b", "Optional / None"),
    (r"tuple\[", "tuple types"),
]


def classify(diag: Dict, source: str, module_names=()) -> Optional[str]:
    """The pending compiler feature this diagnostic is about, 'cascade' for follow-on parse errors, or None."""
    msg = diag.get("msg", "")
    lines = source.splitlines()
    line = lines[diag["line"] - 1] if 0 < diag.get("line", 0) <= len(lines) else ""
    if re.search(r"unexpected token '(DEDENT|\s+)'|found 'DEDENT'|expected 'NAME' but found '\s+'", msg):
        return "cascade"
    if "found 'for'" in msg or re.search(r"[\[(].*\bfor\b.*\bin\b", line):
        return "comprehensions / generators"
    for pat, what in _RULES:
        if re.search(pat, line):
            return what
    if "found ','" in msg:
        return "tuples / tuple unpacking"
    if "found '='" in msg:
        return "default parameter values / keyword arguments"
    m = re.search(r"name '(\w+)' is not defined", msg)
    if m and m.group(1) in module_names:
        return "module globals / global"
    if "unexpected token ':'" in msg or re.search(r"\[[^\]]*:[^\]]*\]", line):
        return "slicing"
    if "expected ':' but found" in msg:          # parser recovery after an earlier error
        return "cascade"
    if "expected 'else'" in msg or "found 'else'" in msg:
        return "cascade"
    return None


def triage(diags: List[Dict], source: str) -> Dict[str, List[str]]:
    """{'pending': [features...], 'real': [messages...]}"""
    import ast
    try:
        tree = ast.parse(source)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    except SyntaxError:
        names = set()
    pending, real = [], []
    for d in diags:
        c = classify(d, source, names)
        if c is None:
            real.append(f"line {d['line']}: {d['msg']}")
        elif c != "cascade" and c not in pending:
            pending.append(c)
    return {"pending": pending, "real": real}
