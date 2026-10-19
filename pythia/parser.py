"""
PYTHIA :: Phase 2 -- Syntax Analysis
Owner: Member 1 (Vishal Vivek)

Recursive-descent parser for statements, Pratt (precedence-climbing)
parser for expressions.  Panic-mode error recovery lets one run report
several syntax errors instead of dying on the first.
"""
import copy
from typing import List, Optional
from .lexer import LexError, Token, tokenize
from . import ast_nodes as A
from . import parse_ext as PX
from . import parse_iter as PI


def _chain_tail(e: A.Node) -> Optional[A.Compare]:
    """The last comparison of an unparenthesised comparison chain ending at `e`, else None."""
    if getattr(e, "paren", False):
        return None
    if isinstance(e, A.Compare):
        return e
    if isinstance(e, A.BoolOp) and getattr(e, "chain", False):
        return e.values[1]
    return None


def _pure(e: A.Node) -> bool:
    """Safe to evaluate twice: no calls (side effects), just names, literals, fields and subscripts of those."""
    if isinstance(e, (A.Name, A.IntLit, A.FloatLit, A.StrLit, A.BoolLit)):
        return True
    if isinstance(e, A.UnaryOp) and e.op == "-":
        return _pure(e.operand)
    if isinstance(e, A.Attribute):
        return _pure(e.value)
    if isinstance(e, A.Subscript):
        return _pure(e.value) and _pure(e.index)
    if isinstance(e, A.BinOp):
        return _pure(e.left) and _pure(e.right)
    return False

# Pratt binding powers. Higher binds tighter.
BP = {
    "or": 1, "and": 2,
    "==": 4, "!=": 4, "<": 4, "<=": 4, ">": 4, ">=": 4,
    "|": 5, "^": 6, "&": 7, "<<": 8, ">>": 8,        # Python: comparisons < | < ^ < & < shifts < + -
    "+": 10, "-": 10,
    "*": 12, "/": 12, "//": 12, "%": 12,
    "**": 16,                      # right-associative
}
RIGHT_ASSOC = {"**"}
AUG_OPS = {"+=": "+", "-=": "-", "*=": "*", "/=": "/",
           "//=": "//", "%=": "%", "**=": "**",
           "&=": "&", "|=": "|", "^=": "^", "<<=": "<<", ">>=": ">>"}


class Diagnostic:
    def __init__(self, msg: str, line: int, col: int, kind: str = "SyntaxError"):
        self.msg, self.line, self.col, self.kind = msg, line, col, kind

    def __str__(self) -> str:
        return f"{self.line}:{self.col}: {self.kind}: {self.msg}"


class _Panic(Exception):
    pass


class Parser:
    def __init__(self, tokens: List[Token], filename: str = "<input>"):
        self.toks = tokens
        self.i = 0
        self.filename = filename
        self.errors: List[Diagnostic] = []
        self.imports = PX.Imports()            # `import math` / `from math import sqrt` bindings seen so far

    # ---- token helpers -----------------------------------------------------
    @property
    def cur(self) -> Token:
        return self.toks[self.i]

    def at(self, kind: str, value: Optional[str] = None) -> bool:
        t = self.cur
        return t.kind == kind and (value is None or t.value == value)

    def at_kw(self, *names: str) -> bool:
        return self.cur.kind == "KEYWORD" and self.cur.value in names

    def at_op(self, *ops: str) -> bool:
        return self.cur.kind == "OP" and self.cur.value in ops

    def next(self) -> Token:
        t = self.toks[self.i]
        if t.kind != "EOF":
            self.i += 1
        return t

    def expect(self, kind: str, value: Optional[str] = None) -> Token:
        if self.at(kind, value):
            return self.next()
        want = value if value else kind
        self.error(f"expected {want!r} but found {self.cur.value or self.cur.kind!r}")
        raise _Panic()

    def error(self, msg: str) -> None:
        self.errors.append(Diagnostic(msg, self.cur.line, self.cur.col))

    def synchronize(self) -> None:
        """Panic-mode recovery: skip to the start of the next statement.

        Must always consume at least one token before considering itself
        done, or a caller parked on a boundary token (e.g. a field-parse
        loop that just failed sitting on INDENT) spins forever: it calls
        synchronize(), synchronize() returns without moving, the caller's
        loop condition is unchanged, and it fails on the same token again.
        """
        start = self.i
        depth = 0
        while not self.at("EOF"):
            if self.at("NEWLINE") and depth == 0:
                self.next()
                return
            if self.i > start and (self.at("DEDENT") or self.at("INDENT")):
                return
            if self.i > start and self.at_kw(
                    "def", "if", "while", "for", "return", "pass",
                    "class", "try", "raise", "assert"):
                return
            if self.at_op("(", "["):
                depth += 1
            elif self.at_op(")", "]"):
                depth = max(0, depth - 1)
            self.next()

    # ---- entry point -------------------------------------------------------
    def parse_module(self) -> A.Module:
        mod = A.Module(line=1, col=1)
        while not self.at("EOF"):
            guard = self.i
            if self.at("NEWLINE"):
                self.next()
                continue
            try:
                if self.at_kw("def"):
                    mod.funcs.append(self.parse_funcdef())
                elif self.at_kw("class"):
                    mod.classes.append(self.parse_classdef())
                elif self.at_op("@"):                       # decorated class / function (classes_ext)
                    _cls().parse_decorated(self, mod)
                else:
                    st = self.parse_statement()
                    if self._is_main_guard(st):            # if __name__ == "__main__": runs as the program body
                        mod.main.extend(st.body)
                    else:
                        mod.main.extend(st if isinstance(st, list) else [st])   # unpacking desugars to several
            except _Panic:
                self.synchronize()
            if self.i == guard:      # safety net: never spin with zero progress
                self.next()
        mod.import_table = self.imports
        return mod

    def parse_classdef(self) -> A.ClassDef:
        kw = self.expect("KEYWORD", "class")
        name = self.expect("NAME").value
        bases = _cls().parse_bases(self)              # class C(Base): (classes_ext)
        self.expect("OP", ":")
        self.expect("NEWLINE")
        self.expect("INDENT")
        cd = A.ClassDef(line=kw.line, col=kw.col, name=name)
        cd.bases = bases
        while not self.at("DEDENT") and not self.at("EOF"):
            guard = self.i
            if self.at("NEWLINE"):
                self.next()
                continue
            try:
                if _cls().parse_class_item(self, cd):   # decorators, docstrings, pass, class attributes
                    pass
                elif self.at_kw("def"):
                    cd.methods.append(self.parse_funcdef())
                else:
                    ft = self.expect("NAME")
                    self.expect("OP", ":")
                    ann = self.parse_type()
                    self.expect("NEWLINE")
                    cd.fields.append(A.ClassField(line=ft.line, col=ft.col,
                                                  name=ft.value, ann=ann))
            except _Panic:
                self.synchronize()
            if self.i == guard:      # safety net: never spin with zero progress
                self.next()
        if self.at("DEDENT"):
            self.next()
        return cd

    # ---- declarations ------------------------------------------------------
    def parse_funcdef(self) -> A.FuncDef:
        kw = self.expect("KEYWORD", "def")
        name = self.expect("NAME").value
        self.expect("OP", "(")
        params: List[A.Param] = []
        while not self.at_op(")"):
            pt = self.expect("NAME")
            if pt.value in ("self", "cls") and not params and not self.at_op(":"):
                params.append(A.Param(line=pt.line, col=pt.col, name=pt.value, ann=None))
            else:
                self.expect("OP", ":")
                ann = self.parse_type()
                params.append(A.Param(line=pt.line, col=pt.col, name=pt.value, ann=ann))
                if self.at_op("="):
                    self.next()
                    params[-1].default = self.parse_expr()
                elif any(q.default is not None for q in params[:-1]):
                    self.error("parameter without a default follows parameter with a default")
            if self.at_op(","):
                self.next()
            else:
                break
        self.expect("OP", ")")
        ret = None
        if self.at_op("->"):
            self.next()
            ret = self.parse_type()
        self.expect("OP", ":")
        body = self.parse_block()
        return A.FuncDef(line=kw.line, col=kw.col, name=name,
                         params=params, ret=ret, body=body)

    def parse_type(self) -> A.TypeExpr:
        return self._parse_type_ext()        # parse_types.py: dotted names, T[A, B], A | B, "Forward"

    def parse_block(self) -> List[A.Node]:
        self.expect("NEWLINE")
        self.expect("INDENT")
        stmts: List[A.Node] = []
        while not self.at("DEDENT") and not self.at("EOF"):
            guard = self.i
            if self.at("NEWLINE"):
                self.next()
                continue
            try:
                st = self.parse_statement()
                stmts.extend(st if isinstance(st, list) else [st])   # unpacking desugars to several
            except _Panic:
                self.synchronize()
            if self.i == guard:      # safety net: never spin with zero progress
                self.next()
        if self.at("DEDENT"):
            self.next()
        if not stmts:
            stmts.append(A.Pass())
        return stmts

    # ---- statements --------------------------------------------------------
    def parse_statement(self) -> A.Node:
        t = self.cur
        if self.at_kw("if"):
            return self.parse_if()
        if self.at_kw("while"):
            return self.parse_while()
        if self.at_kw("for"):
            return self.parse_for()
        if self.at_kw("return"):
            self.next()
            val = None
            if not self.at("NEWLINE"):
                val = self.parse_exprlist()
            self.expect("NEWLINE")
            return A.Return(line=t.line, col=t.col, value=val)
        if self.at_kw("pass"):
            self.next(); self.expect("NEWLINE")
            return A.Pass(line=t.line, col=t.col)
        if self.at_kw("break"):
            self.next(); self.expect("NEWLINE")
            return A.Break(line=t.line, col=t.col)
        if self.at_kw("continue"):
            self.next(); self.expect("NEWLINE")
            return A.Continue(line=t.line, col=t.col)
        if self.at_kw("def"):
            self.error("nested function definitions are outside the PySub subset")
            raise _Panic()
        if self.at_kw("try"):
            return self.parse_try()
        if self.at_kw("raise"):
            return self.parse_raise()
        if self.at_kw("assert"):
            return self.parse_assert()
        if self.at("NAME", "global") and self.toks[self.i + 1].kind == "NAME":
            return self._parse_global()
        if self.cur.kind == "NAME" and self.cur.value in ("import", "from") and self.toks[self.i + 1].kind == "NAME":
            return PX.parse_import(self)
        return self.parse_simple()

    def parse_try(self) -> A.TryExcept:
        t = self.expect("KEYWORD", "try")
        self.expect("OP", ":")
        body = self.parse_block()
        handlers: List[A.ExceptHandler] = []
        while self.at_kw("except"):
            ht = self.next()
            names = [None]
            bind = None
            if not self.at_op(":"):
                if self.at_op("("):                       # except (A, B) as e:  ->  one handler per name, same body
                    self.next()
                    names = [self.expect("NAME").value]
                    while self.at_op(","):
                        self.next()
                        names.append(self.expect("NAME").value)
                    self.expect("OP", ")")
                else:
                    names = [self.expect("NAME").value]
                if self.cur.kind == "NAME" and self.cur.value == "as":
                    self.next()
                    bind = self.expect("NAME").value
            self.expect("OP", ":")
            self.exc_binds = getattr(self, "exc_binds", []) + ([bind] if bind else [])
            hbody = self.parse_block()
            if bind:
                self.exc_binds.pop()
            for k, nm in enumerate(names):
                handlers.append(A.ExceptHandler(line=ht.line, col=ht.col, exc_name=nm, bind=bind,
                                                body=hbody if k == 0 else copy.deepcopy(hbody)))
        # `else:` / `finally:` bodies ride along as marker handlers, so every statement walker visits them
        if self.at_kw("else"):
            et = self.next()
            self.expect("OP", ":")
            if not handlers:
                self.error("'try' with 'else' requires an 'except' clause")
                raise _Panic()
            handlers.append(A.ExceptHandler(line=et.line, col=et.col, exc_name="__else__", body=self.parse_block()))
        if self.at("NAME") and self.cur.value == "finally":
            ft = self.next()
            self.expect("OP", ":")
            handlers.append(A.ExceptHandler(line=ft.line, col=ft.col, exc_name="__finally__", body=self.parse_block()))
        if not handlers:
            self.error("'try' block requires an 'except' or 'finally' clause")
            raise _Panic()
        return A.TryExcept(line=t.line, col=t.col, body=body, handlers=handlers)

    def parse_raise(self) -> A.Raise:
        t = self.expect("KEYWORD", "raise")
        if self.at("NEWLINE"):                         # bare `raise` inside an except clause: re-raise
            self.next()
            return A.Raise(line=t.line, col=t.col, exc_name="", message=None)
        name = self.expect("NAME").value
        msg = None
        if self.at_op("("):
            self.next()
            if not self.at_op(")"):
                msg = self.parse_expr()
            self.expect("OP", ")")
        self.expect("NEWLINE")
        return A.Raise(line=t.line, col=t.col, exc_name=name, message=msg)

    def parse_assert(self) -> A.Node:
        t = self.expect("KEYWORD", "assert")
        test = self.parse_expr()
        msg = None
        if self.at_op(","):
            self.next()
            msg = self.parse_expr()
            if not isinstance(msg, A.StrLit):
                msg = A.Call(msg.line, msg.col, func="str", args=[msg], kwargs=[])
        self.expect("NEWLINE")
        not_test = A.UnaryOp(line=t.line, col=t.col, op="not", operand=test)
        raise_stmt = A.Raise(line=t.line, col=t.col, exc_name="AssertionError", message=msg)
        return A.If(line=t.line, col=t.col, test=not_test, body=[raise_stmt], orelse=[])

    def parse_if(self) -> A.If:
        t = self.next()                       # 'if' or 'elif'
        test = self.parse_expr()
        self.expect("OP", ":")
        body = self.parse_block()
        orelse: List[A.Node] = []
        if self.at_kw("elif"):
            orelse = [self.parse_if()]
        elif self.at_kw("else"):
            self.next()
            self.expect("OP", ":")
            orelse = self.parse_block()
        return A.If(line=t.line, col=t.col, test=test, body=body, orelse=orelse)

    def parse_while(self) -> A.While:
        t = self.expect("KEYWORD", "while")
        test = self.parse_expr()
        self.expect("OP", ":")
        return A.While(line=t.line, col=t.col, test=test, body=self.parse_block())

    def parse_for(self) -> A.Node:
        t = self.expect("KEYWORD", "for")
        var = self._for_target()
        self.expect("KEYWORD", "in")
        if not isinstance(var, str):                   # for a, b in xs: -> for tmp in xs: a, b = tmp
            return self._for_unpack(t, var)
        if self.at_kw("range"):
            self.next()
            self.expect("OP", "(")
            args = [self.parse_expr()]
            while self.at_op(","):
                self.next()
                args.append(self.parse_expr())
            self.expect("OP", ")")
            self.expect("OP", ":")
            body = self.parse_block()
            if len(args) == 1:
                start, stop, step = A.IntLit(t.line, t.col, value=0), args[0], None
            elif len(args) == 2:
                start, stop, step = args[0], args[1], None
            elif len(args) == 3:
                start, stop, step = args
            else:
                self.error("range() takes 1 to 3 arguments")
                raise _Panic()
            return A.ForRange(line=t.line, col=t.col, var=var,
                              start=start, stop=stop, step=step, body=body)
        it = self.parse_expr()
        self.expect("OP", ":")
        return PI.fuse_for(A.ForEach(line=t.line, col=t.col, var=var, iter=it,
                                     body=self.parse_block()))

    def parse_simple(self) -> A.Node:
        t = self.cur
        # annotated declaration:  name : T = expr
        if self.at("NAME") and self.toks[self.i + 1].kind == "OP" \
                and self.toks[self.i + 1].value == ":":
            nm = self.next()
            self.next()                       # ':'
            ann = self.parse_type()
            self.expect("OP", "=")
            val = self.parse_exprlist()
            self.expect("NEWLINE")
            return A.Assign(line=nm.line, col=nm.col,
                            target=A.Name(nm.line, nm.col, id=nm.value),
                            ann=ann, value=val)

        if self.at("NAME") and self.cur.value == "del" and self.toks[self.i + 1].kind != "OP":
            return PI.parse_del(self)
        first = self.parse_exprlist()
        if self.at_op(":") and isinstance(first, A.Attribute):     # self.x: T = v (classes_ext)
            return _cls().parse_attr_ann(self, t, first)

        if self.at_op("="):
            self.next()
            val = self.parse_exprlist()
            if self.at_op("="):                        # a = b = v  ->  tmp = v; a = tmp; b = tmp (v evaluated once)
                targets = [first, val]
                while self.at_op("="):
                    self.next()
                    targets.append(self.parse_exprlist())
                value = targets.pop()
                self.expect("NEWLINE")
                tmp = self._fresh_unpack()
                nm = lambda: A.Name(t.line, t.col, id=tmp)          # noqa: E731
                out = [A.Assign(line=t.line, col=t.col, target=nm(), value=value)]
                for tg in targets:
                    if isinstance(tg, A.TupleLit):
                        out += self._unpack_stmts(tg, nm(), t.line, t.col)
                    elif isinstance(tg, (A.Name, A.Subscript, A.Attribute)):
                        out.append(A.Assign(line=t.line, col=t.col, target=tg, value=nm()))
                    else:
                        self.error("invalid assignment target")
                        raise _Panic()
                return out
            self.expect("NEWLINE")
            if isinstance(first, A.Call) and first.func == "__slice":      # a[i:j] = ys
                return A.ExprStmt(line=t.line, col=t.col,
                                  value=A.Call(t.line, t.col, func="__slice_assign", args=first.args + [val], kwargs=[]))
            if isinstance(first, A.TupleLit):          # a, b = ...  ->  tmp = ...; a = tmp[0]; b = tmp[1]
                return self._unpack_stmts(first, val, t.line, t.col)
            if not isinstance(first, (A.Name, A.Subscript, A.Attribute)):
                self.error("invalid assignment target")
                raise _Panic()
            if isinstance(first, A.Name) and isinstance(val, A.Name) and val.id == "__stdin_readline_fn":
                self.readline_aliases = getattr(self, "readline_aliases", set()) | {first.id}   # input = sys.stdin.readline
                return A.Pass(line=t.line, col=t.col)
            return A.Assign(line=t.line, col=t.col, target=first, value=val)

        if self.cur.kind == "OP" and self.cur.value in AUG_OPS:
            op = AUG_OPS[self.next().value]
            val = self.parse_expr()
            self.expect("NEWLINE")
            if not isinstance(first, (A.Name, A.Subscript, A.Attribute)):
                self.error("invalid augmented-assignment target")
                raise _Panic()
            return A.AugAssign(line=t.line, col=t.col, target=first,
                               op=op, value=val)

        self.expect("NEWLINE")
        return A.ExprStmt(line=t.line, col=t.col, value=first)

    # ---- expressions (Pratt) ----------------------------------------------
    def parse_expr(self, min_bp: int = 0) -> A.Node:
        left = self.parse_unary()
        while True:
            t = self.cur
            op = t.value
            is_in = t.kind == "KEYWORD" and op == "in"
            is_not_in = (t.kind == "KEYWORD" and op == "not"
                        and self.toks[self.i + 1].kind == "KEYWORD"
                        and self.toks[self.i + 1].value == "in")
            is_is = t.kind == "NAME" and op == "is"
            is_is_not = is_is and self.toks[self.i + 1].kind == "KEYWORD" and self.toks[self.i + 1].value == "not"
            if t.kind == "KEYWORD" and op in ("and", "or"):
                pass
            elif t.kind == "OP" and op in BP:
                pass
            elif is_in or is_not_in:
                op = "in" if is_in else "not in"
            elif is_is:
                op = "is not" if is_is_not else "is"
            else:
                break
            bp = BP["=="] if (is_in or is_not_in or is_is) else BP[op]
            if bp < min_bp:
                break
            if is_not_in or is_is_not:
                self.next()
            self.next()
            nxt = bp if op in RIGHT_ASSOC else bp + 1
            pct_args = PX.parse_pct_rhs(self) if (op == "%" and isinstance(left, A.StrLit)) else None
            right = self.parse_expr(nxt) if pct_args is None else None
            if op in ("and", "or"):
                left = A.BoolOp(t.line, t.col, op=op, values=[left, right])
            elif op in ("==", "!=", "<", "<=", ">", ">=", "in", "not in", "is", "is not"):
                cmp_left = _chain_tail(left)
                if cmp_left is None:
                    left = A.Compare(t.line, t.col, op=op, left=left, right=right)
                else:                                   # a < b < c  ==  a < b and b < c  (b evaluated once)
                    mid = cmp_left.right
                    if not _pure(mid):
                        self.errors.append(Diagnostic(
                            "chained comparison with a computed middle operand: assign it to a variable first "
                            "(PySub evaluates `a < b < c` as `a < b and b < c`)", mid.line, mid.col))
                    nxt = A.Compare(t.line, t.col, op=op, left=copy.deepcopy(mid), right=right)
                    left = A.BoolOp(t.line, t.col, op="and", values=[left, nxt])
                    left.chain = True
            elif pct_args is not None:
                left = PX.desugar_percent(self, left, pct_args, t)
            elif op == "%" and isinstance(left, A.StrLit):
                left = PX.desugar_percent(self, left, [right], t)
            else:
                left = A.BinOp(t.line, t.col, op=op, left=left, right=right)
        if min_bp == 0 and self.at_kw("if"):           # body if test else orelse (loosest; orelse may nest)
            t = self.next()
            test = self.parse_expr(1)
            self.expect("KEYWORD", "else")
            left = A.IfExp(t.line, t.col, test=test, body=left, orelse=self.parse_expr(0))
        return left

    def parse_unary(self) -> A.Node:
        t = self.cur
        if self.at_op("-", "+", "~"):
            self.next()
            # -x ** 2 is -(x ** 2): the operand of a prefix operator absorbs a following `**`
            return A.UnaryOp(t.line, t.col, op=t.value, operand=self.parse_expr(BP["**"]))
        if self.at_kw("not"):
            self.next()
            # `not` binds looser than comparisons, tighter than `and`: not a == b is not (a == b)
            return A.UnaryOp(t.line, t.col, op="not", operand=self.parse_expr(BP["and"] + 1))
        return self.parse_postfix()

    def parse_postfix(self) -> A.Node:
        node = self.parse_atom()
        while True:
            if self.at_op("["):
                t = self.next()
                node = PX.parse_subscript(self, node, t)
            elif self.at_op(".") and isinstance(node, A.Name) and node.id in self.imports.modules:
                node = PX.module_attr(self, node, self.cur)
            elif self.at_op("."):
                t = self.next()
                m = self.expect("NAME").value
                if self.at_op("("):
                    self.next()
                    args, kwargs = self._call_args()
                    args = PI.check_method_star(self, t, args)
                    if m == "format" and isinstance(node, A.StrLit):
                        node = PX.desugar_format(self, node, args, kwargs, t)
                    else:
                        node = A.MethodCall(t.line, t.col, recv=node, method=m, args=args, kwargs=kwargs)
                elif m == "__name__" and isinstance(node, A.Call) and node.func == "type" and len(node.args) == 1 \
                        and isinstance(node.args[0], A.Name) and node.args[0].id in getattr(self, "exc_binds", ()):
                    node = A.Name(t.line, t.col, id="__en_" + node.args[0].id)     # type(e).__name__ in an except clause
                else:
                    node = A.Attribute(t.line, t.col, value=node, attr=m)
            else:
                return node

    def parse_atom(self) -> A.Node:
        t = self.cur
        if t.kind == "INT":
            self.next(); return A.IntLit(t.line, t.col, value=int(t.value))
        if t.kind == "FLOAT":
            self.next(); return A.FloatLit(t.line, t.col, value=float(t.value))
        if t.kind in ("STRING", "FSTRING"):
            return PX.parse_string_run(self)             # adjacent literals (plain and f-strings) concatenate
        if t.kind == "KEYWORD" and t.value in ("True", "False"):
            self.next(); return A.BoolLit(t.line, t.col, value=(t.value == "True"))
        if t.kind == "KEYWORD" and t.value == "None":
            self.next(); return A.NoneLit(t.line, t.col)
        if t.kind == "NAME" and t.value in self.imports.names:
            self.next()
            return PX.imported_name(self, t)
        if t.kind == "NAME" and t.value == "lambda":
            return _lambda(self)
        if t.kind == "KEYWORD" and t.value == "range" and self.toks[self.i + 1].value == "(":
            t = Token("NAME", "range", t.line, t.col)      # range(...) as a value: comprehension / zip / reversed source
        if t.kind == "NAME":
            if t.value == "isinstance" and self.toks[self.i + 1].kind == "OP" and self.toks[self.i + 1].value == "(":
                return self._parse_isinstance()
            self.next()
            if self.at_op("("):
                self.next()
                args, kwargs = self._call_args()
                return PI.make_call(self, t, args, kwargs)   # map/filter/print(*xs) desugaring, star-arg checks
            return A.Name(t.line, t.col, id=t.value)
        if self.at_op("("):
            return self._paren(t)
        if self.at_op("["):
            self.next()
            elts = []
            while not self.at_op("]"):
                elts.append(self.parse_expr())
                if len(elts) == 1 and self.at_kw("for"):
                    return _comp_tail(self, t, elts[0], "]")
                if self.at_op(","):
                    self.next()
                else:
                    break
            self.expect("OP", "]")
            return A.ListLit(t.line, t.col, elts=elts)
        if self.at_op("{"):
            self.next()
            keys, vals = [], []
            while not self.at_op("}"):
                k = self.parse_expr()
                if not keys and self.at_kw("for"):
                    self.error("set comprehensions are outside the PySub subset (build the set with a loop and .add())")
                    raise _Panic()
                if not keys and not self.at_op(":"):
                    return self._set_lit_rest(t, k)
                self.expect("OP", ":")
                v = self.parse_expr()
                if not keys and self.at_kw("for"):
                    return _comp_tail(self, t, (k, v), "}")
                keys.append(k); vals.append(v)
                if self.at_op(","):
                    self.next()
                else:
                    break
            self.expect("OP", "}")
            return A.DictLit(t.line, t.col, keys=keys, values=vals)
        self.error(f"unexpected token {t.value or t.kind!r} in expression")
        raise _Panic()


# ---- helpers: call arguments, f-strings, the __main__ guard ---------------------------------------------
_ESC = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "0": "\0",
        "a": "\a", "b": "\b", "f": "\f", "v": "\v"}
_HEXLEN = {"x": 2, "u": 4, "U": 8}


def _relocate(n, line, col):
    """Give every node parsed out of an f-string field the f-string's own position."""
    import dataclasses
    if isinstance(n, A.Node):
        n.line, n.col = line, col
        for f in dataclasses.fields(n):
            v = getattr(n, f.name)
            if isinstance(v, (A.Node, list)):
                _relocate(v, line, col)
    elif isinstance(n, list):
        for x in n:
            _relocate(x, line, col)


def _call_args(self):
    args, kwargs = [], []
    while not self.at_op(")"):
        nxt = self.toks[self.i + 1] if self.i + 1 < len(self.toks) else None
        if self.at("NAME") and nxt is not None and nxt.kind == "OP" and nxt.value == "=":
            kt = self.next()
            self.next()
            kwargs.append(A.Keyword(kt.line, kt.col, name=kt.value, value=self.parse_expr()))
        elif self.at_op("*"):                          # f(*xs): only print(*xs) is accepted (see parse_iter)
            st = self.next()
            args.append(PI.StarArg(st.line, st.col, value=self.parse_expr()))
        else:
            if kwargs:
                self.error("positional argument follows keyword argument")
                raise _Panic()
            args.append(self.parse_expr())
            if self.at_kw("for"):                      # f(x for x in xs): a bare generator argument
                args[-1] = _comp_tail(self, self.cur, args[-1], None)
        if self.at_op(","):
            self.next()
        else:
            break
    _check_bare_genexp(self, args, kwargs)
    self.expect("OP", ")")
    return args, kwargs


# ---- comprehensions, generator expressions, lambdas; comprehension targets ------------------------------------
def _target1(self):
    if self.at_op("(", "["):
        close = ")" if self.next().value == "(" else "]"
        t = _targets(self)
        self.expect("OP", close)
        return t
    return self.expect("NAME").value


def _targets(self):
    """for-loop target: NAME, or a comma list of (possibly parenthesised) targets -> str | nested list."""
    items, trailing = [_target1(self)], False
    while self.at_op(","):
        self.next()
        if self.at_kw("in") or self.at_op(")", "]"):
            trailing = True
            break
        items.append(_target1(self))
    return items[0] if len(items) == 1 and not trailing else items


def _comp_tail(self, open_tok, elt, close):
    """After `[elt`, `{k: v`, `(elt` or a bare call argument: parse the `for ... in ... if ...` clauses."""
    gens = []
    while self.at_kw("for"):
        ft = self.next()
        target = _targets(self)
        self.expect("KEYWORD", "in")
        it = self.parse_expr(1)                        # an `if` here is a filter, not a conditional expression
        ifs = []
        while self.at_kw("if"):
            self.next()
            ifs.append(self.parse_expr(1))
        gens.append(A.CompFor(ft.line, ft.col, target=target, iter=it, ifs=ifs))
    if close is not None:
        self.expect("OP", close)
    ln, cl = open_tok.line, open_tok.col
    if close == "]":
        return A.ListComp(ln, cl, elt=elt, gens=gens)
    if close == "}":
        return A.DictComp(ln, cl, key=elt[0], value=elt[1], gens=gens)
    g = A.GenExp(ln, cl, elt=elt, gens=gens)
    if close is None:
        g.line, g.col = elt.line, elt.col
        g.bare = True
    return g


def _check_bare_genexp(self, args, kwargs):
    if len(args) + len(kwargs) > 1 and any(getattr(a, "bare", False) for a in args):
        self.error("Generator expression must be parenthesized")
        raise _Panic()


def _lambda(self):
    t = self.next()                                    # 'lambda'
    params = []
    while not self.at_op(":"):
        params.append(self.expect("NAME").value)
        if self.at_op(","):
            self.next()
        else:
            break
    self.expect("OP", ":")
    return A.Lambda(t.line, t.col, params=params, body=self.parse_expr())


def _is_main_guard(self, st) -> bool:
    if not isinstance(st, A.If) or st.orelse or not isinstance(st.test, A.Compare) or st.test.op != "==":
        return False
    sides = (st.test.left, st.test.right)
    return (any(isinstance(x, A.Name) and x.id == "__name__" for x in sides) and
            any(isinstance(x, A.StrLit) and x.value == "__main__" for x in sides))


def _fstring_fail(self, tok, msg):
    self.errors.append(Diagnostic(msg, tok.line, tok.col))
    raise _Panic()


def _sub_expr(self, text, tok):
    try:
        toks = tokenize("(" + text.strip() + ")\n", self.filename)
    except LexError as ex:
        _fstring_fail(self, tok, f"in f-string field {{{text}}}: {ex.msg}")
    sub = Parser(toks, self.filename)
    sub.imports = self.imports
    try:
        e = sub.parse_expr()
    except _Panic:
        e = None
    if sub.errors or e is None or not sub.at("NEWLINE") or not text.strip():
        _fstring_fail(self, tok, f"invalid expression in f-string field {{{text}}}")
    _relocate(e, tok.line, tok.col)
    return e


def _fstring(self, tok):
    """f"a {x} b {y:.2f}" -> "a " + str(x) + " b " + format(y, ".2f")."""
    raw, n, parts, lit, i = tok.value, len(tok.value), [], "", 0
    while i < n:
        c = raw[i]
        if c == "\\" and i + 1 < n:
            e1 = raw[i + 1]
            if e1 in "xuU" and e1 in _HEXLEN and all(h in "0123456789abcdefABCDEF" for h in raw[i + 2:i + 2 + _HEXLEN[e1]]) \
                    and len(raw[i + 2:i + 2 + _HEXLEN[e1]]) == _HEXLEN[e1]:
                lit += chr(int(raw[i + 2:i + 2 + _HEXLEN[e1]], 16))
                i += 2 + _HEXLEN[e1]
                continue
            if e1 in "1234567" or (e1 == "0" and raw[i + 2:i + 3] in tuple("01234567")):
                j = i + 1
                while j < n and j < i + 4 and raw[j] in "01234567":
                    j += 1
                lit += chr(int(raw[i + 1:j], 8))
                i = j
                continue
            lit += _ESC.get(e1, "\\" + e1)
            i += 2
            continue
        if raw.startswith("{{", i) or raw.startswith("}}", i):
            lit += c
            i += 2
            continue
        if c == "}":
            _fstring_fail(self, tok, "f-string: single '}' is not allowed")
        if c != "{":
            lit += c
            i += 1
            continue
        j, depth, quote, cut = i + 1, 0, None, None
        while j < n:
            ch = raw[j]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in "'\"":
                quote = ch
            elif ch in "([{":
                depth += 1
            elif ch in ")]":
                depth -= 1
            elif ch == "}":
                if depth == 0:
                    break
                depth -= 1
            elif depth == 0 and cut is None and ch in ":!" and not raw.startswith("!=", j):
                cut = j
            j += 1
        if j >= n:
            _fstring_fail(self, tok, "f-string: expecting '}'")
        field = raw[i + 1:j]
        k = (cut - i - 1) if cut is not None else len(field)
        expr_text, rest = field[:k], field[k:]
        conv = spec = None
        if rest.startswith("!"):
            conv, rest = rest[1:2], rest[2:]
        if rest.startswith(":"):
            spec = rest[1:]
        if expr_text.rstrip().endswith("=") and not expr_text.rstrip().endswith(("==", "!=", "<=", ">=")):
            lit += expr_text                       # f"{x = }": the text, `=` and spaces included, then the value
            expr_text = expr_text.rstrip()[:-1]
            if conv is None and not spec:
                conv = "r"                         # CPython: repr() unless a format spec or conversion is given
        if conv not in (None, "s", "r"):
            _fstring_fail(self, tok, f"f-string conversion '!{conv}' is outside the PySub subset (use !r, !s or none)")
        if spec and "{" in spec:
            _fstring_fail(self, tok, "nested format specs in f-strings are outside the PySub subset")
        if lit:
            parts.append(A.StrLit(tok.line, tok.col, value=lit))
            lit = ""
        e = _sub_expr(self, expr_text, tok)
        if conv == "r":
            e = A.Call(tok.line, tok.col, func="repr", args=[e])
        if spec:
            parts.append(A.Call(tok.line, tok.col, func="format", args=[e, A.StrLit(tok.line, tok.col, value=spec)]))
        else:
            parts.append(A.Call(tok.line, tok.col, func="str", args=[e]))
        i = j + 1
    if lit:
        parts.append(A.StrLit(tok.line, tok.col, value=lit))
    if not parts:
        return A.StrLit(tok.line, tok.col, value="")
    node = parts[0]
    for p in parts[1:]:
        node = A.BinOp(tok.line, tok.col, op="+", left=node, right=p)
    return node


# ---- tuples: literals, tuple[...] types, unpacking (desugared into plain assignments) ---------------------
_LIST_END = ("=", ")", "]", "}", ":") + tuple(AUG_OPS)


def _paren(self, t):
    """( ) -> empty tuple, (a,) / (a, b) -> TupleLit, (a) -> a (marked parenthesised)."""
    self.next()
    if self.at_op(")"):
        self.next()
        return A.TupleLit(t.line, t.col, elts=[])
    e = self.parse_expr()
    if self.at_kw("for"):                      # (x for x in xs): a generator expression
        return _comp_tail(self, t, e, ")")
    if self.at_op(","):
        elts = [e]
        while self.at_op(","):
            self.next()
            if self.at_op(")"):
                break
            elts.append(self.parse_expr())
        e = A.TupleLit(t.line, t.col, elts=elts)
    self.expect("OP", ")")
    e.paren = True                             # (a < b) < c is NOT a chain
    return e


def parse_exprlist(self) -> A.Node:
    """expr or a bare tuple `a, b` / `a,` (return values, assignment sides, subscripts)."""
    first = self.parse_expr()
    if not self.at_op(","):
        return first
    elts = [first]
    while self.at_op(","):
        self.next()
        if self.at("NEWLINE") or (self.cur.kind == "OP" and self.cur.value in _LIST_END):
            break
        elts.append(self.parse_expr())
    return A.TupleLit(first.line, first.col, elts=elts)


def _tuple_type(self, te):
    """tuple[T1, T2, ...]; `tuple[T, ...]` is parsed (as a '...' element) so the checker can reject it clearly."""
    self.next()                                # '['
    while not self.at_op("]"):
        if self.at_op("."):
            d = self.cur
            for _ in range(3):
                self.expect("OP", ".")
            te.params.append(A.TypeExpr(line=d.line, col=d.col, name="..."))
        else:
            te.params.append(self.parse_type())
        if self.at_op(","):
            self.next()
        else:
            break
    self.expect("OP", "]")
    return te


def _target_atom(self):
    t = self.cur
    if self.at_op("("):
        self.next()
        elts, comma = [], False
        while not self.at_op(")"):
            elts.append(self._target_atom())
            if self.at_op(","):
                self.next()
                comma = True
            else:
                break
        self.expect("OP", ")")
        return elts[0] if len(elts) == 1 and not comma else A.TupleLit(t.line, t.col, elts=elts)
    n = self.expect("NAME")
    return A.Name(n.line, n.col, id=n.value)


def _for_target(self):
    """The loop variable name (str), or a TupleLit of Names for `for a, (b, c) in ...`."""
    t = self.cur
    nxt = self.toks[self.i + 1] if self.i + 1 < len(self.toks) else None
    if self.at("NAME") and nxt is not None and nxt.kind == "KEYWORD" and nxt.value == "in":
        return self.next().value
    elts = [self._target_atom()]
    comma = False
    while self.at_op(","):
        self.next()
        comma = True
        if self.at_kw("in"):
            break
        elts.append(self._target_atom())
    if not comma and isinstance(elts[0], A.Name):
        return elts[0].id                       # for (x) in xs
    return elts[0] if not comma else A.TupleLit(t.line, t.col, elts=elts)


def _fresh_unpack(self) -> str:
    self._unpack_n = getattr(self, "_unpack_n", 0) + 1
    return f"__pythia_u{self._unpack_n}"        # not a name PySub programs use; emitted as a hidden local


def _unpack_stmts(self, target, value, line, col):
    """a, (b, c) = v  ->  u1 = __pythia_unpack(v, 2); a = u1[0]; u2 = __pythia_unpack(u1[1], 2); b = u2[0]; c = u2[1]
    The right-hand side is evaluated (and its length checked) before any target is assigned, as in CPython."""
    tmp = self._fresh_unpack()
    value = PI.eager(value)                      # a, b = map(int, ...): the generator is consumed at once
    call = A.Call(line, col, func="__pythia_unpack", args=[value, A.IntLit(line, col, value=len(target.elts))])
    out = [A.Assign(line, col, target=A.Name(line, col, id=tmp), value=call)]
    for i, tg in enumerate(target.elts):
        item = A.Subscript(tg.line, tg.col, value=A.Name(tg.line, tg.col, id=tmp),
                           index=A.IntLit(tg.line, tg.col, value=i))
        if isinstance(tg, A.TupleLit):
            out += self._unpack_stmts(tg, item, tg.line, tg.col)
        elif isinstance(tg, (A.Name, A.Subscript, A.Attribute)):
            out.append(A.Assign(tg.line, tg.col, target=tg, value=item))
        else:
            self.errors.append(Diagnostic("invalid unpacking target (names, subscripts, fields or nested "
                                          "(a, b) only; starred targets are outside the PySub subset)",
                                          tg.line, tg.col))
            raise _Panic()
    return out


def _for_unpack(self, t, target):
    if self.at_kw("range"):
        self.error("range() yields ints, which cannot be unpacked into several names")
        raise _Panic()
    it = self.parse_expr()
    self.expect("OP", ":")
    body = self.parse_block()
    tmp = self._fresh_unpack()
    body = self._unpack_stmts(target, A.Name(t.line, t.col, id=tmp), t.line, t.col) + body
    return PI.fuse_for(A.ForEach(line=t.line, col=t.col, var=tmp, iter=it, body=body))


Parser._paren = _paren
Parser.parse_exprlist = parse_exprlist
Parser._tuple_type = _tuple_type
Parser._target_atom = _target_atom
Parser._for_target = _for_target
Parser._fresh_unpack = _fresh_unpack
Parser._unpack_stmts = _unpack_stmts
Parser._for_unpack = _for_unpack
Parser._call_args = _call_args
Parser._is_main_guard = _is_main_guard
Parser._fstring = _fstring
from .parse_types import install as _install_types  # noqa: E402  (PySub 1.3: annotations, sets, global, isinstance)
_install_types(Parser, _Panic, Diagnostic)


def _cls():
    from . import classes_ext                 # user classes: bases, decorators, class attributes
    return classes_ext


def parse(src: str, filename: str = "<input>"):
    p = Parser(tokenize(src, filename), filename)
    mod = p.parse_module()
    return mod, p.errors
