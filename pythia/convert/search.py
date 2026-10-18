"""Types for parameters that no call site pins down (LeetCode-style `class Solution` methods, library functions
nobody calls in the pasted file): try candidate types, most plausible first, and let the PySub type checker
decide. A combination is accepted only if the whole converted program type-checks.

    best_assignment(tree, unresolved, build, accepts) -> (seeds, out) | None
"""
from __future__ import annotations

import ast
import itertools
from typing import Callable, Dict, List, Optional, Tuple

INT, FLOAT, STR, BOOL = "int", "float", "str", "bool"
L = lambda t: ("list", t)  # noqa: E731

CANDIDATES = [INT, STR, FLOAT, BOOL, L(INT), L(STR), L(FLOAT), L(L(INT)), L(BOOL), L(L(STR)), L(L(FLOAT)),
              ("dict", STR, INT), ("dict", INT, INT), ("dict", STR, STR), ("dict", STR, L(STR)), ("dict", INT, L(INT))]
STR_METHODS = {"lower", "upper", "strip", "split", "join", "replace", "startswith", "endswith", "isdigit", "isalpha",
               "find", "title", "isalnum", "count"}
LIST_METHODS = {"append", "pop", "extend", "insert", "sort", "reverse", "remove", "index"}
MAX_TRIES = 400


def _hints(fn: ast.FunctionDef, name: str) -> Dict[str, int]:
    """Syntactic evidence about parameter `name`: kind -> weight."""
    h: Dict[str, int] = {}

    def add(k, w=1):
        h[k] = h.get(k, 0) + w
    for n in ast.walk(fn):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
            args = n.args
            if n.func.id == "range" and any(isinstance(a, ast.Name) and a.id == name for a in args):
                add("int", 3)
            if n.func.id == "range" and any(_mentions(a, name) for a in args):
                add("int", 1)
            if n.func.id == "len" and args and isinstance(args[0], ast.Name) and args[0].id == name:
                add("seq", 3)
            if n.func.id in ("int", "float") and args and isinstance(args[0], ast.Name) and args[0].id == name:
                add("str", 2)
            if n.func.id in ("sum", "sorted", "min", "max", "list") and args and isinstance(args[0], ast.Name) \
                    and args[0].id == name:
                add("list", 2)
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name) and n.value.id == name:
            add("seq", 3)
            if isinstance(n.value, ast.Name) and isinstance(n.slice, ast.Subscript):
                add("nested", 1)
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Subscript) and isinstance(n.value.value, ast.Name) \
                and n.value.value.id == name:
            add("nested", 3)
        if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == name:
            if n.attr in STR_METHODS:
                add("str", 3)
            if n.attr in LIST_METHODS:
                add("list", 3)
        if isinstance(n, (ast.For, ast.comprehension)) and isinstance(n.iter, ast.Name) and n.iter.id == name:
            add("seq", 2)
        if isinstance(n, ast.Compare):
            parts = [n.left] + n.comparators
            if any(isinstance(p, ast.Name) and p.id == name for p in parts):
                if any(isinstance(p, ast.Constant) and isinstance(p.value, str) for p in parts):
                    add("str", 3)
                if any(isinstance(p, ast.Constant) and isinstance(p.value, (int, float)) for p in parts):
                    add("num", 1)
        if isinstance(n, ast.BinOp) and any(isinstance(x, ast.Name) and x.id == name for x in (n.left, n.right)):
            add("num", 1)
        if isinstance(n, ast.JoinedStr):
            pass
    return h


def _mentions(e: ast.AST, name: str) -> bool:
    return any(isinstance(x, ast.Name) and x.id == name for x in ast.walk(e))


def ranked(fn: ast.FunctionDef, name: str) -> List[object]:
    h = _hints(fn, name)

    def score(c) -> float:
        s = 0.0
        islist = isinstance(c, tuple) and c[0] == "list"
        isdict = isinstance(c, tuple) and c[0] == "dict"
        nested = islist and isinstance(c[1], tuple) and c[1][0] == "list"
        if c == INT:
            s += h.get("int", 0) * 2 + h.get("num", 0) * 1.0 - h.get("seq", 0) * 2 - h.get("list", 0) * 3 \
                - h.get("str", 0) * 3
        elif c == FLOAT:
            s += h.get("num", 0) * 0.5 - h.get("seq", 0) * 2 - h.get("list", 0) * 3 - h.get("str", 0) * 3 \
                - h.get("int", 0)
        elif c == STR:
            s += h.get("str", 0) * 2 + h.get("seq", 0) * 0.6 - h.get("list", 0) * 3 - h.get("int", 0)
        elif c == BOOL:
            s -= 1
        elif islist:
            s += h.get("seq", 0) * 1.5 + h.get("list", 0) * 2 - h.get("str", 0) * 2 - h.get("int", 0) * 1.5 \
                + (h.get("nested", 0) * 2 if nested else -h.get("nested", 0) * 2)
            if not nested and c[1] != INT:
                s -= 0.3
            if nested:
                s -= 0.2
        elif isdict:
            s += h.get("seq", 0) * 0.3 - 1.5
        return s
    order = sorted(range(len(CANDIDATES)), key=lambda i: (-score(CANDIDATES[i]), i))
    return [CANDIDATES[i] for i in order]


def best_assignment(unresolved: List[Tuple[str, ast.FunctionDef, str]],
                    build: Callable[[Dict[tuple, object]], Optional[str]],
                    accepts: Callable[[str], bool]):
    """unresolved: [(qualname, FunctionDef, param name)]. build(seeds) -> converted source (or None);
    accepts(source) -> the PySub type checker takes it. Best-first over the product of the per-parameter rankings."""
    lists = [ranked(fn, p) for _q, fn, p in unresolved]
    combos = sorted(itertools.product(*[range(len(x)) for x in lists]), key=lambda ix: (sum(ix), ix))
    for ix in combos[:MAX_TRIES]:
        seeds = {("var", q, p): lists[k][ix[k]] for k, (q, _fn, p) in enumerate(unresolved)}
        out = build(seeds)
        if out is not None and accepts(out):
            return seeds, out
        if out is not None and not best_assignment.tried:
            best_assignment.first = (seeds, out)      # the most plausible guess, kept for diagnostics
        best_assignment.tried += 1
    return None


best_assignment.tried = 0
best_assignment.first = None
