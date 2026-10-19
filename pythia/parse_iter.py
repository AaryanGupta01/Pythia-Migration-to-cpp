"""Parse-time desugaring of iterator-style calls into constructs the compiler already has.

  map(f, xs)            -> generator expression  (f x for x in xs)          ; lazy and single-use like CPython's map
  map(f, xs, ys)        -> (f(a, b) for a, b in zip(xs, ys))
  filter(f, xs)         -> (x for x in xs if f(x))
  print(*xs, sep=s)     -> print(s.join([str(x) for x in xs]), end=...)
  for v in map/filter   -> the loop is fused:  for t in xs: v = f(t); body   (exact even when f has side effects)
  a, b = map(int, ...)  -> the generator is built eagerly as a list (unpacking consumes it at once)

Because the result of map/filter is a generator expression, the existing rule that generators are accepted only
where they are consumed on the spot (sum/min/max/any/all/sorted/list/str.join, for loops, unpacking) keeps
`print(map(...))` and `m = map(...)` rejected instead of printing a list where CPython prints `<map object ...>`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from . import ast_nodes as A


@dataclass
class StarArg(A.Node):                      # a *expr call argument (only print() accepts it; checked in make_call)
    value: Any = None


def _fresh(self, tag: str) -> str:
    self._pi_n = getattr(self, "_pi_n", 0) + 1
    return f"__pi_{tag}{self._pi_n}"


def _name(t, n):
    return A.Name(t.line, t.col, id=n)


def _apply(self, t, f, arg_names):
    """The expression `f(arg1, arg2, ...)` for f given to map/filter; None if f is not something we can inline."""
    args = [_name(t, n) for n in arg_names]
    if isinstance(f, A.Name):
        return A.Call(t.line, t.col, func=f.id, args=args, kwargs=[])
    if isinstance(f, A.Attribute) and isinstance(f.value, A.Name) and f.value.id == "str" and len(args) == 1:
        return A.MethodCall(t.line, t.col, recv=args[0], method=f.attr, args=[], kwargs=[])      # map(str.lower, xs)
    return None


def _bad(self, t, what):
    self.errors.append(self_diag(self, f"{what}: pass a function name, a lambda or str.<method>", t))
    return None


def self_diag(self, msg, t):
    from .parser import Diagnostic
    return Diagnostic(msg, t.line, t.col)


def _gen(t, elt, gens):
    g = A.GenExp(t.line, t.col, elt=elt, gens=gens)
    g.from_iter_call = True
    return g


def make_map(self, t, args):
    if len(args) < 2:
        return _bad(self, t, "map() needs a function and at least one iterable")
    f, its = args[0], args[1:]
    if isinstance(f, A.Lambda):
        if len(f.params) != len(its):
            return _bad(self, t, "the lambda's parameter count must match the number of iterables given to map()")
        target = f.params[0] if len(f.params) == 1 else list(f.params)
        it = its[0] if len(its) == 1 else A.Call(t.line, t.col, func="zip", args=its, kwargs=[])
        return _gen(t, f.body, [A.CompFor(t.line, t.col, target=target, iter=it, ifs=[])])
    names = [_fresh(self, "m") for _ in its]
    elt = _apply(self, t, f, names)
    if elt is None:
        return _bad(self, t, "map() with this function is outside the PySub subset")
    target = names[0] if len(names) == 1 else names
    it = its[0] if len(its) == 1 else A.Call(t.line, t.col, func="zip", args=its, kwargs=[])
    return _gen(t, elt, [A.CompFor(t.line, t.col, target=target, iter=it, ifs=[])])


def make_filter(self, t, args):
    if len(args) != 2:
        return _bad(self, t, "filter() needs a function and one iterable")
    f, it = args
    if isinstance(f, A.Lambda):
        if len(f.params) != 1:
            return _bad(self, t, "filter() needs a one-parameter lambda")
        v, cond = f.params[0], f.body
    else:
        v = _fresh(self, "f")
        cond = A.Name(t.line, t.col, id=v) if isinstance(f, A.NoneLit) else _apply(self, t, f, [v])
        if cond is None:
            return _bad(self, t, "filter() with this function is outside the PySub subset")
    return _gen(t, _name(t, v), [A.CompFor(t.line, t.col, target=v, iter=it, ifs=[cond])])


def _print_star(self, t, args, kwargs):
    sep = next((k.value for k in kwargs if k.name == "sep"), None) or A.StrLit(t.line, t.col, value=" ")
    rest = [k for k in kwargs if k.name != "sep"]
    parts = None
    for a in args:
        if isinstance(a, StarArg):
            v = a.value
            if isinstance(v, A.GenExp) and getattr(v, "from_iter_call", False):
                lc = A.ListComp(t.line, t.col, elt=A.Call(t.line, t.col, func="str", args=[v.elt], kwargs=[]),
                                gens=v.gens)
            else:
                n = _fresh(self, "s")
                lc = A.ListComp(t.line, t.col, elt=A.Call(t.line, t.col, func="str", args=[_name(t, n)], kwargs=[]),
                                gens=[A.CompFor(t.line, t.col, target=n, iter=v, ifs=[])])
        else:
            lc = A.ListLit(t.line, t.col, elts=[A.Call(t.line, t.col, func="str", args=[a], kwargs=[])])
        parts = lc if parts is None else A.BinOp(t.line, t.col, op="+", left=parts, right=lc)
    joined = A.MethodCall(t.line, t.col, recv=sep, method="join", args=[parts], kwargs=[])
    return A.Call(t.line, t.col, func="print", args=[joined], kwargs=rest)


def make_call(self, t, args, kwargs):
    """Every `name(args)` call goes through here."""
    name = t.value
    if name in getattr(self, "readline_aliases", ()) and not args and not kwargs:
        return A.Call(t.line, t.col, func="__stdin_readline", args=[], kwargs=[])     # input = sys.stdin.readline
    if name == "print":
        for a in args:
            if isinstance(a, A.IfExp):
                a.print_arg = True                    # `print(x if c else y)`: the branches may have different types
    star = any(isinstance(a, StarArg) for a in args)
    if star and name == "print":
        return _print_star(self, t, args, kwargs)
    if star:
        self.errors.append(self_diag(self, "star-arguments `f(*xs)` are outside the PySub subset (only print(*xs) "
                                         "is supported)", t))
        args = [a.value if isinstance(a, StarArg) else a for a in args]
    if name == "map" and not kwargs:
        g = make_map(self, t, args)
        if g is not None:
            return g
    if name == "filter" and not kwargs:
        g = make_filter(self, t, args)
        if g is not None:
            return g
    return A.Call(t.line, t.col, func=name, args=args, kwargs=kwargs)


def check_method_star(self, t, args):
    if any(isinstance(a, StarArg) for a in args):
        self.errors.append(self_diag(self, "star-arguments `f(*xs)` are outside the PySub subset", t))
        return [a.value if isinstance(a, StarArg) else a for a in args]
    return args


def eager(value):
    """A map/filter generator that is consumed immediately (unpacking) becomes a list comprehension."""
    if isinstance(value, A.GenExp) and getattr(value, "from_iter_call", False):
        return A.ListComp(value.line, value.col, elt=value.elt, gens=value.gens)
    return value


def fuse_for(node):
    """for v in <map/filter generator>: body  ->  for t in xs: [if cond:] v = elt; body  (single iterable only)."""
    g = node.iter
    if not (isinstance(node, A.ForEach) and isinstance(g, A.GenExp) and getattr(g, "from_iter_call", False)
            and len(g.gens) == 1 and isinstance(g.gens[0].target, str)):
        return node
    gen = g.gens[0]
    first = A.Assign(node.line, node.col, target=A.Name(node.line, node.col, id=node.var), value=g.elt)
    inner = [first] + list(node.body)
    if gen.ifs:
        test = gen.ifs[0]
        for extra in gen.ifs[1:]:
            test = A.BoolOp(node.line, node.col, op="and", values=[test, extra])
        inner = [A.If(node.line, node.col, test=test, body=inner, orelse=[])]
    return A.ForEach(line=node.line, col=node.col, var=gen.target, iter=gen.iter, body=inner)


def parse_del(self):
    """del a[i] -> list element removal (CPython's `del` IndexError text); del a[i:j] -> a[i:j] = [] ."""
    t = self.next()                                    # 'del'
    target = self.parse_expr()
    self.expect("NEWLINE")
    ln, cl = t.line, t.col
    if isinstance(target, A.Call) and target.func == "__slice":
        return A.ExprStmt(ln, cl, value=A.Call(ln, cl, func="__slice_assign", kwargs=[],
                                               args=target.args + [A.ListLit(ln, cl, elts=[])]))
    if isinstance(target, A.Subscript):
        return A.ExprStmt(ln, cl, value=A.Call(ln, cl, func="__del_index", args=[target.value, target.index], kwargs=[]))
    self.errors.append(self_diag(self, "`del` is supported for list elements and list slices in PySub", t))
    from .parser import _Panic
    raise _Panic()
