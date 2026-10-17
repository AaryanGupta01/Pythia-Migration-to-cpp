"""
PYTHIA :: Phase 4.5 -- Guard Elision by Interval Analysis
Owner: Member 3 (Koliparthy Venkata Jahnavi) -- Review 2 deliverable

Motivation: t10_collatz.py is the slowest benchmark in the suite (5-8x
versus CPython, against 9-14x for everything else) precisely because it is
integer-arithmetic-bound, so almost every operation pays for the D1
overflow guard (py_add_i64 / py_sub_i64 / py_mul_i64 instead of a bare C
operator). This pass proves, for as many operations as it safely can, that
the guard can never fire -- and only then removes it.

Soundness contract: this analysis NEVER elides a guard unless it can prove
the result fits inside a wide safety margin, for every possible execution.
It is allowed to be incomplete (leave a guard in place where one wasn't
strictly needed); it must never be wrong. Where the analysis can't be sure
-- a variable that survives a loop iteration and feeds back into itself
(the classic accumulator pattern), a value read from a function parameter,
a value returned by a function call -- it marks the interval unknown and
changes nothing. This is why elision is scored as "guarded, sound but
possibly incomplete", the same standard the D1 divergence note already
holds itself to.

The technique is textbook abstract interpretation with intervals (Cousot &
Cousot's original domain), deliberately kept to a single forward pass
without a loop fixpoint solver: loop-carried variables are always widened
to "unknown" before their body is analysed, which is exactly what makes a
single pass sound without needing to iterate to a fixpoint.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from . import ast_nodes as A
from .typecheck import INT

Interval = Optional[Tuple[int, int]]     # None = unknown

# Comfortably inside int64 range (|n| < 2**62) so that even a subsequent
# +, -, or * with another safe value can't be the operation that overflows
# int64 -- one bit of headroom is not enough; we keep two.
SAFE_LO = -(2 ** 62)
SAFE_HI = 2 ** 62


def _union(a: Interval, b: Interval) -> Interval:
    if a is None or b is None:
        return None
    return (min(a[0], b[0]), max(a[1], b[1]))


def _add(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    return (a[0] + b[0], a[1] + b[1])


def _sub(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    return (a[0] - b[1], a[1] - b[0])


def _mul(a: Tuple[int, int], b: Tuple[int, int]) -> Tuple[int, int]:
    prods = (a[0] * b[0], a[0] * b[1], a[1] * b[0], a[1] * b[1])
    return (min(prods), max(prods))


def _safe(iv: Interval) -> bool:
    return iv is not None and SAFE_LO <= iv[0] and iv[1] <= SAFE_HI


@dataclass
class Stats:
    elided: int = 0
    kept: int = 0


class NameCollector:
    """Finds every plain-Name assignment target within a block, so a loop
    body's carried variables can be widened to unknown before entry."""

    @staticmethod
    def collect(stmts: List[A.Node]) -> Set[str]:
        names: Set[str] = set()
        NameCollector._walk(stmts, names)
        return names

    @staticmethod
    def _walk(stmts: List[A.Node], out: Set[str]) -> None:
        for s in stmts:
            if isinstance(s, A.Assign) and isinstance(s.target, A.Name):
                out.add(s.target.id)
            elif isinstance(s, A.AugAssign) and isinstance(s.target, A.Name):
                out.add(s.target.id)
            if isinstance(s, A.If):
                NameCollector._walk(s.body, out)
                NameCollector._walk(s.orelse, out)
            elif isinstance(s, (A.While,)):
                NameCollector._walk(s.body, out)
            elif isinstance(s, (A.ForRange, A.ForEach)):
                out.add(s.var)
                NameCollector._walk(s.body, out)
            elif isinstance(s, A.TryExcept):
                NameCollector._walk(s.body, out)
                for h in s.handlers:
                    NameCollector._walk(h.body, out)


def _references(expr: Optional[A.Node], name: str) -> bool:
    if expr is None:
        return False
    if isinstance(expr, A.Name):
        return expr.id == name
    if isinstance(expr, A.Coerce):
        return _references(expr.value, name)
    if isinstance(expr, A.BinOp):
        return _references(expr.left, name) or _references(expr.right, name)
    if isinstance(expr, A.UnaryOp):
        return _references(expr.operand, name)
    if isinstance(expr, A.Compare):
        return _references(expr.left, name) or _references(expr.right, name)
    if isinstance(expr, A.BoolOp):
        return any(_references(v, name) for v in expr.values)
    if isinstance(expr, A.Call):
        return any(_references(a, name) for a in expr.args)
    if isinstance(expr, A.MethodCall):
        return _references(expr.recv, name) or any(_references(a, name) for a in expr.args)
    if isinstance(expr, A.Subscript):
        return _references(expr.value, name) or _references(expr.index, name)
    if isinstance(expr, A.Attribute):
        return _references(expr.value, name)
    return False


class GuardElider:
    def __init__(self):
        self.stats = Stats()

    # ---- expression evaluation: computes an interval AND annotates every
    # BinOp it visits with .no_guard when the result is provably safe -----
    def eval(self, e: Optional[A.Node], env: Dict[str, Interval]) -> Interval:
        if e is None:
            return None
        if isinstance(e, A.IntLit):
            return (e.value, e.value)
        if isinstance(e, A.Coerce):
            return self.eval(e.value, env)
        if isinstance(e, A.Name):
            return env.get(e.id)
        if isinstance(e, A.UnaryOp):
            sub = self.eval(e.operand, env)
            if e.op == "-" and sub is not None:
                return (-sub[1], -sub[0])
            if e.op == "+" and sub is not None:
                return sub
            return None
        if isinstance(e, A.BinOp):
            a = self.eval(e.left, env)
            b = self.eval(e.right, env)
            if e.ty != INT or e.op not in ("+", "-", "*"):
                return None            # only the guarded int ops are in scope
            if a is None or b is None:
                self.stats.kept += 1
                return None
            result = {"+": _add, "-": _sub, "*": _mul}[e.op](a, b)
            if _safe(result):
                e.no_guard = True
                self.stats.elided += 1
            else:
                self.stats.kept += 1
            return result if _safe(result) else None
        # Anything else (calls, subscripts, comparisons, ...): we don't
        # track its value, but sub-expressions may still contain BinOps
        # worth annotating -- e.g. print(a + b) should still get a+b
        # checked even though print()'s own result isn't an interval.
        if isinstance(e, A.Call):
            for a in e.args:
                self.eval(a, env)
            return None
        if isinstance(e, A.MethodCall):
            self.eval(e.recv, env)
            for a in e.args:
                self.eval(a, env)
            return None
        if isinstance(e, A.Compare):
            self.eval(e.left, env)
            self.eval(e.right, env)
            return None
        if isinstance(e, A.BoolOp):
            for v in e.values:
                self.eval(v, env)
            return None
        if isinstance(e, A.Subscript):
            self.eval(e.value, env)
            self.eval(e.index, env)
            return None
        if isinstance(e, A.ListLit):
            for x in e.elts:
                self.eval(x, env)
            return None
        if isinstance(e, A.DictLit):
            for k, v in zip(e.keys, e.values):
                self.eval(k, env)
                self.eval(v, env)
            return None
        return None

    # ---- statements ---------------------------------------------------
    def block(self, stmts: List[A.Node], env: Dict[str, Interval]) -> None:
        for s in stmts:
            self.stmt(s, env)

    def stmt(self, s: A.Node, env: Dict[str, Interval]) -> None:
        if isinstance(s, A.Assign):
            iv = self.eval(s.value, env)
            if isinstance(s.target, A.Name):
                env[s.target.id] = iv if s.ty == INT else None
            else:
                self.eval(s.target, env)   # index/attribute targets: just annotate

        elif isinstance(s, A.AugAssign):
            # Self-referential by construction; never claim a bound for the
            # target here (that would need real fixpoint reasoning across
            # every future iteration), but still annotate the RHS's own
            # sub-expressions if they don't mention the target.
            if not _references(s.value, getattr(s.target, "id", "")):
                self.eval(s.value, env)
            if isinstance(s.target, A.Name):
                env[s.target.id] = None

        elif isinstance(s, A.ExprStmt):
            self.eval(s.value, env)

        elif isinstance(s, A.Return):
            self.eval(s.value, env)

        elif isinstance(s, A.If):
            self.eval(s.test, env)
            then_env = dict(env)
            else_env = dict(env)
            self.block(s.body, then_env)
            self.block(s.orelse, else_env)
            merged = {}
            for k in set(then_env) | set(else_env):
                merged[k] = _union(then_env.get(k), else_env.get(k))
            env.clear()
            env.update(merged)

        elif isinstance(s, A.While):
            self.eval(s.test, env)
            carried = NameCollector.collect(s.body)
            body_env = dict(env)
            for n in carried:
                body_env[n] = None
            self.block(s.body, body_env)
            for n in carried:
                env[n] = None

        elif isinstance(s, A.ForRange):
            lo_iv = self.eval(s.start, env)
            hi_iv = self.eval(s.stop, env)
            step_iv = self.eval(s.step, env) if s.step is not None else (1, 1)
            loop_iv = None
            if (lo_iv and lo_iv[0] == lo_iv[1] and hi_iv and hi_iv[0] == hi_iv[1]
                    and step_iv and step_iv[0] == step_iv[1] and step_iv[0] != 0):
                start, stop, step = lo_iv[0], hi_iv[0], step_iv[0]
                if step > 0 and start < stop:
                    last = start + ((stop - start - 1) // step) * step
                    loop_iv = (start, last)
                elif step < 0 and start > stop:
                    last = start + ((stop - start + 1) // step) * step
                    loop_iv = (last, start)
                else:
                    loop_iv = (start, start)   # zero-iteration loops: body never runs, harmless
            carried = NameCollector.collect(s.body) - {s.var}
            body_env = dict(env)
            body_env[s.var] = loop_iv
            for n in carried:
                body_env[n] = None
            self.block(s.body, body_env)
            env[s.var] = None
            for n in carried:
                env[n] = None

        elif isinstance(s, A.ForEach):
            self.eval(s.iter, env)
            carried = NameCollector.collect(s.body) - {s.var}
            body_env = dict(env)
            body_env[s.var] = None
            for n in carried:
                body_env[n] = None
            self.block(s.body, body_env)
            env[s.var] = None
            for n in carried:
                env[n] = None

        elif isinstance(s, A.TryExcept):
            carried = NameCollector.collect(s.body)
            for h in s.handlers:
                carried |= NameCollector.collect(h.body)
            body_env = dict(env)
            for n in carried:
                body_env[n] = None
            self.block(s.body, body_env)
            for h in s.handlers:
                henv = dict(env)
                for n in carried:
                    henv[n] = None
                self.block(h.body, henv)
            for n in carried:
                env[n] = None

        # Pass / Break / Continue / Raise: no expression to annotate


def elide_guards(mod: A.Module, exposed=()) -> Stats:
    """Run the pass over every function, method, and the module body.
    Each gets a fresh environment: PySub functions are closed over their
    own parameters and locals only (see typecheck.py), so nothing about
    one function's proven bounds can leak into -- or be assumed safe in --
    another's, which keeps the whole-module pass as sound as the
    per-function reasoning it's built from.

    One exception, deliberately: function parameters. A parameter is, in
    general, unknown -- but PySub has no separate compilation and no
    first-class functions, so every call site for a given function is
    visible in this one module. If a parameter is *never* called with
    anything but an integer literal, every one of those literals is a
    value the parameter is provably allowed to take, and their union is a
    sound (if possibly loose) interval for it -- this is a one-shot,
    whole-program version of interprocedural constant propagation, not a
    loop fixpoint, so it stays a single pass. A single call site passing a
    non-literal argument immediately makes that parameter unknown again,
    exactly as conservative as leaving it untouched would have been."""
    param_bounds = _scan_literal_call_sites(mod)

    elider = GuardElider()
    for c in mod.classes:
        for m in c.methods:
            env: Dict[str, Interval] = {}
            for p in m.params[1:]:
                env[p.name] = None
            elider.block(m.body, env)
    for f in mod.funcs:
        # library mode: an exposed function is also called from outside the
        # module with arbitrary values, so literal call sites prove nothing.
        bounds = {} if f.name in exposed else param_bounds.get(f.name, {})
        env = {p.name: bounds.get(p.name) for p in f.params}
        elider.block(f.body, env)
    elider.block(mod.main, {})
    return elider.stats


def _scan_literal_call_sites(mod: A.Module) -> Dict[str, Dict[str, Interval]]:
    seen: Dict[str, Dict[str, Interval]] = {}     # func -> {param: interval-or-mixed}
    poisoned: Dict[str, Set[str]] = {}            # func -> params ever seen non-literal

    def visit_call(call: A.Call) -> None:
        sig_params = _func_param_names.get(call.func)
        if sig_params is None:
            return
        for i, arg in enumerate(call.args):
            if i >= len(sig_params):
                continue
            pname = sig_params[i]
            bare = arg.value if isinstance(arg, A.Coerce) else arg
            if isinstance(bare, A.IntLit):
                cur = seen.setdefault(call.func, {}).get(pname)
                v = (bare.value, bare.value)
                seen[call.func][pname] = v if cur is None else _union(cur, v)
            else:
                poisoned.setdefault(call.func, set()).add(pname)

    def walk_expr(e: Optional[A.Node]) -> None:
        if e is None:
            return
        if isinstance(e, A.Call):
            for a in e.args:
                walk_expr(a)
            visit_call(e)
        elif isinstance(e, A.Coerce):
            walk_expr(e.value)
        elif isinstance(e, A.BinOp):
            walk_expr(e.left); walk_expr(e.right)
        elif isinstance(e, A.UnaryOp):
            walk_expr(e.operand)
        elif isinstance(e, A.Compare):
            walk_expr(e.left); walk_expr(e.right)
        elif isinstance(e, A.BoolOp):
            for v in e.values:
                walk_expr(v)
        elif isinstance(e, A.MethodCall):
            walk_expr(e.recv)
            for a in e.args:
                walk_expr(a)
        elif isinstance(e, A.Subscript):
            walk_expr(e.value); walk_expr(e.index)
        elif isinstance(e, A.ListLit):
            for x in e.elts:
                walk_expr(x)
        elif isinstance(e, A.DictLit):
            for k, v in zip(e.keys, e.values):
                walk_expr(k); walk_expr(v)
        elif isinstance(e, A.Attribute):
            walk_expr(e.value)

    def walk_stmts(stmts: List[A.Node]) -> None:
        for s in stmts:
            if isinstance(s, A.Assign):
                walk_expr(s.value)
            elif isinstance(s, A.AugAssign):
                walk_expr(s.value)
            elif isinstance(s, A.ExprStmt):
                walk_expr(s.value)
            elif isinstance(s, A.Return):
                walk_expr(s.value)
            elif isinstance(s, A.If):
                walk_expr(s.test); walk_stmts(s.body); walk_stmts(s.orelse)
            elif isinstance(s, A.While):
                walk_expr(s.test); walk_stmts(s.body)
            elif isinstance(s, A.ForRange):
                walk_expr(s.start); walk_expr(s.stop); walk_expr(s.step)
                walk_stmts(s.body)
            elif isinstance(s, A.ForEach):
                walk_expr(s.iter); walk_stmts(s.body)
            elif isinstance(s, A.TryExcept):
                walk_stmts(s.body)
                for h in s.handlers:
                    walk_stmts(h.body)

    _func_param_names = {f.name: [p.name for p in f.params] for f in mod.funcs}
    for f in mod.funcs:
        walk_stmts(f.body)
    for c in mod.classes:
        for m in c.methods:
            walk_stmts(m.body)
    walk_stmts(mod.main)

    for fname, params in poisoned.items():
        for p in params:
            seen.setdefault(fname, {})[p] = None
    return seen
