"""Plain-English reasons a Python program can't become PySub (compiled C++), found by a quick AST scan.

`blockers(source)` -> [{line, what, why, fix}] for things NO rewrite can preserve: randomness, files, the network,
third-party libraries, eval... (the AI converter is not even asked: the answer would be wrong).  Constructs the
AI can rewrite (dicts as records, lambdas, comprehensions, math, collections, ...) are not listed.
`runtime(python, cpp)` -> a sentence for the common ways a compiled run legitimately differs (64-bit ints, ...).
"""
from __future__ import annotations

import ast
from typing import Dict, List, Optional

# modules whose behaviour a rewrite into plain loops and arithmetic can keep exactly
REWRITABLE = {"doctest", "math", "collections", "itertools", "functools", "string", "sys", "typing", "dataclasses", "copy",
              "heapq", "bisect", "operator", "statistics", "__future__", "abc", "enum"}

_WHY = {
    "random": ("random numbers", "the compiled program can't reproduce Python's exact random sequence, so its output "
               "could never be checked against your original",
               "pass the numbers in as input, or compute them with a fixed formula"),
    "time": ("the clock", "timings and dates differ on every run, so the outputs can't be compared",
             "remove the timing code; the Playground already times both versions"),
    "datetime": ("dates and times", "the current date differs on every run",
                 "pass the date in as input"),
    "os": ("the operating system", "PySub programs only read input() and print(); they can't touch files, folders "
           "or environment variables", "keep this part in Python"),
    "pathlib": ("files", "PySub programs only read input() and print()", "read the data with input() instead"),
    "json": ("JSON files", "PySub has no JSON parser", "keep this part in Python"),
    "csv": ("CSV files", "PySub programs only read input() and print()", "read the rows with input() instead"),
    "re": ("regular expressions", "PySub has no regex engine", "use str methods (split, find, startswith...)"),
    "threading": ("threads", "PySub programs are single-threaded", "keep this part in Python"),
    "multiprocessing": ("processes", "PySub programs are single-threaded", "keep this part in Python"),
    "asyncio": ("async code", "PySub has no event loop", "keep this part in Python"),
    "subprocess": ("other programs", "PySub programs can't start processes", "keep this part in Python"),
    "socket": ("the network", "PySub programs can't use the network", "keep this part in Python"),
    "tkinter": ("a GUI", "PySub programs are text-only", "keep the GUI in Python"),
    "turtle": ("turtle graphics", "PySub programs are text-only", "keep the drawing in Python"),
}
_LIB = ("a third-party library", "PySub compiles your own code only; library code (numpy, pandas, requests, ...) "
        "can't be translated to C++ by PYTHIA", "keep this part in Python; open the program as a Project and PYTHIA "
        "accelerates just the plain-Python hot functions")
_CALLS = {
    "open": ("files", "PySub programs only read input() and print()", "read the data with input() instead"),
    "eval": ("eval()", "running code built at run time can't be compiled ahead of time", "write the code directly"),
    "exec": ("exec()", "running code built at run time can't be compiled ahead of time", "write the code directly"),
    "__import__": ("dynamic imports", "PySub has no imports", "remove it"),
    "globals": ("globals()", "PySub variables are fixed at compile time", "pass values as parameters"),
    "locals": ("locals()", "PySub variables are fixed at compile time", "pass values as parameters"),
    "hash": ("hash()", "Python randomises string hashes on every run", "compare the values directly"),
    "id": ("id()", "object addresses differ between Python and C++", "compare the values directly"),
}


def blockers(source: str) -> List[Dict[str, object]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    out: List[Dict[str, object]] = []
    seen = set()

    def add(line: int, what: str, why: str, fix: str) -> None:
        if what not in seen:
            seen.add(what)
            out.append({"line": line, "what": what, "why": why, "fix": fix})

    for n in ast.walk(tree):
        mods: List[str] = []
        if isinstance(n, ast.Import):
            mods = [a.name.split(".")[0] for a in n.names]
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            mods = [n.module.split(".")[0]]
        for m in mods:
            if m in REWRITABLE:
                continue
            topic, why, fix = _WHY.get(m, _LIB)
            add(n.lineno, f"`import {m}` ({topic})", why, fix)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _CALLS:
            topic, why, fix = _CALLS[n.func.id]
            add(n.lineno, f"`{n.func.id}()`" + ("" if topic.endswith("()") else f" ({topic})"), why, fix)
        if isinstance(n, (ast.AsyncFunctionDef, ast.Await)):
            add(n.lineno, "async code", "PySub has no event loop", "keep this part in Python")
    return out


def syntax_error(source: str) -> Optional[str]:
    try:
        ast.parse(source)
        return None
    except SyntaxError as e:
        return f"This is not valid Python yet: line {e.lineno}: {e.msg}. Fix it first (the AI converts working programs)."


def runtime(python: Optional[dict], cpp: Optional[dict]) -> Optional[str]:
    """Why a compiled run differs from CPython, when the reason is a known PySub limit rather than a bug."""
    if not python or not cpp:
        return None
    pe, ce = python.get("exception"), cpp.get("exception")
    if ce == "OverflowError" and pe != "OverflowError":
        return ("The program computes integers beyond 64 bits (about ±9.2 × 10^18). Python switches to unlimited-size "
                "integers automatically; compiled PySub integers are 64-bit, so the C++ version stops with "
                "OverflowError instead of printing a wrong number. Keep values smaller (e.g. take results modulo a "
                "number) or keep this program in Python.")
    if ce == "PythiaSemanticError" and pe != ce:
        msg = (cpp.get("stderr") or "").strip().splitlines()[-1:] or [""]
        return ("The compiled program reached something PySub can't reproduce exactly and stopped instead of guessing: "
                + msg[0].split(":", 1)[-1].strip() + ". Keep that part (e.g. non-ASCII text) out of the compiled "
                "program or keep the program in Python.")
    if ce == "RecursionError" or (ce and "exit code" in ce and pe is None):
        return ("The compiled program crashed (often: recursion deeper than the C++ stack allows). Rewrite the "
                "deepest recursion as a loop, or keep this program in Python.")
    if python.get("timed_out") and not cpp.get("timed_out"):
        return "CPython hit the 10-second limit, so its output is incomplete; the compiled version finished."
    return None
