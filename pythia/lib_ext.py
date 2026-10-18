"""
PYTHIA :: PySub 1.3 in library mode: Optional/set/dict-of-anything marshalling, default values and
keyword arguments for Python callers, module-level constants used by exposed functions.
"""
from typing import Dict, List, Optional

from . import ast_nodes as A
from .emit_c import LIST_RT, c_string, dict_rt_name
from .types_ext import is_class, is_mutable_default, opt_scalar, walk

_SCALAR = {"int": "pyb::I64", "float": "pyb::F64", "bool": "pyb::Bool", "str": "pyb::Str"}
_SCALAR_C = {"int": "int64_t", "float": "double", "bool": "bool", "str": "pyrt::PyStr *"}
MUTATORS = {"append", "pop", "insert", "extend", "clear", "reverse", "remove", "sort", "add", "discard",
            "update", "intersection_update", "difference_update", "symmetric_difference_update"}


def trait(t, base_trait) -> Optional[str]:
    if t.name == "optional":
        inner = base_trait(t.elem)
        if inner is None:
            return None
        return f"pyb::Opt<{inner}>" if opt_scalar(t) else f"pyb::OptP<{inner}>"
    if t.name == "set" and t.elem is not None:
        return f"pyb::Set<{_SCALAR[t.elem.name]}, {_SCALAR_C[t.elem.name]}>"
    if t.name == "dict" and t.key is not None and t.elem is not None and t.elem.name not in _SCALAR:
        v = base_trait(t.elem)
        if v is None or t.key.name not in _SCALAR:
            return None
        return f"pyb::Dict<{_SCALAR[t.key.name]}, {v}, {dict_rt_name(t)}>"
    return None


def py_default(d) -> str:
    """C++ expression for the Python object of a constant default (pybind py::arg(...) = ...)."""
    neg = isinstance(d, A.UnaryOp) and d.op == "-"
    x = d.operand if isinstance(d, A.UnaryOp) else d
    if isinstance(d, A.Coerce):
        return py_default(d.value)
    if isinstance(x, A.BoolLit):
        return f"py::bool_({'true' if x.value else 'false'})"
    if isinstance(x, A.IntLit):
        return f"py::int_(INT64_C({'-' if neg else ''}{x.value}))"
    if isinstance(x, A.FloatLit):
        return f"py::float_({'-' if neg else ''}{float(x.value)!r})"
    if isinstance(x, A.StrLit):
        return f"py::str({c_string(x.value)})"
    return "py::none()"


def arg_spec(p) -> str:
    s = f'py::arg("{p.name}")'
    return s + (f" = {py_default(p.default)}" if p.default is not None else "")


def is_container(t) -> bool:
    return t is not None and (t.name in ("list", "dict", "set") or
                              (t.name == "optional" and t.elem.name in ("list", "dict", "set")))


def _root(e) -> Optional[A.Name]:
    while isinstance(e, (A.Subscript, A.Attribute, A.Coerce)):
        e = e.value
    return e if isinstance(e, A.Name) else None


def _heap(t) -> bool:
    if t is None:
        return False
    if t.name in ("list", "set"):
        return t.elem is None or t.elem.name not in ("int", "float", "bool")
    if t.name == "dict":
        return t.key.name == "str" or t.elem.name not in ("int", "float", "bool")
    return t.name not in ("int", "float", "bool")


def check_globals(mod, tc, add_diag) -> List[dict]:
    """Module-level variables the compiled functions read become library globals built at import.
    Returns extra fidelity notes; reports what cannot be reproduced through add_diag(line, col, msg)."""
    hoisted = set(getattr(tc, "_fn_globals", set()))
    tc._gcheck = set()                       # the module has run completely before Python calls in
    if not hoisted:
        return []
    top = [s for s in mod.main if isinstance(s, A.Assign) and isinstance(s.target, A.Name)]
    grew = True
    while grew:                                # values may mention other module-level names
        grew = False
        for s in top:
            if s.target.id in hoisted:
                for n in walk(s.value):
                    if isinstance(n, A.Name) and n.id in mod.globals_ and n.id not in hoisted:
                        hoisted.add(n.id)
                        grew = True
    tc._fn_globals = hoisted
    top_ids = {id(s) for s in top}
    for n in walk(mod.main):
        tgt = getattr(n, "target", None) if isinstance(n, (A.Assign, A.AugAssign)) else None
        name = tgt.id if isinstance(tgt, A.Name) else n.var if isinstance(n, (A.ForRange, A.ForEach)) else None
        if name in hoisted and id(n) not in top_ids:
            add_diag(n.line, n.col, f"module-level variable {name!r} is used by compiled functions, so library "
                                    f"mode needs it assigned by plain top-level assignments only")
    for s in top:
        if s.target.id not in hoisted:
            continue
        for n in walk(s.value):
            if (isinstance(n, A.Call) and (n.func in tc.funcs or n.func in tc.classes or n.func in ("print", "input"))) \
                    or (isinstance(n, A.MethodCall) and is_class(n.recv.ty)):
                add_diag(s.line, s.col, f"module-level variable {s.target.id!r} is used by compiled functions; "
                                        f"library mode builds it at import, so its value may not call functions "
                                        f"with side effects")
                break
    notes = []
    fns = list(mod.funcs) + [m for c in mod.classes for m in c.methods]
    for f in fns:
        for g in getattr(f, "global_names", set()) & hoisted:
            add_diag(f.line, f.col, f"{f.name}() rebinds module-level variable {g!r} (`global`): not supported in "
                                    f"library mode (the Python module keeps its own variable)")
        for n in walk(f.body):
            r = None
            if isinstance(n, (A.Assign, A.AugAssign)) and isinstance(n.target, (A.Subscript, A.Attribute)):
                r = _root(n.target)
            elif isinstance(n, A.MethodCall) and n.method in MUTATORS:
                r = _root(n.recv)
            if r is None or not getattr(r, "global_ref", False) or r.id not in hoisted:
                continue
            t = mod.globals_.get(r.id)
            if _heap(t):
                add_diag(n.line, n.col, f"{f.name}() modifies module-level {t} {r.id!r}: library mode cannot keep "
                                        f"str/list/object values stored into it alive between calls")
            else:
                notes.append({"line": n.line, "col": n.col, "cls": "L5 module-level state in the library",
                              "detail": f"{f.name}() modifies module-level {r.id!r}; the compiled library keeps its "
                                        f"own copy, built when the module is imported.",
                              "mitigation": "the state persists across calls exactly as in Python, but Python code "
                                            "reading the module's variable does not see the compiled updates.",
                              "severity": "guarded"})
    return notes


def check_exposed(f, add_diag) -> None:
    for p in f.params:
        if p.default is not None and is_mutable_default(p.default):
            add_diag(f.line, f.col, f"{f.name}(): mutable default for parameter {p.name!r} cannot be shared with "
                                    f"Python callers in library mode; default to None instead")
