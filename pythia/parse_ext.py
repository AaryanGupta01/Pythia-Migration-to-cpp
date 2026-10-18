"""
PYTHIA :: parse-time sugar for the builtins / standard-library surface.

Everything here runs inside the parser and rewrites into nodes the rest of the compiler already understands:

  * `import math` / `from math import sqrt` / `import string`  -> namespaced calls `Call("math.sqrt", ...)`,
    constants (math.pi, string.ascii_lowercase) -> literals;
  * `a[i:j:k]`                      -> `Call("__slice", [a, i, j, k])` (missing parts are NoneLit);
  * `"{} {x:.2f}".format(a, x=b)`   -> the same concatenation of str()/format() calls an f-string produces;
  * `"%d items, %s" % (n, s)`       -> likewise (the tuple on the right is read here, so no tuple type is needed).

Only module-name tables and syntax live here; types, emission and fidelity notes are in builtins_ext.py.
"""
import copy
import math
import string as _string
from typing import List, Optional

from . import ast_nodes as A

# --------------------------------------------------------------------------------------------- module tables
# name -> (min_args, max_args, per-position arg kind (last repeats), result kind)
#   arg kinds:  f = any number (int/bool/float, read as float)   i = integer (int/bool)   n = any number, kept as is
#   result kinds: F float  I int  B bool
MATH_FUNCS = {}
for _n in ("sqrt exp log2 log10 sin cos tan asin acos atan degrees radians fabs sinh cosh tanh asinh acosh atanh "
           "log1p expm1").split():
    MATH_FUNCS[_n] = (1, 1, "f", "F")
MATH_FUNCS.update({
    "log": (1, 2, "f", "F"),
    "atan2": (2, 2, "f", "F"), "hypot": (2, 2, "f", "F"), "pow": (2, 2, "f", "F"),
    "copysign": (2, 2, "f", "F"), "fmod": (2, 2, "f", "F"),
    "isqrt": (1, 1, "i", "I"), "factorial": (1, 1, "i", "I"),
    "floor": (1, 1, "n", "I"), "ceil": (1, 1, "n", "I"), "trunc": (1, 1, "n", "I"),
    "gcd": (1, 8, "i", "I"), "lcm": (1, 8, "i", "I"),
    "comb": (2, 2, "i", "I"), "perm": (1, 2, "i", "I"),
    "isclose": (2, 2, "f", "B"),
    "isfinite": (1, 1, "f", "B"), "isinf": (1, 1, "f", "B"), "isnan": (1, 1, "f", "B"),
})
MATH_FLOAT_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}    # become FloatLit
MATH_CALL_CONSTS = {"inf", "nan"}                                    # zero-argument Call("math.inf")

STRING_CONSTS = {
    "ascii_lowercase": _string.ascii_lowercase, "ascii_uppercase": _string.ascii_uppercase,
    "ascii_letters": _string.ascii_letters, "digits": _string.digits, "hexdigits": _string.hexdigits,
    "octdigits": _string.octdigits, "punctuation": _string.punctuation, "whitespace": _string.whitespace,
    "printable": _string.printable,
}

MODULES = {
    "math": set(MATH_FUNCS) | set(MATH_FLOAT_CONSTS) | MATH_CALL_CONSTS,
    "string": set(STRING_CONSTS),
}
MODULES.update({                       # annotations and containers (resolved in types_ext.py)
    "typing": {"List", "Dict", "Set", "Tuple", "Optional", "Union", "Sequence", "Iterable", "DefaultDict"},
    "__future__": {"annotations"},
    "collections": {"defaultdict", "Counter"},
})
MODULES["dataclasses"] = {"dataclass"}  # @dataclass on user classes (classes_ext.py)


class Imports:
    """What the file has imported so far: `modules` alias -> module, `names` local name -> (module, attr)."""

    def __init__(self):
        self.modules = {}
        self.names = {}


def _const_or_call(p, mod: str, attr: str, tok, allow_call_args: bool = True) -> A.Node:
    """The node for module attribute `mod.attr` (after the name has been consumed); parses the call if present."""
    if attr not in MODULES[mod]:
        p.error(f"module {mod!r} has no attribute {attr!r} in PySub (available: {', '.join(sorted(MODULES[mod]))})")
        raise _panic()
    line, col = tok.line, tok.col
    if mod == "string":
        return A.StrLit(line, col, value=STRING_CONSTS[attr])
    if attr in MATH_FLOAT_CONSTS:
        return A.FloatLit(line, col, value=MATH_FLOAT_CONSTS[attr])
    if p.at_op("("):
        p.next()
        args, kwargs = p._call_args()
        return A.Call(line, col, func=f"{mod}.{attr}", args=args, kwargs=kwargs)
    if attr in MATH_CALL_CONSTS:
        return A.Call(line, col, func=f"{mod}.{attr}", args=[], kwargs=[])
    p.error(f"{mod}.{attr} is a function; PySub has no first-class functions (call it: {mod}.{attr}(...))")
    raise _panic()


def _panic():
    from .parser import _Panic            # lazy: parser imports this module
    return _Panic()


def module_attr(p, base: A.Name, dot_tok) -> A.Node:
    """`mod . attr [ (args) ]` where `mod` names an imported module; the '.' is the current token."""
    p.next()                                    # '.'
    attr = p.expect("NAME")
    return _const_or_call(p, p.imports.modules[base.id], attr.value, dot_tok)


def imported_name(p, t) -> Optional[A.Node]:
    """A bare name bound by `from math import sqrt` -> the namespaced call / constant. `t` was just consumed."""
    mod, attr = p.imports.names[t.value]
    return _const_or_call(p, mod, attr, t)


def parse_import(p) -> A.Node:
    """import m [as a][, m2 ...]   |   from m import x [as y][, ...]  |  from m import (x, y)"""
    first = p.next()
    pas = A.Pass(first.line, first.col)

    def mod_name():
        nm = p.expect("NAME")
        if p.at_op("."):
            p.error(f"submodule imports are outside the PySub subset (supported modules: {', '.join(sorted(MODULES))})")
            raise _panic()
        if nm.value not in MODULES:
            p.error(f"module {nm.value!r} is not supported in PySub (supported modules: {', '.join(sorted(MODULES))})")
            raise _panic()
        return nm.value

    def alias(default: str) -> str:
        if p.cur.kind == "NAME" and p.cur.value == "as":
            p.next()
            return p.expect("NAME").value
        return default

    if first.value == "import":
        while True:
            m = mod_name()
            p.imports.modules[alias(m)] = m
            if p.at_op(","):
                p.next()
                continue
            break
    else:
        m = mod_name()
        if not (p.cur.kind == "NAME" and p.cur.value == "import"):
            p.error("expected 'import'")
            raise _panic()
        p.next()
        if p.at_op("*"):
            p.error("`from ... import *` is outside the PySub subset; import the names you use")
            raise _panic()
        paren = p.at_op("(")
        if paren:
            p.next()
        while True:
            nm = p.expect("NAME")
            if nm.value not in MODULES[m]:
                p.error(f"module {m!r} has no attribute {nm.value!r} in PySub (available: "
                        f"{', '.join(sorted(MODULES[m]))})")
                raise _panic()
            p.imports.names[alias(nm.value)] = (m, nm.value)
            if p.at_op(","):
                p.next()
                if paren and p.at_op(")"):
                    break
                continue
            break
        if paren:
            p.expect("OP", ")")
    p.expect("NEWLINE")
    return pas


def parse_string_run(p) -> A.Node:
    """One or more adjacent string literals (plain and f-strings, possibly on several lines inside parentheses)."""
    nodes: List[A.Node] = []
    while p.cur.kind in ("STRING", "FSTRING"):
        t = p.next()
        nodes.append(A.StrLit(t.line, t.col, value=t.value) if t.kind == "STRING" else p._fstring(t))
    merged: List[A.Node] = []
    for n in nodes:
        if merged and isinstance(merged[-1], A.StrLit) and isinstance(n, A.StrLit):
            merged[-1] = A.StrLit(merged[-1].line, merged[-1].col, value=merged[-1].value + n.value)
        else:
            merged.append(n)
    node = merged[0]
    for q in merged[1:]:
        node = A.BinOp(q.line, q.col, op="+", left=node, right=q)
    return node


# ------------------------------------------------------------------------------------------------- slicing
def parse_subscript(p, base: A.Node, t) -> A.Node:
    """After '[': an index `a[i]` or a slice `a[i:j]`, `a[::k]`; consumes the closing ']'."""
    parts: List[Optional[A.Node]] = []
    cur: Optional[A.Node] = None
    colons = 0
    while True:
        if p.at_op(":"):
            parts.append(cur)
            cur = None
            colons += 1
            p.next()
            if colons > 2:
                p.error("a slice has at most two ':' separators")
                raise _panic()
            continue
        if p.at_op("]"):
            break
        if cur is not None:
            p.error("expected ']' in subscript")
            raise _panic()
        cur = p.parse_exprlist()                 # a[i] or a bare-tuple index a[i, j]
    p.expect("OP", "]")
    if colons == 0:
        return A.Subscript(t.line, t.col, value=base, index=cur)
    parts.append(cur)
    while len(parts) < 3:
        parts.append(None)
    args = [base] + [x if x is not None else A.NoneLit(t.line, t.col) for x in parts]
    return A.Call(t.line, t.col, func="__slice", args=args, kwargs=[])


# ------------------------------------------------------------------------------------- str.format / % sugar
def _pure(e: A.Node) -> bool:
    if isinstance(e, (A.Name, A.IntLit, A.FloatLit, A.StrLit, A.BoolLit)):
        return True
    if isinstance(e, A.UnaryOp):
        return _pure(e.operand)
    if isinstance(e, A.Attribute):
        return _pure(e.value)
    if isinstance(e, A.Subscript):
        return _pure(e.value) and _pure(e.index)
    if isinstance(e, A.BinOp):
        return _pure(e.left) and _pure(e.right)
    return False


def _fail(p, tok, msg: str):
    from .parser import Diagnostic
    p.errors.append(Diagnostic(msg, tok.line, tok.col))
    raise _panic()


def _concat(parts: List[A.Node], tok) -> A.Node:
    if not parts:
        return A.StrLit(tok.line, tok.col, value="")
    node = parts[0]
    for q in parts[1:]:
        node = A.BinOp(tok.line, tok.col, op="+", left=node, right=q)
    return node


def _lit(tok, s: str) -> A.Node:
    return A.StrLit(tok.line, tok.col, value=s)


def _call(tok, fn: str, *args: A.Node) -> A.Node:
    return A.Call(tok.line, tok.col, func=fn, args=list(args), kwargs=[])


def desugar_format(p, recv: A.StrLit, args: List[A.Node], kwargs: list, tok) -> A.Node:
    """'literal'.format(...) with positional / keyword / auto-numbered fields -> str()/format() concatenation."""
    tpl = recv.value
    n, i, lit = len(tpl), 0, ""
    parts: List[A.Node] = []
    fields = []                       # (arg_expr_key, conv, spec)  in order of appearance
    auto = manual = False
    next_auto = 0
    while i < n:
        c = tpl[i]
        if c == "{":
            if tpl.startswith("{{", i):
                lit += "{"
                i += 2
                continue
            j, depth = i + 1, 0
            while j < n and not (tpl[j] == "}" and depth == 0):
                if tpl[j] == "{":
                    depth += 1
                elif tpl[j] == "}":
                    depth -= 1
                j += 1
            if j >= n:
                _fail(p, tok, "str.format: expected '}' before end of string")
            body = tpl[i + 1:j]
            spec = ""
            conv = None
            name = body
            if ":" in body:
                name, spec = body.split(":", 1)
            if "!" in name:
                name, conv = name.split("!", 1)
            if "{" in spec or "}" in spec:
                _fail(p, tok, "str.format: nested replacement fields in a format spec are outside the PySub subset")
            if conv not in (None, "s", "r"):
                _fail(p, tok, f"str.format: conversion '!{conv}' is outside the PySub subset (use !s, !r or none)")
            if "." in name or "[" in name:
                _fail(p, tok, "str.format: attribute / index access inside a replacement field is outside the PySub "
                              "subset; pass the value as an argument")
            if name == "":
                if manual:
                    _fail(p, tok, "str.format: cannot switch from manual field specification to automatic field numbering")
                auto = True
                key = next_auto
                next_auto += 1
            elif name.isdigit():
                if auto:
                    _fail(p, tok, "str.format: cannot switch from automatic field numbering to manual field specification")
                manual = True
                key = int(name)
            elif name.isidentifier():
                key = name
            else:
                _fail(p, tok, f"str.format: invalid replacement field name {name!r}")
            if lit:
                parts.append(("lit", lit))
                lit = ""
            fields.append(len(parts))
            parts.append(("field", key, conv, spec))
            i = j + 1
            continue
        if c == "}":
            if tpl.startswith("}}", i):
                lit += "}"
                i += 2
                continue
            _fail(p, tok, "str.format: single '}' encountered in format string")
        lit += c
        i += 1
    if lit:
        parts.append(("lit", lit))

    kw = {k.name: k.value for k in kwargs}
    used_order = []
    for pt in parts:
        if pt[0] != "field":
            continue
        key = pt[1]
        if isinstance(key, int):
            if key >= len(args):
                _fail(p, tok, f"str.format: Replacement index {key} out of range for positional args tuple "
                              f"(IndexError in CPython)")
        elif key not in kw:
            _fail(p, tok, f"str.format: no keyword argument {key!r} was given (KeyError in CPython)")
        used_order.append(key)
    # every argument expression must be evaluated exactly once, in order
    exprs = list(args) + [k.value for k in kwargs]
    keys = list(range(len(args))) + [k.name for k in kwargs]
    for ex_, key in zip(exprs, keys):
        if not _pure(ex_):
            uses = used_order.count(key)
            if uses != 1:
                _fail(p, tok, "str.format: an argument that calls a function must be used exactly once in the template "
                              "(assign it to a variable first)")
    impure_seen = [k for k in used_order if not _pure(exprs[keys.index(k)])]
    if impure_seen != [k for k in keys if k in impure_seen]:
        _fail(p, tok, "str.format: arguments that call functions must appear in the template in argument order "
                      "(assign them to variables first)")
    out: List[A.Node] = []
    for pt in parts:
        if pt[0] == "lit":
            out.append(_lit(tok, pt[1]))
            continue
        _, key, conv, spec = pt
        val = copy.deepcopy(exprs[keys.index(key)])
        if conv == "r":
            val = _call(tok, "repr", val)
        elif conv == "s" and spec:
            val = _call(tok, "str", val)
        out.append(_call(tok, "format", val, _lit(tok, spec)) if spec else _call(tok, "str", val))
    return _concat(out, tok)


_PCT_TYPES = "diuoxXeEfFgGcrs"


def parse_pct_rhs(p) -> Optional[List[A.Node]]:
    """Right operand of `'literal' % ...`: a parenthesised tuple `(a, b)` is read here as a list of arguments.
    Returns None when the operand is not a tuple (the caller then parses a normal expression)."""
    if not p.at_op("("):
        return None
    save, nerr = p.i, len(p.errors)
    p.next()
    items: List[A.Node] = []
    try:
        if p.at_op(")"):
            p.next()
            return []
        items.append(p.parse_expr())
        if not p.at_op(","):
            p.i = save
            del p.errors[nerr:]
            return None
        while p.at_op(","):
            p.next()
            if p.at_op(")"):
                break
            items.append(p.parse_expr())
        p.expect("OP", ")")
    except Exception:
        p.i = save
        del p.errors[nerr:]
        return None
    # a tuple followed by more operators (e.g. `% (a, b) + c`) is still a tuple operand
    return items


def desugar_percent(p, fmt: A.StrLit, args: List[A.Node], tok) -> A.Node:
    """'literal' % arg  /  'literal' % (a, b)  ->  str()/format() concatenation (flags, width, precision, d i u o x X
    e E f F g G c r s %%)."""
    s = fmt.value
    n, i, lit = len(s), 0, ""
    out: List[A.Node] = []
    ai = 0
    uses = []
    while i < n:
        c = s[i]
        if c != "%":
            lit += c
            i += 1
            continue
        i += 1
        if i >= n:
            _fail(p, tok, "%-format: incomplete format (ValueError in CPython)")
        if s[i] == "%":
            lit += "%"
            i += 1
            continue
        if s[i] == "(":
            _fail(p, tok, "%-format: mapping keys (%(name)s) are outside the PySub subset; use str.format or an f-string")
        flags = ""
        while i < n and s[i] in "-+ 0#":
            flags += s[i]
            i += 1
        if "#" in flags:
            _fail(p, tok, "%-format: the '#' flag is outside the PySub subset")
        width = ""
        if i < n and s[i] == "*":
            _fail(p, tok, "%-format: '*' width is outside the PySub subset")
        while i < n and s[i].isdigit():
            width += s[i]
            i += 1
        prec = None
        if i < n and s[i] == ".":
            i += 1
            prec = ""
            if i < n and s[i] == "*":
                _fail(p, tok, "%-format: '*' precision is outside the PySub subset")
            while i < n and s[i].isdigit():
                prec += s[i]
                i += 1
        while i < n and s[i] in "hlL":
            i += 1
        if i >= n:
            _fail(p, tok, "%-format: incomplete format (ValueError in CPython)")
        ty = s[i]
        i += 1
        if ty not in _PCT_TYPES:
            _fail(p, tok, f"%-format: unsupported format character {ty!r}")
        if ai >= len(args):
            _fail(p, tok, "%-format: not enough arguments for the format string (TypeError in CPython)")
        a = args[ai]
        uses.append(a)
        ai += 1
        if lit:
            out.append(_lit(tok, lit))
            lit = ""
        left = "-" in flags
        spec_sign = "+" if "+" in flags else (" " if " " in flags else "")
        zero = "0" in flags and not left
        if ty in "sr":
            val = _call(tok, "repr" if ty == "r" else "str", a)
            if width or prec:
                spec = ("<" if left else ">") + width + (("." + prec) if prec else "")
                out.append(_call(tok, "format", val, _lit(tok, spec)))
            else:
                out.append(val)
            continue
        if ty == "c":
            if width or flags.strip("-"):
                _fail(p, tok, "%-format: width/flags with %c are outside the PySub subset")
            out.append(_call(tok, "__pct_c", a))
            continue
        if ty in "diuoxX":
            if prec:
                _fail(p, tok, "%-format: a precision with an integer conversion is outside the PySub subset")
            val = _call(tok, "__pct_d" if ty in "diu" else "__pct_i", a)
            code = "d" if ty in "diu" else ty
        else:
            val = a
            code = ty
        spec = ("<" if left else (">" if width and not zero else "")) + spec_sign + ("0" if zero else "") + width
        if prec is not None and ty not in "diuoxX":
            spec += "." + (prec or "0")
        spec += code
        if spec == "d":
            out.append(_call(tok, "str", val))
        else:
            out.append(_call(tok, "format", val, _lit(tok, spec)))
    if ai != len(args):
        _fail(p, tok, "%-format: not all arguments converted during string formatting (TypeError in CPython)")
    if lit:
        out.append(_lit(tok, lit))
    # arguments are evaluated once each, in order, so any expression is fine
    return _concat(out, tok)
