"""
PYTHIA :: comprehensions, generator expressions, key lambdas, iteration helpers

Everything for these features lives here; typecheck / lower / optimize / emit_c / libmode only
delegate to it with a line or two.

  [e for x in it if c ...]   {k: v for ...}   (e for x in it)      -> compiled to nested C++ loops
  for i, x in enumerate(xs[, start])   for a, b in zip(xs, ys[, zs])   for x in reversed(xs|s|range(..))
  range(...) as a comprehension / zip / enumerate source
  any/all/sum/min/max of a generator: streamed loops, short-circuiting like CPython
  sorted/min/max(..., key=lambda v: ...), list.sort(key=...): key functions (lambda, len, str.lower, f)

Semantics kept CPython-exact:
  * the first clause's iterable is evaluated once, in the enclosing scope, before the loop; later ones per
    outer iteration; comprehension variables are local to the comprehension (C++ block scope).
  * list sources are walked by index re-checking the length (CPython's list iterator), dict sources raise
    RuntimeError if the dict changes size, reversed() reads the length once like listreviter.
  * key functions are called once per element, in order; sorts are stable; reverse keeps ties in order;
    min/max keep the FIRST extreme element; list.sort hides the list while sorting (see pyl_sort_key).
"""
from typing import List, Optional
from . import ast_nodes as A
from .typecheck import Ty, INT, FLOAT, BOOL, STR, NONE, ERR, Scope, list_of, dict_of, widens_to, PRIM

HELPERS = ("enumerate", "zip", "reversed", "range")
CONSUMERS = ("sum", "min", "max", "any", "all", "sorted", "list")
COMP_NODES = (A.ListComp, A.DictComp, A.GenExp, A.Lambda)
ITER = Ty("<iter>")                       # type of an enumerate/zip/reversed/range call (iteration-only)
_IT = "_it"                               # name of the variable of a synthesised (v for v in src)
_KEY_FUNCS = ("len", "abs", "str", "int", "float", "bool", "ord", "chr", "round", "sum", "min", "max")
_GEN_WHERE = ("generator expressions are supported only as the sole argument of sum(), min(), max(), any(), "
              "all(), sorted(), list() and str.join(); use a list comprehension [...] elsewhere")


def is_comp_node(e) -> bool:
    return isinstance(e, COMP_NODES)


def is_helper(tc, e) -> bool:
    return isinstance(e, A.Call) and e.func in HELPERS and e.func not in tc.funcs and e.func not in tc.classes


def is_special_foreach(tc, s) -> bool:
    """`for v in enumerate/zip/reversed(...)` (`for a, b in ...` arrives here as `for tmp in ...` + unpacking)."""
    return is_helper(tc, s.iter)


def names_of(target) -> List[str]:
    if isinstance(target, str):
        return [target]
    return [n for t in target for n in names_of(t)]


def _as_ty(item) -> Ty:
    """An item as one value: enumerate/zip items are tuples."""
    from .tuples import tuple_of
    return tuple_of([_as_ty(x) for x in item]) if isinstance(item, list) else item


def _kw(e, name):
    for kw in getattr(e, "kwargs", None) or []:
        if kw.name == name:
            return kw
    return None


def _wrap(src: A.Node) -> A.GenExp:
    """src -> (_it for _it in src): any iterable as a generator a consumer can stream."""
    g = A.GenExp(src.line, src.col, elt=A.Name(src.line, src.col, id=_IT),
                 gens=[A.CompFor(src.line, src.col, target=_IT, iter=src)])
    g.consumer = True
    return g


# =============================================================== type checking
def item_of(tc, it):
    """Type of what iterating `it` yields: a Ty, or a list of items for an enumerate/zip tuple."""
    if not is_helper(tc, it):
        from .tuples import mark_items
        from .builtins_ext import mark_view_ok
        mark_items(it)                                 # [k for k, v in d.items()] is fine: it is consumed at once
        mark_view_ok(tc, it)                           # likewise d.keys() / d.values()
        t = tc.synth(it)
        if t is ERR:
            return ERR
        if t.name == "list":
            if t.elem is None:
                return tc.err(it, "cannot iterate over an empty list literal")
            return t.elem
        if t == STR:
            return STR
        if t.name == "dict":
            return t.key
        return tc.err(it, f"cannot iterate over a value of type {t}")
    it.ty = ITER
    n, args = it.func, it.args
    for kw in it.kwargs:
        if not (n == "enumerate" and kw.name == "start"):
            tc.err(kw, f"keyword argument {kw.name!r} of {n}() is outside the PySub subset")
    if n == "range":
        if not 1 <= len(args) <= 3:
            return tc.err(it, "range() takes 1 to 3 arguments")
        for a in args:
            t = tc.synth(a)
            if t is not ERR and not widens_to(t, INT):
                tc.err(a, f"range() argument must be int, found {t}")
        return INT
    if n == "reversed":
        if len(args) != 1:
            return tc.err(it, "reversed() takes exactly one argument")
        a = args[0]
        if is_helper(tc, a) and a.func == "range":
            return item_of(tc, a)
        t = tc.synth(a)
        if t is ERR:
            return ERR
        if (t.name == "list" and t.elem is not None) or t == STR:
            return t.elem if t.name == "list" else STR
        return tc.err(a, f"reversed() needs a list, a str or a range in PySub, found {t}")
    if n == "enumerate":
        start = _kw(it, "start")
        if not 1 <= len(args) + (start is not None) <= 2:
            return tc.err(it, "enumerate() takes an iterable and optionally start")
        inner = item_of(tc, args[0])
        sx = start.value if start is not None else (args[1] if len(args) > 1 else None)
        if sx is not None:
            t = tc.synth(sx)
            if t is not ERR and not widens_to(t, INT):
                tc.err(sx, f"enumerate() start must be int, found {t}")
        return [INT, inner]
    if len(args) < 2:                                  # zip
        return tc.err(it, "zip() needs at least two iterables in PySub")
    return [item_of(tc, a) for a in args]


def _bind(tc, node, target, item, declare) -> None:
    if isinstance(target, str):
        declare(target, _as_ty(item))
        return
    if isinstance(item, Ty) and item.name == "tuple":
        item = list(item.elts)
    if not isinstance(item, list) or len(item) != len(target):
        if item is not ERR:
            what = f"{len(item)} values" if isinstance(item, list) else f"a {item}"
            tc.err(node, f"cannot unpack {what} into {len(target)} names (a comprehension target unpacks tuples "
                         f"only, with exactly one name per value)")
        for t in target:
            _bind(tc, node, t, ERR, declare)
        return
    for t, i in zip(target, item):
        _bind(tc, node, t, i, declare)


def _check_target(tc, node, target) -> None:
    ns = names_of(target)
    if len(set(ns)) != len(ns):
        tc.err(node, "a name appears twice in one loop target")


def check_foreach(tc, s) -> None:
    """`for v in <enumerate|zip|reversed|...>:` -- v is a function local, like any loop variable."""
    _bind(tc, s, s.var, item_of(tc, s.iter), lambda n, t: tc.bind(s, n, t))
    tc.loop_depth += 1
    tc.block(s.body)
    tc.loop_depth -= 1


def _elem_ok(tc, e, t: Ty) -> Ty:
    if t is ERR:
        return ERR
    if t == NONE:
        return tc.err(e, "a comprehension element cannot be None")
    if t is ITER:
        return tc.err(e, "an enumerate()/zip()/reversed()/range() object cannot be stored in PySub")
    if t.name == "list" and t.elem is not None and t.elem.name == "list":
        return tc.err(e, "list nesting deeper than two levels is outside the PySub subset")
    return t


def synth(tc, e) -> Ty:
    """Type of a ListComp / DictComp / GenExp / Lambda node."""
    if isinstance(e, A.Lambda):
        return tc.err(e, "lambda is supported only as the key= argument of sorted(), min(), max() and "
                         "list.sort(); PySub has no first-class functions")
    if isinstance(e, A.GenExp) and not getattr(e, "consumer", False):
        return tc.err(e, _GEN_WHERE)
    saved = tc.scope
    try:
        for i, g in enumerate(e.gens):
            item = item_of(tc, g.iter)
            if i == 0:
                tc.scope = Scope(saved, "block")         # Python 3: comprehension variables don't leak
            _check_target(tc, g, g.target)
            _bind(tc, g, g.target, item, tc.scope.declare)
            for c in g.ifs:
                tc.check_truthy(c)
        if isinstance(e, A.DictComp):
            kt, vt = tc.synth(e.key), tc.synth(e.value)
            if kt is ERR or vt is ERR:
                return ERR
            if kt.name not in ("int", "str"):
                return tc.err(e.key, f"dict key type must be int or str; found {kt}")
            if vt.name not in PRIM:
                return tc.err(e.value, f"dict value type must be int, float, bool or str; found {vt}")
            return dict_of(kt, vt)
        if isinstance(e.elt, (A.ListLit, A.DictLit)) and not getattr(e.elt, "elts", getattr(e.elt, "keys", None)):
            tc.synth(e.elt)
            return Ty("list", None)                       # [[] for ...]: element type comes from an annotation
        t = _elem_ok(tc, e.elt, tc.synth(e.elt))
        return ERR if t is ERR else list_of(t)
    finally:
        tc.scope = saved


def _as_key_lambda(tc, k: A.Node) -> Optional[A.Lambda]:
    ln, cl = k.line, k.col
    v = A.Name(ln, cl, id="_k")
    if isinstance(k, A.Lambda):
        return k
    if isinstance(k, A.Name) and (k.id in tc.funcs or (k.id in _KEY_FUNCS and tc.scope.lookup(k.id) is None)):
        return A.Lambda(ln, cl, params=["_k"], body=A.Call(ln, cl, func=k.id, args=[v]))
    if isinstance(k, A.Attribute) and isinstance(k.value, A.Name) and k.value.id == "str" \
            and tc.scope.lookup("str") is None:
        return A.Lambda(ln, cl, params=["_k"], body=A.MethodCall(ln, cl, recv=v, method=k.attr))
    tc.err(k, "key= must be a lambda, a function name (len, abs, str, a def'd function) or a str method "
              "like str.lower in PySub")
    return None


def _dict_get_key(tc, k: A.Node, elem: Ty) -> Optional[A.Lambda]:
    """key=d.get over the keys of d (max(d, key=d.get), sorted(d, key=d.get)): the key always exists, so d[k] is
    the same value. (If the iterable held keys absent from d, CPython would fail on None < int; PySub raises KeyError.)"""
    if isinstance(k, A.Attribute) and k.attr == "get" and isinstance(k.value, A.Name):
        t = tc.scope.lookup(k.value.id)
        if t is not None and t.name == "dict" and t.key == elem:
            v = A.Name(k.line, k.col, id="_k")
            return A.Lambda(k.line, k.col, params=["_k"],
                            body=A.Subscript(k.line, k.col, value=A.Name(k.line, k.col, id=k.value.id), index=v))
    return None


def check_key(tc, kw: A.Keyword, elem: Ty) -> Ty:
    lam = _dict_get_key(tc, kw.value, elem) or _as_key_lambda(tc, kw.value)
    if lam is None:
        return ERR
    kw.value = lam
    if len(lam.params) != 1:
        return tc.err(lam, "a key function takes exactly one argument")
    lam.param_tys = [elem]
    saved = tc.scope
    tc.scope = Scope(saved, "block")
    tc.scope.declare(lam.params[0], elem)
    try:
        kt = tc.synth(lam.body)
    finally:
        tc.scope = saved
    lam.ty = kt
    from .tuples import orderable
    if kt is not ERR and not orderable(kt):
        return tc.err(lam, f"a key function must return int, float, bool, str or a tuple of those in PySub, "
                           f"found {kt}")
    return kt


def _check_reverse(tc, e, allow_calls: bool = True) -> None:
    kw = _kw(e, "reverse")
    if kw is None:
        return
    t = tc.synth(kw.value)
    if t is not ERR and t != BOOL:
        tc.err(kw.value, f"reverse= must be bool, found {t}")
    if not allow_calls and _has_call(kw.value):
        tc.err(kw.value, "reverse= calls a function while sorting a generator: assign it to a variable first")


def _has_call(n) -> bool:
    if isinstance(n, (A.Call, A.MethodCall)):
        return True
    return any(_has_call(c) for c in children(n))


def _bad_kwargs(tc, e, allowed) -> bool:
    bad = [kw for kw in e.kwargs if kw.name not in allowed]
    for kw in bad:
        tc.err(kw, f"keyword argument {kw.name!r} of {e.func}() is outside the PySub subset")
    return bool(bad)


def synth_call_hook(tc, e: A.Call) -> Optional[Ty]:
    """Called first by TypeChecker.synth_call. Returns a type when it handled the call, else None (after
    possibly turning a generator / iteration-helper argument into a marked GenExp for the existing code)."""
    n = e.func
    if n in tc.funcs or n in tc.classes:
        return None
    if n in HELPERS:
        for a in e.args:
            tc.synth(a) if not is_helper(tc, a) else None
        return tc.err(e, f"{n}() is supported only as the iterable of a for loop or comprehension, or as the "
                         f"argument of list()/sorted()/sum()/min()/max()/any()/all()/str.join()")
    if n not in CONSUMERS or len(e.args) != 1:
        if n in ("min", "max", "sorted") and _kw(e, "key") is not None:
            return tc.err(e, f"{n}() with key= takes exactly one iterable in PySub")
        return None
    a = e.args[0]
    if is_helper(tc, a):
        a = e.args[0] = _wrap(a)
    key = _kw(e, "key")
    if n in ("any", "all"):
        if e.kwargs:
            _bad_kwargs(tc, e, ())
            return ERR
        if not isinstance(a, A.GenExp):
            a = e.args[0] = _wrap(a)
        a.consumer = True
        return ERR if tc.synth(a) is ERR else BOOL
    if key is not None and n in ("sorted", "min", "max"):
        if _bad_kwargs(tc, e, ("key", "reverse") if n == "sorted" else ("key",)):
            return ERR
        from .tuples import mark_items
        mark_items(a)                                  # sorted(d.items(), key=...) consumes the view at once
        if n != "sorted" or isinstance(a, A.GenExp) or tc.synth(a).name not in ("list", "<error>"):
            if not isinstance(a, A.GenExp):
                a = e.args[0] = _wrap(a)
            a.consumer = True
        t = tc.synth(a)
        if t is ERR:
            tc.synth(key.value) if not isinstance(key.value, A.Lambda) else None
            return ERR
        check_key(tc, key, t.elem)
        _check_reverse(tc, e, allow_calls=not isinstance(a, A.GenExp))
        return t if n == "sorted" else t.elem
    if isinstance(a, A.GenExp):
        a.consumer = True
        if n == "sorted":
            _check_reverse(tc, e, allow_calls=False)
    return None


def synth_method_hook(tc, e: A.MethodCall) -> Optional[Ty]:
    """Called first by TypeChecker.synth_method: str.join(<generator>), list.sort(key=...)."""
    if e.method == "join" and len(e.args) == 1 and (isinstance(e.args[0], A.GenExp) or is_helper(tc, e.args[0])):
        if tc.synth(e.recv) == STR:
            if not isinstance(e.args[0], A.GenExp):
                e.args[0] = _wrap(e.args[0])
            e.args[0].consumer = True
        return None
    key = _kw(e, "key")
    if e.method != "sort" or key is None:
        return None
    recv = tc.synth(e.recv)
    if recv.name != "list":
        return None
    bad = [kw for kw in e.kwargs if kw.name not in ("key", "reverse")]
    for kw in bad:
        tc.err(kw, f"keyword argument {kw.name!r} of sort() is outside the PySub subset")
    if e.args:
        return tc.err(e, "sort() takes no positional arguments")
    check_key(tc, key, recv.elem)
    _check_reverse(tc, e)
    return NONE


# =============================================================== lowering
def lower_expr(lw, e):
    if isinstance(e, A.Lambda):
        e.body = lw.expr(e.body)
        return e
    for g in e.gens:
        g.iter = lw.expr(g.iter)
        g.ifs = [lw.expr(c) for c in g.ifs]
    t = e.ty
    if isinstance(e, A.DictComp):
        e.key = lw.coerce(lw.expr(e.key), t.key if t is not None and t.name == "dict" else None)
        e.value = lw.coerce(lw.expr(e.value), t.elem if t is not None and t.name == "dict" else None)
    else:
        e.elt = lw.coerce(lw.expr(e.elt), t.elem if t is not None and t.name == "list" else None)
    return e


# =============================================================== optimizer / alias analysis support
def children(e):
    """Direct sub-expressions of any node (generic, for walkers)."""
    if not isinstance(e, A.Node):
        return
    for f in e.__dataclass_fields__:
        if f == "ty":
            continue
        v = getattr(e, f)
        if isinstance(v, A.Node):
            yield v
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, A.Node):
                    yield x


def mentions(e, name: str) -> bool:
    if isinstance(e, A.Name):
        return e.id == name
    return any(mentions(c, name) for c in children(e))


def eval_interval(el, e, env):
    """GuardElider.eval for comprehension nodes: their variables are unknown inside, invisible outside."""
    inner = dict(env)
    if isinstance(e, A.Lambda):
        for p in e.params:
            inner[p] = None
        el.eval(e.body, inner)
        return None
    for i, g in enumerate(e.gens):
        el.eval(g.iter, env if i == 0 else inner)
        for nm in names_of(g.target):
            inner[nm] = None
        for c in g.ifs:
            el.eval(c, inner)
    for x in ((e.key, e.value) if isinstance(e, A.DictComp) else (e.elt,)):
        el.eval(x, inner)
    return None


def alias_sources(e) -> List[A.Node]:
    """Expressions whose list/dict objects a comprehension / helper call may hand out."""
    if isinstance(e, A.Call):
        return list(e.args)
    if isinstance(e, A.DictComp):
        return [g.iter for g in e.gens]
    return [g.iter for g in e.gens] + [e.elt]


def alias_edges(n):
    """(name, source expr) pairs: a comprehension / loop / key-lambda variable may denote source's objects."""
    if isinstance(n, A.CompFor):
        return [(nm, n.iter) for nm in names_of(n.target)]
    if isinstance(n, A.ForEach) and isinstance(n.iter, A.Call) and n.iter.func in HELPERS:
        return [(n.var, n.iter)]
    if isinstance(n, (A.Call, A.MethodCall)):
        kw = _kw(n, "key")
        if kw is not None and isinstance(kw.value, A.Lambda) and kw.value.params:
            src = n.recv if isinstance(n, A.MethodCall) else (n.args[0] if n.args else None)
            if src is not None:
                return [(kw.value.params[0], src)]
    return []


# =============================================================== C++ emission
def _ctype(t):
    from .emit_c import ctype
    return ctype(t)


def _nested(t) -> bool:
    from .emit_c import list_rt_name
    return list_rt_name(t) == "PyListList"


def _store(t) -> str:
    """C++ element type stored in a list of type t."""
    return "void *" if _nested(t) else _ctype(t.elem).strip()


def _elem(t, x: str) -> str:
    return f"({_ctype(t.elem)}){x}" if _nested(t) else x


def _range_setup(em, it):
    setup, vals = [], []
    for a in it.args:                                  # evaluated left to right, then the range is built
        v = em.fresh()
        setup.append(f"int64_t {v} = {em.ex(a)};")
        vals.append(v)
    if len(vals) == 1:
        vals = ["INT64_C(0)", vals[0]]
    if len(vals) == 2:
        vals.append("INT64_C(1)")
    r = em.fresh()
    setup.append(f"PyRangeIter {r}({', '.join(vals)});")
    return setup, r


def _source(em, it):
    """-> (setup statements, continue-condition, advance statements, item); item = (Ty, C expr) | [items]."""
    f = em.fresh
    if is_helper(em.tc, it):
        n = it.func
        if n == "range":
            setup, r = _range_setup(em, it)
            k = f()
            return setup + [f"uint64_t {k} = 0;"], f"{k} < {r}.n", [f"{k}++;"], (INT, f"{r}.at({k})")
        if n == "reversed":
            a = it.args[0]
            if is_helper(em.tc, a):                        # reversed(range(...))
                setup, r = _range_setup(em, a)
                k = f()
                return setup + [f"uint64_t {k} = {r}.n;"], f"{k} > 0", [f"{k}--;"], (INT, f"{r}.at({k} - 1)")
            s, i = f(), f()
            if a.ty == STR:
                return ([f"PyStr *{s} = {em.ex(a)};", f"int64_t {i} = static_cast<int64_t>({s}->data.size()) - 1;"],
                        f"{i} >= 0", [f"{i}--;"], (STR, f"pystr_new({s}->data.data() + {i}, 1)"))
            return ([f"auto *{s} = {em.ex(a)};", f"int64_t {i} = {s}->size() - 1;"],
                    f"{i} >= 0 && {i} < {s}->size()", [f"{i}--;"], (a.ty.elem, _elem(a.ty, f"{s}->data[{i}]")))
        if n == "enumerate":
            setup, cond, adv, item = _source(em, it.args[0])
            start = _kw(it, "start")
            sx = start.value if start is not None else (it.args[1] if len(it.args) > 1 else None)
            st, c = f(), f()
            setup = setup + [f"int64_t {st} = {em.ex(sx) if sx is not None else 'INT64_C(0)'};", f"int64_t {c} = 0;"]
            return setup, cond, adv + [f"{c}++;"], [(INT, f"py_add_i64({st}, {c})"), item]
        subs = [_source(em, a) for a in it.args]           # zip: stops at the shortest
        return ([x for s in subs for x in s[0]], " && ".join(f"({s[1]})" for s in subs),
                [x for s in subs for x in s[2]], [s[3] for s in subs])
    t, s, i = it.ty, f(), f()
    if t == STR:
        return ([f"PyStr *{s} = {em.ex(it)};", f"int64_t {i} = 0;"], f"{i} < static_cast<int64_t>({s}->data.size())",
                [f"{i}++;"], (STR, f"pystr_new({s}->data.data() + {i}, 1)"))
    if t.name == "dict":
        n0 = f()
        return ([f"auto *{s} = {em.ex(it)};", f"int64_t {n0} = {s}->size();", f"int64_t {i} = 0;"],
                f"py_dict_iter_ok({s}->size(), {n0}, {i})", [f"{i}++;"], (t.key, f"{s}->keys[{i}]"))
    return ([f"auto *{s} = {em.ex(it)};", f"int64_t {i} = 0;"], f"{i} < {s}->size()", [f"{i}++;"],
            (t.elem, _elem(t, f"{s}->data[{i}]")))


def _value(item):
    """(Ty, C expr) of an item; an enumerate/zip item becomes a std::tuple built left to right."""
    if not isinstance(item, list):
        return item
    from .tuples import ctype_tuple, tuple_of
    parts = [_value(i) for i in item]
    t = tuple_of([ty for ty, _ in parts])
    return t,f"{ctype_tuple(t).strip()}{{{', '.join(cx for _, cx in parts)}}}"


def _binds(target, item, declare: bool) -> List[str]:
    if isinstance(target, str):
        ty, cx = _value(item)
        return [f"{_ctype(ty) if declare else ''}p_{target} = {cx};"]
    if not isinstance(item, list):                     # a tuple value (list element, d.items()): source fetches are pure
        ty, cx = item
        item = [(t, f"std::get<{k}>({cx})") for k, t in enumerate(ty.elts)]
    return [x for t, i in zip(target, item) for x in _binds(t, i, declare)]


def _loops(em, gens, action: str) -> str:
    """Nested loops for the clauses (one line); comprehension variables are declared in their loop body."""
    def rec(i):
        if i == len(gens):
            return action
        g = gens[i]
        setup, cond, adv, item = _source(em, g.iter)
        parts = ["{"] + setup + [f"for (;;) {{ if (!({cond})) break;"] + _binds(g.target, item, True) + adv
        parts += [f"if (!({em.cond(c)})) continue;" for c in g.ifs]
        return " ".join(parts + [rec(i + 1), "} }"])
    return rec(0)


def emit_foreach(em, s, d: int) -> None:
    setup, cond, adv, item = _source(em, s.iter)
    em.w(d, "{")
    for x in setup:
        em.w(d + 1, x)
    em.w(d + 1, "for (;;) {")
    em.w(d + 2, f"if (!({cond})) break;")
    for x in _binds(s.var, item, False) + adv:
        em.w(d + 2, x)
    for x in s.body:
        em.stmt(x, d + 2)
    em.w(d + 1, "}")
    em.w(d, "}")


def _key_fn(em, lam, list_ty) -> str:
    p, pt, kt = lam.params[0], lam.param_tys[0], _ctype(lam.ty).strip()
    if list_ty is not None and _nested(list_ty):
        return (f"[&](void *_raw) -> {kt} {{ {_ctype(pt)}p_{p} = ({_ctype(pt)})_raw; "
                f"return {em.ex(lam.body)}; }}")
    return f"[&]({_ctype(pt)}p_{p}) -> {kt} {{ return {em.ex(lam.body)}; }}"


def emit_expr(em, e) -> str:
    if isinstance(e, A.Lambda):                       # only reached through key=, handled by the callers
        return "0"
    r = em.fresh()
    if isinstance(e, A.DictComp):
        from .emit_c import dict_rt_name
        rt = dict_rt_name(e.ty)
        k, v = em.fresh(), em.fresh()
        act = (f"{{ {_ctype(e.ty.key)}{k} = {em.ex(e.key)}; {_ctype(e.ty.elem)}{v} = {em.ex(e.value)}; "
               f"{rt}_set({r}, {k}, {v}); }}")
        return f"[&]() {{ {rt} *{r} = {rt}_new(); {_loops(em, e.gens, act)} return {r}; }}()"
    act = f"pyl_append({r}, {em.ex(e.elt)});"
    return f"[&]() {{ auto *{r} = pyl_new<{_store(e.ty)}>(); {_loops(em, e.gens, act)} return {r}; }}()"


def emit_call_hook(em, e: A.Call) -> Optional[str]:
    n = e.func
    if n in em.tc.funcs or not e.args:
        return None
    a, key = e.args[0], _kw(e, "key")
    if n in ("any", "all") and isinstance(a, A.GenExp):
        hit, miss = ("true", "false") if n == "any" else ("false", "true")
        test = em.cond(a.elt) if n == "any" else f"!({em.cond(a.elt)})"
        return f"[&]() -> bool {{ {_loops(em, a.gens, f'if ({test}) return {hit};')} return {miss}; }}()"
    if n == "sum" and isinstance(a, A.GenExp):
        et, s = a.ty.elem, em.fresh()
        if et == FLOAT:
            c = em.fresh()
            act = f"py_sum_f64_add({s}, {c}, {em.ex(a.elt)});"
            return f"[&]() {{ double {s} = 0.0, {c} = 0.0; {_loops(em, a.gens, act)} return py_sum_f64_result({s}, {c}); }}()"
        act = f"{s} += ({em.ex(a.elt)}) ? 1 : 0;" if et == BOOL else f"{s} = py_add_i64({s}, {em.ex(a.elt)});"
        return f"[&]() {{ int64_t {s} = 0; {_loops(em, a.gens, act)} return {s}; }}()"
    if n in ("min", "max") and isinstance(a, A.GenExp):
        et = a.ty.elem
        ct, seen, best, v = _ctype(et), em.fresh(), em.fresh(), em.fresh()
        pre = f"bool {seen} = false; {ct}{best}{{}};"
        if key is None:
            better = f"pyl_lt({v}, {best})" if n == "min" else f"pyl_lt({best}, {v})"
            act = f"{{ {ct}{v} = {em.ex(a.elt)}; if (!{seen} || {better}) {{ {best} = {v}; {seen} = true; }} }}"
        else:
            kf, kv, bk = em.fresh(), em.fresh(), em.fresh()
            kct = _ctype(key.value.ty)
            pre += f" {kct}{bk}{{}}; auto {kf} = {_key_fn(em, key.value, None)};"
            better = f"pyl_lt({kv}, {bk})" if n == "min" else f"pyl_lt({bk}, {kv})"
            act = (f"{{ {ct}{v} = {em.ex(a.elt)}; {kct}{kv} = {kf}({v}); "
                   f"if (!{seen} || {better}) {{ {best} = {v}; {bk} = {kv}; {seen} = true; }} }}")
        return (f"[&]() {{ {pre} {_loops(em, a.gens, act)} if (!{seen}) py_minmax_empty(\"{n}\"); "
                f"return {best}; }}()")
    if n == "sorted" and key is not None:
        rev = _kw(e, "reverse")
        src, lst, rv = em.fresh(), em.fresh(), em.fresh()
        parts = [f"auto *{src} = {em.ex(a)};", f"bool {rv} = {em.ex(rev.value) if rev else 'false'};",
                 f"auto *{lst} = {src if isinstance(a, A.GenExp) else f'pyl_copy({src})'};"]
        return (f"[&]() {{ {' '.join(parts)} return pyl_sort_key({lst}, {_key_fn(em, key.value, e.ty)}, {rv}); }}()")
    return None


def emit_sort_key(em, e: A.MethodCall, recv: str) -> str:
    rev, key = _kw(e, "reverse"), _kw(e, "key")
    lst, rv = em.fresh(), em.fresh()
    return (f"[&]() {{ auto *{lst} = {recv}; bool {rv} = {em.ex(rev.value) if rev else 'false'}; "
            f"pyl_sort_key({lst}, {_key_fn(em, key.value, e.recv.ty)}, {rv}); return 0; }}()")
