"""
PYTHIA :: PySub 1.3 code generation (Optional, nullable objects, sets, dicts of any value type,
module-level variables, defaults and keyword arguments).  Hooked into emit_c.Emitter.
"""
import re
from typing import Optional

from . import ast_nodes as A
from .typecheck import Ty, INT, FLOAT, BOOL, STR, NONE, ERR
from .types_ext import is_class, opt_scalar, is_mutable_default, c_func_name

_SCALAR_C = {"int": "int64_t", "float": "double", "bool": "bool", "str": "PyStr *"}


def _c(t: Ty) -> str:
    from .emit_c import ctype
    return ctype(t).strip()


def ctype(t: Ty) -> Optional[str]:
    if t.name == "optional":
        if t.elem.name in ("int", "float", "bool"):
            return f"std::optional<{_SCALAR_C[t.elem.name]}> "
        return _c(t.elem) + " "
    if t.name == "set":
        return f"PySet<{_SCALAR_C[t.elem.name]}> *"
    return None


def none_value(t: Optional[Ty]) -> str:
    if t is None or t == NONE or t is ERR:
        return "0"
    if opt_scalar(t):
        return f"{_c(t)}()"
    return "nullptr"


def _pure_name(e) -> bool:
    return isinstance(e, (A.Name, A.IntLit, A.FloatLit, A.StrLit, A.BoolLit, A.NoneLit))


def _static(em, st) -> str:
    """('const', b) | ('test', node, nonnull) -> C boolean expression."""
    if st[0] == "const":
        return "true" if st[1] else "false"
    node, nonnull = st[1], st[2]
    v = em.ex(node)
    t = node.ty
    if opt_scalar(t) and getattr(node, "unwrap", False):
        return "true" if nonnull else "false"      # narrowed: provably not None
    test = f"({v}).has_value()" if opt_scalar(t) else f"(({v}) != nullptr)"
    return test if nonnull else f"(!{test})"


def _const_with_effects(em, node, value: str) -> str:
    if node is None or _pure_name(node):
        return value
    return f"((void)({em.ex(node)}), {value})"


# ---------------------------------------------------------------- module layout
def module_prelude(em, mod) -> list:
    """Forward class declarations, needed when a generic dict (PyDictT) holds objects."""
    if not mod.classes or "PyDictT_" not in "\n".join(em.buf):
        return []
    return [f"struct {c.name};" for c in mod.classes] + [""]


def hoisted(em) -> set:
    return set(getattr(em.tc, "_fn_globals", set()))


def emit_globals(em, mod) -> None:
    """File-scope storage for module-level variables that functions use, and mutable default values."""
    from .emit_c import zero
    gs = sorted(hoisted(em))
    checks = getattr(em.tc, "_gcheck", set())
    if gs:
        em.w(0, "/* module-level variables used inside functions */")
        for g in gs:
            t = mod.globals_.get(g)
            if t is None or t is ERR:
                continue
            em.w(0, f"static {_c(t)} p_{g} = {zero(t)};")
            if g in checks:
                em.w(0, f"static bool g_ok_{g} = false;   /* NameError until first assigned */")
        em.w(0)
    fns = [(f, None) for f in mod.funcs] + [(m, c.name) for c in mod.classes for m in c.methods]
    first = True
    for f, owner in fns:
        sig = em.tc.classes[owner].methods.get(f.name) if owner else em.tc.funcs.get(f.name)
        if sig is None:
            continue
        ps = f.params[1:] if owner else f.params
        for p, t in zip(ps, sig.params):
            if p.default is not None and is_mutable_default(p.default):
                if first:
                    em.w(0, "/* mutable default values: evaluated once, shared by every call (as in CPython) */")
                    first = False
                ct = _c(t)
                em.w(0, f"static {ct} dflt_{c_func_name(sig)}_{p.name}() {{")
                em.w(1, f"static {ct} v = []() {{ ArenaPause _p; return ({em.ex(p.default)}); }}();")
                em.w(1, "return v;")
                em.w(0, "}")
    if not first:
        em.w(0)


def emit_lib_init(em, mod) -> None:
    """Library mode: module-level constants used by the compiled functions are built once at import."""
    gs = hoisted(em)
    em.w(0, "static void pythia_init_globals() {")
    for s in mod.main:
        if isinstance(s, A.Assign) and isinstance(s.target, A.Name) and s.target.id in gs:
            em.stmt(s, 1)
    em.w(0, "}")
    em.w(0)


def after_stmt(em, s, d: int) -> None:
    """A write to a module-level variable whose reads are NameError-checked marks it assigned."""
    checks = getattr(em.tc, "_gcheck", None)
    if not checks or not isinstance(s, (A.Assign, A.AugAssign)) or not isinstance(s.target, A.Name):
        return
    g = s.target.id
    if g in checks and (em._fn is None or g in getattr(em._fn, "global_names", ())):
        em.w(d, f"g_ok_{g} = true;")


# ---------------------------------------------------------------- statements
def stmt(em, s, d: int) -> bool:
    if isinstance(s, A.AugAssign) and s.target.ty is not None and s.target.ty.name == "set":
        fn = {"|": "pyset_ior", "&": "pyset_iand", "-": "pyset_isub", "^": "pyset_ixor"}[s.op]
        em.w(d, f"(void){fn}({em.ex(s.target)}, {em.ex(s.value)});")      # in place: aliases see it
        return True
    if isinstance(s, A.Assign) and isinstance(s.target, A.Attribute) and not _is_self(s.target.value):
        em.w(d, f"py_nn_set({em.ex(s.target.value)}, \"{s.target.attr}\")->{s.target.attr} = {em.ex(s.value)};")
        return True
    return False


def _is_self(e) -> bool:
    return isinstance(e, A.Name) and e.id == "self"


# ---------------------------------------------------------------- expressions
def ex(em, e) -> Optional[str]:
    if isinstance(e, A.NoneLit):
        return none_value(e.ty)
    if isinstance(e, A.Name):
        if getattr(e, "raw", None):
            return e.raw
        v = f"p_{e.id}"
        if getattr(e, "global_ref", False) and e.id in getattr(em.tc, "_gcheck", ()):
            v = f"(py_global_ok(g_ok_{e.id}, \"{e.id}\"), p_{e.id})"
        return f"(*{v})" if getattr(e, "unwrap", False) else v
    if isinstance(e, A.DefaultRef):
        return f"dflt_{e.func}_{e.param}()"
    if isinstance(e, A.Coerce) and e.to is not None and e.to.name == "optional":
        return f"{_c(e.to)}({em.ex(e.value)})"
    if isinstance(e, A.SetLit):
        v = em.fresh()
        parts = [f"auto *{v} = pyset_new<{_SCALAR_C[e.ty.elem.name]}>();"]
        parts += [f"pyset_add({v}, {em.ex(x)});" for x in e.elts]
        return "[&]() { " + " ".join(parts) + f" return {v}; }}()"
    st = getattr(e, "static", None)
    if st is not None and isinstance(e, (A.Compare, A.Call)):
        if st[0] == "const":
            if isinstance(e, A.Call):
                x = e.args[0]
            elif isinstance(e.left, A.Call) and e.left.func == "type":
                x = e.left.args[0]
            elif isinstance(e.right, A.Call) and e.right.func == "type":
                x = e.right.args[0]
            else:
                x = e.right if isinstance(e.left, A.NoneLit) else e.left
            return _const_with_effects(em, x, _static(em, st))
        return _static(em, st)
    if isinstance(e, A.Compare):
        lt, rt = e.left.ty, e.right.ty
        if e.op in ("is", "is not"):
            return f"(({em.ex(e.left)}) {'==' if e.op == 'is' else '!='} ({em.ex(e.right)}))"
        if rt is not None and rt.name == "set" and e.op in ("in", "not in"):
            t = f"pyset_contains({em.ex(e.right)}, {em.ex(e.left)})"
            return t if e.op == "in" else f"(!{t})"
        if lt is not None and lt.name == "set":
            l, r = em.ex(e.left), em.ex(e.right)
            return {"==": f"pyset_eq({l}, {r})", "!=": f"(!pyset_eq({l}, {r}))", "<=": f"pyset_le({l}, {r})",
                    "<": f"pyset_lt({l}, {r})", ">=": f"pyset_le({r}, {l})", ">": f"pyset_lt({r}, {l})"}[e.op]
        if "optional" in (getattr(lt, "name", ""), getattr(rt, "name", "")):
            return f"(({em.ex(e.left)}) {e.op} ({em.ex(e.right)}))"
        return None
    if isinstance(e, A.BinOp) and e.ty is not None and e.ty.name == "set":
        fn = {"|": "pyset_or", "&": "pyset_and", "-": "pyset_sub", "^": "pyset_xor"}[e.op]
        return f"{fn}({em.ex(e.left)}, {em.ex(e.right)})"
    if isinstance(e, A.Attribute) and not _is_self(e.value):
        return f"py_nn({em.ex(e.value)}, \"{e.attr}\")->{e.attr}"
    if isinstance(e, A.MethodCall):
        return _method(em, e)
    if isinstance(e, A.Call):
        return _call(em, e)
    return None


def _set_arg(em, a, el: str) -> str:
    v = em.ex(a)
    return v if a.ty.name == "set" and a.ty.elem.name == _elem_name(el) else f"pyset_of<{el}>({v})"


def _elem_name(c: str) -> str:
    return {v: k for k, v in _SCALAR_C.items()}[c]


def _method(em, e) -> Optional[str]:
    rt = e.recv.ty
    if rt is not None and rt.name == "set":
        el = _SCALAR_C[rt.elem.name]
        r, m = em.ex(e.recv), e.method
        a = [em.ex(x) for x in e.args]
        if m in ("add", "remove", "discard"):
            return f"(pyset_{m}({r}, {a[0]}), 0)"
        if m == "clear":
            return f"(pyset_clear({r}), 0)"
        if m == "copy":
            return f"pyset_copy({r})"
        o = _set_arg(em, e.args[0], el)
        ops = {"update": "ior", "intersection_update": "iand", "difference_update": "isub",
               "symmetric_difference_update": "ixor", "union": "or", "intersection": "and",
               "difference": "sub", "symmetric_difference": "xor"}
        if m in ops:
            call = f"pyset_{ops[m]}({r}, {o})"
            return f"((void){call}, 0)" if m.endswith("update") else call
        return {"issubset": f"pyset_le({r}, {o})", "issuperset": f"pyset_le({o}, {r})",
                "isdisjoint": f"pyset_disjoint({r}, {o})"}[m]
    if rt is not None and is_class(rt) and rt.name in em.tc.classes:
        mname = em.method_name(rt.name, e.method)
        if _is_self(e.recv):
            recv = em.ex(e.recv)
        else:
            recv = f"py_nn({em.ex(e.recv)}, \"{e.method}\")"
        return _ordered_call(em, e, mname, [recv])
    return None


def _ordered_call(em, e, fname: str, lead) -> str:
    """fname(lead..., args...) with arguments evaluated in CPython's order (receiver, then source order)."""
    order = getattr(e, "arg_order", None)
    needs_hoist = order is not None or (lead and lead[0].startswith("py_nn(") and
                                        any(not _pure_name(a) and _has_call(a) for a in e.args))
    if not needs_hoist:
        return f"{fname}(" + ", ".join(list(lead) + [em.ex(a) for a in e.args]) + ")"
    parts, names = [], {}
    lead_vars = []
    for x in lead:
        v = em.fresh()
        parts.append(f"auto {v} = {x};")
        lead_vars.append(v)
    for j in (order or range(len(e.args))):
        v = em.fresh()
        parts.append(f"auto {v} = {em.ex(e.args[j])};")
        names[j] = v
    args = lead_vars + [names[j] if j in names else em.ex(a) for j, a in enumerate(e.args)]
    return "[&]() { " + " ".join(parts) + f" return {fname}(" + ", ".join(args) + "); }()"


def _has_call(n) -> bool:
    from .types_ext import walk
    return any(isinstance(x, (A.Call, A.MethodCall)) for x in walk(n))


def _call(em, e) -> Optional[str]:
    n = e.func
    if n in em.tc.classes:
        return _ordered_call(em, e, f"{n}_new", [])
    if n in em.tc.funcs:
        return _ordered_call(em, e, f"f_{n}", [])
    a0 = e.args[0] if e.args else None
    if n == "set":
        el = _SCALAR_C[e.ty.elem.name]
        if a0 is None:
            return f"pyset_new<{el}>()"
        if a0.ty == STR:
            return f"pyset_of_chars<{el}>({em.ex(a0)})"
        if a0.ty.name == "dict":
            return f"pyset_of_keys<{el}>({em.ex(a0)})"
        return f"pyset_of<{el}>({em.ex(a0)})"
    if a0 is None or a0.ty is None:
        return None
    if n == "sorted" and a0.ty.name == "set":
        rev = em.kwarg(e, "reverse")
        return f"pyset_sorted({em.ex(a0)}, {em.ex(rev) if rev is not None else 'false'})"
    if n == "str" and a0.ty.name == "optional":
        from .emit_c import Emitter
        inner = A.Call(e.line, e.col, func="str", args=[_typed_var("_o", a0.ty)])
        inner.ty = STR
        return f"[&](const auto &_o) {{ return _o ? {Emitter.call(em, inner)} : pystr_lit(\"None\"); }}({em.ex(a0)})"
    return None


def _typed_var(name: str, opt: Ty):
    v = A.Name(0, 0, id="__raw__")
    v.raw = f"(*{name})" if opt_scalar(opt) else name
    v.ty = opt.elem
    return v


def truthy(expr: str, t) -> Optional[str]:
    if t is None:
        return None
    if t.name == "optional":
        from .emit_c import Emitter
        inner = Emitter.truthy("(*_o)" if opt_scalar(t) else "_o", t.elem)
        return f"[&](const auto &_o) {{ return _o && {inner}; }}({expr})"
    if is_class(t):
        return f"(({expr}) != nullptr)"           # None is falsy; objects have no __bool__/__len__ in PySub
    return None


def print_call(em, a, value: Optional[str]) -> Optional[str]:
    t = a.ty
    if t is None:
        return None
    e = value if value is not None else em.ex(a)
    if t.name == "optional":
        inner = em.print_call(_typed_var("_o", t), "(*_o)" if opt_scalar(t) else "_o")
        return f"[&](const auto &_o) {{ if (!_o) py_print_none(); else {inner}; }}({e})"
    if t.name == "dict" and t.elem.name not in ("int", "float", "bool", "str"):
        return f"py_print_repr({e})"
    return None
