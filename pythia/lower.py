"""
PYTHIA :: Phase 4 -- Semantic Normalisation (TAST -> PIR)
Owner: Member 3 (Koliparthy Venkata Jahnavi)

This is the pass that makes the translation *semantics-preserving* rather
than merely syntax-preserving.  It does two things:

  1. Makes every implicit Python coercion explicit, by wrapping expressions
     in `Coerce` nodes.  After this pass the tree is homogeneously typed and
     the emitter never has to guess.

  2. Records a *Semantic Fidelity Report*: every construct whose C image is
     not bit-for-bit identical to CPython is logged with source position,
     the divergence class, and the mitigation applied.  A transpiler that
     silently approximates is a miscompiler; one that reports is a tool.
"""
from dataclasses import dataclass
from typing import List, Optional
from . import ast_nodes as A
from .typecheck import Ty, INT, FLOAT, BOOL, STR, NONE, ERR, TypeChecker
from . import builtins_ext as _bx
from . import tuples as _tup


@dataclass
class FidelityNote:
    line: int
    col: int
    cls: str          # divergence class
    detail: str
    mitigation: str
    severity: str     # 'exact' | 'guarded' | 'divergent'

    def __str__(self) -> str:
        return (f"{self.line}:{self.col}: [{self.severity.upper()}] {self.cls}\n"
                f"    {self.detail}\n    mitigation: {self.mitigation}")


# The seven divergence classes PYTHIA currently recognises.
D_INTWIDTH  = "D1 unbounded-int vs int64"
D_FLOORDIV  = "D2 floor-division rounding direction"
D_MODSIGN   = "D3 modulo sign convention"
D_TRUEDIV   = "D4 true division always yields float"
D_NEGINDEX  = "D5 negative indexing and bounds checking"
D_POWNEG    = "D6 int ** negative int changes result type"
D_MEMORY    = "D7 object lifetime / reclamation"
D_EXC       = "D8 exception propagation across a call boundary"
D_FIELDINIT = "D9 class fields are zero-initialised before __init__ runs"
D_SUMFLOAT  = "D10 sum() of an empty list[float]"
D_NANORDER  = "D11 ordering of NaN"
D_STDIN     = "D12 interactive input"
D_ASCII     = "D13 characters are ASCII"


class Lowerer:
    def __init__(self, tc: TypeChecker):
        self.tc = tc
        self.notes: List[FidelityNote] = []
        self._seen = set()

    def note(self, n: A.Node, cls: str, detail: str, mit: str, sev: str) -> None:
        key = (n.line, n.col, cls)
        if key in self._seen:
            return
        self._seen.add(key)
        self.notes.append(FidelityNote(n.line, n.col, cls, detail, mit, sev))

    # ---- entry -------------------------------------------------------------
    def run(self, mod: A.Module) -> List[FidelityNote]:
        for c in mod.classes:
            for m in c.methods:
                self.block(m.body)
        for f in mod.funcs:
            self.block(f.body)
        self.block(mod.main)
        _x.lower_defaults(self, mod)
        _cls.lower_notes(self, mod)           # user comparisons in sort/min/max (classes_ext)
        if mod.classes:
            self.notes.append(FidelityNote(
                0, 0, D_FIELDINIT,
                "CPython raises AttributeError for a field never assigned by "
                "__init__; PySub gives every declared field a zero value "
                "(0 / 0.0 / False / NULL) before __init__ runs.",
                "A field __init__ forgets to set reads as its zero value "
                "instead of raising. Reachable only if __init__ is itself "
                "incomplete, which is a bug in the source program either way.",
                "guarded"))
        if any(v.name == "list" for v in list(mod.globals_.values())) or True:
            self.notes.append(FidelityNote(
                0, 0, D_MEMORY,
                "PySub objects (str, list) are heap-allocated and never freed; "
                "CPython reclaims them by reference counting.",
                "Peak memory may exceed CPython's. Region-based reclamation is "
                "the Review 3 target. Observable output is unaffected.",
                "guarded"))
        return self.notes

    def block(self, body: List[A.Node]) -> None:
        for i, s in enumerate(body):
            body[i] = self.stmt(s)

    # ---- statements --------------------------------------------------------
    def stmt(self, s: A.Node) -> A.Node:
        if isinstance(s, A.Assign):
            if isinstance(s.target, A.Subscript):
                s.target.value = self.expr(s.target.value)
                base = s.target.value.ty
                if base is not None and base.name == "dict":
                    s.target.index = self.coerce(self.expr(s.target.index), base.key)
                else:
                    s.target.index = self.coerce(self.expr(s.target.index), INT)
            elif isinstance(s.target, A.Attribute):
                s.target.value = self.expr(s.target.value)
            want = s.ty if s.ty is not None else (s.target.ty or ERR)
            s.value = self.coerce(self.expr(s.value), want)
        elif isinstance(s, A.AugAssign):
            s.value = self.expr(s.value)
            s.target = self.expr(s.target)
            self.check_binop(s, s.op, s.target.ty, s.value.ty)
        elif isinstance(s, A.ExprStmt):
            s.value = self.expr(s.value)
        elif isinstance(s, A.Return):
            if s.value is not None:
                s.value = self.coerce(self.expr(s.value), s.ty or s.value.ty)
        elif isinstance(s, A.If):
            s.test = self.expr(s.test)
            self.block(s.body); self.block(s.orelse)
        elif isinstance(s, A.While):
            s.test = self.expr(s.test)
            self.block(s.body)
        elif isinstance(s, A.ForRange):
            s.start = self.coerce(self.expr(s.start), INT)
            s.stop = self.coerce(self.expr(s.stop), INT)
            if s.step is not None:
                s.step = self.coerce(self.expr(s.step), INT)
            self.block(s.body)
        elif isinstance(s, A.ForEach):
            s.iter = self.expr(s.iter)
            if s.iter.ty is not None and s.iter.ty.name == "tuple":    # for x in (1, 2, 3): iterate a list copy
                s.iter = _tup.tolist_node(s.iter)
            self.block(s.body)
        elif isinstance(s, A.TryExcept):
            self.note(s, D_EXC,
                      "Python unwinds the call stack to the nearest matching "
                      "except; C has no built-in unwinding mechanism.",
                      "compiled with setjmp/longjmp through a per-thread "
                      "handler stack; the runtime raises by longjmp-ing to "
                      "the innermost matching frame, which matches Python's "
                      "dynamic-scope exception search.", "exact")
            self.block(s.body)
            for h in s.handlers:
                self.block(h.body)
        elif isinstance(s, A.Raise):
            if s.message is not None:
                s.message = self.coerce(self.expr(s.message), STR)
        return s

    # ---- expressions -------------------------------------------------------
    def expr(self, e: Optional[A.Node]) -> Optional[A.Node]:
        if e is None:
            return None
        ext = _x.lower_expr(self, e)          # sets, None tests, isinstance, Optional branches
        if ext is not None:
            return ext
        if isinstance(e, (A.ListComp, A.DictComp, A.GenExp, A.Lambda)):
            from .comprehensions import lower_expr
            return lower_expr(self, e)
        if isinstance(e, A.BinOp):
            e.left = self.expr(e.left)
            e.right = self.expr(e.right)
            lt, rt = e.left.ty, e.right.ty
            self.check_binop(e, e.op, lt, rt)
            if lt.name in ("int", "float", "bool") and rt.name in ("int", "float", "bool"):
                target = FLOAT if (e.ty == FLOAT or e.op == "/") else INT
                if e.op == "**" and e.ty == INT:
                    target = INT
                e.left = self.coerce(e.left, target)
                e.right = self.coerce(e.right, target)
            elif e.op == "*" and (lt == STR or rt == STR):
                if lt == STR:
                    e.right = self.coerce(e.right, INT)
                else:
                    e.left = self.coerce(e.left, INT)
            return e

        if isinstance(e, A.Compare):
            e.left = self.expr(e.left); e.right = self.expr(e.right)
            if e.op in ("in", "not in"):
                rt = e.right.ty
                if rt is not None and rt.name == "dict":
                    e.left = self.coerce(e.left, rt.key)
                elif rt is not None and rt.name == "list":
                    e.left = self.coerce(e.left, rt.elem)
                return e
            lt, rt = e.left.ty, e.right.ty
            if lt.name in ("int", "float", "bool") and rt.name in ("int", "float", "bool"):
                target = FLOAT if FLOAT in (lt, rt) else INT
                e.left = self.coerce(e.left, target)
                e.right = self.coerce(e.right, target)
            return e

        if isinstance(e, A.BoolOp):
            e.values = [self.coerce(self.expr(v), e.ty) for v in e.values]
            return e

        if isinstance(e, A.IfExp):
            e.test, e.body, e.orelse = self.expr(e.test), self.expr(e.body), self.expr(e.orelse)
            return e

        if isinstance(e, A.TupleLit):            # tuple types match exactly: nothing to coerce
            e.elts = [self.expr(x) for x in e.elts]
            return e

        if isinstance(e, A.UnaryOp):
            e.operand = self.expr(e.operand)
            if e.op == "-" and e.ty == INT:
                self.note(e, D_INTWIDTH,
                          "unary negation of an int64 traps at INT64_MIN, where "
                          "CPython would return 2**63.",
                          "guarded by py_neg_i64(); raises OverflowError instead "
                          "of silently wrapping.", "guarded")
            return e

        if isinstance(e, A.Subscript):
            e.value = self.expr(e.value)
            e.index = self.coerce(self.expr(e.index), INT)
            self.note(e, D_NEGINDEX,
                      "Python supports negative indices and raises IndexError "
                      "out of range; C does neither.",
                      "index normalised and bounds-checked in the runtime; "
                      "IndexError reproduced exactly.", "exact")
            return e

        if isinstance(e, A.ListLit):
            elem = e.ty.elem if e.ty and e.ty.name == "list" else None
            e.elts = [self.coerce(self.expr(x), elem) if elem else self.expr(x)
                      for x in e.elts]
            return e

        if isinstance(e, A.DictLit):
            k = e.ty.key if e.ty and e.ty.name == "dict" else None
            v = e.ty.elem if e.ty and e.ty.name == "dict" else None
            e.keys = [self.coerce(self.expr(x), k) if k else self.expr(x) for x in e.keys]
            e.values = [self.coerce(self.expr(x), v) if v else self.expr(x) for x in e.values]
            return e

        if isinstance(e, A.Attribute):
            e.value = self.expr(e.value)
            return e

        if isinstance(e, A.MethodCall):
            e.recv = self.expr(e.recv)
            rt = e.recv.ty
            if e.method == "append" and rt and rt.name == "list":
                e.args = [self.coerce(self.expr(e.args[0]), rt.elem)]
            elif rt and rt.name == "dict" and e.method == "get":
                e.args = [self.coerce(self.expr(e.args[0]), rt.key),
                         self.coerce(self.expr(e.args[1]), rt.elem)]
            elif rt and rt.name in self.tc.classes:
                info = self.tc.classes[rt.name]
                msig = info.methods.get(e.method)
                e.args = [self.coerce(self.expr(a), t)
                         for a, t in zip(e.args, msig.params)] if msig else \
                         [self.expr(a) for a in e.args]
            else:
                e.args = [self.expr(a) for a in e.args]
            for kw in e.kwargs:
                kw.value = self.expr(kw.value)
            if rt is not None and rt.name == "list" and e.method in ("sort", "index", "count", "remove"):
                self.builtin_notes(e.method, e, [rt])
            _bx.lower_notes(self, e)
            return e

        if isinstance(e, A.Call):
            sig = self.tc.funcs.get(e.func)
            if sig is not None:
                e.args = [self.coerce(self.expr(a), t)
                          for a, t in zip(e.args, sig.params)]
            elif e.func in self.tc.classes:
                info = self.tc.classes[e.func]
                params = info.init.params if info.init else []
                e.args = [self.coerce(self.expr(a), t)
                          for a, t in zip(e.args, params)]
            elif e.func in ("min", "max"):
                e.args = [self.coerce(self.expr(a), e.ty) for a in e.args]
            else:
                e.args = [self.expr(a) for a in e.args]
            for kw in e.kwargs:
                kw.value = self.expr(kw.value)
            self.builtin_notes(e.func, e, [a.ty for a in e.args])
            _bx.lower_notes(self, e)
            return e

        if isinstance(e, A.Coerce):
            return e
        return e

    def builtin_notes(self, name: str, n: A.Node, arg_tys) -> None:
        lst = arg_tys[0] if arg_tys else None
        float_list = lst is not None and getattr(lst, "name", "") == "list" and lst.elem == FLOAT
        if name == "sum" and float_list:
            self.note(n, D_SUMFLOAT,
                      "CPython's sum() of an EMPTY list[float] is the int 0 (prints 0); the compiled code returns "
                      "0.0 (prints 0.0). Non-empty lists use the same compensated (Neumaier) summation as CPython 3.12+.",
                      "only the empty-list case differs; guard with `if len(xs) > 0` if the output matters.", "guarded")
        if name in ("sort", "sorted", "min", "max", "index", "count", "remove") and float_list:
            self.note(n, D_NANORDER,
                      "NaN compares false with everything, so where NaN ends up after sort()/min()/max() depends on "
                      "the algorithm; the compiled stable merge sort and CPython's timsort can disagree.",
                      "identical for lists without NaN.", "guarded")
        if name in ("ord", "chr"):
            self.note(n, D_ASCII,
                      f"compiled strings hold ASCII characters: {name}() of a character (code point) above 127 raises "
                      "PythiaSemanticError instead of returning what CPython returns.",
                      "identical for ASCII text (letters, digits, punctuation).", "guarded")
        if name == "input":
            self.note(n, D_STDIN,
                      "input() writes the prompt to stdout and reads one line from stdin, as CPython does; end of input "
                      "raises EOFError in both.", "exact; replayed calls never block (stdin is empty in the oracle).",
                      "exact")

    # ---- coercion + fidelity bookkeeping -----------------------------------
    def coerce(self, e: Optional[A.Node], want: Optional[Ty]) -> Optional[A.Node]:
        if e is None or want is None or want is ERR or e.ty is None or e.ty is ERR:
            return e
        if e.ty == want:
            return e
        ext = _x.lower_coerce(self, e, want)  # T -> Optional[T], None -> object, set() -> set[T]
        if ext is not None:
            return ext
        if e.ty.name in ("bool", "int", "float") and want.name in ("bool", "int", "float"):
            c = A.Coerce(e.line, e.col, value=e, to=want)
            c.ty = want
            if e.ty == INT and want == FLOAT:
                self.note(e, D_TRUEDIV,
                          "int operand widened to float, matching CPython's "
                          "numeric tower.",
                          "explicit (double) conversion; exact for |n| < 2**53.",
                          "exact")
            return c
        if e.ty.name == "list" and e.ty.elem is None and want.name == "list":
            e.ty = want
            return e
        if e.ty.name == "dict" and e.ty.key is None and want.name == "dict":
            e.ty = want
            return e
        return e

    def check_binop(self, n: A.Node, op: str, lt: Ty, rt: Ty) -> None:
        both_int = lt == INT and rt == INT
        _bx.binop_notes(self, n, op, lt, rt)
        if op in ("+", "-", "*") and both_int:
            self.note(n, D_INTWIDTH,
                      f"CPython ints are arbitrary precision; the C image uses "
                      f"int64_t, so {op!r} can overflow where CPython cannot.",
                      "checked with __builtin_*_overflow; raises OverflowError "
                      "instead of wrapping. Sound but not complete.", "guarded")
        if op == "//":
            self.note(n, D_FLOORDIV,
                      "Python floors toward -inf; C truncates toward zero, so "
                      "-7 // 2 is -4 in Python and -3 in C.",
                      "emitted as py_floordiv_i64/py_floordiv_f64, which "
                      "reproduces Python exactly.", "exact")
        if op == "%":
            self.note(n, D_MODSIGN,
                      "In Python the sign of % follows the divisor; in C it "
                      "follows the dividend, so -7 % 2 is 1 in Python, -1 in C.",
                      "emitted as py_mod_i64/py_mod_f64; exact.", "exact")
        if op == "/":
            self.note(n, D_TRUEDIV,
                      "Python's / is true division and always produces a float, "
                      "even for two ints; C's / on integers is integer division.",
                      "operands widened to double and divided as py_truediv, "
                      "with ZeroDivisionError preserved.", "exact")
        if op == "**" and both_int:
            self.note(n, D_POWNEG,
                      "int ** negative int returns a float in CPython, changing "
                      "the static type of the expression.",
                      "py_pow_i64 raises PythiaSemanticError at run time; the "
                      "type checker cannot see the exponent's sign. DIVERGENT.",
                      "divergent")


from . import types_ext as _x  # noqa: E402
from . import classes_ext as _cls  # noqa: E402


def lower(mod: A.Module, tc: TypeChecker) -> List[FidelityNote]:
    return Lowerer(tc).run(mod)
