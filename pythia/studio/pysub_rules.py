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
from .. import builtins_ext as _bx
from .. import parse_ext as _px
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
        out[label] = sorted(set(out.get(label, [])) | set(names))    # several `if` blocks per receiver type
    for label, names in _bx.METHOD_TABLE.items():        # methods added through builtins_ext's hook
        out[label] = sorted(set(out.get(label, [])) | set(names))
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
    return {"builtins": sorted(set(names) | _bx.BUILTIN_NAMES)}


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
    mods = ", ".join(sorted(_px.MODULES))
    lines = [
        "PySub is a statically typed subset of Python. A function is valid PySub only if the PySub",
        "parser and typechecker accept it. The rules below are extracted from the compiler source.",
        "",
        "TYPES: int, float, bool, str, None, list[T], dict[K, V].",
        "  * Every parameter needs an annotation; the return annotation `-> T` is required unless the function returns nothing.",
        "  * list[T]: T is int/float/bool/str or list[T2] (at most 2 levels of nesting). Bare `list`/`dict` is an error.",
        "  * dict[K, V]: K is int or str; V is int, float, bool or str.",
        "  * No tuples, sets, Optional, Union, Any, typing imports (write list[int], not List[int]).",
        "  * Classes: fields are declared `name: T` in the class body (no default values) and an explicit",
        "    `def __init__(self, ...) -> None` must assign them; methods take `self` first. A record such as",
        "    {'name': n, 'marks': m} with mixed value types becomes a class (dict values must share one type).",
        "  * list[SomeClass] is allowed (lists of objects); printing an object or a list of objects is not.",
        "VARIABLES: inferred from the first assignment, then fixed (one static type per variable).",
        "  * The only implicit conversions are bool -> int -> float. A variable never changes type.",
        "  * An empty list/dict needs an annotation: `xs: list[int] = []`.",
        "  * Functions are CLOSED: module-level variables are invisible inside a function body. Pass state",
        "    (e.g. the list of records) as a parameter, or write literal constants. No closures, no nested defs,",
        "    no lambdas, no decorators, no default parameter values, no *args/**kwargs, no `global`.",
        "  * Imports: only `import " + mods.replace(", ", "` / `import ") + "` (and `from <module> import name [as alias]`).",
        "    math: sqrt isqrt floor ceil trunc fabs pow exp log(x[, base]) log2 log10 sin cos tan asin acos atan atan2 sinh cosh",
        "    tanh asinh acosh atanh log1p expm1 hypot degrees radians gcd lcm factorial comb perm isclose(rel_tol=, abs_tol=)",
        "    isfinite isinf isnan copysign fmod and the constants pi e tau inf nan. floor/ceil/trunc return int. int results",
        "    (factorial, comb, perm, gcd, lcm, <<) must fit in 64 bits (OverflowError otherwise).",
        "    string: ascii_lowercase ascii_uppercase ascii_letters digits hexdigits octdigits punctuation whitespace printable.",
        "  * Module-level statements run in order; `if __name__ == \"__main__\":` is accepted and runs its body.",
        "STATEMENTS: assignment (name / subscript / attribute target), augmented assignment (" + aug + "),",
        "  if/elif/else, while, `for v in range(a[, b[, step]])`, `for v in <list|str|dict>` (dict yields keys),",
        "  break, continue, pass, return, try/except [Name] [as e] (no finally, no else), raise Name(\"message\").",
        "  Exception names allowed: " + ", ".join(sorted(EXC_NAMES)) + ". In `except E as e`, e is the message (a str).",
        "EXPRESSIONS: literals, names, [..] and {k: v} literals, subscripts a[i], calls, method calls,",
        "  binary operators, loosest to tightest binding: " + ops + " (** is right-associative),",
        "  bitwise operators & | ^ << >> and unary ~ on int/bool with Python's two's-complement semantics (also &= |= ^= <<= >>=;",
        "  bool & | ^ bool stays bool; a shift past int64 raises OverflowError),",
        "  slicing on str and list: a[i:j], a[:j], a[i:], a[::k], a[::-1] (negative / out-of-range bounds as in Python; no slice",
        "  assignment, no del),",
        "  \"literal\".format(...) with {} / {0} / {name} fields (+ !s !r and format specs) and \"%d %s\" % (a, b) (flags, width,",
        "  precision, d i u o x X e E f F g G c r s %%), both only with a string-literal template,",
        "  unary - + not, comparisons and chains like `0 <= i < n` (the middle operand must be a name, literal,",
        "  field or subscript, not a call), `in` / `not in`.",
        "  * f-strings ARE supported: f\"{name} scored {marks:.2f}\" (format specs: fill/align/sign/0/width/,/.precision",
        "    with types d f e g % s; no !r, no {x=}). Triple-quoted strings and docstrings are fine.",
        "  * Conditional expressions ARE supported: `x if c else y`, when both branches have the SAME type",
        "    (an int branch and a float branch is an error: write float(x) or use an if/else statement).",
        "  * No comprehensions, generator expressions,",
        "    tuple unpacking, `is`/`is not`, walrus, star-expressions, `with`, `assert`, `del`, lambda.",
        "  * Comprehension -> explicit loop with append. enumerate/zip -> index loop",
        "    `for i in range(len(xs))`. sort(key=...)/max(key=...) -> an explicit loop over the records.",
        "BUILTIN FUNCTIONS (exactly these): " + ", ".join(sorted(BUILTINS)) + ".",
        "  * input(prompt) -> str. print(..., sep=\" \", end=\"\\n\") (only print/sorted/list.sort take keyword arguments).",
        "  * min/max: two or more numbers (or strs), or ONE list. sum(list of numbers). sorted(list, reverse=bool).",
        "  * list(x) and sorted(x) also take a str (its characters, list[str]) or a dict (its keys); list(xs) copies a list.",
        "  * round(x) -> int, round(x, n). format(value, \".2f\"). len works on list/str/dict.",
        "  * int()/float() parse a str (surrounding spaces allowed) and raise ValueError on bad input; str()/bool() convert.",
        "  * pow(a, b) / pow(a, b, mod) (mod may be negative; pow(a, -1, m) is the modular inverse), bin hex oct (str),",
        "    int(s, base) (base 0 and 2..36), repr(int/float/bool/str), float('inf') / float('nan'), round(x[, n]) (half-to-even).",
        "  * divmod(a, b) -> tuple (ints or floats). repr(x) / f\"{x!r}\" for int/float/bool/str and flat lists, dicts, tuples of",
        "    those (CPython's quoting and escapes). Adjacent string literals concatenate (\"a\" f\"{x}\" \"b\", also across lines).",
        "  * There is NO enumerate, zip, any, all, reversed, set, dict(), open, isinstance, hash.",
        "METHODS (exactly these):",
        "  * str: lower upper strip lstrip rstrip (optional chars) title capitalize swapcase isdigit isalpha isalnum",
        "    isspace isupper islower startswith endswith find rfind index count replace(old, new) split() split(sep) join(list[str])",
        "    zfill center ljust rjust (fill must be 1 char) isnumeric isdecimal istitle isascii casefold removeprefix removesuffix",
        "    expandtabs rsplit(sep, maxsplit) split(sep, maxsplit) split(None, maxsplit) splitlines(keepends) rindex; find / rfind /",
        "    index / rindex / count / startswith / endswith take optional start, end (str arguments only, no tuple prefixes).",
        "    partition / rpartition need tuples and are not available.",
        "  * list: append pop() pop(i) insert(i, x) extend(list) clear() reverse() copy() index(x) count(x) remove(x)",
        "    sort(reverse=bool)   (sort/index/count/remove need int/float/bool/str elements; objects compare by identity)",
        "    index(x, start, stop)",
        "  * dict: get(key, default) pop(key[, default]) setdefault(key, default) update(other) copy() clear() fromkeys via",
        "    dict.fromkeys(keys, value), and keys() / values() (lists, accepted only directly in a for loop, `in`, len, sorted,",
        "    list, sum, min, max or str.join; no items()). Iterate `for k in d` and index d[k].",
        "  * String indexing s[i] returns a one-character str. str + str, str * int, list + list are allowed.",
        "ARITHMETIC: // and % follow Python semantics; / is true division and always float; int arithmetic is",
        "  64-bit (overflow traps); ** of ints is int.",
        "OTHER RESTRICTIONS stated by the compiler:",
    ]
    for s in _restriction_messages()[:14]:
        lines.append("  * " + s)
    return "\n".join(lines)
