"""Whole-program type inference for untyped Python: evidence from every assignment, call site, return, method
use and iteration is joined into slots until nothing changes (a fixpoint over the program).

Slots:  ('var', scope, name)   locals, params and module variables ('<module>' scope)
        ('ret', qual)          a function's return value
        ('attr', Class, name)  instance / class attributes
        ('field', rid, key)    fields of a dict used as a record
Scopes are named like CPython's co_qualname: 'f', 'Class.method', 'f.<locals>.g'.
"""
from __future__ import annotations

import ast
import keyword
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .types import CONTAINERS, complete, contains, elem, is_bad, join

MODULE = "<module>"

STR_RET = {}
for _m in ("capitalize casefold center expandtabs format ljust lower lstrip replace rjust rstrip strip swapcase "
           "title translate upper zfill removeprefix removesuffix join format_map").split():
    STR_RET[_m] = "str"
for _m in "split rsplit splitlines".split():
    STR_RET[_m] = ("list", "str")
for _m in "find rfind index rindex count".split():
    STR_RET[_m] = "int"
for _m in ("startswith endswith isdigit isalpha isalnum isspace isupper islower istitle isnumeric isdecimal "
           "isidentifier isprintable isascii").split():
    STR_RET[_m] = "bool"
STR_RET["partition"] = STR_RET["rpartition"] = ("tuple", ("str", "str", "str"))
STR_ONLY = set(STR_RET) - {"index", "count", "copy"}

MATH_FLOAT = set("sqrt sin cos tan asin acos atan atan2 log log10 log2 log1p exp expm1 pow fabs hypot degrees radians "
                 "fmod copysign cbrt exp2 dist".split())
MATH_INT = set("floor ceil trunc gcd lcm isqrt factorial comb perm".split())
MATH_CONST = {"pi", "e", "tau", "inf", "nan"}
FACTORY = {"list": ("list", None), "int": "int", "float": "float", "str": "str", "set": ("set", None),
           "dict": ("dict", None, None), "bool": "bool"}


@dataclass
class Func:
    qual: str
    node: ast.FunctionDef
    cls: Optional[str] = None
    kind: str = "func"                  # func | method | static | classmethod
    locals: Set[str] = field(default_factory=set)
    globals: Set[str] = field(default_factory=set)
    parent: Optional["Func"] = None
    generator: bool = False

    @property
    def params(self) -> List[ast.arg]:
        a = self.node.args
        return a.posonlyargs + a.args + a.kwonlyargs


@dataclass
class Klass:
    name: str
    node: ast.ClassDef
    bases: List[str]
    methods: Dict[str, Func] = field(default_factory=dict)
    attrs: Set[str] = field(default_factory=set)
    declared: Set[str] = field(default_factory=set)


def stored_names(stmts):
    out, glob = set(), set()

    def visit(n):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
            return
        if isinstance(n, (ast.Lambda, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            return
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            out.add(n.id)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            glob.update(n.names)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            out.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            out.update((a.asname or a.name).split(".")[0] for a in n.names)
        for c in ast.iter_child_nodes(n):
            visit(c)

    for s in stmts:
        visit(s)
    return out - glob, glob


def falls_through(stmts) -> bool:
    if not stmts:
        return True
    s = stmts[-1]
    if isinstance(s, (ast.Return, ast.Raise)):
        return False
    if isinstance(s, ast.If):
        return falls_through(s.body) or falls_through(s.orelse)
    if isinstance(s, ast.While) and isinstance(s.test, ast.Constant) and s.test.value is True:
        return _has_break(s.body)
    if isinstance(s, ast.Try):
        return (falls_through(s.orelse or s.body) or any(falls_through(h.body) for h in s.handlers)) \
            and (not s.finalbody or falls_through(s.finalbody))
    return True


def _has_break(stmts) -> bool:
    for s in stmts:
        for n in _walk_loop(s):
            if isinstance(n, ast.Break):
                return True
    return False


def _walk_loop(n):
    """Nodes of n that belong to the current loop (not nested loops / functions)."""
    yield n
    for c in ast.iter_child_nodes(n):
        if isinstance(c, (ast.For, ast.While, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        yield from _walk_loop(c)


def parse_annotation(a, classes) -> object:
    """A user-written annotation -> our type (None if not understood)."""
    if a is None:
        return None
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        try:
            a = ast.parse(a.value, mode="eval").body
        except SyntaxError:
            return None
    if isinstance(a, ast.Constant) and a.value is None:
        return "None"
    if isinstance(a, ast.Name):
        if a.id in ("int", "float", "str", "bool"):
            return a.id
        if a.id in classes:
            return ("cls", a.id)
        return None
    if isinstance(a, ast.BinOp) and isinstance(a.op, ast.BitOr):
        return join(parse_annotation(a.left, classes), parse_annotation(a.right, classes))
    if isinstance(a, ast.Subscript):
        head = a.value.id if isinstance(a.value, ast.Name) else a.value.attr if isinstance(a.value, ast.Attribute) else ""
        args = a.slice.elts if isinstance(a.slice, ast.Tuple) else [a.slice]
        ps = [parse_annotation(x, classes) for x in args]
        h = head.lower()
        if h in ("list", "set") and len(ps) == 1 and ps[0] is not None:
            return (h, ps[0])
        if h == "dict" and len(ps) == 2 and None not in ps:
            return ("dict", ps[0], ps[1])
        if h == "tuple" and ps and None not in ps and not any(isinstance(x, ast.Constant) and x.value is ... for x in args):
            return ("tuple", tuple(ps))
        if head == "Optional" and ps[0] is not None:
            return join("None", ps[0])
    return None


class Engine:
    def __init__(self, tree: ast.Module, rec_lits: Optional[Dict[int, tuple]] = None, seeds=None):
        self.tree = tree
        self.rec_lits = rec_lits or {}          # id(Dict node) -> rid (tuple of keys)
        self.seeds = seeds or {}
        self.slots: Dict[tuple, object] = {}
        self.fixed: Dict[tuple, object] = {}
        self.types: Dict[ast.AST, object] = {}
        self.funcs: Dict[str, Func] = {}
        self.top_funcs: Dict[str, Func] = {}
        self.classes: Dict[str, Klass] = {}
        self.imports: Dict[str, tuple] = {}
        self.call_kind: Dict[ast.Call, str] = {}  # 'user' or a builtin/method name
        self.scope: Optional[Func] = None
        self.env: List[dict] = []
        self.changed = False
        self.module_vars, mglob = stored_names(tree.body)
        self._collect()

    # ------------------------------------------------------------------ program structure
    def _collect(self):
        for s in self.tree.body:
            self._collect_stmt(s, None, None)
        for f in self.funcs.values():
            f.generator = any(isinstance(n, (ast.Yield, ast.YieldFrom)) for n in self._own_nodes(f.node))
        for f in self.funcs.values():
            self.module_vars |= f.globals
        self.module_vars -= set(self.classes) | set(self.top_funcs)
        for s in ast.walk(self.tree):
            if isinstance(s, (ast.Import, ast.ImportFrom)):
                self.module_vars -= {(a.asname or a.name).split(".")[0] for a in s.names}
        for s in ast.walk(self.tree):
            if isinstance(s, ast.Import):
                for a in s.names:
                    self.imports[a.asname or a.name.split(".")[0]] = ("mod", a.name)
            elif isinstance(s, ast.ImportFrom) and s.module:
                for a in s.names:
                    self.imports[a.asname or a.name] = ("from", s.module, a.name)
        # declared annotations become fixed slots
        for f in self.funcs.values():
            for p in f.params:
                t = parse_annotation(p.annotation, self.classes)
                if t is not None:
                    self.fixed[("var", f.qual, p.arg)] = t
            if f.node.returns is not None:
                t = parse_annotation(f.node.returns, self.classes)
                if t is not None:
                    self.fixed[("ret", f.qual)] = t
        for k in self.classes.values():
            for s in k.node.body:
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                    k.declared.add(s.target.id)
                    t = parse_annotation(s.annotation, self.classes)
                    if t is not None:
                        self.fixed[("attr", k.name, s.target.id)] = t
        for n in ast.walk(self.tree):
            if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
                t = parse_annotation(n.annotation, self.classes)
                if t is not None:
                    scope = self._scope_of_node(n)
                    self.fixed.setdefault(("var", scope, n.target.id), t)
        self.slots.update(self.fixed)

    def _scope_of_node(self, target):
        for f in self.funcs.values():
            for n in self._own_nodes(f.node):
                if n is target:
                    return MODULE if any(isinstance(target, ast.AnnAssign) and target.target.id in f.globals
                                         for _ in [0]) else f.qual
        return MODULE

    @staticmethod
    def _own_nodes(fn):
        """Nodes of a function body, not of nested functions/classes."""
        stack = list(fn.body)
        while stack:
            n = stack.pop()
            yield n
            for c in ast.iter_child_nodes(n):
                if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    stack.append(c)

    def _collect_stmt(self, s, cls: Optional[Klass], parent: Optional[Func]):
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if cls is not None:
                qual = f"{cls.name}.{s.name}"
            elif parent is not None:
                qual = f"{parent.qual}.<locals>.{s.name}"
            else:
                qual = s.name
            decos = {d.id for d in s.decorator_list if isinstance(d, ast.Name)}
            kind = "func" if cls is None else "static" if "staticmethod" in decos else \
                "classmethod" if "classmethod" in decos else "method"
            loc, glob = stored_names(s.body)
            f = Func(qual, s, cls.name if cls else None, kind, loc | {p.arg for p in s.args.posonlyargs + s.args.args +
                                                                       s.args.kwonlyargs}, glob, parent)
            if s.args.vararg:
                f.locals.add(s.args.vararg.arg)
            if s.args.kwarg:
                f.locals.add(s.args.kwarg.arg)
            self.funcs[qual] = f
            if cls is not None:
                cls.methods[s.name] = f
                if kind == "method" and f.params:
                    me = f.params[0].arg
                    for n in self._own_nodes(s):
                        if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store) and \
                                isinstance(n.value, ast.Name) and n.value.id == me:
                            cls.attrs.add(n.attr)
            elif parent is None:
                self.top_funcs[s.name] = f
            for c in s.body:
                self._collect_stmt(c, None, f)
        elif isinstance(s, ast.ClassDef) and cls is None and parent is None:
            k = Klass(s.name, s, [b.id for b in s.bases if isinstance(b, ast.Name)])
            self.classes[s.name] = k
            for c in s.body:
                if isinstance(c, ast.Assign):
                    k.attrs |= {t.id for t in c.targets if isinstance(t, ast.Name)}
                elif isinstance(c, ast.AnnAssign) and isinstance(c.target, ast.Name):
                    k.attrs.add(c.target.id)
                self._collect_stmt(c, k, None)
        elif isinstance(s, (ast.If, ast.For, ast.While, ast.Try, ast.With)):
            for c in ast.iter_child_nodes(s):
                if isinstance(c, ast.stmt) or isinstance(c, ast.ExceptHandler):
                    if isinstance(c, ast.ExceptHandler):
                        for cc in c.body:
                            self._collect_stmt(cc, cls, parent)
                    else:
                        self._collect_stmt(c, cls, parent)

    def mro(self, c: str):
        seen, out, todo = set(), [], [c]
        while todo:
            x = todo.pop(0)
            if x in self.classes and x not in seen:
                seen.add(x)
                out.append(self.classes[x])
                todo += self.classes[x].bases
        return out

    def find_method(self, c: str, m: str) -> Optional[Func]:
        for k in self.mro(c):
            if m in k.methods:
                return k.methods[m]
        return None

    def attr_key(self, c: str, a: str):
        for k in self.mro(c):
            if a in k.attrs:
                return ("attr", k.name, a)
        return ("attr", c, a)

    # ------------------------------------------------------------------ slots
    def add(self, key, t):
        if t is None or key in self.fixed:
            return
        old = self.slots.get(key)
        new = join(old, t)
        if new != old:
            self.slots[key] = new
            self.changed = True

    def var_key(self, name: str):
        """Slot written by `name = ...` in the current scope."""
        f = self.scope
        if f is not None and name not in f.globals:
            return ("var", f.qual, name)
        return ("var", MODULE, name)

    def load_key(self, name: str):
        f = self.scope
        while f is not None:
            if name in f.globals:
                return ("var", MODULE, name)
            if name in f.locals:
                return ("var", f.qual, name)
            f = f.parent
        if name in self.module_vars:
            return ("var", MODULE, name)
        return None

    def in_env(self, name):
        return any(name in d for d in self.env)

    def lookup(self, name):
        for d in reversed(self.env):
            if name in d:
                return d[name]
        key = self.load_key(name)
        if key is not None and not (key[1] == MODULE and name in self.top_funcs and key not in self.slots):
            if name in self.classes and key not in self.slots:
                return ("clsref", name)
            return self.slots.get(key)
        if name in self.top_funcs:
            return ("fn", name)
        if name in self.classes:
            return ("clsref", name)
        if name in self.imports:
            imp = self.imports[name]
            return ("mod", imp[1]) if imp[0] == "mod" else None
        return None

    # ------------------------------------------------------------------ driver
    def run(self, max_iter: int = 60):
        for _ in range(max_iter):
            self.changed = False
            self.types = {}
            self.call_kind = {}
            for k, t in self.seeds.items():
                self.add(k, t)
            self.scope = None
            for s in self.tree.body:
                self.stmt(s)
            for f in self.funcs.values():
                self.scope = f
                if f.kind == "method" and f.params:
                    self.add(("var", f.qual, f.params[0].arg), ("cls", f.cls))
                for s in f.node.body:
                    self.stmt(s)
                if f.generator:
                    continue
                if falls_through(f.node.body):
                    self.add(("ret", f.qual), "None")
                self.scope = None
            if not self.changed:
                return self
        return self

    # ------------------------------------------------------------------ statements
    def stmt(self, s):
        m = getattr(self, "st_" + type(s).__name__, None)
        if m is not None:
            m(s)
            return
        for c in ast.iter_child_nodes(s):
            if isinstance(c, ast.expr):
                self.ty(c)

    def body(self, stmts):
        for s in stmts:
            self.stmt(s)

    def st_FunctionDef(self, s):
        f = self._func_for(s)
        for d in s.decorator_list:
            self.ty(d)
        if f is None:
            return
        a = s.args
        pos = a.posonlyargs + a.args
        for p, d in zip(pos[len(pos) - len(a.defaults):], a.defaults):
            self.add(("var", f.qual, p.arg), self.ty(d))
        for p, d in zip(a.kwonlyargs, a.kw_defaults):
            if d is not None:
                self.add(("var", f.qual, p.arg), self.ty(d))

    st_AsyncFunctionDef = st_FunctionDef

    def _func_for(self, node):
        for f in self.funcs.values():
            if f.node is node:
                return f
        return None

    def st_ClassDef(self, s):
        k = self.classes.get(s.name)
        for c in s.body:
            if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.st_FunctionDef(c)
            elif k is not None and isinstance(c, ast.Assign):
                t = self.ty(c.value)
                for tg in c.targets:
                    if isinstance(tg, ast.Name):
                        self.add(("attr", k.name, tg.id), t)
            elif k is not None and isinstance(c, ast.AnnAssign) and c.value is not None:
                self.add(("attr", k.name, c.target.id), self.ty(c.value))

    def st_Assign(self, s):
        t = self.ty(s.value)
        for tg in s.targets:
            self.assign(tg, t, s.value)

    def st_AnnAssign(self, s):
        if s.value is not None:
            self.assign(s.target, self.ty(s.value), s.value)
        elif isinstance(s.target, ast.Name):
            self.types[s.target] = self.slots.get(self.var_key(s.target.id))

    def st_AugAssign(self, s):
        cur = self.ty(s.target)
        r = self.binop(s.op, cur, self.ty(s.value))
        self.assign(s.target, r, None)

    def st_For(self, s):
        it = self.ty(s.iter)
        self.assign(s.target, elem(it), None)
        self.body(s.body)
        self.body(s.orelse)

    st_AsyncFor = st_For

    def st_While(self, s):
        self.ty(s.test)
        self.body(s.body)
        self.body(s.orelse)

    def st_If(self, s):
        self.st_While(s)

    def st_With(self, s):
        for it in s.items:
            self.ty(it.context_expr)
        self.body(s.body)

    def st_Try(self, s):
        self.body(s.body)
        for h in s.handlers:
            if h.type is not None:
                self.ty(h.type)
            self.body(h.body)
        self.body(s.orelse)
        self.body(s.finalbody)

    st_TryStar = st_Try

    def st_Return(self, s):
        t = self.ty(s.value) if s.value is not None else "None"
        if self.scope is not None:
            self.add(("ret", self.scope.qual), t)

    def st_Global(self, s):
        pass

    st_Nonlocal = st_Import = st_ImportFrom = st_Pass = st_Break = st_Continue = st_Global

    # ------------------------------------------------------------------ assignment
    def assign(self, tg, t, src):
        if isinstance(tg, ast.Name):
            if self.in_env(tg.id):
                for d in reversed(self.env):
                    if tg.id in d:
                        d[tg.id] = join(d[tg.id], t)
                        break
                return
            key = self.var_key(tg.id)
            self.add(key, t)
            self.types[tg] = self.slots.get(key)
            cur = self.slots.get(key)
            if src is not None and isinstance(cur, tuple) and cur[0] in ("list", "dict", "set"):
                self.lv_add(src, cur)                   # aliasing: b = a shares the container
        elif isinstance(tg, (ast.Tuple, ast.List)):
            parts = self.unpack(t, tg.elts)
            self.types[tg] = t
            for e, p in zip(tg.elts, parts):
                self.assign(e, p, None)
        elif isinstance(tg, ast.Starred):
            self.assign(tg.value, t, None)
        elif isinstance(tg, (ast.Attribute, ast.Subscript)):
            self.lv_add(tg, t)
            self.types[tg] = t

    def unpack(self, t, elts):
        n = len(elts)
        star = [i for i, e in enumerate(elts) if isinstance(e, ast.Starred)]
        if isinstance(t, tuple) and t[0] == "tuple" and not star and len(t[1]) == n:
            return list(t[1])
        if isinstance(t, tuple) and t[0] == "bad":
            return [t] * n
        e = elem(t)
        if isinstance(t, tuple) and t[0] == "tuple" and star:
            e = elem(t)
        return [("list", e) if i in star else e for i in range(n)]

    def lv_add(self, n, t):
        """Evidence that the storage location written as `n` holds a value of type t."""
        if t is None:
            return
        if isinstance(n, ast.Name):
            if self.in_env(n.id):
                return
            key = self.load_key(n.id) if not isinstance(n.ctx, ast.Store) else self.var_key(n.id)
            if key is not None:
                self.add(key, t)
        elif isinstance(n, ast.Attribute):
            bt = self.ty(n.value)
            if isinstance(bt, tuple) and bt[0] == "opt":
                bt = bt[1]
            if isinstance(bt, tuple) and bt[0] == "cls":
                self.add(self.attr_key(bt[1], n.attr), t)
            elif isinstance(bt, tuple) and bt[0] == "clsref":
                self.add(("attr", bt[1], n.attr), t)
        elif isinstance(n, ast.Subscript):
            bt = self.ty(n.value)
            if isinstance(bt, tuple) and bt[0] == "rec":
                k = n.slice
                if isinstance(k, ast.Constant) and k.value in bt[1]:
                    self.add(("field", bt[1], k.value), t)
                return
            if isinstance(n.slice, ast.Slice):
                self.ty(n.slice)
                self.lv_add(n.value, ("list", elem(t)))
                return
            kt = self.ty(n.slice)
            if isinstance(bt, tuple) and bt[0] == "dict" or (bt is None and kt == "str"):
                self.lv_add(n.value, ("dict", kt, t))
            elif isinstance(bt, tuple) and bt[0] == "list":
                self.lv_add(n.value, ("list", t))
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "setdefault" and n.args:
            kt = self.ty(n.args[0])
            self.lv_add(n.func.value, ("dict", kt, t))

    # ------------------------------------------------------------------ expressions
    def ty(self, n):
        if n is None:
            return None
        m = getattr(self, "ex_" + type(n).__name__, None)
        if m is None:
            for c in ast.iter_child_nodes(n):
                if isinstance(c, ast.expr):
                    self.ty(c)
            t = None
        else:
            t = m(n)
        self.types[n] = t
        return t

    def ex_Constant(self, n):
        v = n.value
        if isinstance(v, bool):
            return "bool"
        if v is None:
            return "None"
        if isinstance(v, int):
            return "int"
        if isinstance(v, float):
            return "float"
        if isinstance(v, str):
            return "str"
        return None

    def ex_Name(self, n):
        return self.lookup(n.id)

    def ex_JoinedStr(self, n):
        for v in n.values:
            self.ty(v)
        return "str"

    def ex_FormattedValue(self, n):
        self.ty(n.value)
        if n.format_spec is not None:
            self.ty(n.format_spec)
        return "str"

    def ex_List(self, n):
        r = None
        for e in n.elts:
            t = self.ty(e)
            r = join(r, elem(t) if isinstance(e, ast.Starred) else t)
        return ("list", r)

    def ex_Set(self, n):
        return ("set", self.ex_List(n)[1])

    def ex_Tuple(self, n):
        ts = [self.ty(e) for e in n.elts]
        if any(isinstance(e, ast.Starred) for e in n.elts):
            return None
        return ("tuple", tuple(ts))

    def ex_Starred(self, n):
        return self.ty(n.value)

    def ex_Dict(self, n):
        rid = self.rec_lits.get(id(n))
        if rid is not None:
            for k, v in zip(n.keys, n.values):
                self.ty(k)
                self.add(("field", rid, k.value), self.ty(v))
            return ("rec", rid)
        kt = vt = None
        for k, v in zip(n.keys, n.values):
            if k is None:
                t = self.ty(v)
                if isinstance(t, tuple) and t[0] == "dict":
                    kt, vt = join(kt, t[1]), join(vt, t[2])
                continue
            kt = join(kt, self.ty(k))
            vt = join(vt, self.ty(v))
        return ("dict", kt, vt)

    def ex_BinOp(self, n):
        return self.binop(n.op, self.ty(n.left), self.ty(n.right))

    def binop(self, op, a, b):
        if isinstance(a, tuple) and a[0] == "opt":
            a = a[1]
        if isinstance(b, tuple) and b[0] == "opt":
            b = b[1]
        if is_bad(a):
            return a
        if is_bad(b):
            return b
        N = ("bool", "int", "float", "num")
        if a in N and b in N:
            if isinstance(op, ast.Div):
                return "float"
            if isinstance(op, (ast.BitAnd, ast.BitOr, ast.BitXor)):
                return "bool" if a == b == "bool" else "int"
            if isinstance(op, (ast.LShift, ast.RShift)):
                return "int"
            if "float" in (a, b):
                return "float"
            if "num" in (a, b):
                return "num"
            return "int"
        if isinstance(op, ast.Add):
            if a == "str" or b == "str":
                return "str"
            if isinstance(a, tuple) and isinstance(b, tuple) and a[0] == b[0] == "list":
                return join(a, b)
            if isinstance(a, tuple) and isinstance(b, tuple) and a[0] == b[0] == "tuple":
                return ("tuple", a[1] + b[1])
            for x in (a, b):
                if isinstance(x, tuple) and x[0] == "list":
                    return x
            return None
        if isinstance(op, ast.Mult):
            for x, y in ((a, b), (b, a)):
                if (x == "str" or isinstance(x, tuple) and x[0] == "list") and y in ("int", "bool", None):
                    return x
            return None
        if isinstance(op, ast.Mod) and a == "str":
            return "str"
        if isinstance(op, (ast.BitOr, ast.BitAnd, ast.Sub, ast.BitXor)) and isinstance(a, tuple) and a[0] == "set":
            return join(a, b) if isinstance(b, tuple) and b[0] == "set" else a
        if a is None or b is None:
            if isinstance(op, ast.Div):
                return "float"
            return None
        return None

    def ex_UnaryOp(self, n):
        t = self.ty(n.operand)
        if isinstance(n.op, ast.Not):
            return "bool"
        if isinstance(n.op, ast.Invert):
            return "int"
        return "int" if t == "bool" else t

    def ex_BoolOp(self, n):
        r = None
        for v in n.values:
            r = join(r, self.ty(v))
        return r

    def ex_Compare(self, n):
        self.ty(n.left)
        for c in n.comparators:
            self.ty(c)
        return "bool"

    def ex_IfExp(self, n):
        self.ty(n.test)
        return join(self.ty(n.body), self.ty(n.orelse))

    def ex_NamedExpr(self, n):
        t = self.ty(n.value)
        self.assign(n.target, t, n.value)
        return t

    def ex_Lambda(self, n, argtypes=()):
        a = n.args
        names = [p.arg for p in a.posonlyargs + a.args + a.kwonlyargs]
        env = {nm: (argtypes[i] if i < len(argtypes) else None) for i, nm in enumerate(names)}
        self.env.append(env)
        r = self.ty(n.body)
        self.env.pop()
        for p in a.posonlyargs + a.args:
            self.types[p] = env.get(p.arg)
        self.types[n] = ("lambda",)
        return ("lambda", r)

    def lam(self, n, argtypes):
        """A lambda argument bound to known parameter types; returns its body type."""
        if isinstance(n, ast.Lambda):
            r = self.ex_Lambda(n, argtypes)[1]
            self.types[n] = ("lambda",)
            return r
        t = self.ty(n)
        if isinstance(t, tuple) and t[0] == "fn":
            return self.slots.get(("ret", t[1]))
        return None

    def _comp(self, gens, elts):
        env = {}
        self.env.append(env)
        for g in gens:
            it = self.ty(g.iter)
            self._bind(g.target, elem(it), env)
            for c in g.ifs:
                self.ty(c)
        r = [self.ty(e) for e in elts]
        self.env.pop()
        return r

    def _bind(self, tg, t, env):
        self.types[tg] = t
        if isinstance(tg, ast.Name):
            env[tg.id] = t
        elif isinstance(tg, (ast.Tuple, ast.List)):
            for e, p in zip(tg.elts, self.unpack(t, tg.elts)):
                self._bind(e, p, env)

    def ex_ListComp(self, n):
        return ("list", self._comp(n.generators, [n.elt])[0])

    def ex_SetComp(self, n):
        return ("set", self._comp(n.generators, [n.elt])[0])

    def ex_GeneratorExp(self, n):
        return ("iter", self._comp(n.generators, [n.elt])[0])

    def ex_DictComp(self, n):
        k, v = self._comp(n.generators, [n.key, n.value])
        return ("dict", k, v)

    def ex_Subscript(self, n):
        bt = self.ty(n.value)
        if isinstance(bt, tuple) and bt[0] == "opt":
            bt = bt[1]
        if isinstance(n.slice, ast.Slice):
            self.ty(n.slice)
            if bt == "str" or isinstance(bt, tuple) and bt[0] in ("list", "tuple"):
                return bt if not (isinstance(bt, tuple) and bt[0] == "tuple") else None
            return None
        if isinstance(bt, tuple) and bt[0] == "rec":
            self.ty(n.slice)
            k = n.slice
            if isinstance(k, ast.Constant) and k.value in bt[1]:
                return self.slots.get(("field", bt[1], k.value))
            return None
        kt = self.ty(n.slice)
        if bt == "str":
            return "str"
        if isinstance(bt, tuple):
            if bt[0] == "list":
                return bt[1]
            if bt[0] == "dict":
                if bt[1] is None and kt is not None:
                    self.lv_add(n.value, ("dict", kt, None))
                return bt[2]
            if bt[0] == "tuple":
                k = n.slice
                if isinstance(k, ast.UnaryOp) and isinstance(k.op, ast.USub) and isinstance(k.operand, ast.Constant):
                    k = ast.Constant(-k.operand.value)
                if isinstance(k, ast.Constant) and isinstance(k.value, int) and -len(bt[1]) <= k.value < len(bt[1]):
                    return bt[1][k.value]
                return elem(bt)
            if bt[0] == "bad":
                return bt
        return None

    def ex_Attribute(self, n):
        bt = self.ty(n.value)
        if isinstance(bt, tuple) and bt[0] == "opt":
            bt = bt[1]
        if not isinstance(bt, tuple):
            return None
        if bt[0] == "mod":
            if bt[1] == "math" and n.attr in MATH_CONST:
                return "float"
            if bt[1] == "sys" and n.attr == "maxsize":
                return "int"
            if bt[1] == "string":
                return "str"
            return None
        if bt[0] in ("cls", "clsref"):
            m = self.find_method(bt[1], n.attr)
            if m is not None and not any(n.attr in k.attrs for k in self.mro(bt[1])):
                return ("fn", m.qual)
            return self.slots.get(self.attr_key(bt[1], n.attr))
        return None

    # ------------------------------------------------------------------ calls
    def ex_Call(self, n):
        f = n.func
        if isinstance(f, ast.Name) and not self.in_env(f.id) and self.load_key(f.id) is None:
            name = f.id
            if name in self.top_funcs:
                return self.call_user(self.top_funcs[name], n, False)
            if name in self.classes:
                init = self.find_method(name, "__init__")
                if init is not None:
                    self.call_user(init, n, True)
                else:
                    self._args(n)
                self.call_kind[n] = "user"
                return ("cls", name)
            if name in self.imports and self.imports[name][0] == "from":
                return self.call_lib(self.imports[name][1], self.imports[name][2], n)
            return self.call_builtin(name, n)
        if isinstance(f, ast.Attribute):
            bt = self.ty(f.value)
            if isinstance(bt, tuple) and bt[0] == "opt":
                bt = bt[1]
            if isinstance(bt, tuple) and bt[0] == "mod":
                return self.call_lib(bt[1], f.attr, n)
            if isinstance(bt, tuple) and bt[0] in ("cls", "clsref"):
                m = self.find_method(bt[1], f.attr)
                if m is not None:
                    skip = m.kind == "method" and bt[0] == "cls" or m.kind == "classmethod"
                    return self.call_user(m, n, skip)
                self._args(n)
                return None
            return self.call_method(bt, f.attr, n, f.value)
        ft = self.ty(f)
        if isinstance(ft, tuple) and ft[0] == "fn" and ft[1] in self.funcs:
            return self.call_user(self.funcs[ft[1]], n, False)
        if isinstance(ft, tuple) and ft[0] == "lambda":
            self._args(n)
            return ft[1]
        self._args(n)
        return None

    def _args(self, n, skip=()):
        out = []
        for i, a in enumerate(n.args):
            out.append(None if i in skip else self.ty(a))
        for k in n.keywords:
            if k.arg not in skip:
                self.ty(k.value)
        return out

    def call_user(self, func: Func, n, skip_first: bool):
        self.call_kind[n] = "user"
        a = func.node.args
        pos = a.posonlyargs + a.args
        if skip_first:
            pos = pos[1:]
        for i, arg in enumerate(n.args):
            t = self.ty(arg)
            if isinstance(arg, ast.Starred):
                break
            if i < len(pos):
                self.param(func, pos[i].arg, t, arg)
        names = {p.arg for p in pos + a.kwonlyargs}
        for k in n.keywords:
            t = self.ty(k.value)
            if k.arg in names:
                self.param(func, k.arg, t, k.value)
        if func.generator:
            return None
        return self.slots.get(("ret", func.qual))

    def param(self, func, pname, t, argnode):
        key = ("var", func.qual, pname)
        self.add(key, t)
        pt = self.slots.get(key)
        if isinstance(pt, tuple) and pt[0] in ("list", "dict", "set"):
            self.lv_add(argnode, pt)                   # the callee fills a container the caller passed

    def call_lib(self, mod, attr, n):
        if mod == "math":
            args = self._args(n)
            if attr in MATH_FLOAT:
                return "float"
            if attr in MATH_INT:
                return "int"
            if attr in ("isclose", "isnan", "isinf", "isfinite"):
                return "bool"
            if attr == "prod":
                return elem(args[0]) if args else None
            return None
        if mod == "collections":
            if attr == "deque":
                args = self._args(n)
                return args[0] if args and args[0] is not None else ("list", None)
            if attr == "defaultdict":
                self._args(n)
                fa = n.args[0] if n.args else None
                if isinstance(fa, ast.Name) and fa.id in FACTORY:
                    return ("dict", None, FACTORY[fa.id])
                if isinstance(fa, ast.Lambda):
                    return ("dict", None, self.lam(fa, []))
                return ("dict", None, None)
            if attr == "Counter":
                args = self._args(n)
                return ("dict", elem(args[0]) if args else None, "int")
            if attr == "OrderedDict":
                args = self._args(n)
                return args[0] if args else ("dict", None, None)
        if mod == "heapq":
            args = self._args(n)
            if attr == "heappush":
                if len(n.args) >= 2 and args[1] is not None:
                    self.lv_add(n.args[0], ("list", args[1]))
                return "None"
            if attr in ("heappop", "heappushpop", "heapreplace"):
                if len(n.args) >= 2 and attr in ("heappushpop", "heapreplace") and args[1] is not None:
                    self.lv_add(n.args[0], ("list", args[1]))
                return elem(args[0]) if args else None
            if attr == "heapify":
                return "None"
        if mod == "bisect":
            args = self._args(n)
            if attr.startswith("bisect"):
                return "int"
            if attr.startswith("insort"):
                if len(n.args) >= 2 and args[1] is not None:
                    self.lv_add(n.args[0], ("list", args[1]))
                return "None"
        if mod == "copy":
            args = self._args(n)
            return args[0] if args else None
        if mod == "itertools":
            args = self._args(n)
            if attr == "accumulate":
                return args[0] if args else None
            if attr == "chain":
                return args[0] if args else None
        if mod == "functools":
            args = self._args(n)
            if attr == "reduce":
                if len(args) >= 3 and args[2] is not None:
                    return args[2]
                return elem(args[1]) if len(args) >= 2 else None
            if attr in ("lru_cache", "cache", "wraps", "total_ordering"):
                return "None"
        if mod == "enum":
            self._args(n)
            return "int" if attr == "auto" else None
        self._args(n)
        return None

    def call_builtin(self, name, n):
        kw = {k.arg: k.value for k in n.keywords}
        key = kw.get("key")
        args = []
        if name in ("sorted", "min", "max") and n.args:
            args = [self.ty(a) for a in n.args]
            et = elem(args[0]) if len(args) == 1 else None
            if len(args) > 1:
                for t in args:
                    et = join(et, t)
            if key is not None:
                self.lam(key, [et])
            for k in n.keywords:
                if k.arg != "key":
                    self.ty(k.value)
        elif name in ("map", "filter") and n.args:
            args = [None] + [self.ty(a) for a in n.args[1:]]
            fn = n.args[0]
            r = self.lam(fn, [elem(t) for t in args[1:]]) if not (isinstance(fn, ast.Name) and fn.id in FACTORY) \
                else FACTORY[fn.id]
            self.types[fn] = self.types.get(fn)
            if name == "map":
                return ("iter", r)
            return ("iter", elem(args[1]) if len(args) > 1 else None)
        else:
            args = self._args(n)
        self.call_kind[n] = name
        A = lambda i: args[i] if i < len(args) else None  # noqa: E731
        if name in ("len", "ord", "hash", "id", "int"):
            return "int"
        if name == "float":
            return "float"
        if name in ("str", "repr", "chr", "hex", "bin", "oct", "ascii", "format", "input"):
            return "str"
        if name in ("bool", "isinstance", "callable", "hasattr", "any", "all", "issubclass"):
            return "bool"
        if name == "print":
            return "None"
        if name == "abs":
            return "int" if A(0) == "bool" else A(0)
        if name == "round":
            if len(n.args) == 1 and "ndigits" not in kw:
                return "int"
            return "int" if A(0) == "bool" else A(0)
        if name in ("min", "max"):
            r = elem(A(0)) if len(args) == 1 else None
            if len(args) > 1:
                for t in args:
                    r = join(r, t)
            if "default" in kw:
                r = join(r, self.types.get(kw["default"]))
            return r
        if name == "sum":
            start = A(1) if len(args) > 1 else self.types.get(kw.get("start")) if "start" in kw else "int"
            e = elem(A(0))
            return None if e is None else self.binop(ast.Add(), start, e)
        if name == "sorted":
            return ("list", elem(A(0)))
        if name in ("reversed", "iter"):
            return ("iter", elem(A(0)))
        if name == "list":
            return ("list", elem(A(0)) if args else None)
        if name in ("set", "frozenset"):
            return ("set", elem(A(0)) if args else None)
        if name == "dict":
            if args and isinstance(A(0), tuple) and A(0)[0] == "dict":
                return A(0)
            if not args and kw:
                vt = None
                for v in kw.values():
                    vt = join(vt, self.types.get(v))
                return ("dict", "str", vt)
            if args:
                e = elem(A(0))
                if isinstance(e, tuple) and e[0] == "tuple" and len(e[1]) == 2:
                    return ("dict", e[1][0], e[1][1])
                return None
            return ("dict", None, None)
        if name == "range":
            return ("range",)
        if name == "enumerate":
            return ("iter", ("tuple", ("int", elem(A(0)))))
        if name == "zip":
            return ("iter", ("tuple", tuple(elem(t) for t in args)))
        if name == "divmod":
            r = self.binop(ast.FloorDiv(), A(0), A(1))
            return ("tuple", (r, r))
        if name == "pow":
            return self.binop(ast.Pow(), A(0), A(1))
        if name == "next":
            return elem(A(0))
        if name == "tuple":
            return None
        return None

    def call_method(self, bt, m, n, recv):
        kw = {k.arg: k.value for k in n.keywords}
        kind = bt[0] if isinstance(bt, tuple) else bt
        if bt is None:
            kind = "str" if m in STR_ONLY else "list" if m in ("append", "extend", "insert") else \
                "set" if m == "add" else "dict" if m in ("items", "keys", "values", "setdefault") else None
        if kind == "list" and m == "sort":
            self._args(n, skip=("key",))
            if "key" in kw:
                self.lam(kw["key"], [elem(bt)])
            self.call_kind[n] = "list.sort"
            return "None"
        args = self._args(n)
        A = lambda i: args[i] if i < len(args) else None  # noqa: E731
        self.call_kind[n] = f"{kind}.{m}"
        if kind == "str":
            if bt is None:
                self.lv_add(recv, "str")
            return STR_RET.get(m)
        if kind == "list":
            if m in ("append", "appendleft"):
                self.lv_add(recv, ("list", A(0)))
                return "None"
            if m == "extend":
                self.lv_add(recv, ("list", elem(A(0))))
                return "None"
            if m == "insert":
                self.lv_add(recv, ("list", A(1)))
                return "None"
            if m in ("pop", "popleft"):
                return elem(bt)
            if m in ("index", "count"):
                return "int"
            if m == "copy":
                return bt
            return "None" if m in ("remove", "clear", "reverse") else None
        if kind == "dict":
            K, V = (bt[1], bt[2]) if isinstance(bt, tuple) and bt[0] == "dict" else (None, None)
            if bt is None and args:
                self.lv_add(recv, ("dict", A(0), None))
            if m == "get":
                if A(0) is not None and K is None:
                    self.lv_add(recv, ("dict", A(0), None))
                return join(V, A(1) if len(args) > 1 else "None")
            if m == "setdefault":
                self.lv_add(recv, ("dict", A(0), A(1)))
                return join(V, A(1))
            if m == "keys":
                return ("iter", K)
            if m == "values":
                return ("iter", V)
            if m == "items":
                return ("iter", ("tuple", (K, V)))
            if m == "pop":
                return join(V, A(1)) if len(args) > 1 else V
            if m == "update":
                if isinstance(A(0), tuple) and A(0)[0] == "dict":
                    self.lv_add(recv, A(0))
                return "None"
            if m == "copy":
                return bt
            if m == "popitem":
                return ("tuple", (K, V))
            return "None" if m == "clear" else None
        if kind == "set":
            if m == "add":
                self.lv_add(recv, ("set", A(0)))
                return "None"
            if m == "update":
                self.lv_add(recv, ("set", elem(A(0))))
                return "None"
            if m in ("union", "intersection", "difference", "symmetric_difference", "copy"):
                return bt
            if m in ("issubset", "issuperset", "isdisjoint"):
                return "bool"
            if m == "pop":
                return elem(bt)
            return "None"
        if kind == "tuple" and m in ("index", "count"):
            return "int"
        if kind == "bad":
            return bt
        return None


# ---------------------------------------------------------------------- record detection
def record_keys(n: ast.Dict) -> Optional[tuple]:
    """The key tuple if this dict literal could be a record (fixed identifier-like string keys)."""
    keys = []
    for k in n.keys:
        if not (isinstance(k, ast.Constant) and isinstance(k.value, str) and k.value.isidentifier()
                and not keyword.iskeyword(k.value) and not k.value.startswith("__") and k.value != "self"):
            return None
        keys.append(k.value)
    if not keys or len(set(keys)) != len(keys):
        return None
    return tuple(sorted(keys))


def is_rec(t) -> bool:
    return isinstance(t, tuple) and t[0] == "rec"


def parents(tree):
    p = {}
    for n in ast.walk(tree):
        for c in ast.iter_child_nodes(n):
            p[c] = n
    return p


SINK_CALLS = {"print", "str", "repr", "format", "ascii"}


def sinks(eng: Engine, par) -> List[tuple]:
    """(node, why) for every place a value's int/float-ness or dict-ness becomes visible in the output."""
    out = []
    for n, t in eng.types.items():
        p = par.get(n)
        if p is None or t is None:
            continue
        if isinstance(p, ast.Call) and n in p.args and eng.call_kind.get(p) in SINK_CALLS:
            out.append((n, "printed"))
        elif isinstance(p, ast.FormattedValue) and p.value is n:
            spec = _spec_text(p.format_spec)
            if not (spec and spec[-1] in "eEfFgG%"):
                out.append((n, "printed"))
        elif isinstance(p, ast.Compare) and n is not None and not any(isinstance(o, (ast.Is, ast.IsNot)) for o in p.ops):
            out.append((n, "compared"))
        elif isinstance(p, ast.BinOp) and isinstance(p.op, ast.Mod) and p.right is n and eng.types.get(p.left) == "str":
            out.append((n, "printed"))
    return out


def _spec_text(spec) -> str:
    if spec is None:
        return ""
    if isinstance(spec, ast.JoinedStr) and all(isinstance(v, ast.Constant) for v in spec.values):
        return "".join(v.value for v in spec.values)
    return ""


REC_LIST_METHODS = {"list.append", "list.insert"}


def record_violations(eng: Engine, par) -> Dict[tuple, str]:
    """rid -> plain-English reason it can't become a class."""
    bad: Dict[tuple, str] = {}

    def flag(t, n, why):
        rid = t[1]
        bad.setdefault(rid, f"line {getattr(n, 'lineno', '?')}: {why}")

    for n, t in eng.types.items():
        if not is_rec(t):
            continue
        p = par.get(n)
        keys = t[1]
        if isinstance(p, ast.Subscript) and p.value is n:
            k = p.slice
            if not (isinstance(k, ast.Constant) and k.value in keys):
                flag(t, n, "the dict is indexed with a key that is not one of its fixed keys")
            elif isinstance(p.ctx, ast.Del):
                flag(t, n, "a key is deleted from the dict")
            continue
        if isinstance(p, ast.Call):
            if n is p.func:
                flag(t, n, "the dict is called")
            elif eng.call_kind.get(p) != "user" and eng.call_kind.get(p) not in REC_LIST_METHODS:
                flag(t, n, f"the dict is passed to {eng.call_kind.get(p) or 'a function'}()")
            continue
        if isinstance(p, ast.keyword):
            if eng.call_kind.get(par.get(p)) != "user":
                flag(t, n, "the dict is passed to a library function")
            continue
        if isinstance(p, ast.Compare):
            if not all(isinstance(o, (ast.Is, ast.IsNot)) for o in p.ops):
                flag(t, n, "the dict is compared")
            continue
        if isinstance(p, ast.Dict) and n in p.keys:
            flag(t, n, "the dict is used as a key")
            continue
        if isinstance(p, ast.Attribute):
            flag(t, n, f"dict method .{p.attr}() is used on it")
            continue
        if isinstance(p, (ast.For, ast.comprehension)) and p.iter is n:
            flag(t, n, "the dict is iterated over")
            continue
        if isinstance(p, ast.FormattedValue):
            flag(t, n, "the dict is printed")
            continue
        if isinstance(p, ast.Subscript) and p.slice is n:
            flag(t, n, "the dict is used as an index")
            continue
        if isinstance(p, (ast.BinOp, ast.AugAssign)):
            flag(t, n, "the dict is used in arithmetic")
            continue
        if isinstance(p, ast.Lambda):
            flag(t, n, "a lambda returns the dict itself")
            continue
    for n, why in sinks(eng, par):
        t = eng.types.get(n)
        if why in ("printed", "compared") and contains(t, is_rec):
            sub = t if is_rec(t) else _find(t, is_rec)
            flag(sub, n, f"the dict is {why} (a class would {('print' if why == 'printed' else 'compare')} differently)")
    for key, t in eng.slots.items():
        if is_bad(t) and isinstance(t[1], str) and "record dict" in t[1]:
            pass
    return bad


def _find(t, pred):
    if pred(t):
        return t
    if isinstance(t, tuple):
        for x in t[1:]:
            for y in (x if isinstance(x, tuple) and x and not isinstance(x[0], str) else (x,)):
                r = _find(y, pred)
                if r is not None:
                    return r
    return None


def infer(tree: ast.Module, seeds=None, use_records: bool = True):
    """Run inference; turn mixed-type dict literals into records when every use allows it.
    Returns (engine, {rid: [dict nodes]}, {rid: reason a candidate was rejected})."""
    eng = Engine(tree, seeds=seeds).run()
    if not use_records:
        return eng, {}, {}
    cands: Dict[tuple, list] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            rid = record_keys(n)
            if rid is None:
                continue
            vt = None
            for v in n.values:
                vt = join(vt, eng.types.get(v))
            cands.setdefault(rid, []).append((n, is_bad(vt)))
    live = {rid: [n for n, _ in v] for rid, v in cands.items() if any(b for _, b in v)}
    rejected: Dict[tuple, str] = {}
    par = parents(tree)
    for _ in range(4):
        if not live:
            return eng, {}, rejected
        lits = {id(n): rid for rid, ns in live.items() for n in ns}
        e2 = Engine(tree, rec_lits=lits, seeds=seeds).run()
        v = record_violations(e2, par)
        # a record that ends up mixed with anything else (another dict, None in a non-Optional place) fails too
        for key, t in e2.slots.items():
            if is_bad(t):
                for rid in live:
                    if "record dict" in t[1] and rid not in v:
                        v[rid] = f"a record dict is mixed with other values ({key[-1]})"
        if not v:
            return e2, live, rejected
        for rid, why in v.items():
            if rid in live:
                rejected[rid] = why
                live.pop(rid)
    return Engine(tree, seeds=seeds).run(), {}, rejected


__all__ = ["Engine", "infer", "Func", "Klass", "MODULE", "sinks", "parents", "complete", "CONTAINERS"]
