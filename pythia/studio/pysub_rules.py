"""PySub rules, derived FROM the compiler source (lexer/parser/typecheck), never hand-copied.

* `check_source(src)`  -> list of diagnostic dicts from the REAL parser + typechecker.
* `rules_text()`       -> the PySub rules block placed in the LLM prompt.
* `METHODS`, `BUILTINS`, `EXC_NAMES` -> tables other studio modules use for friendly reasons.
"""
from __future__ import annotations

import ast
import inspect
import re
import textwrap
from functools import lru_cache
from typing import Dict, List, Set

from .. import lexer as _lexer
from .. import parser as _parser
from .. import typecheck as _tc
from ..lexer import LexError


def check_source(src: str, filename: str = "<pysub>") -> List[dict]:
    """Run the real parser + typechecker. Returns [] when `src` is valid PySub."""
    try:
        mod, syn = _parser.parse(src, filename)
    except LexError as e:
        return [{"line": e.line, "col": e.col, "kind": "SyntaxError", "msg": e.msg}]
    except Exception as e:  # pragma: no cover - defensive: never crash the scan
        return [{"line": 1, "col": 1, "kind": "InternalError", "msg": f"parser crashed: {e!r}"}]
    if syn:
        return sorted(({"line": d.line, "col": d.col, "kind": d.kind, "msg": d.msg} for d in syn),
                      key=lambda d: (d["line"], d["col"]))
    try:
        _, errs = _tc.typecheck(mod, filename)
    except Exception as e:  # pragma: no cover
        return [{"line": 1, "col": 1, "kind": "InternalError", "msg": f"typechecker crashed: {e!r}"}]
    return sorted(({"line": d.line, "col": d.col, "kind": d.kind, "msg": d.msg} for d in errs),
                  key=lambda d: (d["line"], d["col"]))


# --------------------------------------------------------- tables from the code
def _src(obj) -> str:
    return textwrap.dedent(inspect.getsource(obj))


@lru_cache(maxsize=1)
def _methods() -> Dict[str, List[str]]:
    """{'list': ['append','pop'], 'str': [...], 'dict': ['get']} read off synth_method's AST."""
    tree = ast.parse(_src(_tc.TypeChecker.synth_method))
    fn = tree.body[0]
    out: Dict[str, List[str]] = {}
    for st in fn.body:
        if not isinstance(st, ast.If):
            continue
        t = ast.unparse(st.test)
        label = "list" if "'list'" in t or '"list"' in t else \
                "dict" if "'dict'" in t or '"dict"' in t else \
                "str" if "STR" in t else None
        if label is None:
            continue
        names = []
        for n in ast.walk(st):
            if isinstance(n, ast.Compare) and ast.unparse(n.left) == "e.method":
                for c in n.comparators:
                    if isinstance(c, ast.Constant) and isinstance(c.value, str):
                        names.append(c.value)
        out[label] = sorted(set(names))
    return out


@lru_cache(maxsize=1)
def _call_names() -> Dict[str, List[str]]:
    """Names handled by synth_call: print/len/abs/min/max/int/float/str/bool."""
    tree = ast.parse(_src(_tc.TypeChecker.synth_call))
    names: List[str] = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Compare) and ast.unparse(n.left) == "name":
            for c in n.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    names.append(c.value)
                elif isinstance(c, ast.Tuple):
                    names += [e.value for e in c.elts if isinstance(e, ast.Constant)]
    return {"builtins": sorted(set(names))}


METHODS: Dict[str, List[str]] = _methods()
BUILTINS: Set[str] = set(_call_names()["builtins"]) | set(_tc.BUILTIN_SIGS) | {"range"}
EXC_NAMES: Set[str] = set(_tc.EXC_NAMES)
KEYWORDS: Set[str] = set(_lexer.KEYWORDS)
ALL_METHOD_NAMES: Set[str] = {m for v in METHODS.values() for m in v}


@lru_cache(maxsize=1)
def _restriction_messages() -> List[str]:
    """Every error string in the compiler that states an explicit PySub restriction."""
    msgs: List[str] = []
    for mod in (_tc, _parser):
        tree = ast.parse(inspect.getsource(mod))
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                s = " ".join(n.value.split())
                if ("PySub" in s or "outside" in s or "not allowed" in s) and 25 < len(s) < 220                         and "{" not in s and s.split()[0] not in ("is", "instance", "instances", "declares"):
                    msgs.append(s)
    seen, out = set(), []
    for m in msgs:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


@lru_cache(maxsize=1)
def rules_text() -> str:
    tiers: Dict[int, List[str]] = {}
    for k, v in _parser.BP.items():
        tiers.setdefault(v, []).append(k)
    ops = "  |  ".join(" ".join(sorted(tiers[b])) for b in sorted(tiers))
    aug = " ".join(sorted(_parser.AUG_OPS))
    m = METHODS
    lines = [
        "PySub is a statically typed subset of Python. A function is valid PySub only if the PySub",
        "parser and typechecker accept it. The rules below are extracted from the compiler source.",
        "",
        "TYPES: int, float, bool, str, None, list[T], dict[K, V].",
        "  * Every parameter needs an annotation; the return annotation `-> T` is required unless the function returns nothing.",
        "  * list[T]: T is int/float/bool/str or list[T2] (at most 2 levels of nesting). Bare `list`/`dict` is an error.",
        "  * dict[K, V]: K is int or str; V is int, float, bool or str.",
        "  * No tuples, sets, Optional, Union, Any, typing imports (write list[int], not List[int]).",
        "  * Classes: fields are declared `name: T` in the class body and an explicit __init__ is required;",
        "    prefer plain functions over classes.",
        "VARIABLES: inferred from the first assignment, then fixed (one static type per variable).",
        "  * The only implicit conversions are bool -> int -> float. A variable never changes type.",
        "  * An empty list/dict needs an annotation: `xs: list[int] = []`.",
        "  * Functions are CLOSED: module-level globals are invisible inside a function body. Pass values as",
        "    parameters or write literal constants. No closures, no nested defs, no lambdas, no decorators,",
        "    no default parameter values, no *args/**kwargs, no keyword arguments, no imports.",
        "STATEMENTS: assignment (name / subscript / attribute target), augmented assignment (" + aug + "),",
        "  if/elif/else, while, `for v in range(a[, b[, step]])`, `for v in <list|str|dict>` (dict yields keys),",
        "  break, continue, pass, return, try/except [Name] [as e] (no finally, no else), raise Name(\"message\").",
        "  Exception names allowed: " + ", ".join(sorted(EXC_NAMES)) + ".",
        "EXPRESSIONS: literals, names, [..] and {k: v} literals, subscripts a[i], calls, method calls,",
        "  binary operators, loosest to tightest binding: " + ops + " (** is right-associative),",
        "  unary - + not, comparisons (chains like a < b < c are NOT supported), `in` / `not in`.",
        "  * No comprehensions, generator expressions, conditional expressions (x if c else y), f-strings,",
        "    slicing a[i:j], tuple unpacking, `is`/`is not`, walrus, star-expressions, `with`, `assert`, `del`, `global`.",
        "  * Ternary -> if/else statement. Comprehension -> explicit loop with append. enumerate/zip -> index loop.",
        "BUILTIN FUNCTIONS (exactly these): " + ", ".join(sorted(BUILTINS)) + ".",
        "  * min/max take exactly two arguments. len works on list/str/dict. int()/float()/str()/bool() convert.",
        "  * There is NO sum, sorted, enumerate, zip, round, divmod, pow, any, all, reversed, set, list(), dict(), ord, chr.",
        "METHODS (exactly these): " + "; ".join(f"{k}: {', '.join('.' + x + '()' for x in v)}" for k, v in sorted(m.items())) + ".",
        "  * list.pop() takes no index. dict.get(key, default) takes exactly two arguments.",
        "  * No str.split/join/strip/replace/find/startswith, no list.extend/insert/remove/sort/index, no dict.items/keys/values.",
        "  * String indexing s[i] returns a one-character str. str + str, str * int, list + list are allowed.",
        "ARITHMETIC: // and % follow Python semantics; / is true division and always float; int arithmetic is",
        "  64-bit (overflow traps); ** of ints is int.",
        "OTHER RESTRICTIONS stated by the compiler:",
    ]
    for s in _restriction_messages()[:14]:
        lines.append("  * " + s)
    return "\n".join(lines)
