"""
PYTHIA :: Phase 3 -- Semantic Analysis (symbol table + static type checking)
Owner: Member 2 (Rujuta Mangesh Kulkarni)

A bidirectional type checker: expressions are *synthesised* bottom-up, and
*checked* against an expected type where one is known (annotations, return
statements, argument positions).  Local variables need no annotation --
their type is inferred from the first binding and then fixed, which is the
key property that makes translation to a statically typed target sound.

Implicit widening int -> float is the ONLY subtyping edge.  bool is a
subtype of int (as in Python) for arithmetic, but not for print formatting.
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional
from . import ast_nodes as A
from .parser import Diagnostic


# ------------------------------------------------------------------- types
@dataclass(frozen=True)
class Ty:
    name: str                       # int float bool str list dict None
    elem: Optional["Ty"] = None      # list element type, or dict value type
    key: Optional["Ty"] = None       # dict key type only
    elts: Optional[tuple] = None     # tuple element types only (see tuples.py)

    def __str__(self) -> str:
        if self.name == "tuple":
            return "tuple[" + (", ".join(map(str, self.elts)) or "()") + "]"
        if self.name == "list":
            return f"list[{self.elem}]"
        if self.name == "dict":
            return f"dict[{self.key}, {self.elem}]"
        return _x.ty_str(self) or self.name


INT, FLOAT, BOOL, STR, NONE = Ty("int"), Ty("float"), Ty("bool"), Ty("str"), Ty("None")
ERR = Ty("<error>")


def list_of(t: Ty) -> Ty:
    return Ty("list", t)


def dict_of(k: Ty, v: Ty) -> Ty:
    return Ty("dict", v, k)


NUMERIC = {"int", "float", "bool"}


def widens_to(src: Ty, dst: Ty) -> bool:
    """Implicit-conversion lattice.  bool -> int -> float."""
    if src == dst or src is ERR or dst is ERR:
        return True
    if _cls.sub_widens(src, dst):              # Sub -> Base upcast (classes_ext)
        return True
    ext = _x.widens(src, dst)                 # Optional / nullable objects (types_ext)
    if ext is not None:
        return ext
    order = {"bool": 0, "int": 1, "float": 2}
    if src.name in order and dst.name in order:
        return order[src.name] <= order[dst.name]
    return False


def join(a: Ty, b: Ty) -> Ty:
    if a == b:
        return a
    if a.name in NUMERIC and b.name in NUMERIC:
        return FLOAT if FLOAT in (a, b) else INT
    if a.name == b.name and a.name in ("list", "dict") and (a.elem is None or b.elem is None):
        return b if a.elem is None else a                     # [] next to [1, 2], {} next to {"k": 1}
    return _cls.join(a, b) or ERR                             # nearest common base class (classes_ext)


# ------------------------------------------------------------ symbol table
class Scope:
    def __init__(self, parent: Optional["Scope"] = None, kind: str = "block"):
        self.parent = parent
        self.kind = kind                     # 'global' | 'function' | 'block'
        self.names: Dict[str, Ty] = {}

    def declare(self, name: str, ty: Ty) -> None:
        self.names[name] = ty

    def lookup(self, name: str) -> Optional[Ty]:
        s: Optional[Scope] = self
        while s:
            if name in s.names:
                return s.names[name]
            s = s.parent
        return None

    def lookup_local(self, name: str) -> Optional[Ty]:
        return self.names.get(name)


@dataclass
class FuncSig:
    name: str
    params: List[Ty]
    ret: Ty
    node: A.FuncDef
    owner: Optional[str] = None      # class name if this is a method


@dataclass
class ClassInfo:
    name: str
    fields: List[Ty] = None          # type: ignore
    field_names: List[str] = None    # type: ignore
    field_index: Dict[str, int] = None   # type: ignore
    methods: Dict[str, FuncSig] = None   # type: ignore
    node: Optional[A.ClassDef] = None
    init: Optional[FuncSig] = None   # __init__, if the class defines one


EXC_NAMES = {"IndexError", "ZeroDivisionError", "OverflowError",
            "ValueError", "KeyError", "PythiaSemanticError", "EOFError", "TypeError", "AssertionError"}
EXC_NAMES |= {"AttributeError", "NameError"}
# builtin hierarchy members a program may raise or catch (the base classes only match by name, see py_exc_isa)
EXC_NAMES |= {"Exception", "BaseException", "LookupError", "ArithmeticError", "RuntimeError", "RecursionError",
              "NotImplementedError"}
EXC_MARKERS = ("__else__", "__finally__")        # try/else and try/finally bodies, stored as marker handlers

PRIM = ("int", "float", "bool", "str")
_FMT_RE = re.compile(r"^(?:(?P<fill>.)?(?P<align>[<>^=]))?(?P<sign>[+\- ])?(?P<zero>0)?(?P<width>\d+)?"
                     r"(?P<group>[,_])?(?:\.(?P<prec>\d+))?(?P<type>[a-zA-Z%])?$", re.S)


def fmt_spec_problem(spec: str, t: "Ty") -> Optional[str]:
    """None if format(value_of_type_t, spec) is in the PySub subset, else why not."""
    m = _FMT_RE.match(spec)
    if not m:
        return f"format spec {spec!r} is outside the PySub subset"
    ty = m.group("type")
    if m.group("zero") and m.group("group"):
        return "zero-padding together with digit grouping is outside the PySub subset"
    if t.name == "str":
        if ty not in (None, "s"):
            return f"format code {ty!r} cannot format a str"
        if m.group("sign") or m.group("group") or m.group("align") == "=" or m.group("zero"):
            return "sign, grouping, zero-padding and '=' alignment are not allowed when formatting a str"
        return None
    if t.name in ("int", "bool"):
        if ty not in (None, "d", "f", "F", "e", "E", "g", "G", "%", "x", "X", "o", "b"):
            return f"format code {ty!r} is not supported for int in PySub"
        if ty in (None, "d", "x", "X", "o", "b") and m.group("prec") is not None:
            return "precision is not allowed in an integer format spec"
        return None
    if t.name == "float":
        if ty is None and m.group("prec") is not None:
            return "a float precision needs a type in PySub, e.g. '.2f' or '.3e'"
        if ty not in (None, "f", "F", "e", "E", "g", "G", "%"):
            return f"format code {ty!r} cannot format a float"
        return None
    return f"cannot format a value of type {t}"

BUILTIN_SIGS = {
    "len":   ("any_seq", INT),
    "abs":   ("numeric", None),      # returns same numeric type
    "int":   ("cast", INT),
    "float": ("cast", FLOAT),
    "str":   ("cast", STR),
    "bool":  ("cast", BOOL),
    "min":   ("numeric2", None),
    "max":   ("numeric2", None),
}


class TypeChecker:
    def __init__(self, mod: A.Module, filename: str = "<input>"):
        self.mod = mod
        self.filename = filename
        self.errors: List[Diagnostic] = []
        self.funcs: Dict[str, FuncSig] = {}
        self.classes: Dict[str, ClassInfo] = {}
        self.global_scope = Scope(None, "global")
        self.scope = self.global_scope
        self.cur_fn: Optional[FuncSig] = None
        self.cur_class: Optional[str] = None
        self.loop_depth = 0
        self.try_depth = 0
        self.returns_seen = False

    # ---- diagnostics -------------------------------------------------------
    def err(self, node: A.Node, msg: str) -> Ty:
        self.errors.append(Diagnostic(msg, node.line, node.col, "TypeError"))
        return ERR

    def resolve_type(self, te: Optional[A.TypeExpr]) -> Ty:
        if te is None:
            return NONE
        if getattr(te, "pre", None) is not None:  # resolved ahead of pass 1 (classes_ext field inference)
            return te.pre
        ext = _x.resolve_type(self, te)       # typing names, Optional, unions, set, dict values (types_ext)
        if ext is not None:
            return ext
        if te.name in ("int", "float", "bool", "str"):
            return Ty(te.name)
        if te.name == "None":
            return NONE
        if te.name == "list":
            if te.param is None:
                self.errors.append(Diagnostic(
                    "bare 'list' is not allowed; write list[int], list[float], "
                    "list[str], list[bool] or list[list[...]]",
                    te.line, te.col, "TypeError"))
                return ERR
            inner = self.resolve_type(te.param)
            if inner.name == "list" and inner.elem is not None and inner.elem.name == "list":
                self.errors.append(Diagnostic(
                    "list nesting deeper than two levels is outside the PySub "
                    "subset", te.line, te.col, "TypeError"))
                return ERR
            return list_of(inner)
        if te.name == "dict":
            if te.param is None or te.param2 is None:
                self.errors.append(Diagnostic(
                    "bare 'dict' is not allowed; write dict[K, V]",
                    te.line, te.col, "TypeError"))
                return ERR
            k = self.resolve_type(te.param)
            v = self.resolve_type(te.param2)
            if k.name == "tuple" or v.name == "tuple":
                return _tup.resolve_dict(self, te, k, v)
            if k.name not in ("int", "str"):
                self.errors.append(Diagnostic(
                    f"dict key type must be int or str; found {k}",
                    te.line, te.col, "TypeError"))
                return ERR
            if v.name not in ("int", "float", "bool", "str"):
                self.errors.append(Diagnostic(
                    f"dict value type must be int, float, bool or str; found {v}",
                    te.line, te.col, "TypeError"))
                return ERR
            return dict_of(k, v)
        if te.name == "tuple":
            return _tup.resolve(self, te)
        if te.name in self.classes:
            return Ty(te.name)
        self.errors.append(Diagnostic(f"unknown type {te.name!r}",
                                      te.line, te.col, "TypeError"))
        return ERR

    # ---- driver ------------------------------------------------------------
    def run(self) -> List[Diagnostic]:
        _x.check_imports(self)
        self._narrow, self._fn_globals = {}, set()
        # pass 0: register class names (stub) so field/method/param types can
        # forward-reference any class, including the class's own methods.
        for c in self.mod.classes:
            if c.name in self.classes or c.name in ("int", "float", "bool", "str", "list", "dict", "None"):
                self.err(c, f"class {c.name!r} is already defined")
                continue
            self.classes[c.name] = ClassInfo(c.name, [], [], {}, {}, c)
        _cls.prepare(self)                    # bases, decorators, class attributes, inferred fields (classes_ext)

        # pass 1: resolve field types and method signatures
        for c in self.mod.classes:
            info = self.classes.get(c.name)
            if info is None:
                continue
            seen = set()
            _cls.inherit(self, c, info)           # base-class fields first
            for fld in c.fields:
                if fld.name in seen:
                    self.err(fld, f"duplicate field {fld.name!r} in class {c.name!r}")
                    continue
                seen.add(fld.name)
                t = self.resolve_type(fld.ann)
                info.field_index[fld.name] = len(info.fields)
                info.fields.append(t)
                info.field_names.append(fld.name)
            for m in c.methods:
                if not m.params or m.params[0].name != "self":
                    self.err(m, f"method {m.name!r} must take 'self' as its "
                                f"first parameter")
                    continue
                sig = FuncSig(f"{c.name}.{m.name}",
                             [self.resolve_type(p.ann) for p in m.params[1:]],
                             self.resolve_type(m.ret), m, owner=c.name)
                info.methods[m.name] = sig
                if m.name == "__init__":
                    if sig.ret != NONE:
                        self.err(m, "__init__ must not declare a return type "
                                    "other than None, matching Python")
                    info.init = sig
            if info.fields and info.init is None and _cls.needs_init(self, c, info):
                self.err(c, f"class {c.name!r} declares typed fields but no "
                            f"__init__; PySub requires an explicit constructor "
                            f"so field initialisation can never be skipped")

        _cls.after_pass1(self)                # inherited methods, overrides, class ids, dunder signatures

        # pass 2: collect function signatures so functions may be mutually recursive
        for f in self.mod.funcs:
            if f.name in self.funcs or f.name in self.classes:
                self.err(f, f"function {f.name!r} is already defined")
            self.funcs[f.name] = FuncSig(
                f.name,
                [self.resolve_type(p.ann) for p in f.params],
                self.resolve_type(f.ret),
                f)

        # pass 3 (was 5): the module-level main block first, so function bodies can see module-level names
        self.scope = self.global_scope
        self.cur_fn = None
        for s in self.mod.main:
            self.check_stmt(s)
        self.mod.globals_ = dict(self.global_scope.names)

        # pass 4: check class method bodies
        for c in self.mod.classes:
            info = self.classes.get(c.name)
            if info is None:
                continue
            for m in c.methods:
                sig = info.methods.get(m.name)
                if sig is not None:
                    self.check_func(sig, self_ty=Ty(c.name))

        # pass 5: check free-function bodies
        for f in self.mod.funcs:
            self.check_func(self.funcs[f.name])
        self.scope = self.global_scope
        _x.finish(self)
        return self.errors

    def check_func(self, sig: FuncSig, self_ty: Optional[Ty] = None) -> None:
        f = sig.node
        self.cur_fn = sig
        self.cur_class = sig.owner
        fn_scope = Scope(None, "function")   # PySub functions are closed:
        # module-level state is deliberately invisible inside a function body.
        self.scope = fn_scope
        params = f.params[1:] if self_ty is not None else f.params
        if self_ty is not None:
            fn_scope.declare("self", self_ty)
            f.params[0].ty = self_ty
        for p, t in zip(params, sig.params):
            if p.name in fn_scope.names:
                self.err(p, f"duplicate parameter {p.name!r}")
            fn_scope.declare(p.name, t)
            p.ty = t
        _x.begin_func(self, sig, fn_scope)    # module-level names, `global`, defaults
        self.returns_seen = False
        for s in f.body:
            self.check_stmt(s)
        if sig.ret != NONE and not self.always_returns(f.body) and not _x.may_fall_off(sig.ret):
            self.err(f, f"function {sig.name!r} declared -> {sig.ret} but control "
                        f"can reach the end without returning a value")
        f.locals_ = {k: v for k, v in fn_scope.names.items()
                     if k not in {p.name for p in f.params}}
        self.scope = self.global_scope
        self.cur_fn = None
        self.cur_class = None

    @staticmethod
    def always_returns(body: List[A.Node]) -> bool:
        for s in body:
            if isinstance(s, A.Return):
                return True
            if isinstance(s, A.If) and s.orelse:
                if TypeChecker.always_returns(s.body) and \
                   TypeChecker.always_returns(s.orelse):
                    return True
            if isinstance(s, A.While) and isinstance(s.test, A.BoolLit) and s.test.value:
                return True
            if isinstance(s, A.TryExcept):
                els = [h.body for h in s.handlers if h.exc_name == "__else__"]
                if (TypeChecker.always_returns(s.body) or any(TypeChecker.always_returns(b) for b in els)) and \
                   all(TypeChecker.always_returns(h.body) for h in s.handlers
                       if h.exc_name not in ("__else__", "__finally__")):
                    return True
            if isinstance(s, A.Raise):
                return True
        return False

    # ---- statements --------------------------------------------------------
    def check_stmt(self, s: A.Node) -> None:
        if _cls.check_stmt(self, s):          # class attributes, properties, __setitem__, __iadd__ (classes_ext)
            return
        if isinstance(s, A.ForEach) and _comp().is_special_foreach(self, s):   # enumerate/zip/reversed loops
            _comp().check_foreach(self, s)
            return
        if _x.check_stmt(self, s):            # narrowing-aware if/while/assign, global (types_ext)
            return
        if isinstance(s, A.Assign):
            self.check_assign(s)
        elif isinstance(s, A.AugAssign):
            self.check_augassign(s)
        elif isinstance(s, A.ExprStmt):
            self.synth(s.value)
        elif isinstance(s, A.Return):
            self.check_return(s)
        elif isinstance(s, A.If):
            self.check_truthy(s.test)
            self.block(s.body)
            self.block(s.orelse)
        elif isinstance(s, A.While):
            self.check_truthy(s.test)
            self.loop_depth += 1
            self.block(s.body)
            self.loop_depth -= 1
        elif isinstance(s, A.ForRange):
            for e in (s.start, s.stop, s.step):
                if e is not None:
                    t = self.synth(e)
                    if t is not ERR and not widens_to(t, INT):
                        self.err(e, f"range() argument must be int, found {t}")
            self.bind(s, s.var, INT)
            self.loop_depth += 1
            self.block(s.body)
            self.loop_depth -= 1
        elif isinstance(s, A.ForEach) and _comp().is_special_foreach(self, s):
            _comp().check_foreach(self, s)
        elif isinstance(s, A.ForEach):
            _bx.mark_view_ok(self, s.iter)
            _tup.mark_items(s.iter)
            t = self.synth(s.iter)
            if t.name == "list":
                self.bind(s, s.var, t.elem)
            elif t.name == "tuple" and _tup.homogeneous(t) is not None:
                self.bind(s, s.var, _tup.homogeneous(t))
            elif t == STR:
                self.bind(s, s.var, STR)
            elif t.name == "dict":
                self.bind(s, s.var, t.key)
            elif t is not ERR:
                self.err(s.iter, f"cannot iterate over a value of type {t}")
                self.bind(s, s.var, ERR)
            self.loop_depth += 1
            self.block(s.body)
            self.loop_depth -= 1
        elif isinstance(s, (A.Break, A.Continue)):
            if self.loop_depth == 0:
                kind = "break" if isinstance(s, A.Break) else "continue"
                self.err(s, f"{kind!r} outside loop")
        elif isinstance(s, A.Pass):
            pass
        elif isinstance(s, A.TryExcept):
            self.try_depth += 1
            self.block(s.body)
            self.try_depth -= 1
            seen_bare = False
            seen_names = set()
            for h in s.handlers:
                if h.exc_name in EXC_MARKERS:
                    if h.exc_name == "__finally__":
                        self.check_finally_body(h.body)
                    self.block(h.body)
                    continue
                if h.exc_name is not None:
                    if h.exc_name not in EXC_NAMES:
                        self.err(h, f"unknown exception type {h.exc_name!r}; "
                                    f"PySub raises {sorted(EXC_NAMES)}")
                    if h.exc_name in seen_names:
                        self.err(h, f"duplicate except clause for {h.exc_name!r}")
                    seen_names.add(h.exc_name)
                    if seen_bare:
                        self.err(h, "except clause after a bare 'except' is unreachable")
                else:
                    if seen_bare:
                        self.err(h, "only one bare 'except' is allowed, and it must be last")
                    seen_bare = True
                if h.bind:
                    self.bind(h, h.bind, STR)   # exception object surfaces as its message
                    self.bind(h, "__en_" + h.bind, STR)   # ... and its class name, for type(e).__name__
                self.in_handler = getattr(self, "in_handler", 0) + 1
                self.block(h.body)
                self.in_handler -= 1
        elif isinstance(s, A.Raise) and s.exc_name == "":
            if getattr(self, "in_handler", 0) <= 0:
                self.err(s, "a bare `raise` re-raises the exception being handled: use it inside an except clause")
        elif isinstance(s, A.Raise):
            if s.exc_name not in EXC_NAMES:
                self.err(s, f"unknown exception type {s.exc_name!r}; "
                            f"PySub raises {sorted(EXC_NAMES)}")
            if s.message is not None:
                mt = self.synth(s.message)
                if mt is not ERR and mt != STR:
                    self.err(s.message, f"raise message must be str, found {mt}")
        else:
            self.err(s, f"unsupported statement {type(s).__name__}")

    def check_finally_body(self, body: List[A.Node]) -> None:
        """The finally block runs in a C++ destructor: it must not leave the try statement by return/break/continue/raise."""
        stack = list(body)
        while stack:
            n = stack.pop()
            if isinstance(n, (A.Return, A.Break, A.Continue, A.Raise)):
                self.err(n, f"`{type(n).__name__.lower()}` inside a finally block is outside the PySub subset "
                            f"(it would replace the pending exit of the try statement)")
            for f in ("body", "orelse"):
                stack.extend(getattr(n, f, None) or [])
            for h in getattr(n, "handlers", None) or []:
                stack.extend(h.body)

    def block(self, body: List[A.Node]) -> None:
        for s in body:
            self.check_stmt(s)

    def bind(self, node: A.Node, name: str, ty: Ty) -> None:
        prev = self.scope.lookup(name)
        if prev is None:
            self.scope.declare(name, ty)
        elif prev != ty and not widens_to(ty, prev):
            self.err(node,
                     f"variable {name!r} was inferred as {prev}; cannot rebind to {ty}. "
                     f"PySub requires every variable to keep one static type.")

    def check_assign(self, s: A.Assign) -> None:
        if isinstance(s.target, A.Subscript):
            base = self.synth(s.target.value)
            if base.name == "dict":
                k = self.check_expr(s.target.index, base.key)
                if not widens_to(k, base.key):
                    self.err(s.target.index, f"dict key must be {base.key}, found {k}")
                v = self.check_expr(s.value, base.elem)
                if not widens_to(v, base.elem):
                    self.err(s.value, f"cannot store {v} into {base}")
                s.ty = base.elem
                return
            it = self.synth(s.target.index)
            if base.name == "list":
                if not widens_to(it, INT):
                    self.err(s.target.index, f"list index must be int, found {it}")
                v = self.synth(s.value)
                if not widens_to(v, base.elem):
                    self.err(s.value, f"cannot store {v} into {base}")
                s.ty = base.elem
            elif base == STR:
                self.err(s.target, "'str' object does not support item assignment")
            elif base is not ERR:
                self.err(s.target, f"{base} does not support item assignment")
            return

        if isinstance(s.target, A.Attribute):
            recv = self.synth(s.target.value)
            if recv.name in self.classes:
                info = self.classes[recv.name]
                idx = info.field_index.get(s.target.attr)
                if idx is None:
                    self.err(s.target, f"class {recv.name!r} has no field "
                                       f"{s.target.attr!r}")
                    return
                ft = info.fields[idx]
                v = self.check_expr(s.value, ft)
                if not widens_to(v, ft):
                    self.err(s.value, f"field {s.target.attr!r} of {recv.name!r} "
                                      f"expects {ft}, found {v}")
                s.ty = ft
                s.target.ty = ft
            elif recv is not ERR:
                self.err(s.target, f"{recv} has no assignable fields")
            return

        name = s.target.id
        if s.ann is not None:
            declared = self.resolve_type(s.ann)
            actual = self.check_expr(s.value, declared)
            if not widens_to(actual, declared):
                self.err(s.value,
                         f"{name!r} is annotated {declared} but the initialiser has "
                         f"type {actual}")
            prev = self.scope.lookup_local(name)
            if prev is not None and prev != declared:
                self.err(s, f"{name!r} already has static type {prev} in this "
                            f"scope and cannot be re-annotated as {declared}")
            self.scope.declare(name, declared)
            s.declares = True
            s.ty = declared
            s.target.ty = declared
            return

        prev = self.scope.lookup(name)
        # an existing variable has a declared type: literals (`xs = []`, `t = ()`) are checked against it
        actual = self.check_expr(s.value, prev) if prev is not None and prev is not ERR else self.synth(s.value)
        if prev is None:
            if actual.name == "list" and actual.elem is None:
                self.err(s.value,
                         f"cannot infer element type of empty list for {name!r}; "
                         f"add an annotation, e.g. {name}: list[int] = []")
                actual = ERR
            if actual.name == "dict" and actual.key is None:
                self.err(s.value,
                         f"cannot infer key/value type of empty dict for {name!r}; "
                         f"add an annotation, e.g. {name}: dict[str, int] = {{}}")
                actual = ERR
            self.scope.declare(name, actual)
            s.declares = True
            s.ty = actual
        else:
            if not widens_to(actual, prev):
                self.err(s.value,
                         f"{name!r} has static type {prev}; cannot assign {actual}")
            s.ty = prev
        s.target.ty = s.ty

    def check_augassign(self, s: A.AugAssign) -> None:
        t = self.synth(s.target)
        v = self.synth(s.value)
        res = self.binop_result(s, s.op, t, v)
        if not widens_to(res, t):
            self.err(s, f"{s.op}= produces {res} but the target has type {t}")
        s.ty = t

    def check_return(self, s: A.Return) -> None:
        if self.cur_fn is None:
            self.err(s, "'return' outside function")
            return
        _x.check_return(self, s)
        want = self.cur_fn.ret
        if s.value is None:
            if want != NONE:
                self.err(s, f"function declared -> {want} must return a value")
            return
        got = self.check_expr(s.value, want)
        if want == NONE:
            self.err(s, "function declared -> None must not return a value")
        elif not widens_to(got, want):
            self.err(s.value, f"returning {got} from a function declared -> {want}")
        s.ty = want

    def mark_cond(self, e: A.Node) -> None:
        """`a and b` / `a or b` / `not a` used only as a condition: their operands need no common type."""
        if isinstance(e, A.BoolOp):
            e.cond_only = True
            for v in e.values:
                self.mark_cond(v)
        elif isinstance(e, A.UnaryOp) and e.op == "not":
            self.mark_cond(e.operand)

    def check_truthy(self, e: A.Node) -> None:
        self.mark_cond(e)
        t = self.synth(e)
        if t.name == "None" or t is ERR:
            if t.name == "None":
                self.err(e, "condition has type None and is always false")

    # ---- expressions -------------------------------------------------------
    def check_expr(self, e: A.Node, expected: Ty) -> Ty:
        """Checking mode: pushes `expected` inward where it helps inference."""
        if isinstance(e, A.TupleLit) and e.ty is None:
            return _tup.check_lit(self, e, expected)
        if expected is not None and expected.name == "optional" and expected.elem is not None \
                and expected.elem.name in ("list", "dict") \
                and isinstance(e, (A.ListLit, A.DictLit)) and not getattr(e, "elts", getattr(e, "keys", None)):
            return self.check_expr(e, expected.elem)      # `seen = []` into an Optional[list[T]] variable
        if isinstance(e, A.ListLit) and expected.name == "list":
            if not e.elts:
                e.ty = expected
                return expected
            elem_ty = expected.elem
            if elem_ty is not None:
                ts = [self.check_expr(x, elem_ty) for x in e.elts]
                acc = ts[0]
                for it in ts[1:]:
                    acc = join(acc, it)
                if acc is not ERR and widens_to(acc, elem_ty):
                    e.ty = expected
                    return expected
        if isinstance(e, A.DictLit) and expected.name == "dict":
            if not e.keys:
                e.ty = expected
                return expected
            val_ty = expected.elem
            key_ty = expected.key
            if val_ty is not None and key_ty is not None:
                kts = [self.check_expr(k, key_ty) for k in e.keys]
                vts = [self.check_expr(v, val_ty) for v in e.values]
                kacc = kts[0]
                for kt in kts[1:]:
                    kacc = join(kacc, kt)
                vacc = vts[0]
                for vt in vts[1:]:
                    vacc = join(vacc, vt)
                if kacc is not ERR and vacc is not ERR and widens_to(kacc, key_ty) and widens_to(vacc, val_ty):
                    e.ty = expected
                    return expected
        t = self.synth(e)
        if t.name == "list" and t.elem is None and expected.name == "list":
            e.ty = expected
            return expected
        if t.name == "dict" and t.key is None and expected.name == "dict":
            e.ty = expected
            _x.check_factory(self, e)         # defaultdict(int) / Counter() against the declared value type
            return expected
        if t.name == "set" and t.elem is None and expected.name == "set":
            e.ty = expected
            return expected
        return t

    def synth(self, e: Optional[A.Node]) -> Ty:
        if e is None:
            return NONE
        if e.ty is not None and not isinstance(e, (A.Name,)):
            return e.ty
        t = self._synth(e)
        e.ty = t
        return t

    def _synth(self, e: A.Node) -> Ty:
        ext = _cls.synth(self, e)             # user-class constructs: dunders, super(), class attributes ...
        if ext is not None:
            return ext
        ext = _x.synth(self, e)               # names (narrowing, globals), sets, None tests, isinstance ...
        if ext is not None:
            return ext
        if isinstance(e, A.IntLit):
            return INT
        if isinstance(e, A.FloatLit):
            return FLOAT
        if isinstance(e, A.StrLit):
            return STR
        if isinstance(e, A.BoolLit):
            return BOOL
        if isinstance(e, A.NoneLit):
            return NONE

        if isinstance(e, A.Name):
            t = self.scope.lookup(e.id)
            if t is None:
                if e.id in self.funcs:
                    return self.err(e, f"{e.id!r} is a function; PySub has no "
                                       f"first-class functions")
                return self.err(e, f"name {e.id!r} is not defined")
            return t

        if isinstance(e, A.TupleLit):
            return _tup.synth_lit(self, e)

        if isinstance(e, A.ListLit):
            if not e.elts:
                return Ty("list", None)          # unresolved; fixed in check mode
            ts = [self.synth(x) for x in e.elts]
            acc = ts[0]
            for t in ts[1:]:
                acc = join(acc, t)
            if acc is ERR:
                return self.err(e, "list literal mixes incompatible element types: "
                                   + ", ".join(str(t) for t in dict.fromkeys(map(str, ts))))
            if acc.name == "list" and acc.elem is not None and acc.elem.name == "list":
                return self.err(e, "list nesting deeper than two levels is outside "
                                   "the PySub subset")
            return list_of(acc)

        if isinstance(e, A.DictLit):
            if not e.keys:
                return Ty("dict", None, None)    # unresolved; fixed in check mode
            kts = [self.synth(k) for k in e.keys]
            vts = [self.synth(v) for v in e.values]
            kacc = kts[0]
            for t in kts[1:]:
                kacc = join(kacc, t)
            if kacc is ERR or (kacc.name not in ("int", "str", "bool") and not _tup.hashable_key(kacc)):
                return self.err(e, "dict literal keys must share one type "
                                   "(int, str or bool)")
            vacc = vts[0]
            for t in vts[1:]:
                vacc = join(vacc, t)
            if vacc is ERR:
                return self.err(e, "dict literal values mix incompatible types")
            return dict_of(kacc, vacc)

        if isinstance(e, A.Attribute):
            recv = self.synth(e.value)
            if recv.name in self.classes:
                info = self.classes[recv.name]
                idx = info.field_index.get(e.attr)
                if idx is None:
                    return self.err(e, f"class {recv.name!r} has no field {e.attr!r}")
                return info.fields[idx]
            if recv is ERR:
                return ERR
            return self.err(e, f"{recv} has no field {e.attr!r}")

        if isinstance(e, A.UnaryOp):
            t = self.synth(e.operand)
            if e.op == "not":
                return BOOL
            if e.op == "~":
                return _bx.invert_result(self, e, t)
            if t.name in NUMERIC:
                return INT if t == BOOL else t
            return self.err(e, f"unary {e.op!r} is not defined for {t}")

        if isinstance(e, A.BoolOp):
            for v in e.values:
                self.synth(v)
            if getattr(e, "cond_only", False):
                return BOOL                      # only its truthiness is used (if / while / not)
            ts = [v.ty for v in e.values]
            # Python returns an operand, not a bool. If both sides share a type
            # we keep it; otherwise we require bool to stay translatable.
            if ts[0] == ts[1]:
                return ts[0]
            j = join(ts[0], ts[1])
            if j is ERR:
                return self.err(e, f"operands of {e.op!r} have unrelated types "
                                   f"{ts[0]} and {ts[1]}; PySub requires a single "
                                   f"static result type")
            return j

        if isinstance(e, A.IfExp):
            self.synth(e.test)
            bt, ot = self.synth(e.body), self.synth(e.orelse)
            if bt is ERR or ot is ERR:
                return ERR
            if bt != ot:                 # no widening: `83 if odd else 83.0` must not print 83.0
                return self.err(e, f"the branches of `x if c else y` have types {bt} and {ot}; PySub requires a single "
                                   f"static result type (convert one branch explicitly, e.g. float(x))")
            return bt

        if isinstance(e, A.Compare):
            if e.op in ("in", "not in"):
                _bx.mark_view_ok(self, e.right)
            lt, rt = self.synth(e.left), self.synth(e.right)
            if rt.name == "tuple" or (lt.name == "tuple" and e.op not in ("in", "not in")):
                return _tup.compare(self, e, lt, rt)
            if e.op in ("in", "not in"):
                if lt is ERR or rt is ERR:
                    return BOOL
                if rt.name == "list":
                    if not (lt == rt.elem or widens_to(lt, rt.elem) or widens_to(rt.elem, lt)):
                        return self.err(e, f"{lt} cannot appear in a {rt}")
                    if rt.elem is not None and rt.elem.name == "list":
                        return self.err(e, "membership tests on nested lists are outside the PySub subset")
                    return BOOL
                if rt.name == "dict":
                    if not widens_to(lt, rt.key):
                        return self.err(e, f"{lt} is not a valid key for {rt}")
                    return BOOL
                if rt == STR:
                    if lt != STR:
                        return self.err(e, "substring test needs a str on both sides")
                    return BOOL
                return self.err(e, f"{e.op!r} needs a list, dict or str on the right, "
                                   f"found {rt}")
            if lt is ERR or rt is ERR:
                return BOOL
            if lt.name in NUMERIC and rt.name in NUMERIC:
                return BOOL
            if lt == rt and lt.name in ("str", "list"):
                if lt.name == "list" and e.op not in ("==", "!="):
                    return self.err(e, "lists support only == and != in PySub")
                return BOOL
            return self.err(e, f"cannot compare {lt} with {rt}")

        if isinstance(e, A.BinOp):
            lt, rt = self.synth(e.left), self.synth(e.right)
            return self.binop_result(e, e.op, lt, rt)

        if isinstance(e, A.Subscript):
            base = self.synth(e.value)
            if base is ERR:
                return ERR
            if base.name == "tuple":
                return _tup.subscript(self, e, base)
            if base.name == "dict":
                k = self.check_expr(e.index, base.key)
                if not widens_to(k, base.key):
                    self.err(e.index, f"dict key must be {base.key}, found {k}")
                return base.elem or ERR
            idx = self.synth(e.index)
            if not widens_to(idx, INT):
                self.err(e.index, f"index must be int, found {idx}")
            if base.name == "list":
                return base.elem or ERR
            if base == STR:
                return STR
            return self.err(e, f"{base} is not subscriptable")

        if isinstance(e, A.MethodCall):
            return self.synth_method(e)

        if isinstance(e, A.Call):
            return self.synth_call(e)

        if _comp().is_comp_node(e):
            return _comp().synth(self, e)
        return self.err(e, f"unsupported expression {type(e).__name__}")

    def binop_result(self, node: A.Node, op: str, lt: Ty, rt: Ty) -> Ty:
        ext = _cls.binop(self, node, op, lt, rt)  # __add__ / __radd__ ... on user classes
        if ext is not None:
            return ext
        ext = _x.binop(self, node, op, lt, rt)
        if ext is not None:
            return ext
        if lt is ERR or rt is ERR:
            return ERR
        if op in _bx.BITOPS:
            return _bx.bitop_result(self, node, op, lt, rt)
        if lt.name == "tuple" or rt.name == "tuple":
            return _tup.binop(self, node, op, lt, rt)
        if op == "+" and lt == STR and rt == STR:
            return STR
        if op == "+" and lt.name == "list" and rt.name == "list" and lt == rt:
            return lt
        if op == "*" and ((lt == STR and rt.name in ("int", "bool")) or
                          (rt == STR and lt.name in ("int", "bool"))):
            return STR
        if op == "*" and lt.name == "list" and lt.elem is not None and rt.name in ("int", "bool"):
            return lt                            # [0] * n (shallow, like Python: [[0]] * 3 shares the inner list)
        if op == "*" and rt.name == "list" and rt.elem is not None and lt.name in ("int", "bool"):
            return rt
        if lt.name in NUMERIC and rt.name in NUMERIC:
            if op == "/":
                return FLOAT                       # true division is always float
            if op == "**":
                return FLOAT if FLOAT in (lt, rt) else INT
            if op in ("//", "%", "+", "-", "*"):
                return FLOAT if FLOAT in (lt, rt) else INT
        return self.err(node, f"operator {op!r} is not defined for {lt} and {rt}")

    def _margs(self, e, n_min: int, n_max: int, what: str) -> bool:
        if not (n_min <= len(e.args) <= n_max):
            want = str(n_min) if n_min == n_max else f"{n_min} to {n_max}"
            self.err(e, f"{what}() takes {want} argument(s) in PySub, {len(e.args)} given")
            return False
        return True

    def _want(self, a: A.Node, want: Ty, what: str) -> None:
        got = self.check_expr(a, want)
        if got is not ERR and not widens_to(got, want):
            self.err(a, f"{what}: expected {want}, found {got}")

    def synth_dict_get1(self, e: A.MethodCall, recv: Ty) -> Ty:
        """d.get(k) -> `d[k] if k in d else None` (Optional value), when d and k are cheap to evaluate twice."""
        from .tuples import is_pure_expr
        if not (is_pure_expr(e.recv) and is_pure_expr(e.args[0])):
            return self.err(e, "d.get(key) needs a plain name or literal for the dict and the key (it is looked up "
                               "twice): assign them to variables first, or use d.get(key, default)")
        ln, cl = e.line, e.col
        recv_n, key_n = e.recv, e.args[0]
        test = A.Compare(ln, cl, op="in", left=key_n, right=recv_n)
        e.__class__ = A.IfExp                    # rewrite this node in place and type it as the conditional
        e.test, e.body, e.orelse = test, A.Subscript(ln, cl, value=recv_n, index=key_n), A.NoneLit(ln, cl)
        return self.synth(e)

    def synth_method(self, e: A.MethodCall) -> Ty:
        if _bx.is_fromkeys(self, e):
            return _bx.synth_fromkeys(self, e)
        hooked = _comp().synth_method_hook(self, e)
        if hooked is not None:
            return hooked
        hooked = _cls.synth_method(self, e)           # super().m(), C.m(obj), list[C].sort(), static/property misuse
        if hooked is not None:
            return hooked
        recv = self.synth(e.recv)
        ext = _x.synth_method(self, e, recv)  # set methods; keyword/default arguments of methods
        if ext is not None:
            return ext
        self.check_kwargs(e, {"reverse"} if (recv.name == "list" and e.method == "sort") else set())
        _r = _bx.synth_method(self, e, recv)          # str / list / dict methods beyond the core set
        if _r is not None:
            return _r
        if recv.name == "list" and e.method in ("pop", "insert", "extend", "clear", "reverse", "copy", "index",
                                                "count", "remove", "sort"):
            m, el = e.method, recv.elem
            prim = el is not None and el.name in PRIM
            obj = el is not None and el.name in self.classes
            if m == "pop":
                if not self._margs(e, 0, 1, "pop"):
                    return ERR
                if e.args:
                    self._want(e.args[0], INT, "pop() index")
                return el
            if m == "insert":
                if self._margs(e, 2, 2, "insert"):
                    self._want(e.args[0], INT, "insert() index")
                    self._want(e.args[1], el, "insert() value")
                return NONE
            if m == "extend":
                if self._margs(e, 1, 1, "extend"):
                    self._want(e.args[0], recv, "extend() argument")
                return NONE
            if m in ("clear", "reverse"):
                self._margs(e, 0, 0, m)
                return NONE
            if m == "copy":
                self._margs(e, 0, 0, m)
                return recv
            if m == "sort":
                self._margs(e, 0, 0, m)
                if not (prim or _tup.orderable(el)):
                    return self.err(e, f"sort() needs a list of int, float, bool or str in PySub, found {recv}")
                return NONE
            if not (prim or obj or _tup.orderable(el)):
                return self.err(e, f"{m}() on a {recv} needs element equality, which nested lists don't have in PySub")
            if self._margs(e, 1, 1, m):
                self._want(e.args[0], el, f"{m}() value")
            return INT if m in ("index", "count") else NONE
        if recv == STR and e.method not in ("upper", "lower"):
            m = e.method
            zero_str = ("title", "capitalize", "swapcase")
            if m in ("strip", "lstrip", "rstrip"):
                if self._margs(e, 0, 1, m) and e.args:
                    self._want(e.args[0], STR, f"{m}() characters")
                return STR
            if m in zero_str:
                self._margs(e, 0, 0, m)
                return STR
            if m in ("isdigit", "isalpha", "isalnum", "isspace", "isupper", "islower"):
                self._margs(e, 0, 0, m)
                return BOOL
            if m in ("startswith", "endswith", "find", "rfind", "index", "count"):
                if self._margs(e, 1, 1, m):
                    self._want(e.args[0], STR, f"{m}() argument")
                return BOOL if m in ("startswith", "endswith") else INT
            if m == "replace":
                if self._margs(e, 2, 2, m):
                    self._want(e.args[0], STR, "replace() old")
                    self._want(e.args[1], STR, "replace() new")
                return STR
            if m == "split":
                if self._margs(e, 0, 1, m) and e.args:
                    self._want(e.args[0], STR, "split() separator")
                return list_of(STR)
            if m == "join":
                if self._margs(e, 1, 1, m):
                    self._want(e.args[0], list_of(STR), "join() argument")
                return STR
            return self.err(e, f"str has no method {m!r} in PySub")
        if recv.name == "list":
            if e.method in ("append", "appendleft"):
                if len(e.args) != 1:
                    return self.err(e, f"{e.method}() takes exactly one argument")
                at = self.check_expr(e.args[0], recv.elem)
                if not widens_to(at, recv.elem):
                    return self.err(e.args[0],
                                    f"cannot {e.method} {at} to {recv}")
                return NONE
            if e.method == "popleft":
                if len(e.args) != 0:
                    return self.err(e, "popleft() takes no arguments")
                return recv.elem
            return self.err(e, f"list has no method {e.method!r} in PySub")
        if recv == STR:
            if e.method == "upper" or e.method == "lower":
                return STR
            return self.err(e, f"str has no method {e.method!r} in PySub")
        if recv.name == "dict":
            if e.method == "get" and len(e.args) == 1 and not e.kwargs:
                return self.synth_dict_get1(e, recv)
            if e.method == "get":
                if len(e.args) != 2:
                    return self.err(e, "dict.get() takes (key) or (key, default)")
                k = self.check_expr(e.args[0], recv.key)
                if not widens_to(k, recv.key):
                    self.err(e.args[0], f"dict key must be {recv.key}, found {k}")
                d = self.check_expr(e.args[1], recv.elem)
                if not widens_to(d, recv.elem):
                    self.err(e.args[1], f"default must be {recv.elem}, found {d}")
                return recv.elem
            if e.method == "items":
                return _tup.items_call(self, e, recv)
            return self.err(e, f"dict has no method {e.method!r} in PySub")
        if recv.name in self.classes:
            info = self.classes[recv.name]
            msig = info.methods.get(e.method)
            if msig is None:
                return self.err(e, f"class {recv.name!r} has no method {e.method!r}")
            if len(e.args) != len(msig.params):
                return self.err(e, f"{recv.name}.{e.method}() expects "
                                   f"{len(msig.params)} argument(s) but "
                                   f"{len(e.args)} were given")
            for i, (a, want) in enumerate(zip(e.args, msig.params)):
                got = self.check_expr(a, want)
                if not widens_to(got, want):
                    self.err(a, f"argument {i + 1} of {recv.name}.{e.method}(): "
                                f"expected {want}, found {got}")
            return msig.ret
        if recv is ERR:
            return ERR
        return self.err(e, f"{recv} has no methods in PySub")

    def check_kwargs(self, e, allowed) -> Dict[str, A.Node]:
        out: Dict[str, A.Node] = {}
        for kw in getattr(e, "kwargs", None) or []:
            if kw.name not in allowed:
                self.err(kw, f"keyword argument {kw.name!r} is outside the PySub subset (only print(sep=, end=), "
                             f"sorted(reverse=) and list.sort(reverse=) take keywords)")
                self.synth(kw.value)
                continue
            t = self.synth(kw.value)
            want = BOOL if kw.name == "reverse" else STR
            if t is not ERR and t != want:
                self.err(kw.value, f"{kw.name}= must be {want}, found {t}")
            kw.ty = t
            out[kw.name] = kw.value
        return out

    def synth_call(self, e: A.Call) -> Ty:
        name = e.func
        if name in ("sorted", "list", "sum", "min", "max", "any", "all", "len") and e.args:
            _bx.mark_view_ok(self, e.args[0])         # d.keys()/d.values() read once here: same as a list
        hooked = _comp().synth_call_hook(self, e)     # generator / key= / enumerate-zip arguments: claim them first
        if hooked is not None:
            return hooked
        hooked = _cls.synth_call(self, e)             # str/repr/len/bool/abs/sorted/min/max of user objects, super()
        if hooked is not None:
            return hooked
        ext = _x.synth_call(self, e)          # isinstance, set(), defaults/keywords of user functions ...
        if ext is not None:
            return ext
        _r = _bx.synth_call(self, e)                  # math module, slices, pow, bin/hex/oct, int(s, base), repr
        if _r is not None:
            return _r
        self.check_kwargs(e, {"print": {"sep", "end"}, "sorted": {"reverse"}}.get(name, set()))
        if name == "__pythia_unpack":
            return _tup.unpack_call(self, e)
        if name in ("list", "sorted") and e.args:
            _tup.mark_items(e.args[0])
        if name == "print":
            for a in e.args:
                t = self.synth(a)
                if t.name in self.classes and not _cls.print_ok(self, t, a):
                    self.err(a, f"cannot print a {t.name} instance directly: "
                                f"PySub classes have no reproducible repr(); "
                                f"print specific fields instead")
                if t.name == "list" and t.elem is not None and t.elem.name in self.classes and not _cls.print_ok(self, t, a):
                    self.err(a, f"cannot print a list of {t.elem.name} instances: "
                                f"PySub classes have no reproducible repr(); "
                                f"print specific fields instead")
                if _tup.involves_tuple(t) and not _tup.reprable(t):
                    self.err(a, f"cannot print a {t}: only tuples of int, float, bool, str, tuples and "
                                f"flat lists of those have a reproducible repr in PySub")
            return NONE
        if name == "len":
            if len(e.args) != 1:
                return self.err(e, "len() takes exactly one argument")
            t = self.synth(e.args[0])
            if t.name in ("list", "str", "dict", "tuple") or t is ERR:
                return INT
            return self.err(e.args[0], f"object of type {t} has no len()")
        if name in ("ord", "chr"):
            if len(e.args) != 1:
                return self.err(e, f"{name}() takes exactly one argument")
            t = self.synth(e.args[0])
            want = STR if name == "ord" else INT
            if t is ERR:
                return ERR
            if not (t == want or (want == INT and t == BOOL)):
                return self.err(e.args[0], f"{name}() needs a {want}, found {t}")
            return INT if name == "ord" else STR
        if name == "abs":
            if len(e.args) != 1:
                return self.err(e, "abs() takes exactly one argument")
            t = self.synth(e.args[0])
            if t.name in NUMERIC:
                return INT if t == BOOL else t
            return self.err(e.args[0], f"bad operand type for abs(): {t}")
        if name in ("min", "max"):
            if not e.args:
                return self.err(e, f"{name}() needs at least one argument")
            ts = [self.synth(a) for a in e.args]
            if any(t is ERR for t in ts):
                return ERR
            if len(ts) == 1:
                t = ts[0]
                if t.name == "list" and t.elem is not None and (t.elem.name in PRIM or _tup.orderable(t.elem)):
                    return t.elem
                return self.err(e.args[0], f"{name}() of one argument needs a list of numbers or strings, found {t}")
            if all(t.name in NUMERIC for t in ts):
                acc = ts[0]
                for t in ts[1:]:
                    acc = join(acc, t)
                return acc
            if all(t == STR for t in ts) and len(ts) > 1:
                return STR
            return self.err(e, f"{name}() needs numeric arguments, found {' and '.join(str(t) for t in ts)}")
        if name == "input":
            if len(e.args) > 1:
                return self.err(e, "input() takes at most one argument (the prompt)")
            if e.args:
                t = self.synth(e.args[0])
                if t is not ERR and t != STR:
                    self.err(e.args[0], f"input() prompt must be str, found {t}")
            return STR
        if name == "format":
            if len(e.args) != 2 or not isinstance(e.args[1], A.StrLit):
                return self.err(e, "format() needs a value and a literal format spec, e.g. format(x, '.2f')")
            t = self.synth(e.args[0])
            self.synth(e.args[1])
            if t is ERR:
                return STR
            why = fmt_spec_problem(e.args[1].value, t)
            return self.err(e, why) if why else STR
        if name == "round":
            if len(e.args) not in (1, 2):
                return self.err(e, "round() takes a number and optionally ndigits")
            t = self.synth(e.args[0])
            if t is ERR:
                return ERR
            if t.name not in NUMERIC:
                return self.err(e.args[0], f"round() needs a number, found {t}")
            if len(e.args) == 2:
                n = self.synth(e.args[1])
                if n is not ERR and not widens_to(n, INT):
                    self.err(e.args[1], f"round() ndigits must be int, found {n}")
                return FLOAT if t == FLOAT else INT
            return INT
        if name == "sum":
            if len(e.args) != 1:
                return self.err(e, "sum() takes exactly one list in PySub (no start value)")
            t = self.synth(e.args[0])
            if t is ERR:
                return ERR
            if t.name == "list" and t.elem is not None and t.elem.name in NUMERIC:
                return FLOAT if t.elem == FLOAT else INT
            return self.err(e.args[0], f"sum() needs a list of numbers, found {t}")
        if name in ("sorted", "list"):
            if len(e.args) != 1:
                return self.err(e, f"{name}() takes exactly one argument in PySub" +
                                   (" (an empty list is written `xs: list[int] = []`)" if name == "list" else ""))
            t = self.synth(e.args[0])
            if t is ERR:
                return ERR
            if t == STR:                        # characters
                return list_of(STR)
            if t.name == "dict":                # keys, in insertion order
                return list_of(t.key)
            if t.name == "list" and (name == "list" or (t.elem is not None and _tup.orderable(t.elem))):
                return t
            if t.name == "tuple" and _tup.homogeneous(t) is not None and (name == "list" or _tup.orderable(t.elts[0])):
                return list_of(t.elts[0])
            return self.err(e.args[0], f"sorted() needs a list of int, float, bool or str, a str or a dict, found {t}"
                            if name == "sorted" else f"list() takes a list, a str or a dict, found {t}")
        if name in ("int", "float", "str", "bool"):
            if len(e.args) != 1:
                return self.err(e, f"{name}() takes exactly one argument")
            t = self.synth(e.args[0])
            target = {"int": INT, "float": FLOAT, "str": STR, "bool": BOOL}[name]
            if name == "str":
                if t.name in ("list", "dict"):           # str(container) == repr(container) in CPython
                    e.func = "repr"
                    return self.synth(e)
                if t.name == "tuple":
                    return STR if _tup.reprable(t) else self.err(
                        e.args[0], f"str() of a {t} has no reproducible repr in PySub")
                if t.name in self.classes and not _cls.can_str(self, t.name):
                    return self.err(e.args[0], f"str() of a {t.name} instance has no reproducible repr in PySub; "
                                               f"format its fields instead")
                return STR
            if name in ("int", "float"):
                if t.name in NUMERIC or t == STR:
                    return target
                return self.err(e.args[0], f"cannot convert {t} to {name}")
            if t.name in NUMERIC or t == STR or t.name == "list":
                return BOOL
            return self.err(e.args[0], f"cannot convert {t} to bool")

        if name in self.classes:
            info = self.classes[name]
            if info.init is None:
                if e.args:
                    return self.err(e, f"{name}() takes no arguments "
                                       f"(no __init__ is defined)")
                return Ty(name)
            sig = info.init
            if len(e.args) != len(sig.params):
                return self.err(e, f"{name}() expects {len(sig.params)} "
                                   f"argument(s) but {len(e.args)} were given")
            for i, (a, want) in enumerate(zip(e.args, sig.params)):
                got = self.check_expr(a, want)
                if not widens_to(got, want):
                    self.err(a, f"argument {i + 1} of {name}(): expected {want}, "
                                f"found {got}")
            return Ty(name)

        sig = self.funcs.get(name)
        if sig is None:
            return self.err(e, f"function {name!r} is not defined")
        if len(e.args) != len(sig.params):
            return self.err(e, f"{name}() expects {len(sig.params)} argument(s) "
                               f"but {len(e.args)} were given")
        for i, (a, want) in enumerate(zip(e.args, sig.params)):
            got = self.check_expr(a, want)
            if not widens_to(got, want):
                self.err(a, f"argument {i + 1} of {name}(): expected {want}, "
                            f"found {got}")
        return sig.ret


from . import builtins_ext as _bx  # noqa: E402  (math / bitwise / slice / extra methods; imports this module's types)
from . import tuples as _tup  # noqa: E402  (tuples.py builds on Ty, defined above)
from . import types_ext as _x  # noqa: E402  (PySub 1.3 type-system extensions; imports this module)
from . import classes_ext as _cls  # noqa: E402  (user classes: inheritance, dunders, class attributes ...)


def _comp():
    from . import comprehensions          # comprehensions, generators, key lambdas, enumerate/zip/reversed
    return comprehensions


def typecheck(mod: A.Module, filename: str = "<input>"):
    tc = TypeChecker(mod, filename)
    errs = tc.run()
    return tc, errs
