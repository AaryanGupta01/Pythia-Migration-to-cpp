"""
PYTHIA :: user classes done properly (parser, type-checker, lowering and C++ emitter hooks)

Hooked into parser / typecheck / types_ext / emit_c / emit_ext by one-line delegations; the logic lives here.

  * class C(Base): single inheritance, method overriding, super().m(...), virtual dispatch through
    base-typed references (a class id `_cid` in the root struct; dispatchers switch on it)
  * fields inferred from `self.x = ...` / `self.x: T = ...` in the methods (no class-level declaration needed)
  * class attributes (`X = 0`, `X: int = 0`): shared storage, read via self.X / obj.X / C.X, written via C.X = v
  * @staticmethod, @classmethod (cls(...) / cls.X), @property (+ .setter), @dataclass (init / repr / eq / order)
  * dunders: __str__ __repr__ __eq__ __ne__ __lt__ __le__ __gt__ __ge__ __len__ __bool__ __contains__
    __getitem__ __setitem__, arithmetic (__add__ ... and reflected __radd__ ...), __neg__ __pos__ __abs__ __invert__,
    in-place __iadd__ ...; sorted()/min()/max()/list.sort() of list[C] through __lt__ / __gt__
  * isinstance(x, C) is decided at run time (class id range) when x may hold a subclass instance

Everything else about classes (metaclasses, multiple inheritance, __getattr__, __iter__, __hash__, ...) is rejected
with a precise diagnostic instead of being approximated.
"""
import copy
import threading
from typing import Dict, List, Optional, Set, Tuple

from . import ast_nodes as A
from .typecheck import Ty, INT, FLOAT, BOOL, STR, NONE, ERR, PRIM, NUMERIC, list_of, dict_of, widens_to

_tls = threading.local()

BUILTIN_BASES = {"Exception", "BaseException", "ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError",
                 "ABC", "abc.ABC", "dict", "list", "int", "str", "float", "tuple", "set", "NamedTuple",
                 "typing.NamedTuple", "Enum", "enum.Enum", "Generic", "Protocol"}
ARITH = {"+": "add", "-": "sub", "*": "mul", "/": "truediv", "//": "floordiv", "%": "mod", "**": "pow",
         "&": "and", "|": "or", "^": "xor", "<<": "lshift", ">>": "rshift"}
CMP = {"<": ("__lt__", "__gt__"), "<=": ("__le__", "__ge__"), ">": ("__gt__", "__lt__"), ">=": ("__ge__", "__le__")}
UNARY = {"-": "__neg__", "+": "__pos__", "~": "__invert__"}
# dunders CPython would call implicitly in places PySub cannot reproduce: reject the definition
FORBIDDEN = {"__getattr__", "__getattribute__", "__setattr__", "__delattr__", "__format__", "__new__", "__del__",
             "__init_subclass__", "__set_name__", "__class_getitem__", "__iter__", "__next__", "__hash__",
             "__call__", "__enter__", "__exit__", "__index__", "__int__", "__float__", "__round__", "__reversed__",
             "__missing__", "__delitem__", "__copy__", "__deepcopy__", "__getstate__", "__setstate__", "__reduce__",
             "__sizeof__", "__dir__", "__get__", "__set__", "__delete__", "__complex__", "__bytes__", "__aiter__",
             "__await__", "__matmul__", "__rmatmul__", "__imatmul__", "__divmod__", "__rdivmod__", "__trunc__",
             "__floor__", "__ceil__", "__length_hint__"}
BOOL_RET = {"__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__contains__", "__bool__"}


def _cur():
    return getattr(_tls, "tc", None)


def _diag(tc, node, msg: str) -> Ty:
    from .parser import Diagnostic
    tc.errors.append(Diagnostic(msg, getattr(node, "line", 0), getattr(node, "col", 0), "TypeError"))
    return ERR


def _at(line: int, col: int) -> A.Node:
    return A.Node(line, col)


def walk(n):
    from .types_ext import walk as _w
    return _w(n)


def _transform(node, fn) -> None:
    """Post-order rewrite: every child node x is replaced by fn(x) when that returns a node."""
    for f in node.__dataclass_fields__:
        if f == "ty":
            continue
        v = getattr(node, f)
        if isinstance(v, A.Node):
            _transform(v, fn)
            r = fn(v)
            if r is not None:
                setattr(node, f, r)
        elif isinstance(v, list):
            for i, x in enumerate(v):
                if isinstance(x, A.Node):
                    _transform(x, fn)
                    r = fn(x)
                    if r is not None:
                        v[i] = r


# =============================================================================================== parser
class Deco(A.Node):
    def __init__(self, name, args, kwargs, line, col):
        super().__init__(line, col)
        self.name, self.args, self.kwargs = name, args, kwargs


def _panic(p, tok, msg: str):
    from .parser import Diagnostic, _Panic
    p.errors.append(Diagnostic(msg, tok.line, tok.col))
    raise _Panic()


def _dotted(p) -> str:
    name = p.expect("NAME").value
    while p.at_op("."):
        p.next()
        name += "." + p.expect("NAME").value
    return name


def parse_bases(p) -> list:
    """`(Base)` after the class name -> [(name, line, col)] (`object` dropped); [] without parentheses."""
    if not p.at_op("("):
        return []
    p.next()
    out = []
    while not p.at_op(")"):
        t = p.cur
        nxt = p.toks[p.i + 1]
        if t.kind == "NAME" and nxt.kind == "OP" and nxt.value == "=":
            _panic(p, t, "keyword arguments in a class statement (metaclass=..., ...) are outside the PySub subset")
        if t.kind != "NAME":
            _panic(p, t, "a base class must be a class name")
        out.append((_dotted(p), t.line, t.col))
        if p.at_op(","):
            p.next()
        else:
            break
    p.expect("OP", ")")
    return [b for b in out if b[0] != "object"]


def parse_decorators(p) -> list:
    decos = []
    while p.at_op("@"):
        t = p.next()
        if p.cur.kind != "NAME":
            _panic(p, p.cur, "a decorator must be a name, e.g. @staticmethod")
        name = _dotted(p)
        args = kwargs = None
        if p.at_op("("):
            p.next()
            args, kwargs = p._call_args()
        p.expect("NEWLINE")
        decos.append(Deco(name, args, kwargs, t.line, t.col))
    return decos


def parse_decorated(p, mod) -> None:
    decos = parse_decorators(p)
    if p.at_kw("class"):
        cd = p.parse_classdef()
        cd.decorators = decos
        mod.classes.append(cd)
    elif p.at_kw("def"):
        f = p.parse_funcdef()
        f.decorators = decos
        mod.funcs.append(f)
    else:
        _panic(p, p.cur, "expected 'def' or 'class' after a decorator")


def parse_class_item(p, cd) -> bool:
    """One class-body item other than a plain method: decorated method, docstring, pass, field, class attribute."""
    t = p.cur
    if p.at_op("@"):
        decos = parse_decorators(p)
        if not p.at_kw("def"):
            _panic(p, p.cur, "only methods can be decorated inside a class body")
        m = p.parse_funcdef()
        m.decorators = decos
        cd.methods.append(m)
        return True
    if t.kind in ("STRING", "FSTRING"):
        e = p.parse_expr()
        p.expect("NEWLINE")
        if not isinstance(e, A.StrLit):
            _panic(p, t, "only a docstring may appear as an expression in a class body")
        return True
    if p.at_kw("pass"):
        p.next()
        p.expect("NEWLINE")
        return True
    if p.at_kw("class"):
        _panic(p, t, "nested class definitions are outside the PySub subset")
    if t.kind == "OP" and t.value == "." and p.toks[p.i + 1].value == "." and p.toks[p.i + 2].value == ".":
        for _ in range(3):
            p.next()
        p.expect("NEWLINE")
        return True
    if t.kind != "NAME":
        return False
    nxt = p.toks[p.i + 1]
    attrs = cd.__dict__.setdefault("attrs", [])
    if nxt.kind == "OP" and nxt.value == "=":
        p.next()
        p.next()
        val = p.parse_exprlist()
        p.expect("NEWLINE")
        attrs.append(A.Assign(t.line, t.col, target=A.Name(t.line, t.col, id=t.value), ann=None, value=val))
        return True
    if nxt.kind == "OP" and nxt.value == ":":
        p.next()
        p.next()
        ann = p.parse_type()
        if p.at_op("="):
            p.next()
            val = p.parse_exprlist()
            p.expect("NEWLINE")
            attrs.append(A.Assign(t.line, t.col, target=A.Name(t.line, t.col, id=t.value), ann=ann, value=val))
            return True
        p.expect("NEWLINE")
        cd.fields.append(A.ClassField(line=t.line, col=t.col, name=t.value, ann=ann))
        return True
    return False


def parse_attr_ann(p, t, target) -> A.Assign:
    """`self.x: T = value` (the ':' is the current token)."""
    p.next()
    ann = p.parse_type()
    if not p.at_op("="):
        _panic(p, p.cur, "an annotated attribute needs a value here: write `self.x: T = value`")
    p.next()
    val = p.parse_exprlist()
    p.expect("NEWLINE")
    return A.Assign(t.line, t.col, target=target, ann=ann, value=val)


# =============================================================================================== context
class Ctx:
    def __init__(self, tc):
        self.tc = tc
        self.defs: Dict[str, A.ClassDef] = {}
        self.order: List[str] = []
        self.base: Dict[str, Optional[str]] = {}
        self.subs: Dict[str, List[str]] = {}
        self.cattr: Dict[str, Dict[str, tuple]] = {}        # class -> {name: (Ty, Assign)}
        self.cattr_field: Dict[str, Set[str]] = {}          # instance fields initialised from a class attribute
        self.props: Dict[str, Dict[str, dict]] = {}         # class -> {prop: {"get": FuncDef, "set": FuncDef}}
        self.statics: Dict[str, Dict[str, tuple]] = {}      # class -> {method: (function name, kind)}
        self.dc: Dict[str, dict] = {}                       # dataclass options
        self.synth: Dict[str, Set[str]] = {}                # natively generated dunders per class
        self.cid: Dict[str, int] = {}
        self.hi: Dict[str, int] = {}
        self.declared: Dict[str, Set[str]] = {}             # class-level `x: T` fields (no value)

    def mro(self, c: str) -> List[str]:
        out = []
        while c is not None and c not in out:
            out.append(c)
            c = self.base.get(c)
        return out

    def is_sub(self, a: str, b: str) -> bool:
        return a in self.base and b in self.mro(a)

    def below(self, c: str) -> List[str]:
        out = []
        for s in self.subs.get(c, []):
            out.append(s)
            out += self.below(s)
        return out

    def in_hier(self, c: str) -> bool:
        return self.base.get(c) is not None or bool(self.subs.get(c))

    def own(self, c: str) -> Set[str]:
        d = self.defs.get(c)
        return ({m.name for m in d.methods} if d else set()) | self.synth.get(c, set())


def ctx(tc) -> Optional[Ctx]:
    return getattr(tc, "cx", None)


def is_cls(tc, t: Optional[Ty]) -> bool:
    return t is not None and t is not ERR and tc is not None and t.name in getattr(tc, "classes", {})


SYN_SIG = {"__repr__": ([], STR), "__eq__": (["self"], BOOL), "__lt__": (["self"], BOOL), "__le__": (["self"], BOOL),
           "__gt__": (["self"], BOOL), "__ge__": (["self"], BOOL)}


class SynSig:
    """Signature of a dunder PySub generates natively (dataclass __repr__ / __eq__ / ordering)."""
    def __init__(self, cls: str, name: str):
        ps, ret = SYN_SIG[name]
        self.name, self.owner, self.ret, self.node = f"{cls}.{name}", cls, ret, None
        self.params = [Ty(cls) for _ in ps]


def resolve(tc, cls: str, name: str):
    """(owner, sig) of the method `name` as seen from class `cls` (nearest definition in the MRO), else None."""
    cx = ctx(tc)
    if cx is None or cls not in tc.classes:
        return None
    for k in cx.mro(cls):
        d = cx.defs.get(k)
        if d is not None and any(m.name == name for m in d.methods):
            sig = tc.classes[k].methods.get(name)
            return (k, sig) if sig is not None else None
        if name in cx.synth.get(k, set()):
            return k, SynSig(k, name)
    return None


def resolve_str(tc, cls: str):
    """str(obj): the nearest __str__, else the nearest __repr__ (object.__str__ calls repr())."""
    return resolve(tc, cls, "__str__") or resolve(tc, cls, "__repr__")


def dynamic_impls(tc, cls: str, resolver) -> Dict[str, tuple]:
    """For the static type `cls`: run-time class -> implementation (owner, sig) or None."""
    cx = ctx(tc)
    return {d: resolver(d) for d in [cls] + cx.below(cls)}


def needs_dispatch(tc, cls: str, resolver) -> bool:
    impls = dynamic_impls(tc, cls, resolver)
    owners = {(r[0] if r else None) for r in impls.values()}
    return len(owners) > 1


def all_have(tc, cls: str, resolver) -> Optional[str]:
    """None if every run-time class a `cls` reference may hold has an implementation, else a class without one."""
    for d, r in dynamic_impls(tc, cls, resolver).items():
        if r is None:
            return d
    return None


# =============================================================================================== type checker
def sub_widens(src: Ty, dst: Ty) -> bool:
    """Implicit upcast Sub -> Base (hooked into typecheck.widens_to)."""
    tc = _cur()
    cx = ctx(tc) if tc is not None else None
    return cx is not None and src.name != dst.name and src.name in cx.base and cx.is_sub(src.name, dst.name)


def join(a: Ty, b: Ty) -> Optional[Ty]:
    """Nearest common base class of two class types (list literals of mixed subclasses)."""
    tc = _cur()
    cx = ctx(tc) if tc is not None else None
    if cx is None or a.name not in cx.base or b.name not in cx.base:
        return None
    for k in cx.mro(a.name):
        if k in cx.mro(b.name):
            return Ty(k)
    return None


def prepare(tc) -> None:
    """After the class names are registered (pass 0), before fields and signatures are resolved (pass 1)."""
    _tls.tc = tc
    cx = Ctx(tc)
    tc.cx = cx
    mod = tc.mod
    for f in mod.funcs:
        for d in getattr(f, "decorators", None) or []:
            _diag(tc, d, f"decorator @{d.name} on function {f.name!r} is outside the PySub subset "
                         f"(supported: @staticmethod / @classmethod / @property inside a class, @dataclass on a class)")
    seen = set()
    for c in mod.classes:
        if tc.classes.get(c.name) is None or tc.classes[c.name].node is not c:
            continue
        cx.defs[c.name] = c
        cx.order.append(c.name)
        cx.subs.setdefault(c.name, [])
        for k in ("cattr", "props", "statics", "synth", "declared", "cattr_field"):
            getattr(cx, k)[c.name] = {} if k in ("cattr", "props", "statics") else set()
        b = None
        bases = getattr(c, "bases", None) or []
        if len(bases) > 1:
            _diag(tc, _at(bases[1][1], bases[1][2]), f"class {c.name!r}: multiple inheritance is outside the PySub "
                                                     f"subset (one base class at most)")
        elif bases:
            bn, ln, cl = bases[0]
            if bn in BUILTIN_BASES or "." in bn:
                _diag(tc, _at(ln, cl), f"class {c.name!r} inherits from {bn!r}: PySub classes may only inherit from "
                                       f"another class defined in the same file")
            elif bn not in tc.classes:
                _diag(tc, _at(ln, cl), f"unknown base class {bn!r}")
            elif bn not in seen:
                _diag(tc, _at(ln, cl), f"base class {bn!r} must be defined before {c.name!r} (CPython raises "
                                       f"NameError otherwise)")
            else:
                b = bn
        cx.base[c.name] = b
        if b is not None:
            cx.subs[b].append(c.name)
        seen.add(c.name)
    for name in cx.order:
        _class_decorators(tc, cx, cx.defs[name])
    for name in cx.order:
        _method_decorators(tc, cx, cx.defs[name])
    for name in cx.order:
        _dataclass(tc, cx, cx.defs[name])
    for name in cx.order:
        _class_attrs(tc, cx, cx.defs[name])
    _rewrite_static_calls(tc, cx)
    _Infer(tc, cx).run()
    for name in cx.order:
        _object_params(tc, cx, cx.defs[name])


# ---- decorators --------------------------------------------------------------------------------------------
def _class_decorators(tc, cx: Ctx, c: A.ClassDef) -> None:
    for d in getattr(c, "decorators", None) or []:
        if d.name not in ("dataclass", "dataclasses.dataclass") or \
                (d.name == "dataclass" and _imported(tc, "dataclass") != ("dataclasses", "dataclass")):
            _diag(tc, d, f"class decorator @{d.name} is outside the PySub subset (supported: @dataclass from "
                         f"`from dataclasses import dataclass`)")
            continue
        opts = {"init": True, "repr": True, "eq": True, "order": False, "frozen": False}
        if d.args:
            _diag(tc, d, "@dataclass takes keyword arguments only")
        for kw in d.kwargs or []:
            if kw.name not in opts or not isinstance(kw.value, A.BoolLit):
                _diag(tc, kw, f"@dataclass({kw.name}=...) is outside the PySub subset (supported: init, repr, eq, "
                              f"order, frozen with True/False)")
                continue
            opts[kw.name] = kw.value.value
        if opts["order"] and not opts["eq"]:
            _diag(tc, d, "eq must be true if order is true (CPython raises ValueError)")
        cx.dc[c.name] = opts


def _imported(tc, local: str):
    table = getattr(tc.mod, "import_table", None)
    return table.names.get(local) if table is not None else None


def _method_decorators(tc, cx: Ctx, c: A.ClassDef) -> None:
    for m in list(c.methods):
        decos = getattr(m, "decorators", None) or []
        if not decos:
            if m.params and m.params[0].name == "cls" and m.params[0].ann is None:
                _diag(tc, m, f"method {m.name!r} takes `cls` first: mark it @classmethod")
            continue
        if len(decos) > 1:
            _diag(tc, decos[1], f"stacked decorators on {c.name}.{m.name} are outside the PySub subset")
            continue
        d = decos[0]
        if d.args is not None:
            _diag(tc, d, f"decorator @{d.name}(...) with arguments is outside the PySub subset")
            continue
        if d.name in ("staticmethod", "classmethod"):
            _make_static(tc, cx, c, m, d.name == "classmethod")
        elif d.name == "property":
            if [p.name for p in m.params] != ["self"]:
                _diag(tc, m, f"property {c.name}.{m.name} must take only self")
                continue
            if m.name in cx.props[c.name]:
                _diag(tc, m, f"property {m.name!r} is defined twice in class {c.name!r}")
                continue
            cx.props[c.name][m.name] = {"get": m, "set": None}
        elif d.name.endswith(".setter") and d.name[:-7] in cx.props[c.name]:
            prop = d.name[:-7]
            if m.name != prop:
                _diag(tc, m, f"the setter of property {prop!r} must be named {prop!r}")
                continue
            if len(m.params) != 2 or m.params[0].name != "self":
                _diag(tc, m, f"the setter of property {prop!r} must take self and the new value")
                continue
            m.name = f"{prop}__set"
            cx.props[c.name][prop]["set"] = m
        else:
            _diag(tc, d, f"decorator @{d.name} is outside the PySub subset (supported on methods: @staticmethod, "
                         f"@classmethod, @property and @<property>.setter)")


def _make_static(tc, cx: Ctx, c: A.ClassDef, m: A.FuncDef, is_cls: bool) -> None:
    kind = "classmethod" if is_cls else "staticmethod"
    if is_cls:
        if not m.params or m.params[0].name != "cls" or m.params[0].ann is not None:
            _diag(tc, m, f"classmethod {c.name}.{m.name} must take `cls` as its first parameter")
            return
        m.params = m.params[1:]
        _rewrite_cls(tc, c.name, m)
    elif m.params and m.params[0].name in ("self", "cls") and m.params[0].ann is None:
        _diag(tc, m, f"staticmethod {c.name}.{m.name} has no self/cls parameter; remove it or drop @staticmethod")
        return
    cname = f"{c.name}__{m.name}"
    if cname in tc.classes or any(f.name == cname for f in tc.mod.funcs):
        _diag(tc, m, f"{kind} {c.name}.{m.name} clashes with the module-level name {cname!r}")
        return
    c.methods.remove(m)
    m.static_of = (c.name, m.name, kind)
    m.name = cname
    tc.mod.funcs.append(m)
    cx.statics[c.name][m.static_of[1]] = (cname, kind)


def _rewrite_cls(tc, cname: str, m: A.FuncDef) -> None:
    def fn(n):
        if isinstance(n, A.Call) and n.func == "cls":
            n.func = cname
        elif isinstance(n, A.Attribute) and isinstance(n.value, A.Name) and n.value.id == "cls":
            n.value = A.Name(n.value.line, n.value.col, id=cname)
        elif isinstance(n, A.MethodCall) and isinstance(n.recv, A.Name) and n.recv.id == "cls":
            n.recv = A.Name(n.recv.line, n.recv.col, id=cname)
        return None
    for s in m.body:
        _transform(s, fn)
        fn(s)
    for n in walk(m.body):
        if isinstance(n, A.Name) and n.id == "cls":
            _diag(tc, n, "in a classmethod PySub supports `cls(...)`, `cls.attr` and `cls.method(...)` only")


# ---- dataclasses -------------------------------------------------------------------------------------------
def _dataclass(tc, cx: Ctx, c: A.ClassDef) -> None:
    opts = cx.dc.get(c.name)
    if opts is None:
        return
    if cx.base.get(c.name) is not None or any(cx.base.get(k) == c.name for k in cx.order):
        _diag(tc, c, f"dataclass {c.name!r} takes part in inheritance, which is outside the PySub subset")
    items = []                                     # (line, col, name, ann, default)
    for f in c.fields:
        items.append((f.line, f.col, f.name, f.ann, None))
    keep = []
    for s in getattr(c, "attrs", []):
        if s.ann is None:
            keep.append(s)                         # unannotated: a plain class attribute
        else:
            items.append((s.line, s.col, s.target.id, s.ann, s.value))
    c.attrs = keep
    items.sort(key=lambda x: (x[0], x[1]))
    c.fields = [A.ClassField(line=ln, col=cl, name=n, ann=ann) for ln, cl, n, ann, _ in items]
    seen_default = False
    for ln, cl, n, ann, dflt in items:
        if dflt is None and seen_default:
            _diag(tc, _at(ln, cl), f"non-default argument {n!r} follows default argument (CPython raises TypeError)")
        if dflt is not None:
            seen_default = True
            if isinstance(dflt, (A.ListLit, A.DictLit, A.SetLit)) or (isinstance(dflt, A.Call) and dflt.func == "set"):
                _diag(tc, dflt, f"mutable default for field {n!r} is not allowed (CPython raises ValueError: use "
                                f"default_factory, which is outside the PySub subset)")
            elif isinstance(dflt, A.Call):
                _diag(tc, dflt, f"default for dataclass field {n!r} must be a constant in PySub")
    c.dc_fields = [(n, ann, dflt) for _, _, n, ann, dflt in items]
    names = {m.name for m in c.methods}
    if opts["init"] and "__init__" not in names:
        params = [A.Param(c.line, c.col, name="self", ann=None)]
        body: List[A.Node] = []
        for n, ann, dflt in c.dc_fields:
            params.append(A.Param(c.line, c.col, name=n, ann=copy.deepcopy(ann),
                                  default=copy.deepcopy(dflt) if dflt is not None else None))
            body.append(A.Assign(c.line, c.col, target=A.Attribute(c.line, c.col, value=A.Name(c.line, c.col, id="self"),
                                                                  attr=n),
                                 value=A.Name(c.line, c.col, id=n)))
        if "__post_init__" in names:
            body.append(A.ExprStmt(c.line, c.col, value=A.MethodCall(c.line, c.col, recv=A.Name(c.line, c.col, id="self"),
                                                                      method="__post_init__", args=[], kwargs=[])))
        if not body:
            body = [A.Pass(c.line, c.col)]
        init = A.FuncDef(c.line, c.col, name="__init__", params=params, ret=None, body=body)
        init.dc_init = True
        c.methods.insert(0, init)
    if opts["repr"] and "__repr__" not in names:
        cx.synth[c.name].add("__repr__")
    if opts["eq"] and "__eq__" not in names:
        cx.synth[c.name].add("__eq__")
    if opts["order"]:
        for k in ("__lt__", "__le__", "__gt__", "__ge__"):
            if k in names:
                _diag(tc, c, f"cannot overwrite attribute {k} in class {c.name} (order=True; CPython raises TypeError)")
            cx.synth[c.name].add(k)


# ---- class attributes --------------------------------------------------------------------------------------
def _const_expr(e) -> bool:
    if isinstance(e, (A.IntLit, A.FloatLit, A.StrLit, A.BoolLit, A.NoneLit)):
        return True
    if isinstance(e, A.UnaryOp):
        return _const_expr(e.operand)
    if isinstance(e, A.BinOp):
        return _const_expr(e.left) and _const_expr(e.right)
    if isinstance(e, (A.ListLit, A.TupleLit, A.SetLit)):
        return all(_const_expr(x) for x in e.elts)
    if isinstance(e, A.DictLit):
        return all(_const_expr(x) for x in e.keys + e.values)
    return False


def _class_attrs(tc, cx: Ctx, c: A.ClassDef) -> None:
    taken = {m.name for m in c.methods} | set(cx.statics[c.name]) | set(cx.props[c.name])
    for s in getattr(c, "attrs", []):
        name = s.target.id
        if name in taken or name in cx.cattr[c.name]:
            _diag(tc, s, f"class attribute {name!r} of {c.name!r} clashes with another member of that name")
            continue
        if name.startswith("__") and name.endswith("__"):
            _diag(tc, s, f"class attribute {name} is outside the PySub subset")
            continue
        if not _const_expr(s.value):
            _diag(tc, s.value, f"class attribute {c.name}.{name} must be a constant in PySub (literals and "
                               f"arithmetic on them): CPython evaluates it when the class statement runs")
            continue
        if s.ann is not None:
            t = tc.resolve_type(s.ann)
            if t is ERR:
                continue
            got = tc.check_expr(s.value, t)
            if got is ERR:
                continue
            if not widens_to(got, t):
                _diag(tc, s.value, f"class attribute {c.name}.{name} is annotated {t} but the value has type {got}")
                continue
            if got != t and got.name in NUMERIC and (t.name in NUMERIC or t.name == "optional"):
                _diag(tc, s.value, f"class attribute {c.name}.{name}: CPython keeps the {got} value; write a "
                                   f"{t.elem if t.name == 'optional' else t} literal")
                continue
        else:
            t = tc.synth(s.value)
            if t is ERR:
                continue
            if t == NONE or (t.name in ("list", "dict", "set") and t.elem is None):
                _diag(tc, s.value, f"cannot infer the type of class attribute {c.name}.{name}; annotate it, "
                                   f"e.g. {name}: list[int] = []")
                continue
        s.ty = t
        s.target.ty = t
        cx.cattr[c.name][name] = (t, s)


def cattr_lookup(cx: Ctx, cls: str, name: str):
    for k in cx.mro(cls):
        if name in cx.cattr.get(k, {}):
            return k, cx.cattr[k][name][0]
    return None


# ---- C.static(...) / self.static(...) -> plain calls ---------------------------------------------------------
def _rewrite_static_calls(tc, cx: Ctx) -> None:
    def lookup(cls, m):
        for k in cx.mro(cls):
            if m in cx.statics.get(k, {}):
                return k, cx.statics[k][m]
        return None

    def make(cur_cls):
        def fn(n):
            if not (isinstance(n, A.MethodCall) and isinstance(n.recv, A.Name)):
                return None
            r = n.recv.id
            if r in cx.defs:
                target, via = r, "class"
            elif r == "self" and cur_cls is not None:
                target, via = cur_cls, "self"
            else:
                return None
            hit = lookup(target, n.method)
            if hit is None:
                return None
            owner, (fname, kind) = hit
            if kind == "classmethod" and via == "class" and owner != target:
                _diag(tc, n, f"classmethod {owner}.{n.method} called through subclass {target}: `cls` would be "
                             f"{target}, which PySub does not model; call {owner}.{n.method}(...)")
                return None
            if kind == "classmethod" and via == "self" and cx.below(owner):
                _diag(tc, n, f"classmethod {owner}.{n.method} called through self: `cls` is the run-time class of "
                             f"self, which may be a subclass; call {owner}.{n.method}(...)")
                return None
            call = A.Call(n.line, n.col, func=fname, args=n.args, kwargs=n.kwargs)
            call.display = f"{owner}.{n.method}"
            return call
        return fn

    def run(body, cur_cls):
        fn = make(cur_cls)
        for i, s in enumerate(body):
            _transform(s, fn)
            r = fn(s)
            if r is not None:
                body[i] = r
    for f in tc.mod.funcs:
        run(f.body, None)
        for p in f.params:
            if p.default is not None:
                run([p.default], None)
    for name in cx.order:
        for m in cx.defs[name].methods:
            run(m.body, name)
    run(tc.mod.main, None)


# ---- `__eq__(self, other: object)` -> other: C ----------------------------------------------------------------
def _object_params(tc, cx: Ctx, c: A.ClassDef) -> None:
    for m in c.methods:
        if m.name in FORBIDDEN:
            _diag(tc, m, f"{c.name}.{m.name} is outside the PySub subset: CPython calls it implicitly in places "
                         f"PySub does not reproduce")
        if m.name in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__") and len(m.params) == 2:
            ann = m.params[1].ann
            if ann is not None and ann.name == "object" and not getattr(ann, "args", None):
                ann.pre = Ty(c.name)          # compared with another C (or None) in PySub
                m.object_param = True


# ---- field inference ---------------------------------------------------------------------------------------
class _Infer:
    """Instance fields: class-level `x: T` declarations plus every `self.x = ...` in the methods.  Types come from
    annotations (`self.x: T = ...`), a class attribute of the same name, or the assigned values."""

    def __init__(self, tc, cx: Ctx):
        self.tc, self.cx = tc, cx
        self.allf: Dict[str, List[str]] = {}
        self.decl: Dict[str, Dict[str, A.ClassField]] = {}
        self.assigns: Dict[str, Dict[str, list]] = {}
        self.inferred: Dict[str, List[str]] = {}
        self.cache: Dict[tuple, Optional[Ty]] = {}
        self.busy: Set[tuple] = set()

    def run(self) -> None:
        cx = self.cx
        for name in cx.order:
            self._names(name)
        for name in cx.order:
            c = cx.defs[name]
            for fld in c.fields:
                if fld.ann is not None and getattr(fld.ann, "pre", None) is None:
                    fld.ann.pre = self.tc.resolve_type(fld.ann)
            for f in self.inferred[name]:
                t = self.ftype(name, f)
                first = self.assigns[name][f][0][3]
                if t is None:
                    _diag(self.tc, first, f"cannot infer the type of field {f!r} of class {name!r} from the values "
                                          f"assigned to it; annotate the first assignment, e.g. "
                                          f"`self.{f}: int = ...`, or declare `{f}: T` in the class body")
                    t = ERR
                te = A.TypeExpr(line=first.line, col=first.col, name="<inferred>")
                te.pre = t
                c.fields.append(A.ClassField(line=first.line, col=first.col, name=f, ann=te))

    def _methods(self, c: A.ClassDef) -> List[A.FuncDef]:
        ms = [m for m in c.methods if m.name == "__init__"]
        return ms + [m for m in c.methods if m.name != "__init__"]

    def _names(self, cls: str) -> None:
        cx, tc = self.cx, self.tc
        c = cx.defs[cls]
        b = cx.base.get(cls)
        inherited = list(self.allf.get(b, [])) if b else []
        self.decl[cls] = {}
        keep = []
        for fld in c.fields:
            if fld.name in inherited:
                bt = self.ftype(b, fld.name)
                t = tc.resolve_type(fld.ann)
                if bt is not None and t != bt and t is not ERR:
                    _diag(tc, fld, f"field {fld.name!r} of {cls!r} redeclares the {bt} field of a base class as {t}")
                continue
            keep.append(fld)
            self.decl[cls][fld.name] = fld
            cx.declared[cls].add(fld.name)
        c.fields = keep
        assigns: Dict[str, list] = {}
        for m in self._methods(c):
            for n in walk(m.body):
                tgt = n.target if isinstance(n, (A.Assign, A.AugAssign)) else None
                if isinstance(tgt, A.Attribute) and isinstance(tgt.value, A.Name) and tgt.value.id == "self":
                    ann = n.ann if isinstance(n, A.Assign) else None
                    val = n.value if isinstance(n, A.Assign) else None
                    assigns.setdefault(tgt.attr, []).append((val, ann, m, n))
        self.assigns[cls] = assigns
        members = {m.name for m in c.methods} | set(cx.props[cls]) | set(cx.statics[cls])
        out = []
        for f, uses in assigns.items():
            if f in inherited or f in self.decl[cls]:
                continue
            if all(v is None for v, _, _, _ in uses) and f not in cx.cattr[cls]:
                continue                       # only `self.f += ...`: typecheck reports the missing field
            if f in members:
                _diag(tc, uses[0][3], f"assigning self.{f} would hide the method/property {cls}.{f}; rename the field")
                continue
            hit = cattr_lookup(cx, cls, f)
            if hit is not None and hit[0] != cls:
                _diag(tc, uses[0][3], f"self.{f} = ... creates an instance attribute that hides class attribute "
                                      f"{hit[0]}.{f} of a base class, which is outside the PySub subset")
                continue
            if hit is not None:
                cx.cattr_field[cls].add(f)
            out.append(f)
        for k in cx.below(cls):
            pass
        self.inferred[cls] = out
        self.allf[cls] = inherited + list(self.decl[cls]) + out

    def owner(self, cls: str, f: str) -> Optional[str]:
        for k in self.cx.mro(cls):
            if f in self.decl.get(k, {}) or f in self.inferred.get(k, []):
                return k
        return None

    def quiet(self, te) -> Optional[Ty]:
        if te is None:
            return None
        n = len(self.tc.errors)
        t = self.tc.resolve_type(te)
        del self.tc.errors[n:]
        return None if t is ERR else t

    def ftype(self, cls: str, f: str) -> Optional[Ty]:
        k = self.owner(cls, f)
        if k is None:
            return None
        key = (k, f)
        if key in self.cache:
            return self.cache[key]
        if key in self.busy:
            return None
        self.busy.add(key)
        try:
            t = self._ftype(k, f)
        finally:
            self.busy.discard(key)
        self.cache[key] = t
        return t

    def _ftype(self, k: str, f: str) -> Optional[Ty]:
        if f in self.decl.get(k, {}):
            fld = self.decl[k][f]
            pre = getattr(fld.ann, "pre", None)
            return pre if pre is not None else self.quiet(fld.ann)
        uses = self.assigns[k][f]
        for v, ann, m, n in uses:
            if ann is not None:
                return self.tc.resolve_type(ann)
        if f in self.cx.cattr[k]:
            return self.cx.cattr[k][f][0]
        guesses = [self.guess(k, v, m, 0) for v, _, m, _ in uses if v is not None]
        known = [g for g in guesses if g is not None and g != NONE]
        if not known:
            known = self._evidence(k, f)
        known = [g for g in known if g is not None]
        if not known:
            return None
        t = known[0]
        for g in known[1:]:
            if g == t:
                continue
            if t.name in ("list", "dict", "set") and t.elem is None and g.name == t.name:
                t = g
                continue
            if g.name in ("list", "dict", "set") and g.elem is None and g.name == t.name:
                continue
            j = join(t, g) if is_cls(self.tc, t) and is_cls(self.tc, g) else None
            if j is not None:
                t = j
                continue
            return None
        if t.name in ("list", "dict", "set") and t.elem is None:
            ev = [g for g in self._evidence(k, f) if g is not None and g.name == t.name]
            if not ev:
                return None
            t = ev[0]
        if any(g == NONE for g in guesses) and not is_cls(self.tc, t):
            from .types_ext import opt_of
            t = opt_of(t)
        return t

    def _evidence(self, k: str, f: str) -> List[Optional[Ty]]:
        """`self.f.append(x)` -> list[type(x)]; `self.f[k] = v` -> dict[type(k), type(v)]; `self.f.add(x)` -> set."""
        out = []
        for m in self.cx.defs[k].methods:
            for n in walk(m.body):
                if isinstance(n, A.MethodCall) and _is_self_attr(n.recv, f) and n.args:
                    if n.method == "append":
                        g = self.guess(k, n.args[0], m, 0)
                        out.append(list_of(g) if g is not None and g != NONE else None)
                    elif n.method == "insert" and len(n.args) == 2:
                        g = self.guess(k, n.args[1], m, 0)
                        out.append(list_of(g) if g is not None and g != NONE else None)
                    elif n.method == "add":
                        g = self.guess(k, n.args[0], m, 0)
                        out.append(Ty("set", g) if g is not None and g.name in PRIM else None)
                elif isinstance(n, A.Assign) and isinstance(n.target, A.Subscript) and _is_self_attr(n.target.value, f):
                    kt, vt = self.guess(k, n.target.index, m, 0), self.guess(k, n.value, m, 0)
                    if kt is not None and vt is not None and vt != NONE and kt.name in ("int", "str"):
                        out.append(dict_of(kt, vt))
        return out

    def guess(self, cls: str, e, m: A.FuncDef, depth: int) -> Optional[Ty]:
        if e is None or depth > 8:
            return None
        g = lambda x: self.guess(cls, x, m, depth + 1)          # noqa: E731
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
        if isinstance(e, A.UnaryOp):
            if e.op == "not":
                return BOOL
            t = g(e.operand)
            return t if t is not None and t.name in ("int", "float") else INT if t == BOOL else None
        if isinstance(e, A.Name):
            return self._name(cls, e.id, m, depth)
        if isinstance(e, A.Call):
            return self._call(cls, e, m, depth)
        if isinstance(e, A.ListLit):
            if not e.elts:
                return Ty("list", None)
            ts = [g(x) for x in e.elts]
            return list_of(ts[0]) if ts[0] is not None and ts[0] != NONE and all(t == ts[0] for t in ts) else None
        if isinstance(e, A.DictLit):
            if not e.keys:
                return Ty("dict", None, None)
            kt, vt = g(e.keys[0]), g(e.values[0])
            return dict_of(kt, vt) if kt is not None and vt is not None and vt != NONE else None
        if isinstance(e, A.SetLit):
            t = g(e.elts[0]) if e.elts else None
            return Ty("set", t) if t is not None and t.name in PRIM else None
        if isinstance(e, A.TupleLit):
            ts = [g(x) for x in e.elts]
            return Ty("tuple", elts=tuple(ts)) if all(t is not None and t != NONE for t in ts) else None
        if isinstance(e, A.Attribute):
            if isinstance(e.value, A.Name) and e.value.id in self.cx.defs:
                hit = cattr_lookup(self.cx, e.value.id, e.attr)
                return hit[1] if hit else None
            rt = g(e.value)
            if rt is not None and rt.name in self.cx.defs:
                hit = cattr_lookup(self.cx, rt.name, e.attr)
                return self.ftype(rt.name, e.attr) or (hit[1] if hit else None)
            return None
        if isinstance(e, A.BinOp):
            lt, rt = g(e.left), g(e.right)
            if lt is None or rt is None:
                return None
            if lt.name in NUMERIC and rt.name in NUMERIC:
                if e.op == "/":
                    return FLOAT
                return FLOAT if FLOAT in (lt, rt) else INT
            if e.op == "+" and lt == rt and lt.name in ("str", "list"):
                return lt
            if e.op == "*" and {lt.name, rt.name} <= {"str", "int"} and STR in (lt, rt):
                return STR
            if e.op == "*" and lt.name == "list" and rt.name == "int":
                return lt
            return None
        if isinstance(e, A.IfExp):
            bt, ot = g(e.body), g(e.orelse)
            return bt if bt == ot else None
        if isinstance(e, (A.Compare,)):
            return BOOL
        if isinstance(e, A.BoolOp):
            ts = [g(x) for x in e.values]
            return ts[0] if all(t == ts[0] for t in ts) else None
        if isinstance(e, A.Subscript):
            bt = g(e.value)
            if bt is None:
                return None
            if bt.name == "tuple" and isinstance(e.index, A.IntLit) and e.index.value < len(bt.elts):
                return bt.elts[e.index.value]
            if bt.name in ("list", "dict"):
                return bt.elem
            if bt == STR:
                return STR
            return None
        if isinstance(e, A.MethodCall):
            if isinstance(e.recv, A.Name) and e.recv.id == "self":
                for k in self.cx.mro(cls):
                    for mm in self.cx.defs[k].methods:
                        if mm.name == e.method:
                            return self.quiet(mm.ret) if mm.ret is not None else NONE
            rt = g(e.recv)
            if rt == STR and e.method in ("upper", "lower", "strip", "lstrip", "rstrip", "replace", "title",
                                          "capitalize", "join"):
                return STR
            if rt == STR and e.method == "split":
                return list_of(STR)
            if rt is not None and rt.name in self.cx.defs:
                for k in self.cx.mro(rt.name):
                    for mm in self.cx.defs[k].methods:
                        if mm.name == e.method:
                            return self.quiet(mm.ret) if mm.ret is not None else NONE
            if rt is not None and rt.name == "list" and e.method in ("pop", "copy"):
                return rt.elem if e.method == "pop" else rt
            if rt is not None and rt.name == "dict" and e.method == "get" and len(e.args) == 2:
                return rt.elem
            return None
        if isinstance(e, A.ListComp):
            return None
        return None

    def _name(self, cls: str, name: str, m: A.FuncDef, depth: int) -> Optional[Ty]:
        if name == "self":
            return Ty(cls)
        for p in m.params:
            if p.name == name:
                if p.ann is None:
                    return None
                return self.quiet(p.ann)
        for n in walk(m.body):
            if isinstance(n, A.Assign) and isinstance(n.target, A.Name) and n.target.id == name:
                if n.ann is not None:
                    return self.quiet(n.ann)
                t = self.guess(cls, n.value, m, depth + 1)
                if t is not None:
                    return t
            if isinstance(n, A.ForRange) and n.var == name:
                return INT
            if isinstance(n, A.ForEach) and n.var == name:
                it = self.guess(cls, n.iter, m, depth + 1)
                if it is not None and it.name == "list":
                    return it.elem
                if it == STR:
                    return STR
        for s in self.tc.mod.main:
            if isinstance(s, A.Assign) and isinstance(s.target, A.Name) and s.target.id == name:
                if s.ann is not None:
                    return self.quiet(s.ann)
                if isinstance(s.value, (A.IntLit, A.FloatLit, A.StrLit, A.BoolLit)):
                    return self.guess(cls, s.value, m, depth + 1)
                return None
        return None

    def _call(self, cls: str, e: A.Call, m: A.FuncDef, depth: int) -> Optional[Ty]:
        f = e.func
        if f in self.cx.defs:
            return Ty(f)
        for fd in self.tc.mod.funcs:
            if fd.name == f:
                return self.quiet(fd.ret) if fd.ret is not None else NONE
        simple = {"int": INT, "len": INT, "ord": INT, "float": FLOAT, "str": STR, "input": STR, "chr": STR,
                  "repr": STR, "bool": BOOL, "round": None}
        if f in simple and simple[f] is not None:
            return simple[f]
        if f in ("abs", "min", "max", "sum") and e.args:
            t = self.guess(cls, e.args[0], m, depth + 1)
            if t is not None and t.name == "list" and f != "abs":
                t = t.elem
            return t if t is not None and t.name in ("int", "float") else None
        if f in ("list", "sorted") and e.args:
            t = self.guess(cls, e.args[0], m, depth + 1)
            return t if t is not None and t.name == "list" else list_of(STR) if t == STR else None
        if f == "set" and not e.args:
            return Ty("set", None)
        if f == "__pythia_unpack" and e.args:
            return self.guess(cls, e.args[0], m, depth + 1)
        return None


def _is_self_attr(e, f: str) -> bool:
    return isinstance(e, A.Attribute) and e.attr == f and isinstance(e.value, A.Name) and e.value.id == "self"


# ---- pass 1 hooks ------------------------------------------------------------------------------------------
def inherit(tc, c: A.ClassDef, info) -> None:
    """Start of pass 1 for class c: the base class's fields come first (the base was processed already)."""
    cx = ctx(tc)
    b = cx.base.get(c.name) if cx else None
    if b is None:
        return
    binfo = tc.classes[b]
    for n, t in zip(binfo.field_names, binfo.fields):
        info.field_index[n] = len(info.fields)
        info.fields.append(t)
        info.field_names.append(n)


def needs_init(tc, c: A.ClassDef, info) -> bool:
    """Pass 1: a class with class-level field declarations needs an __init__ (its own or a base class's)."""
    cx = ctx(tc)
    if cx is None:
        return True
    if not cx.declared.get(c.name):
        return False
    return not any(any(m.name == "__init__" for m in cx.defs[k].methods) for k in cx.mro(c.name))


def after_pass1(tc) -> None:
    cx = ctx(tc)
    if cx is None:
        return
    for name in cx.order:
        info = tc.classes[name]
        b = cx.base.get(name)
        if b is None:
            continue
        binfo = tc.classes[b]
        for k, bsig in binfo.methods.items():
            sig = info.methods.get(k)
            if sig is None:
                info.methods[k] = bsig
            elif k != "__init__" and sig.owner == name:
                _check_override(tc, cx, name, sig, bsig)
        if info.init is None:
            info.init = binfo.init
        for p, d in cx.props[b].items():
            if p in cx.props[name]:
                g0, g1 = d["get"], cx.props[name][p]["get"]
                s0 = binfo.methods.get(g0.name)
                s1 = info.methods.get(g1.name)
                if s0 and s1 and s0.ret != s1.ret:
                    _diag(tc, g1, f"property {name}.{p} overrides {b}.{p} with a different type")
            else:
                cx.props[name][p] = d
    nxt = 0
    for name in cx.order:
        if cx.base.get(name) is None and cx.subs.get(name):
            for k in [name] + cx.below(name):
                cx.cid[k] = nxt
                nxt += 1
            for k in [name] + cx.below(name):
                cx.hi[k] = cx.cid[k] + 1 + len(cx.below(k))
    tc.cx_names = [n for n in sorted(cx.cid, key=lambda k: cx.cid[k])]
    for name in cx.order:
        _check_dunders(tc, cx, name)
        for f in list(cx.statics[name]):
            pass
    for name in cx.order:
        for k in ("__eq__", "__ne__"):
            if k in cx.own(name) and cx.in_hier(name):
                _diag(tc, cx.defs[name], f"{name}.{k}: classes that take part in inheritance cannot define {k} in "
                                         f"PySub (CPython's reflected-operand rules for subclasses are not modelled)")


def _check_override(tc, cx: Ctx, cls: str, sig, bsig) -> None:
    def defaults(s):
        return [(_const_key(p.default)) for p in s.node.params[1:]] if s.node is not None else []
    ok = len(sig.params) == len(bsig.params) and all(a == b for a, b in zip(sig.params, bsig.params))
    ret_ok = sig.ret == bsig.ret or (is_cls(tc, sig.ret) and is_cls(tc, bsig.ret) and cx.is_sub(sig.ret.name,
                                                                                               bsig.ret.name))
    if not ok or not ret_ok:
        _diag(tc, sig.node, f"{sig.name} overrides {bsig.name} with a different signature "
                            f"({', '.join(map(str, sig.params))}) -> {sig.ret} vs "
                            f"({', '.join(map(str, bsig.params))}) -> {bsig.ret}; PySub needs identical parameter "
                            f"types to dispatch through a base-class reference")
    elif defaults(sig) != defaults(bsig):
        _diag(tc, sig.node, f"{sig.name} overrides {bsig.name} with different default values, which PySub does not "
                            f"dispatch")


def _const_key(d):
    if d is None:
        return None
    if isinstance(d, (A.IntLit, A.FloatLit, A.StrLit, A.BoolLit)):
        return (type(d).__name__, d.value)
    if isinstance(d, A.NoneLit):
        return "None"
    if isinstance(d, A.UnaryOp):
        return (d.op, _const_key(d.operand))
    return id(d)


def _check_dunders(tc, cx: Ctx, cls: str) -> None:
    info = tc.classes[cls]
    for m in cx.defs[cls].methods:
        k = m.name
        if not (k.startswith("__") and k.endswith("__")) or k == "__init__" or k == "__post_init__":
            continue
        sig = info.methods.get(k)
        if sig is None:
            continue
        n = len(sig.params)

        def bad(msg):
            _diag(tc, m, f"{cls}.{k}: {msg}")
        if k in ("__str__", "__repr__"):
            if n or sig.ret != STR:
                bad("must take only self and return str")
        elif k == "__len__":
            if n or sig.ret != INT:
                bad("must take only self and return int")
        elif k == "__bool__":
            if n or sig.ret != BOOL:
                bad("must take only self and return bool")
        elif k in ("__eq__", "__ne__", "__lt__", "__le__", "__gt__", "__ge__", "__contains__"):
            if n != 1 or sig.ret != BOOL:
                bad("must take self and one other value and return bool in PySub")
        elif k in UNARY.values() or k == "__abs__":
            if n:
                bad("must take only self")
        elif k == "__getitem__":
            if n != 1:
                bad("must take self and one index")
        elif k == "__setitem__":
            if n != 2 or sig.ret != NONE:
                bad("must take self, an index and a value and return None")
        elif k[2:-2] in ARITH.values() or (k[2:3] in "ri" and k[3:-2] in ARITH.values()):
            if n != 1:
                bad("must take self and one operand")
        elif k not in FORBIDDEN:
            bad("this special method is outside the PySub subset")


# ---- expressions -------------------------------------------------------------------------------------------
def _class_name_ref(tc, e) -> Optional[str]:
    """`C` used as a value in `C.attr` / `C.method(...)` (a class name that no variable shadows)."""
    if isinstance(e, A.Name) and e.id in getattr(tc, "classes", {}) and tc.scope.lookup(e.id) is None:
        return e.id
    return None


def _enclosing_class(tc) -> Optional[str]:
    fn = tc.cur_fn
    return fn.owner if fn is not None else None


def synth(tc, e) -> Optional[Ty]:
    """Hook at the top of TypeChecker._synth; None = not a class construct."""
    cx = ctx(tc)
    if cx is None or not cx.defs and not isinstance(e, A.Call):
        return None
    if isinstance(e, A.Name) and e.id == "NotImplemented":
        return _notimpl(tc, e)
    if isinstance(e, A.Attribute):
        return _attr(tc, cx, e)
    if isinstance(e, A.MethodCall):
        return _mcall(tc, cx, e)
    if isinstance(e, A.Call):
        return _call(tc, cx, e)
    if isinstance(e, A.Compare):
        return _compare(tc, cx, e)
    if isinstance(e, A.UnaryOp) and e.op in UNARY:
        t = tc.synth(e.operand)
        if not is_cls(tc, t):
            return None
        return _unary(tc, cx, e, t, UNARY[e.op], f"bad operand type for unary {e.op}")
    if isinstance(e, A.Subscript):
        t = tc.synth(e.value)
        if not is_cls(tc, t):
            return None
        r = resolve(tc, t.name, "__getitem__")
        if r is None:
            return _diag(tc, e, f"{t.name!r} object is not subscriptable (no __getitem__)")
        _want_arg(tc, e.index, r[1].params[0], f"{t.name}.__getitem__")
        _no_dispatch_risk(tc, e, t.name, "__getitem__")
        e.getitem = (t.name, r[0])
        return r[1].ret
    return None


def _notimpl(tc, e) -> Ty:
    fn = tc.cur_fn
    if fn is None or fn.owner is None or fn.node.name not in ("__eq__", "__ne__"):
        return _diag(tc, e, "NotImplemented is supported only as the result of __eq__ / __ne__ in PySub")
    e.notimpl = fn.node.name
    return BOOL


def _attr(tc, cx: Ctx, e) -> Optional[Ty]:
    cname = _class_name_ref(tc, e.value)
    if cname is not None:
        hit = cattr_lookup(cx, cname, e.attr)
        if hit is None:
            if any(e.attr in cx.statics.get(k, {}) for k in cx.mro(cname)) or resolve(tc, cname, e.attr):
                return _diag(tc, e, f"{cname}.{e.attr} is a method; PySub has no first-class functions (call it)")
            return _diag(tc, e, f"class {cname!r} has no class attribute {e.attr!r}")
        e.value.ty = NONE
        e.cattr = (cname, hit[0], False)
        return hit[1]
    if isinstance(e.value, A.Call) and e.value.func == "super":
        return _diag(tc, e, "super().attr is supported only for method calls: super().method(...)")
    t = tc.synth(e.value)
    if not is_cls(tc, t):
        return None
    info = tc.classes[t.name]
    if e.attr in info.field_index:
        return None
    props = cx.props.get(t.name, {})
    if e.attr in props:
        g = props[e.attr]["get"]
        sig = info.methods.get(g.name)
        e.prop = (t.name, g.name)
        return sig.ret if sig is not None else ERR
    hit = cattr_lookup(cx, t.name, e.attr)
    if hit is not None:
        e.cattr = (t.name, hit[0], True)
        return hit[1]
    if any(e.attr in cx.statics.get(k, {}) for k in cx.mro(t.name)) or e.attr in info.methods:
        return _diag(tc, e, f"{t.name}.{e.attr} is a method; PySub has no first-class functions (call it)")
    return None


def _want_arg(tc, a, want: Ty, what: str) -> None:
    got = tc.check_expr(a, want)
    if got is not ERR and not widens_to(got, want):
        _diag(tc, a, f"argument of {what}: expected {want}, found {got}")


def _mcall(tc, cx: Ctx, e) -> Optional[Ty]:
    from .types_ext import bind_args
    if isinstance(e.recv, A.Call) and e.recv.func == "super":
        return _super_call(tc, cx, e)
    cname = _class_name_ref(tc, e.recv)
    if cname is not None:                                   # C.method(obj, ...): an unbound instance-method call
        r = resolve(tc, cname, e.method)
        if r is None or isinstance(r[1], SynSig):
            return _diag(tc, e, f"class {cname!r} has no method {e.method!r}")
        owner, sig = r
        if not e.args:
            return _diag(tc, e, f"{cname}.{e.method}() needs the instance as its first argument")
        st = tc.synth(e.args[0])
        if st is not ERR and not (is_cls(tc, st) and cx.is_sub(st.name, owner)):
            return _diag(tc, e.args[0], f"{cname}.{e.method}(): the first argument must be a {owner} instance, "
                                        f"found {st}")
        rest = A.MethodCall(e.line, e.col, recv=e.args[0], method=e.method, args=e.args[1:], kwargs=e.kwargs)
        if not bind_args(tc, rest, sig, f"{cname}.{e.method}"):
            return ERR
        for i, (a, want) in enumerate(zip(rest.args, sig.params)):
            _want_arg(tc, a, want, f"{cname}.{e.method}()")
        e.recv.ty = NONE
        e.args, e.kwargs = [e.args[0]] + rest.args, []
        e.arg_order = getattr(rest, "arg_order", None)
        if e.arg_order is not None:
            e.arg_order = [0] + [j + 1 for j in e.arg_order]
        e.unbound = owner
        return sig.ret
    t = tc.synth(e.recv)
    if is_cls(tc, t):
        info = tc.classes[t.name]
        if e.method not in info.methods:
            if any(e.method in cx.statics.get(k, {}) for k in cx.mro(t.name)):
                return _diag(tc, e, f"{t.name}.{e.method} is a static/class method: call it through the class, "
                                    f"{t.name}.{e.method}(...)")
            if e.method in cx.props.get(t.name, {}):
                return _diag(tc, e, f"{t.name}.{e.method} is a property: read it without calling it")
        return None
    if t.name == "list" and is_cls(tc, t.elem) and e.method == "sort" and not _has_kw(e, "key"):
        tc.check_kwargs(e, {"reverse"})
        if e.args:
            return _diag(tc, e, "sort() takes no positional arguments")
        if _order_plan(tc, e, t.elem, "<") is None:
            return ERR
        e.cls_sort = t.elem.name
        return NONE
    return None


def _has_kw(e, name: str) -> bool:
    return any(k.name == name for k in (getattr(e, "kwargs", None) or []))


def _super_call(tc, cx: Ctx, e) -> Ty:
    from .types_ext import bind_args
    sup = e.recv
    cur = _enclosing_class(tc)
    if cur is None or tc.scope.lookup("self") is None:
        return _diag(tc, e, "super() is supported only inside an instance method")
    if sup.args and not (len(sup.args) == 2 and isinstance(sup.args[0], A.Name) and sup.args[0].id == cur
                         and isinstance(sup.args[1], A.Name) and sup.args[1].id == "self"):
        return _diag(tc, e, f"super(...) with arguments other than ({cur}, self) is outside the PySub subset")
    b = cx.base.get(cur)
    r = resolve(tc, b, e.method) if b is not None else None
    sup.ty = NONE
    for a in sup.args:
        a.ty = NONE
    if r is None:
        if e.method == "__init__" and not e.args and not e.kwargs:
            e.super_owner = None                                 # object.__init__(): nothing to do
            return NONE
        return _diag(tc, e, f"no base class of {cur!r} defines {e.method!r}")
    owner, sig = r
    if isinstance(sig, SynSig):
        return _diag(tc, e, f"super().{e.method}() of a generated dataclass method is outside the PySub subset")
    if not bind_args(tc, e, sig, f"super().{e.method}"):
        return ERR
    for a, want in zip(e.args, sig.params):
        _want_arg(tc, a, want, f"super().{e.method}()")
    e.super_owner = owner
    return sig.ret


def _call(tc, cx: Ctx, e) -> Optional[Ty]:
    f = e.func
    if f == "super":
        return _diag(tc, e, "super() is supported only as super().method(...)")
    if f in ("str", "repr", "len", "bool", "abs") and len(e.args) == 1 and not e.kwargs:
        t = tc.synth(e.args[0])
        if f == "repr" and t.name == "list" and is_cls(tc, t.elem):
            if not can_repr(tc, t.elem.name):
                return _diag(tc, e.args[0], f"repr() of a list of {t.elem.name}: class {t.elem.name!r} has no "
                                            f"__repr__ (CPython would show memory addresses)")
            return STR
        if not is_cls(tc, t):
            return None
        e.cls_builtin = (f, t.name)
        if f == "str":
            return STR if can_str(tc, t.name, e.args[0]) else ERR
        if f == "repr":
            if not can_repr(tc, t.name):
                return _diag(tc, e.args[0], f"repr() of a {t.name}: class {t.name!r} defines no __repr__, and "
                                            f"CPython's default shows a memory address")
            return STR
        if f == "len":
            miss = all_have(tc, t.name, lambda d: resolve(tc, d, "__len__"))
            if miss is not None:
                return _diag(tc, e.args[0], f"object of type {miss!r} has no len()")
            return INT
        if f == "abs":
            return _unary(tc, cx, e, t, "__abs__", "bad operand type for abs()")
        return BOOL
    if f in ("sorted", "min", "max") and e.args and not _has_kw(e, "key"):
        ts = [tc.synth(a) for a in e.args]
        if f == "sorted" or len(e.args) == 1:
            t = ts[0]
            if not (t.name == "list" and is_cls(tc, t.elem)):
                return None
            tc.check_kwargs(e, {"reverse"} if f == "sorted" else set())
            if len(e.args) != 1:
                return _diag(tc, e, f"{f}() takes exactly one argument in PySub")
            if _order_plan(tc, e, t.elem, "<" if f != "max" else ">") is None:
                return ERR
            e.cls_order = (f, t.elem.name)
            return t if f == "sorted" else t.elem
        if not any(is_cls(tc, t) for t in ts):
            return None
        tc.check_kwargs(e, set())
        acc = ts[0]
        for t in ts[1:]:
            if acc == t or widens_to(t, acc):
                continue
            if widens_to(acc, t):
                acc = t
                continue
            return _diag(tc, e, f"{f}() arguments have unrelated types {acc} and {t}")
        if not is_cls(tc, acc):
            return _diag(tc, e, f"{f}() mixes objects and values of type {acc}")
        if _order_plan(tc, e, acc, "<" if f == "min" else ">") is None:
            return ERR
        e.cls_order = (f, acc.name)
        return acc
    return None


def can_repr(tc, cls: str) -> bool:
    return all_have(tc, cls, lambda d: resolve(tc, d, "__repr__")) is None


def can_str(tc, cls: str, node=None) -> bool:
    """str(obj) / print(obj) / f"{obj}": every class the reference may hold has __str__ or __repr__."""
    miss = all_have(tc, cls, lambda d: resolve_str(tc, d))
    if miss is not None and node is not None:
        _diag(tc, node, f"cannot convert a {miss} instance to str: class {miss!r} defines neither __str__ nor "
                        f"__repr__, and CPython's default shows a memory address")
    return miss is None


def print_ok(tc, t: Ty, node) -> bool:
    """typecheck's print(): a class instance (via __str__/__repr__) or a list of them (via __repr__)."""
    if is_cls(tc, t):
        return can_str(tc, t.name, node)
    if t.name == "list" and is_cls(tc, t.elem):
        if can_repr(tc, t.elem.name):
            return True
        _diag(tc, node, f"cannot print a list of {t.elem.name} instances: class {t.elem.name!r} has no __repr__ "
                        f"(CPython would show memory addresses)")
        return True
    return False


def _unary(tc, cx: Ctx, e, t: Ty, name: str, what: str) -> Ty:
    r = resolve(tc, t.name, name)
    if r is None:
        return _diag(tc, e, f"{what}: {t.name!r} (no {name})")
    e.cls_unary = (t.name, name)
    return r[1].ret


def _risk(tc, cls: str, name: str) -> Optional[str]:
    """A proper subclass of `cls` that defines `name` itself (CPython may then prefer its reflected method)."""
    cx = ctx(tc)
    for d in cx.below(cls):
        if name in cx.own(d):
            return d
    return None


def _no_dispatch_risk(tc, e, cls: str, name: str) -> None:
    pass


def _binary_plan(tc, e, op: str, lt: Ty, rt: Ty, fwd: str, refl: str, what: str):
    """Which user method implements `lt op rt`: ('fwd', owner_cls) / ('refl', owner_cls), plus the reflected
    fallback flags the emitter needs for None operands.  None after an error."""
    lc, rc = is_cls(tc, lt), is_cls(tc, rt)
    fr = resolve(tc, lt.name, fwd) if lc else None
    rr = resolve(tc, rt.name, refl) if rc else None
    for side, t in (("left", lt), ("right", rt)):
        if is_cls(tc, t):
            d = _risk(tc, t.name, refl)
            if d is not None:
                _diag(tc, e, f"{what}: subclass {d!r} of {t.name!r} defines {refl}, and CPython then prefers the "
                             f"reflected method depending on the run-time classes; outside the PySub subset")
                return None
    if fr is not None:
        want = fr[1].params[0]
        if not (rt == NONE and (is_cls(tc, want) or want.name == "optional")) and not widens_to(rt, want):
            _diag(tc, e, f"{what}: {lt.name}.{fwd} takes {want}, found {rt}")
            return None
        ok_refl = rr is not None and (lt == NONE or widens_to(lt, rr[1].params[0]))
        return {"plan": "fwd", "sig": fr[1], "owner": fr[0], "lt": lt, "rt": rt, "refl": rr if ok_refl else None,
                "fwd_name": fwd, "refl_name": refl, "ret": fr[1].ret}
    if rr is not None:
        want = rr[1].params[0]
        if not (lt == NONE and is_cls(tc, want)) and not widens_to(lt, want):
            _diag(tc, e, f"{what}: {rt.name}.{refl} takes {want}, found {lt}")
            return None
        return {"plan": "refl", "sig": rr[1], "owner": rr[0], "lt": lt, "rt": rt, "refl": rr, "fwd_name": fwd,
                "refl_name": refl, "ret": rr[1].ret}
    return None


def _tyname(t: Ty) -> str:
    return "NoneType" if t == NONE else t.name


def binop(tc, node, op: str, lt: Ty, rt: Ty) -> Optional[Ty]:
    """Hook at the top of TypeChecker.binop_result: arithmetic on user objects through their dunder methods."""
    if ctx(tc) is None or op not in ARITH or ERR in (lt, rt) or not (is_cls(tc, lt) or is_cls(tc, rt)):
        return None
    name = ARITH[op]
    what = f"unsupported operand type(s) for {op}: '{_tyname(lt)}' and '{_tyname(rt)}'"
    plan = _binary_plan(tc, node, op, lt, rt, f"__{name}__", f"__r{name}__", what)
    if plan is None:
        if not tc.errors or tc.errors[-1].line != node.line or what not in tc.errors[-1].msg:
            _diag(tc, node, what)
        return ERR
    plan["op"] = op
    node.dunder = plan
    return plan["ret"]


def _order_plan(tc, e, t: Ty, op: str):
    fwd, refl = CMP[op]
    what = f"'{op}' not supported between instances of '{t.name}' and '{t.name}'"
    plan = _binary_plan(tc, e, op, t, t, fwd, refl, what)
    if plan is None:
        if not tc.errors or what not in tc.errors[-1].msg:
            _diag(tc, e, what)
        return None
    plan["op"] = op
    if plan["ret"] != BOOL:
        _diag(tc, e, f"{plan['owner']}.{plan['fwd_name'] if plan['plan'] == 'fwd' else plan['refl_name']} must "
                     f"return bool to be used for ordering in PySub")
        return None
    return plan


def _compare(tc, cx: Ctx, e) -> Optional[Ty]:
    op = e.op
    if op in ("in", "not in"):
        rt = tc.synth(e.right)
        if not is_cls(tc, rt):
            return None
        lt = tc.synth(e.left)
        r = resolve(tc, rt.name, "__contains__")
        if r is None:
            return _diag(tc, e, f"argument of type {rt.name!r} is not iterable (no __contains__)")
        if lt is not ERR and not widens_to(lt, r[1].params[0]):
            return _diag(tc, e, f"{rt.name}.__contains__ takes {r[1].params[0]}, found {lt}")
        e.contains = (rt.name, r[0])
        return BOOL
    if isinstance(e.left, A.Call) and e.left.func == "type" or isinstance(e.right, A.Call) and e.right.func == "type":
        return None
    lt, rt = tc.synth(e.left), tc.synth(e.right)
    if ERR in (lt, rt) or not (is_cls(tc, lt) or is_cls(tc, rt)):
        return None
    if op in ("is", "is not"):
        if NONE in (lt, rt):
            return None
        if is_cls(tc, lt) and is_cls(tc, rt) and (cx.is_sub(lt.name, rt.name) or cx.is_sub(rt.name, lt.name)):
            e.identity = True
            return BOOL
        return None
    if op in ("==", "!="):
        eq_l = resolve(tc, lt.name, "__eq__") if is_cls(tc, lt) else None
        eq_r = resolve(tc, rt.name, "__eq__") if is_cls(tc, rt) else None
        if NONE in (lt, rt) and eq_l is None and eq_r is None:
            return None                                          # identity test (types_ext)
        if not (NONE in (lt, rt) or (is_cls(tc, lt) and is_cls(tc, rt)
                                     and (cx.is_sub(lt.name, rt.name) or cx.is_sub(rt.name, lt.name)))):
            if eq_l is None and eq_r is None:
                return _diag(tc, e, f"cannot compare {lt} with {rt}")
        for r, other in ((eq_l, rt), (eq_r, lt)):
            if r is not None and other != NONE and not widens_to(other, r[1].params[0]):
                return _diag(tc, e, f"{r[0]}.__eq__ takes {r[1].params[0]}, found {other}")
        ne_l = resolve(tc, lt.name, "__ne__") if is_cls(tc, lt) else None
        ne_r = resolve(tc, rt.name, "__ne__") if is_cls(tc, rt) else None
        e.cls_eq = {"eq_l": eq_l, "eq_r": eq_r, "ne_l": ne_l, "ne_r": ne_r, "lt": lt, "rt": rt}
        return BOOL
    if op in CMP:
        what = f"'{op}' not supported between instances of '{_tyname(lt)}' and '{_tyname(rt)}'"
        plan = _binary_plan(tc, e, op, lt, rt, CMP[op][0], CMP[op][1], what)
        if plan is None:
            if not tc.errors or what not in tc.errors[-1].msg:
                _diag(tc, e, what)
            return ERR
        plan["op"] = op
        e.dunder = plan
        return plan["ret"]
    return None


# ---- statements --------------------------------------------------------------------------------------------
def check_stmt(tc, s) -> bool:
    """Hook at the top of TypeChecker.check_stmt; True = handled here."""
    cx = ctx(tc)
    if cx is None or not cx.defs:
        return False
    if isinstance(s, A.Assign) and isinstance(s.target, A.Attribute):
        return _assign_attr(tc, cx, s, s.target, s.value, None)
    if isinstance(s, A.AugAssign) and isinstance(s.target, A.Attribute):
        return _assign_attr(tc, cx, s, s.target, s.value, s.op)
    if isinstance(s, A.Assign) and isinstance(s.target, A.Subscript):
        bt = tc.synth(s.target.value)
        if not is_cls(tc, bt):
            return False
        r = resolve(tc, bt.name, "__setitem__")
        if r is None:
            _diag(tc, s.target, f"{bt.name!r} object does not support item assignment (no __setitem__)")
            return True
        _want_arg(tc, s.target.index, r[1].params[0], f"{bt.name}.__setitem__")
        _want_arg(tc, s.value, r[1].params[1], f"{bt.name}.__setitem__")
        s.setitem = (bt.name, r[0])
        return True
    if isinstance(s, A.AugAssign) and isinstance(s.target, A.Subscript):
        bt = tc.synth(s.target.value)
        if is_cls(tc, bt):
            _diag(tc, s, f"augmented assignment to an item of a {bt.name} instance is outside the PySub subset; "
                         f"write x[i] = x[i] {s.op} v")
            return True
        return False
    if isinstance(s, A.AugAssign) and isinstance(s.target, A.Name):
        t = tc.synth(s.target)
        if not is_cls(tc, t):
            return False
        name = "__i" + ARITH.get(s.op, "?") + "__"
        r = resolve(tc, t.name, name)
        if r is None:
            return False                                         # a = a op b (binop hook)
        v = tc.synth(s.value)
        if v is not ERR and not widens_to(v, r[1].params[0]):
            _diag(tc, s.value, f"{t.name}.{name} takes {r[1].params[0]}, found {v}")
        elif not widens_to(r[1].ret, t):
            _diag(tc, s, f"{t.name}.{name} returns {r[1].ret}, which cannot be stored back into {s.target.id!r} ({t})")
        s.iop = (t.name, name)
        s.ty = t
        return True
    return False


def _assign_attr(tc, cx: Ctx, s, tgt, value, aug: Optional[str]) -> bool:
    cname = _class_name_ref(tc, tgt.value)
    if cname is not None:                                       # C.X = v / C.X += v
        hit = cattr_lookup(cx, cname, tgt.attr)
        if hit is None:
            _diag(tc, tgt, f"class {cname!r} has no class attribute {tgt.attr!r} (PySub does not add class "
                           f"attributes after the class statement)")
            return True
        if hit[0] != cname:
            _diag(tc, tgt, f"assigning {cname}.{tgt.attr} would create a new class attribute shadowing "
                           f"{hit[0]}.{tgt.attr}; outside the PySub subset")
            return True
        tgt.value.ty = NONE
        tgt.cattr = (cname, cname, False)
        tgt.ty = hit[1]
        _store(tc, s, tgt, value, aug, hit[1], f"class attribute {cname}.{tgt.attr}")
        s.cattr_set = True
        return True
    rt = tc.synth(tgt.value)
    if not is_cls(tc, rt):
        return False
    info = tc.classes[rt.name]
    if tgt.attr in info.field_index:
        if rt.name in cx.dc and cx.dc[rt.name]["frozen"] and not getattr(getattr(tc.cur_fn, "node", None),
                                                                          "dc_init", False):
            _diag(tc, tgt, f"cannot assign to field {tgt.attr!r} of frozen dataclass {rt.name!r} "
                           f"(CPython raises FrozenInstanceError)")
            return True
        return False
    props = cx.props.get(rt.name, {})
    if tgt.attr in props:
        st = props[tgt.attr]["set"]
        if st is None:
            _diag(tc, tgt, f"property {tgt.attr!r} of {rt.name!r} object has no setter")
            return True
        gsig = info.methods.get(props[tgt.attr]["get"].name)
        ssig = info.methods.get(st.name)
        if gsig is None or ssig is None:
            return True
        tgt.ty = gsig.ret
        tgt.prop = (rt.name, props[tgt.attr]["get"].name)
        _store(tc, s, tgt, value, aug, ssig.params[0], f"property {rt.name}.{tgt.attr}")
        s.prop_set = (rt.name, st.name)
        return True
    hit = cattr_lookup(cx, rt.name, tgt.attr)
    if hit is not None:
        _diag(tc, tgt, f"assigning {tgt.attr!r} through an instance creates an instance attribute that hides class "
                       f"attribute {hit[0]}.{tgt.attr}; assign {hit[0]}.{tgt.attr} = ... or set self.{tgt.attr} "
                       f"in a method of {hit[0]}")
        return True
    return False


def _store(tc, s, tgt, value, aug, want: Ty, what: str) -> None:
    if aug is None:
        v = tc.check_expr(value, want)
        if v is not ERR and not widens_to(v, want):
            _diag(tc, value, f"{what} expects {want}, found {v}")
        s.ty = want
        return
    v = tc.synth(value)
    res = tc.binop_result(s, aug, tgt.ty, v)
    if res is not ERR and not widens_to(res, want):
        _diag(tc, s, f"{aug}= produces {res} but {what} has type {want}")
    s.ty = want


# ---- types_ext hooks: isinstance / narrowing ---------------------------------------------------------------
def decide(tc, x_node, t: Ty, wanted: List[str], exact: bool, what: str, at):
    """isinstance(x, C) / type(x) == C when x's static type is a class in an inheritance hierarchy."""
    cx = ctx(tc)
    if cx is None or not is_cls(tc, t) or not cx.in_hier(t.name):
        return None
    if any(w not in cx.defs for w in wanted):
        if all(w not in cx.defs for w in wanted):
            return ("const", False)
        return None
    ranges = []
    for w in wanted:
        if not (cx.is_sub(w, t.name) or cx.is_sub(t.name, w)):
            continue                                              # unrelated: never an instance
        if exact:
            ranges.append((cx.cid[w], cx.cid[w] + 1))
        elif cx.is_sub(t.name, w):
            return ("test", x_node, True)                         # every T is a W
        else:
            ranges.append((cx.cid[w], cx.hi[w]))
    if not ranges:
        return ("const", False)
    return ("cls", x_node, ranges, True)


def facts(tc, e):
    """isinstance(name, Sub) narrows `name` to Sub in the true branch."""
    cx = ctx(tc)
    if cx is None or not (isinstance(e, A.Call) and e.func == "isinstance" and e.args
                          and isinstance(e.args[0], A.Name)):
        return None
    st = getattr(e, "static", None)
    cls = e.args[1]
    if not (st and st[0] == "cls" and isinstance(cls, A.Name) and cls.id in cx.defs):
        return None
    d = tc.scope.lookup(e.args[0].id)
    if d is None or not is_cls(tc, d) or not cx.is_sub(cls.id, d.name):
        return None
    return {e.args[0].id: Ty(cls.id)}, {}


def narrowed(tc, e, t: Ty, nt: Ty) -> Optional[Ty]:
    cx = ctx(tc)
    if cx is not None and is_cls(tc, t) and is_cls(tc, nt) and nt != t and cx.is_sub(nt.name, t.name):
        e.downcast = nt.name
        return nt
    return None


# =============================================================================================== emitter
def _c(t: Ty) -> str:
    from .emit_c import ctype
    return ctype(t).strip()


def impl_name(owner: str, name: str) -> str:
    return f"m_{owner}_{name}"


def call_name(tc, cls: str, name: str, resolver=None) -> str:
    """The C function implementing `name` for a reference statically typed `cls` (a dispatcher if subclasses
    override it)."""
    resolver = resolver or (lambda d: resolve(tc, d, name))
    if ctx(tc).in_hier(cls) and needs_dispatch(tc, cls, resolver):
        return f"v_{cls}_{_key(name)}"
    r = resolver(cls)
    return impl_name(r[0], name) if r else "0"


def _key(name: str) -> str:
    return name.strip("_") if name.startswith("<") else name


def _nn(em, e, attr: str) -> str:
    v = em.ex(e)
    if isinstance(e, A.Name) and e.id == "self":
        return v
    return f"py_nn({v}, \"{attr}\")"


def _ocall(em, fname: str, lead: List[str], e) -> str:
    from .emit_ext import _ordered_call
    return _ordered_call(em, e, fname, lead)


def ex(em, e) -> Optional[str]:
    """Hook at the top of Emitter.ex."""
    tc = em.tc
    if ctx(tc) is None:
        return None
    if isinstance(e, A.Name):
        if getattr(e, "notimpl", None):
            return "false" if e.notimpl == "__eq__" else "true"
        dc = getattr(e, "downcast", None)
        if dc:
            from . import emit_ext
            return f"std::static_pointer_cast<{dc}>({emit_ext.ex(em, e)})"
        return None
    if isinstance(e, A.Attribute):
        ca = getattr(e, "cattr", None)
        if ca is not None:
            cls, owner, via_inst = ca
            acc = _cattr_access(em, cls, owner, e.attr, e.value if via_inst else None)
            return acc
        pr = getattr(e, "prop", None)
        if pr is not None:
            cls, getter = pr
            return f"{call_name(tc, cls, getter)}({_nn(em, e.value, e.attr)})"
        return None
    if isinstance(e, A.MethodCall):
        return _emit_mcall(em, e)
    if isinstance(e, A.Call):
        cb = getattr(e, "cls_builtin", None)
        if cb is not None:
            return _emit_builtin(em, e, cb)
        co = getattr(e, "cls_order", None)
        if co is not None:
            return _emit_order(em, e, co)
        return None
    if isinstance(e, A.Compare):
        if getattr(e, "contains", None):
            cls, owner = e.contains
            if e.op == "in":
                return f"[&]() {{ auto _i = {em.ex(e.left)}; auto _c = {em.ex(e.right)}; " \
                       f"return {call_name(tc, cls, '__contains__')}(pyc_nn_iter(_c), _i); }}()"
            return f"(![&]() {{ auto _i = {em.ex(e.left)}; auto _c = {em.ex(e.right)}; " \
                   f"return {call_name(tc, cls, '__contains__')}(pyc_nn_iter(_c), _i); }}())"
        if getattr(e, "identity", False):
            return f"(({em.ex(e.left)}) {'==' if e.op == 'is' else '!='} ({em.ex(e.right)}))"
        if getattr(e, "cls_eq", None) is not None:
            return _emit_eq(em, e)
        if getattr(e, "dunder", None) is not None:
            return _emit_binary(em, e.dunder, em.ex(e.left), em.ex(e.right))
        return None
    if isinstance(e, A.UnaryOp) and getattr(e, "cls_unary", None):
        cls, name = e.cls_unary
        msg = f"bad operand type for unary {e.op}: 'NoneType'"
        return f"{call_name(tc, cls, name)}(pyc_nn_type({em.ex(e.operand)}, \"{msg}\"))"
    if isinstance(e, A.Subscript) and getattr(e, "getitem", None):
        cls, _ = e.getitem
        return f"[&]() {{ auto _o = {em.ex(e.value)}; auto _k = {em.ex(e.index)}; return " \
               f"{call_name(tc, cls, '__getitem__')}(pyc_nn_type(_o, \"'NoneType' object is not subscriptable\"), _k); }}()"
    return None


def emit_binop(em, e) -> Optional[str]:
    """Hook at the top of Emitter.binop (also reached for augmented assignments)."""
    plan = getattr(e, "dunder", None)
    if plan is None:
        return None
    return _emit_binary(em, plan, em.ex(e.left), em.ex(e.right))


def _tn(tc, t: Ty, v: str) -> str:
    """C++ expression: CPython's type name of value v (static type t) for error messages."""
    if is_cls(tc, t):
        return f"pyc_tn_{t.name}({v})"
    return f"std::string(\"{_tyname(t)}\")"


def _emit_binary(em, plan: dict, l: str, r: str) -> str:
    tc = em.tc
    lt, rt, op = plan["lt"], plan["rt"], plan["op"]
    parts = [f"auto _a = {l};", f"auto _b = {r};"]
    if plan["plan"] == "fwd":
        fn = call_name(tc, lt.name, plan["fwd_name"])
        parts.append(f"if (_a) return {fn}(_a, _b);")
    if plan["refl"] is not None:
        fn = call_name(tc, rt.name, plan["refl_name"])
        parts.append(f"if (_b) return {fn}(_b, _a);" if is_cls(tc, rt) else f"return {fn}(_b, _a);")
    if op in CMP:
        msg = f"std::string(\"'{op}' not supported between instances of '\") + {_tn(tc, lt, '_a')} + \"' and '\" + {_tn(tc, rt, '_b')} + \"'\""
    else:
        msg = f"std::string(\"unsupported operand type(s) for {op}: '\") + {_tn(tc, lt, '_a')} + \"' and '\" + {_tn(tc, rt, '_b')} + \"'\""
    ret = _c(plan["ret"])
    parts.append(f"pyc_type_error({msg});")
    return f"[&]() -> {ret} {{ " + " ".join(parts) + " }()"


def _emit_eq(em, e) -> str:
    tc = em.tc
    d = e.cls_eq
    lt, rt = d["lt"], d["rt"]
    l, r = em.ex(e.left), em.ex(e.right)
    if NONE in (lt, rt):
        l = l if lt != NONE else "nullptr"
        r = r if rt != NONE else "nullptr"
    neg = e.op == "!="
    use_ne = neg and (d["ne_l"] is not None or d["ne_r"] is not None)
    parts = [f"auto _a = {l};", f"auto _b = {r};"]
    if use_ne:
        if d["ne_l"] is not None:
            parts.append(f"if (_a) return {call_name(tc, lt.name, '__ne__')}(_a, _b);")
        if d["ne_r"] is not None:
            parts.append(f"if (_b) return {call_name(tc, rt.name, '__ne__')}(_b, _a);")
        if d["eq_l"] is not None:
            parts.append(f"if (_a) return !{call_name(tc, lt.name, '__eq__')}(_a, _b);")
        if d["eq_r"] is not None:
            parts.append(f"if (_b) return !{call_name(tc, rt.name, '__eq__')}(_b, _a);")
        parts.append("return _a != _b;")
    else:
        bang = "!" if neg else ""
        if d["eq_l"] is not None:
            parts.append(f"if (_a) return {bang}{call_name(tc, lt.name, '__eq__')}(_a, _b);")
        if d["eq_r"] is not None:
            parts.append(f"if (_b) return {bang}{call_name(tc, rt.name, '__eq__')}(_b, _a);")
        parts.append(f"return _a {'!=' if neg else '=='} _b;")
    return "[&]() -> bool { " + " ".join(parts) + " }()"


def _cattr_access(em, cls: str, owner: str, attr: str, inst) -> str:
    tc = em.tc
    cx = ctx(tc)
    redefined = [d for d in cx.below(cls) if attr in cx.cattr.get(d, {})]
    if inst is None or not redefined:
        acc = f"ca_{owner}_{attr}()"
        if inst is None or (isinstance(inst, A.Name) and inst.id == "self"):
            return acc if inst is None else f"((void)({em.ex(inst)}), {acc})" if not isinstance(inst, A.Name) else acc
        return f"((void)py_nn({em.ex(inst)}, \"{attr}\"), {acc})"
    return f"cav_{cls}_{attr}({_nn(em, inst, attr)})"


def _emit_mcall(em, e) -> Optional[str]:
    tc = em.tc
    if hasattr(e, "super_owner"):
        if e.super_owner is None:
            return "((void)0)"
        return _ocall(em, impl_name(e.super_owner, e.method), ["p_self"], e)
    if getattr(e, "unbound", None):
        owner = e.unbound
        from .emit_ext import _ordered_call
        recv = e.args[0]
        rest = A.MethodCall(e.line, e.col, recv=recv, method=e.method, args=e.args[1:], kwargs=[])
        if getattr(e, "arg_order", None) is not None:
            rest.arg_order = [j - 1 for j in e.arg_order[1:]]
        return _ordered_call(em, rest, impl_name(owner, e.method), [_nn(em, recv, e.method)])
    if getattr(e, "cls_sort", None):
        rev = em.kwarg(e, "reverse")
        return f"(pyc_sort({em.ex(e.recv)}, {em.ex(rev) if rev is not None else 'false'}, pyc_lt_{e.cls_sort}), 0)"
    rt = e.recv.ty
    if not is_cls(tc, rt):
        return None
    info = tc.classes[rt.name]
    sig = info.methods.get(e.method)
    if sig is None:
        return None
    return _ocall(em, call_name(tc, rt.name, e.method), [_nn(em, e.recv, e.method)], e)


def _emit_builtin(em, e, cb) -> str:
    tc = em.tc
    f, cls = cb
    x = em.ex(e.args[0])
    if f == "str":
        return f"pyc_str_{cls}({x})"
    if f == "repr":
        return f"pyc_repr_{cls}({x})"
    if f == "len":
        return f"pyc_len_check({call_name(tc, cls, '__len__')}(pyc_nn_type({x}, \"object of type 'NoneType' has no len()\")))"
    if f == "bool":
        return em.truthy(x, e.args[0].ty)
    if f == "abs":
        return f"{call_name(tc, cls, '__abs__')}(pyc_nn_type({x}, \"bad operand type for abs(): 'NoneType'\"))"
    return "0"


def _emit_order(em, e, co) -> str:
    f, cls = co
    if f == "sorted":
        rev = em.kwarg(e, "reverse")
        return f"pyc_sorted({em.ex(e.args[0])}, {em.ex(rev) if rev is not None else 'false'}, pyc_lt_{cls})"
    better = f"pyc_lt_{cls}" if f == "min" else f"pyc_gt_{cls}"
    if len(e.args) == 1:
        return f"pyc_minmax({em.ex(e.args[0])}, {better}, \"{f}\")"
    parts = [f"std::shared_ptr<{cls}> _r = {em.ex(e.args[0])};"]
    for a in e.args[1:]:
        parts.append(f"{{ std::shared_ptr<{cls}> _x = {em.ex(a)}; if ({better}(_x, _r)) _r = _x; }}")
    return "[&]() { " + " ".join(parts) + " return _r; }()"


def stmt(em, s, d: int) -> bool:
    """Hook at the top of Emitter._stmt."""
    tc = em.tc
    if ctx(tc) is None:
        return False
    if isinstance(s, (A.Assign, A.AugAssign)) and isinstance(s.target, A.Attribute):
        tgt = s.target
        if getattr(s, "cattr_set", False):
            cls = tgt.cattr[0]
            acc = f"ca_{cls}_{tgt.attr}()"
            val = em.ex(s.value) if isinstance(s, A.Assign) else _aug_value(em, s, tgt)
            em.w(d, f"{{ auto _v = {val}; {acc} = _v; }}" if isinstance(s, A.AugAssign) else f"{acc} = {val};")
            return True
        if getattr(s, "prop_set", None):
            cls, setter = s.prop_set
            recv = _nn(em, tgt.value, tgt.attr)
            if isinstance(s, A.Assign):
                em.w(d, "{")
                em.w(d + 1, f"auto _o = {recv};")
                em.w(d + 1, f"auto _v = {em.ex(s.value)};")
                em.w(d + 1, f"{call_name(tc, cls, setter)}(_o, _v);")
                em.w(d, "}")
            else:
                em.w(d, "{")
                em.w(d + 1, f"auto _o = {recv};")
                getter = call_name(tc, cls, tgt.prop[1])
                fake = A.BinOp(s.line, s.col, op=s.op, left=A.Name(s.line, s.col, id="__cur"), right=s.value)
                fake.left.raw = f"{getter}(_o)"
                fake.left.ty = tgt.ty
                fake.ty = getattr(s, "aug_ty", None) or tgt.ty
                fake.dunder = getattr(s, "dunder", None)
                em.w(d + 1, f"auto _v = {em.binop(fake)};")
                em.w(d + 1, f"{call_name(tc, cls, setter)}(_o, _v);")
                em.w(d, "}")
            return True
        return False
    if isinstance(s, A.Assign) and getattr(s, "setitem", None):
        cls, _ = s.setitem
        em.w(d, "{")
        em.w(d + 1, f"auto _o = {em.ex(s.target.value)};")
        em.w(d + 1, f"auto _k = {em.ex(s.target.index)};")
        em.w(d + 1, f"auto _v = {em.ex(s.value)};")
        em.w(d + 1, f"{call_name(tc, cls, '__setitem__')}(pyc_nn_type(_o, \"'NoneType' object does not support item "
                    f"assignment\"), _k, _v);")
        em.w(d, "}")
        return True
    if isinstance(s, A.AugAssign) and getattr(s, "iop", None):
        cls, name = s.iop
        em.w(d, f"p_{s.target.id} = {call_name(tc, cls, name)}(pyc_nn_type({em.ex(s.target)}, "
                f"\"unsupported operand type(s) for {s.op}=: 'NoneType'\"), {em.ex(s.value)});")
        return True
    return False


def _aug_value(em, s, tgt) -> str:
    fake = A.BinOp(s.line, s.col, op=s.op, left=tgt, right=s.value)
    fake.ty = s.ty
    return em.binop(fake)


def print_call(em, a, value: Optional[str]) -> Optional[str]:
    tc = em.tc
    t = a.ty
    if ctx(tc) is None or t is None:
        return None
    e = value if value is not None else None
    if is_cls(tc, t):
        return f"py_print_str(pyc_str_{t.name}({e if e is not None else em.ex(a)}))"
    if t.name == "list" and is_cls(tc, t.elem):
        return f"py_print_repr({e if e is not None else em.ex(a)})"
    return None


def truthy(expr: str, t: Ty) -> Optional[str]:
    tc = _cur()
    if tc is None or ctx(tc) is None or not is_cls(tc, t):
        return None
    if _truth_impl(tc, t.name) is None:
        return None
    return f"pyc_truthy_{t.name}({expr})"


def _truth_impl(tc, cls: str):
    """'bool' / 'len' if some run-time class of a `cls` reference defines __bool__ or __len__, else None."""
    for d in [cls] + ctx(tc).below(cls):
        if resolve(tc, d, "__bool__") or resolve(tc, d, "__len__"):
            return True
    return None


def emit_static(em, st) -> Optional[str]:
    """('cls', node, ranges, nonnull) from decide(): a run-time class-id test."""
    if st[0] != "cls":
        return None
    v = em.ex(st[1])
    tests = " || ".join(f"(_x->_cid >= {lo} && _x->_cid < {hi})" for lo, hi in st[2])
    return f"[&](const auto &_x) {{ return _x != nullptr && ({tests}); }}({v})"


# ---- module layout -----------------------------------------------------------------------------------------
def emit_struct(em, c: A.ClassDef) -> bool:
    tc = em.tc
    cx = ctx(tc)
    if cx is None or c.name not in cx.defs:
        return False
    _tls.tc = tc
    info = tc.classes[c.name]
    b = cx.base.get(c.name)
    em.w(0, f"struct {c.name}" + (f" : {b}" if b else "") + " {")
    if b is None and cx.in_hier(c.name):
        em.w(1, "int32_t _cid = 0;          /* run-time class (virtual dispatch, isinstance) */")
    inherited = set(tc.classes[b].field_names) if b else set()
    for name, t in zip(info.field_names, info.fields):
        if name not in inherited:
            em.w(1, f"{_c(t)} {name};")
    em.w(0, "};")
    return True


def emit_ctor(em, c: A.ClassDef) -> bool:
    from .emit_c import zero
    tc = em.tc
    cx = ctx(tc)
    if cx is None or c.name not in cx.defs:
        return False
    info = tc.classes[c.name]
    em.w(0, em.ctor_signature(c) + " {")
    em.w(1, f"auto p_self = std::make_shared<{c.name}>();")
    if c.name in cx.cid:
        em.w(1, f"p_self->_cid = {cx.cid[c.name]};")
    for k in reversed(cx.mro(c.name)):
        for f in cx.cattr_field.get(k, set()):
            pass
    for name, t in zip(info.field_names, info.fields):
        owner = next((k for k in cx.mro(c.name) if name in cx.cattr_field.get(k, set())), None)
        if owner is not None:
            em.w(1, f"p_self->{name} = ca_{owner}_{name}();   /* reads the class attribute until assigned */")
        else:
            em.w(1, f"p_self->{name} = {zero(t)};")
    if info.init is not None:
        args = ", ".join(f"p_{p.name}" for p in info.init.node.params[1:])
        em.w(1, f"{impl_name(info.init.owner, '__init__')}(p_self" + (f", {args}" if args else "") + ");")
    em.w(1, "return p_self;")
    em.w(0, "}")
    return True


def emit_decls(em, mod) -> None:
    """After the class prototypes: class attributes, generated dunders, dispatchers, str/compare helpers and the
    runtime-template overloads (pyl_eqv / pyl_lt / py_value_repr) for each class."""
    tc = em.tc
    cx = ctx(tc)
    if cx is None or not cx.defs:
        return
    _tls.tc = tc
    w = em.w
    w(0, "/* user classes: class attributes, dispatch, dunder helpers (classes_ext.py) */")
    if cx.cid:
        names = ", ".join(f"\"{n}\"" for n in tc.cx_names)
        w(0, f"static const char *const pyc_cls_names[] = {{{names}}};")
    for name in cx.order:
        hier = name in cx.cid
        w(0, f"static inline std::string pyc_tn_{name}(const std::shared_ptr<{name}> &p) {{ "
             f"return !p ? \"NoneType\" : " + ("pyc_cls_names[p->_cid]" if hier else f"\"{name}\"") + "; }")
    for name in cx.order:
        for attr, (t, s) in cx.cattr[name].items():
            val = em.ex(s.value)
            if s.value.ty is not None and s.value.ty != t and t.name in ("int", "float", "bool"):
                val = f"static_cast<{_c(t)}>({val})"
            w(0, f"static {_c(t)} &ca_{name}_{attr}() {{ static {_c(t)} v = []() {{ ArenaPause _p; return "
                 f"({_c(t)})({val}); }}(); return v; }}")
    for name in cx.order:                              # generated dataclass dunders: prototypes
        for k in sorted(cx.synth[name]):
            ps = f"std::shared_ptr<{name}> p_self" + (", std::shared_ptr<" + name + "> p_other" if k != "__repr__" else "")
            w(0, f"static {_c(SynSig(name, k).ret)} {impl_name(name, k)}({ps});")
    for name in cx.order:                              # dispatchers
        if name not in cx.cid or not cx.below(name):
            continue
        seen = set()
        for k in cx.mro(name) + cx.below(name):
            for mname in sorted(cx.own(k)):
                if mname in seen or mname == "__init__" or resolve(tc, name, mname) is None:
                    continue
                seen.add(mname)
                _emit_dispatcher(em, name, mname)
        for attr in sorted({a for k in cx.mro(name) for a in cx.cattr[k]}):
            if any(attr in cx.cattr[d] for d in cx.below(name)):
                _emit_cattr_dispatch(em, name, attr)
    for name in cx.order:
        _emit_helpers(em, name)
    for name in cx.order:
        for k in sorted(cx.synth[name]):
            _emit_synth(em, name, k)
    w(0)


def _switch(tc, cls: str, resolver, call) -> List[str]:
    """`switch (p->_cid)` lines dispatching on the run-time class; call(owner, sig) -> C expression for `p`."""
    impls = dynamic_impls(tc, cls, resolver)
    default = impls[cls]
    groups: Dict[str, List[int]] = {}
    for d, r in impls.items():
        if r is None or (default is not None and r[0] == default[0]):
            continue
        groups.setdefault(r[0], []).append(ctx(tc).cid[d])
    lines = []
    for owner, ids in groups.items():
        lines.append(" ".join(f"case {i}:" for i in sorted(ids)) + f" return {call(owner, impls_for(impls, owner))};")
    return lines, default


def impls_for(impls, owner):
    for r in impls.values():
        if r is not None and r[0] == owner:
            return r[1]
    return None


def _emit_dispatcher(em, cls: str, mname: str) -> None:
    tc = em.tc
    resolver = lambda d: resolve(tc, d, mname)          # noqa: E731
    if not needs_dispatch(tc, cls, resolver):
        return
    owner0, sig0 = resolver(cls)
    params = list(sig0.params)
    ps = "".join(f", {_c(t)} a{i}" for i, t in enumerate(params))
    args = "".join(f", a{i}" for i in range(len(params)))
    ret = _c(sig0.ret)
    em.w(0, f"static {ret} v_{cls}_{_key(mname)}(std::shared_ptr<{cls}> p{ps}) {{")
    em.w(1, "switch (p->_cid) {")
    lines, default = _switch(tc, cls, resolver,
                             lambda o, s: f"{impl_name(o, mname)}(std::static_pointer_cast<{o}>(p){args})")
    for ln in lines:
        em.w(2, ln)
    em.w(2, f"default: return {impl_name(default[0], mname)}(p{args});")
    em.w(1, "}")
    em.w(0, "}")


def _emit_cattr_dispatch(em, cls: str, attr: str) -> None:
    tc = em.tc
    cx = ctx(tc)
    resolver = lambda d: (lambda h: (h[0], None) if h else None)(cattr_lookup(cx, d, attr))   # noqa: E731
    t = cattr_lookup(cx, cls, attr)[1]
    em.w(0, f"static {_c(t)} &cav_{cls}_{attr}(const std::shared_ptr<{cls}> &p) {{")
    em.w(1, "switch (p->_cid) {")
    lines, default = _switch(tc, cls, resolver, lambda o, s: f"ca_{o}_{attr}()")
    for ln in lines:
        em.w(2, ln)
    em.w(2, f"default: return ca_{default[0]}_{attr}();")
    em.w(1, "}")
    em.w(0, "}")


def _emit_helpers(em, cls: str) -> None:
    tc = em.tc
    cx = ctx(tc)
    w = em.w
    P = f"const std::shared_ptr<{cls}> &"
    hier = cls in cx.cid
    # str() / repr()
    rs = lambda d: resolve_str(tc, d)            # noqa: E731
    rr = lambda d: resolve(tc, d, "__repr__")    # noqa: E731
    for fn, resolver in (("str", rs), ("repr", rr)):
        if all_have(tc, cls, resolver) is not None:
            continue
        w(0, f"static PyStr *pyc_{fn}_{cls}({P}p) {{")
        w(1, "if (!p) return pystr_lit(\"None\");")
        if hier and needs_dispatch(tc, cls, resolver):
            w(1, "switch (p->_cid) {")
            lines, default = _switch(tc, cls, resolver,
                                     lambda o, s: f"{impl_name(o, _mname(s))}(std::static_pointer_cast<{o}>(p))")
            for ln in lines:
                w(2, ln)
            w(2, f"default: return {impl_name(default[0], _mname(default[1]))}(p);")
            w(1, "}")
        else:
            r = resolver(cls)
            w(1, f"return {impl_name(r[0], _mname(r[1]))}(p);")
        w(0, "}")
    if all_have(tc, cls, rr) is None:
        w(0, f"inline std::string py_value_repr({P}p) {{ return pyc_repr_{cls}(p)->data; }}")
    # == for containers (identity first, like CPython's list.__contains__ / index / count / remove / ==)
    if resolve(tc, cls, "__eq__") is not None:
        eq = call_name(tc, cls, "__eq__")
        w(0, f"inline bool pyl_eqv({P}a, {P}b) {{ return a == b || (a ? {eq}(a, b) : (b ? {eq}(b, a) : true)); }}")
    # ordering helpers for sort / sorted / min / max
    for op, name in (("<", "lt"), (">", "gt")):
        fwd, refl = CMP[op]
        f_ok = resolve(tc, cls, fwd) is not None and _risk(tc, cls, refl) is None
        r_ok = resolve(tc, cls, refl) is not None and _risk(tc, cls, refl) is None
        if not (f_ok or r_ok):
            continue
        body = []
        if f_ok:
            body.append(f"if (a) return {call_name(tc, cls, fwd)}(a, b);")
        if r_ok:
            body.append(f"if (b) return {call_name(tc, cls, refl)}(b, a);")
        body.append(f"pyc_type_error(std::string(\"'{op}' not supported between instances of '\") + pyc_tn_{cls}(a) "
                    f"+ \"' and '\" + pyc_tn_{cls}(b) + \"'\");")
        w(0, f"static bool pyc_{name}_{cls}({P}a, {P}b) {{ " + " ".join(body) + " }")
        if name == "lt":
            w(0, f"inline bool pyl_lt({P}a, {P}b) {{ return pyc_lt_{cls}(a, b); }}")
    # truthiness: __bool__, else __len__ != 0
    if _truth_impl(tc, cls):
        def tr(d):
            return resolve(tc, d, "__bool__") or resolve(tc, d, "__len__")
        w(0, f"static bool pyc_truthy_{cls}({P}p) {{")
        w(1, "if (!p) return false;")

        def call(o, s):
            m = _mname(s)
            c = f"{impl_name(o, m)}(std::static_pointer_cast<{o}>(p))"
            return c if m == "__bool__" else f"pyc_len_check({c}) != 0"
        if hier and needs_dispatch(tc, cls, tr):
            w(1, "switch (p->_cid) {")
            lines, default = _switch(tc, cls, tr, call)
            for ln in lines:
                w(2, ln)
            w(2, f"default: return {call(default[0], default[1]) if default else 'true'};")
            w(1, "}")
        else:
            r = tr(cls)
            w(1, f"return {call(r[0], r[1]) if r else 'true'};")
        w(0, "}")


def _mname(sig) -> str:
    return sig.name.split(".")[-1]


def _emit_synth(em, cls: str, k: str) -> None:
    """Dataclass __repr__ / __eq__ / ordering, generated natively."""
    tc = em.tc
    c = ctx(tc).defs[cls]
    info = tc.classes[cls]
    fields = [(n, info.fields[info.field_index[n]]) for n, _, _ in c.dc_fields]
    w = em.w
    if k == "__repr__":
        w(0, f"static PyStr *{impl_name(cls, k)}(std::shared_ptr<{cls}> p_self) {{")
        w(1, f"std::string s = \"{cls}(\";")
        for i, (n, t) in enumerate(fields):
            w(1, f"s += \"{', ' if i else ''}{n}=\"; s += {_repr_expr(tc, t, f'p_self->{n}')};")
        w(1, "s += \")\";")
        w(1, "return pystr_new(s.data(), static_cast<int64_t>(s.size()));")
        w(0, "}")
        return
    sig = f"static bool {impl_name(cls, k)}(std::shared_ptr<{cls}> p_self, std::shared_ptr<{cls}> p_other)"
    if k == "__eq__":
        w(0, sig + " {")
        w(1, "if (!p_other) return false;                /* other.__class__ is not self.__class__: NotImplemented */")
        w(1, "if (p_self == p_other) return true;")
        for n, t in fields:
            w(1, f"if (!pyl_eqv(p_self->{n}, p_other->{n})) return false;")
        w(1, "return true;")
        w(0, "}")
        return
    op = {"__lt__": "<", "__le__": "<=", "__gt__": ">", "__ge__": ">="}[k]
    w(0, sig + " {")
    w(1, f"if (!p_other) pyc_type_error(std::string(\"'{op}' not supported between instances of '{cls}' and 'NoneType'\"));")
    for n, t in fields:
        a, b = f"p_self->{n}", f"p_other->{n}"
        if op in ("<", "<="):
            w(1, f"if (!pyl_eqv({a}, {b})) return pyl_lt({a}, {b});")
        else:
            w(1, f"if (!pyl_eqv({a}, {b})) return pyl_lt({b}, {a});")
    w(1, f"return {'true' if op in ('<=', '>=') else 'false'};")
    w(0, "}")


def _repr_expr(tc, t: Ty, v: str) -> str:
    if t.name == "optional":
        return f"([&](const auto &_o) {{ return _o ? {_repr_expr(tc, t.elem, '(*_o)' if t.elem.name in ('int', 'float', 'bool') else '_o')} : std::string(\"None\"); }}({v}))"
    if is_cls(tc, t):
        return f"std::string(pyc_repr_{t.name}({v})->data)"
    return f"py_value_repr({v})"


def dc_repr_ok(tc, cls: str) -> bool:
    return True
