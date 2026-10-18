"""
PYTHIA :: PySub 1.3 type-system extensions (type-checker side)

Hooked into typecheck.TypeChecker by a handful of one-line delegations, so the
bulk of the logic lives here:

  * typing imports and annotations (List/Dict/Set/Optional/Union/Sequence/Iterable, `T | None`, "Forward")
  * default parameter values and keyword arguments for user functions, methods and constructors
  * Optional[T] (`Ty("optional", T)`) with flow-sensitive narrowing on local names;
    class types are nullable references (None flows into them exactly as in CPython, and
    every attribute access / method call is checked at run time -> AttributeError)
  * isinstance(x, T | (T1, T2)) and type(x) == T, decided statically from the declared type
  * set[T] for T in int/float/bool/str (order-dependent operations are rejected)
  * dict values of any supported type (lists, dicts, sets, objects)
  * module-level variables visible inside functions, and `global`
"""
import copy
from typing import Dict, List, Optional, Set, Tuple

from . import ast_nodes as A
from .parser import Diagnostic
from .typecheck import (Ty, INT, FLOAT, BOOL, STR, NONE, ERR, PRIM, NUMERIC, Scope,
                        widens_to, list_of, dict_of)

BUILTIN_TYS = {"int", "float", "bool", "str", "list", "dict", "set", "None", "optional", "tuple", "<error>"}
SCALARS = ("int", "float", "bool")

TYPING_ALIAS = {"List": "list", "Dict": "dict", "Set": "set", "Tuple": "tuple", "Optional": "Optional",
                "Union": "Union", "Sequence": "list", "Iterable": "list",
                "DefaultDict": "dict"}


def is_class(t: Optional[Ty]) -> bool:
    return t is not None and t is not ERR and t.name not in BUILTIN_TYS


def opt_of(t: Ty) -> Ty:
    if t is ERR or is_class(t) or t.name in ("optional", "None"):
        return t
    return Ty("optional", t)


def opt_scalar(t: Optional[Ty]) -> bool:
    return t is not None and t.name == "optional" and t.elem.name in SCALARS


def set_of(t: Ty) -> Ty:
    return Ty("set", t)


def ty_str(t: Ty) -> Optional[str]:
    if t.name == "optional":
        return f"{t.elem} | None"
    if t.name == "set":
        return f"set[{t.elem}]"
    return None


def widens(src: Ty, dst: Ty) -> Optional[bool]:
    """Extra edges of the implicit-conversion lattice; None = not decided here."""
    if dst.name == "optional":
        if src == NONE:
            return True
        if src.name == "optional":
            return src.elem == dst.elem
        return widens_to(src, dst.elem)
    if is_class(dst) and src == NONE:
        return True                          # class references are nullable, as in CPython
    if src.name == "optional":
        return False
    return None


def may_fall_off(ret: Ty) -> bool:
    """A function returning Optional[T] or an object may end without `return` (CPython returns None)."""
    return ret.name == "optional" or is_class(ret)


def _err(tc, node, msg: str) -> Ty:
    tc.errors.append(Diagnostic(msg, node.line, node.col, "TypeError"))
    return ERR


# ------------------------------------------------------------------ imports & annotations
def check_imports(tc) -> None:
    """Read the parser's import table (parse_ext.parse_import validated the modules and names)."""
    tc.typing_names = {}             # local name -> typing name
    tc.typing_modules = set()        # local names bound to the typing module
    tc.collections_modules = set()
    tc.future_annotations = False
    tc.collections_names = {}        # local name -> 'defaultdict' | 'Counter'
    table = getattr(tc.mod, "import_table", None)
    if table is None:
        return
    for alias, mod in table.modules.items():
        if mod == "typing":
            tc.typing_modules.add(alias)
        elif mod == "collections":
            tc.collections_modules.add(alias)
    for local, (mod, attr) in table.names.items():
        if mod == "typing":
            tc.typing_names[local] = attr
        elif mod == "__future__":
            tc.future_annotations = True
        elif mod == "collections":
            tc.collections_names[local] = attr


def _te(src: A.TypeExpr, name: str, args) -> A.TypeExpr:
    te = A.TypeExpr(line=src.line, col=src.col, name=name)
    te.args = args
    te.param = args[0] if args else None
    te.param2 = args[1] if args and len(args) > 1 else None
    te.params = list(args or [])
    return te


def _union(tc, te: A.TypeExpr, parts: List[A.TypeExpr]) -> Ty:
    if not tc.future_annotations and te.name == "|" and any(getattr(p, "quoted", False) for p in parts):
        return _err(tc, te, "a quoted forward reference cannot be combined with `|` (CPython raises TypeError "
                            "when the annotation is evaluated); write Optional[\"Name\"] or quote the whole annotation")
    rest = [p for p in parts if p.name != "None"]
    if len(rest) != 1 or len(rest) == len(parts):
        return _err(tc, te, "unions other than `T | None` (Optional[T]) are outside the PySub subset")
    return _optional(tc, te, tc.resolve_type(rest[0]))


def _optional(tc, te, inner: Ty) -> Ty:
    if inner is ERR:
        return ERR
    if inner.name in ("None", "optional"):
        return inner
    return opt_of(inner)


def resolve_type(tc, te: A.TypeExpr) -> Optional[Ty]:
    """PySub 1.3 annotations; None lets the original resolver handle int/float/bool/str/None/classes."""
    name = te.name
    args = getattr(te, "args", None)
    if name == "|":
        return _union(tc, te, args)
    via_typing = False
    if "." in name:
        mod, attr = name.rsplit(".", 1)
        if mod in getattr(tc, "collections_modules", ()) and attr in ("defaultdict", "Counter"):
            return resolve_type(tc, _te(te, attr, args)) if attr in tc.collections_names.values() \
                else _coll_annotation(tc, te, attr, args)
        if mod not in getattr(tc, "typing_modules", ()):
            return _err(tc, te, f"unknown type {name!r}")
        name, via_typing = attr, True
    elif coll_name(tc, name):
        return _coll_annotation(tc, te, coll_name(tc, name), args)
    elif name in getattr(tc, "typing_names", {}):
        name, via_typing = tc.typing_names[name], True
    elif name in TYPING_ALIAS:
        return _err(tc, te, f"{name!r} is not imported; add `from typing import {name}`")
    if via_typing:
        if name not in TYPING_ALIAS:
            return _err(tc, te, f"typing.{name} is outside the PySub subset")
        name = TYPING_ALIAS[name]
    if name in ("Any", "object"):
        return _err(tc, te, f"{name!r} is outside the PySub subset: every value needs one static type")

    def nargs(n: int, what: str) -> bool:
        if args is None or len(args) != n:
            _err(tc, te, f"{what} takes exactly {n} type argument(s), e.g. "
                         + {"Optional": "Optional[int]", "list": "list[int]", "set": "set[int]",
                            "dict": "dict[str, int]"}.get(what, what))
            return False
        return True

    if name == "Optional":
        return _optional(tc, te, tc.resolve_type(args[0])) if nargs(1, "Optional") else ERR
    if name == "Union":
        return _union(tc, te, args or [])
    if name == "set":
        if not nargs(1, "set"):
            return ERR
        el = tc.resolve_type(args[0])
        if el is ERR:
            return ERR
        if el.name not in PRIM:
            return _err(tc, te, f"set elements must be int, float, bool or str in PySub; found {el}")
        return set_of(el)
    if name == "list":
        if args is None:
            return None if not via_typing else nargs(1, "list") and ERR
        if not nargs(1, "list"):
            return ERR
        inner = tc.resolve_type(args[0])
        if inner is ERR:
            return ERR
        if inner.name in ("optional", "None"):
            return _err(tc, te, f"list elements cannot be {inner} in PySub (objects may be None; scalars may not)")
        if inner.name == "list" and inner.elem is not None and inner.elem.name == "list":
            return _err(tc, te, "list nesting deeper than two levels is outside the PySub subset")
        return list_of(inner)
    if name == "dict":
        if args is None:
            return None if not via_typing else nargs(2, "dict") and ERR
        if not nargs(2, "dict"):
            return ERR
        k, v = tc.resolve_type(args[0]), tc.resolve_type(args[1])
        if k is ERR or v is ERR:
            return ERR
        if k.name == "tuple" or v.name == "tuple":
            from . import tuples
            return tuples.resolve_dict(tc, te, k, v)
        if k.name not in ("int", "str"):
            return _err(tc, te, f"dict key type must be int or str; found {k}")
        if v.name in ("optional", "None"):
            return _err(tc, te, f"dict values cannot be {v} in PySub")
        return dict_of(k, v)
    if name != te.name:                       # e.g. typing.Tuple -> tuple: resolved by whoever owns it
        return tc.resolve_type(_te(te, name, args))
    return None


# ------------------------------------------------------------------ functions: globals, defaults
class _Visible:
    """Module-level names as seen from inside a function: everything except the names the function
    assigns (Python makes those local throughout the function unless declared `global`)."""

    def __init__(self, tc, hidden: Set[str]):
        self.tc, self.hidden = tc, hidden

    def __contains__(self, name) -> bool:
        return name not in self.hidden and name in self.tc.global_scope.names

    def __getitem__(self, name):
        return self.tc.global_scope.names[name]

    def get(self, name, default=None):
        return self[name] if name in self else default


class GlobalView(Scope):
    def __init__(self, tc, hidden: Set[str]):
        super().__init__(None, "globals")
        self.names = _Visible(tc, hidden)

    def declare(self, name: str, ty: Ty) -> None:
        raise AssertionError("module-level names are declared by the module body")


def walk(n):
    if isinstance(n, list):
        for x in n:
            yield from walk(x)
        return
    if not isinstance(n, A.Node):
        return
    yield n
    for f in n.__dataclass_fields__:
        if f in ("ty",):
            continue
        v = getattr(n, f)
        if isinstance(v, (A.Node, list)):
            yield from walk(v)


def assigned_names(body) -> Set[str]:
    out: Set[str] = set()
    for n in walk(body):
        if isinstance(n, (A.Assign, A.AugAssign)) and isinstance(n.target, A.Name):
            out.add(n.target.id)
        elif isinstance(n, (A.ForRange, A.ForEach)):
            out.add(n.var)
        elif isinstance(n, A.ExceptHandler) and n.bind:
            out.add(n.bind)
    return out


def global_decls(body) -> Set[str]:
    return {x for n in walk(body) if isinstance(n, A.Global) for x in n.names}


def begin_func(tc, sig, fn_scope: Scope) -> None:
    """Called by check_func once the parameters are declared."""
    f = sig.node
    tc._narrow = {}
    decl = global_decls(f.body)
    f.global_names = decl
    params = {p.name for p in f.params}
    for g in decl & params:
        _err(tc, f, f"name {g!r} is a parameter and global")
    fn_scope.parent = GlobalView(tc, (assigned_names(f.body) | params) - decl)
    tc._fn_globals |= {g for g in decl if g in tc.global_scope.names}
    ps = f.params[1:] if sig.owner else f.params
    for p, t in zip(ps, sig.params):
        if p.default is not None:
            check_default(tc, p, t)


_CONST = (A.IntLit, A.FloatLit, A.StrLit, A.BoolLit, A.NoneLit)


def _is_const(e) -> bool:
    if isinstance(e, _CONST):
        return True
    if isinstance(e, A.UnaryOp) and e.op in ("-", "+"):
        return isinstance(e.operand, (A.IntLit, A.FloatLit))
    return False


def is_mutable_default(e) -> bool:
    return isinstance(e, (A.ListLit, A.DictLit, A.SetLit)) or (isinstance(e, A.Call) and e.func == "set")


def check_default(tc, p: A.Param, t: Ty) -> None:
    d = p.default
    ok = _is_const(d)
    if isinstance(d, (A.ListLit, A.SetLit)):
        ok = all(_is_const(x) for x in d.elts)
    elif isinstance(d, A.DictLit):
        ok = all(_is_const(x) for x in d.keys + d.values)
    elif isinstance(d, A.Call):
        ok = d.func == "set" and not d.args and not d.kwargs
    if not ok:
        _err(tc, d, "default values must be constants in PySub: literals, None, or [] / {} / set() "
                    "(Python evaluates a default once, when the function is defined)")
        return
    got = tc.check_expr(d, t)
    if got is ERR or t is ERR:
        return
    if not widens_to(got, t):
        _err(tc, d, f"default for parameter {p.name!r} must be {t}, found {got}")
    elif got != t and got.name in SCALARS and (t.name in SCALARS or opt_scalar(t)):
        want = t.elem if t.name == "optional" else t
        if got != want:
            _err(tc, d, f"default for {want} parameter {p.name!r} must be a {want} literal: CPython keeps the "
                        f"{got} value (write e.g. {'1.0' if want == FLOAT else 'an int'})")


def c_func_name(sig) -> str:
    if sig.owner:
        return f"m_{sig.owner}_{sig.node.name}"
    return f"f_{sig.node.name}"


def bind_args(tc, e, sig, display: str) -> bool:
    """Map positional + keyword arguments onto the parameters, filling defaults.  Rewrites e.args to the
    full positional list (and clears e.kwargs); False after reporting an error."""
    params = sig.node.params[1:] if sig.owner else sig.node.params
    names = [p.name for p in params]
    n = len(params)
    if not e.kwargs and len(e.args) == n:
        return True
    if len(e.args) > n:
        _err(tc, e, f"{display}() expects {n} argument(s) but {len(e.args)} were given")
        return False
    slots = list(e.args) + [None] * (n - len(e.args))
    order = list(range(len(e.args)))
    ok = True
    for kw in e.kwargs:
        if kw.name not in names:
            _err(tc, kw, f"{display}() got an unexpected keyword argument {kw.name!r}")
            ok = False
            continue
        j = names.index(kw.name)
        if slots[j] is not None:
            _err(tc, kw, f"{display}() got multiple values for argument {kw.name!r}")
            ok = False
            continue
        slots[j] = kw.value
        order.append(j)
    missing = [names[j] for j in range(n) if slots[j] is None and params[j].default is None]
    if missing:
        _err(tc, e, f"{display}() expects {n} argument(s) but {len(order)} were given "
                    f"(missing {', '.join(repr(m) for m in missing)})")
        return False
    if not ok:
        return False
    for j in range(n):
        if slots[j] is None:
            d = params[j].default
            if is_mutable_default(d):
                r = A.DefaultRef(e.line, e.col, func=c_func_name(sig), param=names[j])
                r.ty = sig.params[j]
                slots[j] = r
            else:
                slots[j] = copy.deepcopy(d)
    impure = [j for j in order if not _simple(slots[j])]
    if order != sorted(order) and len(impure) >= 2:
        e.arg_order = order               # evaluate in source order, as CPython does
    e.args, e.kwargs = slots, []
    return True


def _simple(e) -> bool:
    return not any(isinstance(n, (A.Call, A.MethodCall)) for n in walk(e))


# ------------------------------------------------------------------ narrowing
def _declared(tc, e) -> Optional[Ty]:
    return tc.scope.lookup(e.id) if isinstance(e, A.Name) else None


def facts(tc, e) -> Tuple[Dict[str, Ty], Dict[str, Ty]]:
    """(names narrowed when e is true, names narrowed when e is false)."""
    if isinstance(e, A.UnaryOp) and e.op == "not":
        t, f = facts(tc, e.operand)
        return f, t
    if isinstance(e, A.BoolOp) and len(e.values) == 2:
        (t0, f0), (t1, f1) = facts(tc, e.values[0]), facts(tc, e.values[1])
        return ({**t0, **t1}, {}) if e.op == "and" else ({}, {**f0, **f1})
    if isinstance(e, A.Compare) and e.op in ("is", "is not", "==", "!="):
        x = e.left if isinstance(e.right, A.NoneLit) else e.right if isinstance(e.left, A.NoneLit) else None
        d = _declared(tc, x)
        if d is not None and d.name == "optional":
            fact = {x.id: d.elem}
            return (fact, {}) if e.op in ("is not", "!=") else ({}, fact)
    if isinstance(e, A.Name):
        d = _declared(tc, e)
        if d is not None and d.name == "optional":
            return {e.id: d.elem}, {}
    if isinstance(e, A.Call) and e.func == "isinstance" and e.args and isinstance(e.args[0], A.Name):
        st = getattr(e, "static", None)
        d = _declared(tc, e.args[0])
        if st and st[0] == "test" and d is not None and d.name == "optional":
            return {e.args[0].id: d.elem}, {}
    return {}, {}


def _term(s) -> bool:
    if isinstance(s, (A.Return, A.Raise, A.Break, A.Continue)):
        return True
    if isinstance(s, A.If):
        return bool(s.orelse) and terminates(s.body) and terminates(s.orelse)
    if isinstance(s, A.TryExcept):
        return terminates(s.body) and all(terminates(h.body) for h in s.handlers)
    if isinstance(s, A.While):
        return isinstance(s.test, A.BoolLit) and s.test.value and not _has_break(s.body)
    return False


def terminates(body) -> bool:
    return any(_term(s) for s in body)


def _has_break(body) -> bool:
    for s in body:
        if isinstance(s, A.Break):
            return True
        if isinstance(s, A.If) and (_has_break(s.body) or _has_break(s.orelse)):
            return True
        if isinstance(s, A.TryExcept) and (_has_break(s.body) or any(_has_break(h.body) for h in s.handlers)):
            return True
    return False


def _set_narrow(tc, d: Dict[str, Ty]) -> None:
    tc._narrow.clear()
    tc._narrow.update(d)


def check_stmt(tc, s) -> bool:
    """Statements with narrowing / new semantics; False lets the original checker handle s."""
    if getattr(tc, "_reenter", None) is s:
        tc._reenter = None
        return False
    N = tc._narrow
    if isinstance(s, A.Global):
        if tc.cur_fn is not None:
            for g in s.names:
                if g not in tc.global_scope.names:
                    _err(tc, s, f"global {g!r} must be assigned at module level before a function can use it "
                                f"in PySub")
        return True
    if isinstance(s, A.Assign):
        if isinstance(s.target, A.Name) and s.ann is not None and tc.cur_fn is not None \
                and s.target.id in getattr(tc.cur_fn.node, "global_names", ()):
            _err(tc, s, f"annotated name {s.target.id!r} can't be global")
        tc.check_assign(s)
        if isinstance(s.target, A.Name):
            name = s.target.id
            N.pop(name, None)
            declared, vt = s.ty, getattr(s.value, "ty", None)
            if s.declares and declared == NONE:
                _err(tc, s.value, f"cannot infer a type for {name!r} from None; annotate it, "
                                  f"e.g. {name}: Optional[int] = None")
            elif s.declares and declared is not None and declared.name == "set" and declared.elem is None:
                _err(tc, s.value, f"cannot infer the element type of an empty set for {name!r}; "
                                  f"annotate it, e.g. {name}: set[int] = set()")
            elif declared is not None and declared.name == "optional" and vt is not None \
                    and vt.name not in ("optional", "None", "<error>"):
                N[name] = declared.elem
        return True
    if isinstance(s, A.If):
        tc.check_truthy(s.test)
        tt, ff = facts(tc, s.test)
        pre = dict(N)
        N.update(tt)
        tc.block(s.body)
        end_b = None if terminates(s.body) else dict(N)
        _set_narrow(tc, {**pre, **ff})
        tc.block(s.orelse)
        end_e = None if terminates(s.orelse) else dict(N)
        if end_b is None and end_e is None:
            _set_narrow(tc, pre)
        elif end_b is None or end_e is None:
            _set_narrow(tc, end_e if end_b is None else end_b)
        else:
            _set_narrow(tc, {k: v for k, v in end_b.items() if end_e.get(k) == v})
        return True
    if isinstance(s, A.While):
        for k in assigned_names(s.body):
            N.pop(k, None)
        pre = dict(N)
        tc.check_truthy(s.test)
        tt, ff = facts(tc, s.test)
        N.update(tt)
        tc.loop_depth += 1
        tc.block(s.body)
        tc.loop_depth -= 1
        _set_narrow(tc, {**pre, **({} if _has_break(s.body) else ff)})
        return True
    if isinstance(s, A.ForEach):
        from . import tuples
        tuples.mark_items(s.iter)             # `for k, v in d.items()` is allowed (tuples.py)
        _views(tc, [s.iter])
        t = tc.synth(s.iter)
        if t.name in ("set", "optional"):
            for k in assigned_names([s]):
                N.pop(k, None)
            pre = dict(N)
            if t.name == "set":
                _err(tc, s.iter, "iterating over a set visits its elements in CPython's hash order, which PySub "
                                 "does not reproduce; iterate over sorted(s) instead")
            else:
                _err(tc, s.iter, f"{t} may be None here; test `is not None` first")
            tc.bind(s, s.var, t.elem)
            tc.loop_depth += 1
            tc.block(s.body)
            tc.loop_depth -= 1
            _set_narrow(tc, pre)
            return True
    if isinstance(s, (A.ForEach, A.ForRange, A.TryExcept)):
        for k in assigned_names([s]):
            N.pop(k, None)
        pre = dict(N)
        tc._reenter = s
        tc.check_stmt(s)
        _set_narrow(tc, pre)
        return True
    return False


def check_return(tc, s) -> None:
    if tc.cur_fn is None:
        return
    want = tc.cur_fn.ret
    if s.value is None and (want.name == "optional" or is_class(want)):
        s.value = A.NoneLit(s.line, s.col)           # bare `return` returns None
    elif want == NONE and isinstance(s.value, A.NoneLit):
        s.value = None                                # `return None` from a -> None function


# ------------------------------------------------------------------ expressions
def synth(tc, e) -> Optional[Ty]:
    if isinstance(e, A.Name):
        return _name(tc, e)
    if isinstance(e, A.SetLit):
        ts = [tc.synth(x) for x in e.elts]
        if ERR in ts:
            return ERR
        acc = ts[0]
        for t in ts[1:]:
            if acc != t:
                acc = FLOAT if {acc.name, t.name} <= set(NUMERIC) and FLOAT in (acc, t) else \
                      INT if {acc.name, t.name} <= {"int", "bool"} else ERR
        if acc is ERR or acc.name not in PRIM:
            return _err(tc, e, "set elements must share one type: int, float, bool or str")
        return set_of(acc)
    if isinstance(e, A.DefaultRef):
        return e.ty
    if isinstance(e, A.BoolOp) and len(e.values) == 2:
        return _boolop(tc, e)
    if isinstance(e, A.IfExp):
        return _ifexp(tc, e)
    if isinstance(e, A.Compare):
        return _compare(tc, e)
    if isinstance(e, A.Attribute):
        r = tc.synth(e.value)
        if r.name == "optional":
            return _err(tc, e, f"{r} may be None here (CPython: AttributeError); test `is not None` first")
    if isinstance(e, A.Subscript):
        r = tc.synth(e.value)
        if r.name == "optional":
            return _err(tc, e, f"{r} may be None here (CPython: 'NoneType' object is not subscriptable); "
                               f"test `is not None` first")
        if r.name == "set":
            return _err(tc, e, "'set' object is not subscriptable")
    return None


def _in_function_scopes(scope, name: str) -> bool:
    """Bound in a scope between here and the module scope (function body, comprehension, key lambda)."""
    s = scope
    while s is not None and s.kind not in ("global", "globals"):   # "globals": a function's GlobalView
        if name in s.names:
            return True
        s = s.parent
    return False


def _name(tc, e) -> Optional[Ty]:
    t = tc.scope.lookup(e.id)
    if t is None:
        if tc.cur_fn is not None and e.id in tc.global_scope.names and tc.scope.lookup_local(e.id) is None:
            return _err(tc, e, f"{e.id!r} is assigned in this function, so it is a local variable everywhere in "
                               f"it (CPython raises UnboundLocalError here); add `global {e.id}` to use the "
                               f"module-level variable")
        return None
    if tc.cur_fn is not None and not _in_function_scopes(tc.scope, e.id):
        e.global_ref = True
        tc._fn_globals.add(e.id)
    nt = tc._narrow.get(e.id)
    if nt is not None and t.name == "optional":
        e.unwrap = opt_scalar(t)
        return nt
    e.unwrap = False
    return t


def _narrowed(tc, fact: Dict[str, Ty], node) -> Ty:
    saved = dict(tc._narrow)
    tc._narrow.update(fact)
    try:
        return tc.synth(node)
    finally:
        _set_narrow(tc, saved)


def _boolop(tc, e) -> Ty:
    from .typecheck import join
    v0, v1 = e.values
    t0 = tc.synth(v0)
    tt, ff = facts(tc, v0)
    t1 = _narrowed(tc, tt if e.op == "and" else ff, v1)
    if ERR in (t0, t1):
        return ERR
    if t0 == t1:
        return t0
    j = join(t0, t1)
    if j is ERR:
        return _err(tc, e, f"operands of {e.op!r} have unrelated types {t0} and {t1}; PySub requires a single "
                           f"static result type")
    return j


def _ifexp(tc, e) -> Ty:
    tc.synth(e.test)
    tt, ff = facts(tc, e.test)
    bt, ot = _narrowed(tc, tt, e.body), _narrowed(tc, ff, e.orelse)
    if ERR in (bt, ot):
        return ERR
    if bt == ot:
        return bt
    for a, b in ((bt, ot), (ot, bt)):
        if a == NONE and b.name != "None":
            return opt_of(b)
        if a.name == "optional" and b == a.elem:
            return a
    return _err(tc, e, f"the branches of `x if c else y` have types {bt} and {ot}; PySub requires a single "
                       f"static result type (convert one branch explicitly, e.g. float(x))")


# isinstance / type(): the run-time classes a value of a declared type can have
def _classes(t: Ty, node=None) -> Optional[Set[str]]:
    if isinstance(node, (A.IntLit, A.FloatLit, A.BoolLit, A.StrLit)) or \
            (isinstance(node, A.UnaryOp) and isinstance(node.operand, (A.IntLit, A.FloatLit))):
        return {t.name}                  # a literal's class is exact
    if t.name == "int":
        return {"int", "bool"}           # bool values widen into int variables
    if t.name == "float":
        return {"float", "int", "bool"}  # and ints into float variables
    if t.name in ("bool", "str", "list", "dict", "set"):
        return {t.name}
    if is_class(t):
        return {t.name}
    return None


def _matches(c: str, cls: str, exact: bool) -> bool:
    return c == cls or (not exact and c == "bool" and cls == "int")


def decide(tc, x_node, t: Ty, wanted: List[str], exact: bool, what: str, at) -> Optional[tuple]:
    """('const', bool) | ('test', node, nonnull) | None after an error."""
    nullable = t.name == "optional" or is_class(t)
    base = t.elem if t.name == "optional" else t
    cs = _classes(base, x_node)
    if cs is None:
        _err(tc, at, f"{what} is not supported for a value of type {t}")
        return None
    res = {any(_matches(c, w, exact) for w in wanted) for c in cs}
    if len(res) == 2:
        _err(tc, at, f"{what} cannot be decided statically for a value declared {t}: PySub stores "
                     f"{' and '.join(sorted(cs - {base.name}))} values in {base} variables; "
                     + ("use isinstance(x, (int, float))" if base == FLOAT else "test with isinstance(x, int)"))
        return None
    if True in res:
        return ("test", x_node, True) if nullable else ("const", True)
    return ("const", False)


_TYPE_NAMES = {"int", "float", "bool", "str", "list", "dict", "set"}


def _type_name(tc, n) -> Optional[str]:
    if isinstance(n, A.Name) and (n.id in _TYPE_NAMES or n.id in tc.classes):
        return n.id
    return None


def _isinstance(tc, e) -> Ty:
    if len(e.args) != 2 or e.kwargs:
        return _err(tc, e, "isinstance() takes exactly two arguments: a value and a type (or a tuple of types)")
    x, cls = e.args
    t = tc.synth(x)
    elts = cls.elts if isinstance(cls, A.ListLit) and getattr(cls, "tuple_syntax", False) else [cls]
    wanted = [_type_name(tc, c) for c in elts]
    if None in wanted:
        return _err(tc, cls, "isinstance() needs a type name (int, float, bool, str, list, dict, set or a class) "
                             "or a parenthesised tuple of them")
    if t is ERR:
        return BOOL
    st = decide(tc, x, t, wanted, False, "isinstance()", e)
    if st is None:
        return ERR
    e.static = st
    return BOOL


def _compare(tc, e) -> Optional[Ty]:
    op = e.op
    tcall = e.left if isinstance(e.left, A.Call) and e.left.func == "type" else \
        e.right if isinstance(e.right, A.Call) and e.right.func == "type" else None
    if tcall is not None and op in ("==", "!=", "is", "is not"):
        other = e.right if tcall is e.left else e.left
        name = _type_name(tc, other)
        if len(tcall.args) != 1 or name is None:
            return _err(tc, e, "only `type(x) == T` / `type(x) is T` with a type name T is supported")
        t = tc.synth(tcall.args[0])
        tcall.ty = t
        if t is ERR:
            return BOOL
        st = decide(tc, tcall.args[0], t, [name], True, f"type(x) {op} {name}", e)
        if st is None:
            return ERR
        e.static = _negate(st) if op in ("!=", "is not") else st
        return BOOL
    if op in ("in", "not in"):
        _views(tc, [e.right])
    lt, rt = tc.synth(e.left), tc.synth(e.right)
    if ERR in (lt, rt):
        return BOOL
    if op in ("==", "!=", "is", "is not") and NONE in (lt, rt):
        x = e.right if lt == NONE else e.left
        xt = rt if lt == NONE else lt
        nonnull = op in ("!=", "is not")
        if xt == NONE:
            e.static = ("const", not nonnull)
        elif xt.name == "optional" or is_class(xt):
            e.static = ("test", x, nonnull)
        else:
            e.static = ("const", nonnull)      # an int/str/list value is never None
        return BOOL
    if op in ("is", "is not"):
        if lt == rt and (lt == BOOL or is_class(lt) or lt.name in ("list", "dict", "set")):
            return BOOL
        return _err(tc, e, f"`{op}` compares object identity, which CPython leaves implementation-defined for "
                           f"{lt} values; use == / !=")
    if "optional" in (lt.name, rt.name):
        o = lt if lt.name == "optional" else rt
        other = rt if o is lt else lt
        if op in ("==", "!=") and opt_scalar(o) and (other.name in NUMERIC or other == o):
            return BOOL
        return _err(tc, e, f"{o} may be None here (CPython: TypeError for {op!r} with None); "
                           f"test `is not None` first")
    if rt.name == "set" and op in ("in", "not in"):
        if not (widens_to(lt, rt.elem) or (lt.name in NUMERIC and rt.elem.name in NUMERIC)):
            return _err(tc, e, f"{lt} cannot appear in a {rt}")
        return BOOL
    if lt.name == "set" or rt.name == "set":
        if lt == rt and op in ("==", "!=", "<", "<=", ">", ">="):
            return BOOL
        return _err(tc, e, f"cannot compare {lt} with {rt}")
    return None


def _negate(st):
    if st[0] == "const":
        return ("const", not st[1])
    return ("test", st[1], not st[2])


def binop(tc, node, op: str, lt: Ty, rt: Ty) -> Optional[Ty]:
    if ERR in (lt, rt):
        return None
    if lt.name == "set" or rt.name == "set":
        if lt == rt and op in ("|", "&", "-", "^"):
            return lt
        return _err(tc, node, f"operator {op!r} is not defined for {lt} and {rt}")
    if "optional" in (lt.name, rt.name):
        o = lt if lt.name == "optional" else rt
        return _err(tc, node, f"{o} may be None here (CPython: unsupported operand type(s) for {op}: 'NoneType' "
                              f"...); test `is not None` first")
    return None


def _set_arg(tc, a, el: Ty, what: str) -> None:
    t = tc.synth(a)
    if t is ERR:
        return
    if t.name not in ("set", "list") or not (t.elem == el or widens_to(t.elem, el)):
        _err(tc, a, f"{what}: expected a set[{el}] or list[{el}], found {t}")


def synth_method(tc, e, recv: Ty) -> Optional[Ty]:
    if recv.name == "optional":
        return _err(tc, e, f"{recv} may be None here (CPython: AttributeError: 'NoneType' object has no "
                           f"attribute {e.method!r}); test `is not None` first")
    if is_class(recv):
        info = tc.classes.get(recv.name)
        sig = info.methods.get(e.method) if info else None
        if sig is not None and not bind_args(tc, e, sig, f"{recv.name}.{e.method}"):
            return ERR
        return None
    if recv.name == "dict" and e.method == "most_common":
        return most_common(tc, e, recv)
    if recv.name != "set":
        return None
    tc.check_kwargs(e, set())
    m, el = e.method, recv.elem

    def nargs(k: int) -> bool:
        return tc._margs(e, k, k, m)
    if m in ("add", "remove", "discard"):
        if nargs(1):
            tc._want(e.args[0], el, f"{m}() value")
        return NONE
    if m in ("clear",):
        nargs(0)
        return NONE
    if m == "copy":
        nargs(0)
        return recv
    if m in ("update", "intersection_update", "difference_update", "symmetric_difference_update",
             "union", "intersection", "difference", "symmetric_difference", "issubset", "issuperset",
             "isdisjoint"):
        if nargs(1):
            _set_arg(tc, e.args[0], el, f"{m}()")
        if m.endswith("update"):
            return NONE
        return BOOL if m.startswith("is") else recv
    if m == "pop":
        return _err(tc, e, "set.pop() removes an element in CPython's hash order, which PySub does not reproduce")
    return _err(tc, e, f"set has no method {m!r} in PySub")


def _repr_ok(t: Ty, top: bool = True) -> bool:
    if t.name in PRIM:
        return True
    if t.name == "list":
        return t.elem is not None and (t.elem.name in PRIM or (top and t.elem.name == "list"
                                                               and t.elem.elem.name in PRIM))
    if t.name == "dict":
        return _repr_ok(t.elem, False)
    if t.name == "optional":
        return _repr_ok(t.elem, top)
    return False


def _views(tc, nodes) -> None:
    """Contexts where builtins_ext accepts d.keys() / d.values() (marked before they are synthesised)."""
    from . import builtins_ext
    for n in nodes:
        builtins_ext.mark_view_ok(tc, n)


def synth_call(tc, e) -> Optional[Ty]:
    name = e.func
    if name in ("len", "sorted", "list", "sum", "min", "max"):
        _views(tc, e.args)
    if name in tc.funcs and name not in tc.classes:
        if not bind_args(tc, e, tc.funcs[name], name):
            return ERR
        return None
    if name in tc.classes:
        init = tc.classes[name].init
        if init is not None and not bind_args(tc, e, init, name):
            return ERR
        return None
    if name == "isinstance":
        return _isinstance(tc, e)
    if name in ("collections.defaultdict", "collections.Counter"):
        return synth_collections(tc, e, name.split(".")[1])
    if name == "type":
        return _err(tc, e, "type() is supported only in comparisons such as `type(x) == int`")
    if name == "set":
        tc.check_kwargs(e, set())
        if not e.args:
            return Ty("set", None)
        if len(e.args) != 1:
            return _err(tc, e, "set() takes at most one argument")
        t = tc.synth(e.args[0])
        if t is ERR:
            return ERR
        if t.name in ("list", "set") and t.elem is not None and t.elem.name in PRIM:
            return set_of(t.elem)
        if t == STR:
            return set_of(STR)
        if t.name == "dict":
            return set_of(t.key)
        return _err(tc, e.args[0], f"set() takes a list, set, str or dict of int/float/bool/str, found {t}")
    if name in ("len", "sorted", "list", "print", "str", "min", "max", "sum", "bool") and e.args:
        if name in ("list", "sorted"):
            from . import tuples
            tuples.mark_items(e.args[0])
        ts = [tc.synth(a) for a in e.args]
        if ERR in ts:
            return None
        if name == "print":
            for a, t in zip(e.args, ts):
                if t.name == "set":
                    _err(tc, a, "printing a set shows CPython's hash order, which PySub does not reproduce; "
                                "print sorted(s) instead")
                elif t.name in ("dict", "optional") and not _repr_ok(t):
                    _err(tc, a, f"cannot print a {t}: PySub prints dicts whose values are numbers, str, "
                                f"lists of those or such dicts")
            return None
        t = ts[0]
        if name == "bool" and len(ts) == 1 and t.name in ("set", "dict", "optional"):
            return BOOL
        if t.name == "optional":
            if name == "str" and t.elem.name in PRIM:
                return STR
            return _err(tc, e.args[0], f"{t} may be None here; test `is not None` first")
        if t.name != "set":
            return None
        if name == "len":
            return INT if len(e.args) == 1 else None
        if name == "sorted":
            tc.check_kwargs(e, {"reverse"})
            return list_of(t.elem) if len(e.args) == 1 else _err(tc, e, "sorted() takes exactly one argument")
        return _err(tc, e.args[0], f"{name}() of a set depends on CPython's hash order (or is outside PySub); "
                                   f"use sorted(s)")
    return None


# ------------------------------------------------------------------ module-level variables
def finish(tc) -> None:
    """After every body is checked: which module-level variables functions use, and which of them need a
    run-time NameError check (a function may run before the variable is first assigned)."""
    main = tc.mod.main
    fg = tc._fn_globals

    def runs_user_code(st) -> bool:
        for n in walk(st):
            if isinstance(n, A.Call) and (n.func in tc.funcs or n.func in tc.classes):
                return True
            if isinstance(n, A.MethodCall) and n.recv.ty is not None and is_class(n.recv.ty):
                return True
        return False
    u = next((i for i, st in enumerate(main) if runs_user_code(st)), len(main))
    tc._gcheck = set()
    for g in sorted(fg):
        first = next((i for i, st in enumerate(main) if isinstance(st, A.Assign)
                      and isinstance(st.target, A.Name) and st.target.id == g), None)
        if first is None or first >= u:
            tc._gcheck.add(g)
    for n in walk(main):
        bound = n.var if isinstance(n, (A.ForRange, A.ForEach)) else n.bind if isinstance(n, A.ExceptHandler) \
            else None
        if bound in fg and (isinstance(n, A.ExceptHandler) or bound in tc._gcheck):
            _err(tc, n, f"module-level name {bound!r} is used inside a function; bind it with a plain "
                        f"assignment at module level (not a loop variable or `except ... as`)")
    tc.mod.fn_globals = set(fg)
    tc.mod.global_writers = set()
    for f in list(tc.mod.funcs) + [m for c in tc.mod.classes for m in c.methods]:
        tc.mod.global_writers |= getattr(f, "global_names", set())


# ------------------------------------------------------------------ lowering (lower.Lowerer hooks)
def lower_defaults(lw, mod) -> None:
    for f in list(mod.funcs) + [m for c in mod.classes for m in c.methods]:
        for p in f.params:
            if p.default is not None and p.ty is not None:
                p.default = lw.coerce(lw.expr(p.default), p.ty)


def lower_coerce(lw, e, want):
    """None = not handled here."""
    if e.ty is None or want is None or e.ty is ERR or want is ERR:
        return None
    if want.name == "optional":
        if e.ty == want:
            return e
        if e.ty == NONE:
            e.ty = want
            return e
        if e.ty.name == "optional":
            return e
        inner = lw.coerce(e, want.elem)
        if not opt_scalar(want):
            return inner
        c = A.Coerce(e.line, e.col, value=inner, to=want)
        c.ty = want
        return c
    if is_class(want) and e.ty == NONE:
        e.ty = want
        return e
    if e.ty.name == "set" and e.ty.elem is None and want.name == "set":
        e.ty = want
        return e
    return None


def lower_expr(lw, e):
    """None = let the original lowering handle e."""
    if isinstance(e, A.SetLit):
        e.elts = [lw.coerce(lw.expr(x), e.ty.elem) for x in e.elts]
        return e
    if isinstance(e, A.DefaultRef):
        return e
    if isinstance(e, A.IfExp) and e.ty is not None and e.ty.name == "optional":
        e.test = lw.expr(e.test)
        e.body, e.orelse = lw.coerce(lw.expr(e.body), e.ty), lw.coerce(lw.expr(e.orelse), e.ty)
        return e
    if isinstance(e, A.Call) and e.func == "isinstance":
        e.args[0] = lw.expr(e.args[0])
        return e
    if isinstance(e, A.Compare):
        if getattr(e, "static", None) is not None:
            if isinstance(e.left, A.Call) and e.left.func == "type":
                e.left.args[0] = lw.expr(e.left.args[0])
                e.right = lw.expr(e.right)
            elif isinstance(e.right, A.Call) and e.right.func == "type":
                e.right.args[0] = lw.expr(e.right.args[0])
                e.left = lw.expr(e.left)
            else:
                e.left, e.right = lw.expr(e.left), lw.expr(e.right)
            return e
        rt = e.right.ty
        if rt is not None and rt.name == "set" and e.op in ("in", "not in"):
            e.left, e.right = lw.coerce(lw.expr(e.left), rt.elem), lw.expr(e.right)
            return e
        return None
    if isinstance(e, A.MethodCall) and e.recv.ty is not None and e.recv.ty.name == "set":
        e.recv = lw.expr(e.recv)
        el = e.recv.ty.elem
        e.args = [lw.coerce(lw.expr(a), el) if e.method in ("add", "remove", "discard") else lw.expr(a)
                  for a in e.args]
        return e
    return None


# ------------------------------------------------------------------ collections.defaultdict / Counter
# Both are ordinary dicts at the type level (dict[K, V] / dict[K, int]); the runtime dict object carries the
# behaviour (missing key: insert the factory's value / read 0), so a defaultdict passed as `dict[...]` behaves
# exactly as in CPython.
FACTORIES = {"int": "int", "float": "float", "str": "str", "bool": "bool", "list": "list", "set": "set",
             "dict": "dict"}


def coll_name(tc, name: str) -> Optional[str]:
    """'defaultdict' / 'Counter' if `name` is bound to collections.defaultdict / collections.Counter."""
    return getattr(tc, "collections_names", {}).get(name)


def _coll_annotation(tc, te, kind: str, args) -> Ty:
    if kind == "defaultdict":                    # defaultdict[K, V] annotates a dict[K, V]
        return tc.resolve_type(_te(te, "dict", args))
    if args is None or len(args) != 1:
        return _err(tc, te, "Counter takes exactly 1 type argument, e.g. Counter[str]")
    k = tc.resolve_type(args[0])
    return ERR if k is ERR else dict_of(k, INT) if k.name in ("int", "str") else \
        _err(tc, te, f"Counter keys must be int or str in PySub; found {k}")


def _factory_ok(f: str, v: Ty) -> bool:
    if f == "Counter":
        return v == INT
    return v.name == FACTORIES[f] if f in ("list", "set", "dict") else v == Ty(f)


def check_factory(tc, e) -> None:
    """After check mode resolved an empty defaultdict(...)/Counter() to the expected dict type."""
    f = getattr(e, "factory", None)
    if f is None or e.ty is None or e.ty.name != "dict":
        return
    if not _factory_ok(f, e.ty.elem):
        what = "Counter()" if f == "Counter" else f"defaultdict({f})"
        _err(tc, e, f"{what} makes values of type {'int' if f == 'Counter' else f}, but the dict is "
                    f"declared {e.ty}")


def synth_collections(tc, e, kind: str) -> Ty:
    tc.check_kwargs(e, set())
    if kind == "defaultdict":
        if len(e.args) != 1 or not isinstance(e.args[0], A.Name) or e.args[0].id not in FACTORIES:
            return _err(tc, e, "defaultdict() needs one factory in PySub: int, float, str, bool, list, set or dict")
        e.factory = e.args[0].id
        e.args[0].ty = NONE
        return Ty("dict", None, None)                 # resolved by the annotation, like {}
    e.factory = "Counter"
    if not e.args:
        return Ty("dict", None, None)
    if len(e.args) != 1:
        return _err(tc, e, "Counter() takes one list or str in PySub")
    t = tc.synth(e.args[0])
    if t is ERR:
        return ERR
    if t == STR:
        return dict_of(STR, INT)
    if t.name == "list" and t.elem is not None and (t.elem.name in ("int", "str") or t.elem.name == "tuple"):
        if t.elem.name == "tuple":
            from . import tuples
            return tuples.resolve_dict(tc, e, t.elem, INT)
        return dict_of(t.elem, INT)
    return _err(tc, e.args[0], f"Counter() counts a str or a list of int, str or tuples in PySub, found {t}")


def most_common(tc, e, recv: Ty) -> Ty:
    from . import tuples
    tc.check_kwargs(e, set())
    if recv.elem != INT:
        return _err(tc, e, f"most_common() needs a Counter (dict[K, int]), found {recv}")
    if len(e.args) > 1:
        return _err(tc, e, "most_common() takes at most one argument")
    if e.args:
        tc._want(e.args[0], INT, "most_common() n")
    return list_of(tuples.tuple_of([recv.key, INT]))
