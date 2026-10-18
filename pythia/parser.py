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
    "+": 6, "-": 6,
    "*": 8, "/": 8, "//": 8, "%": 8,
    "**": 12,                      # right-associative
}
RIGHT_ASSOC = {"**"}
AUG_OPS = {"+=": "+", "-=": "-", "*=": "*", "/=": "/",
           "//=": "//", "%=": "%", "**=": "**"}
# set algebra (Python: comparisons < | < ^ < & < shifts < + -)
for _k, _v in {"|": 4.25, "^": 4.5, "&": 4.75}.items():
    BP.setdefault(_k, _v)
for _k in ("|", "&", "^"):
    AUG_OPS.setdefault(_k + "=", _k)


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
                    "class", "try", "raise"):
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
                elif self._at_import():
                    mod.imports.append(self._parse_import())
                else:
                    st = self.parse_statement()
                    if self._is_main_guard(st):            # if __name__ == "__main__": runs as the program body
                        mod.main.extend(st.body)
                    else:
                        mod.main.append(st)
            except _Panic:
                self.synchronize()
            if self.i == guard:      # safety net: never spin with zero progress
                self.next()
        return mod

    def parse_classdef(self) -> A.ClassDef:
        kw = self.expect("KEYWORD", "class")
        name = self.expect("NAME").value
        self.expect("OP", ":")
        self.expect("NEWLINE")
        self.expect("INDENT")
        cd = A.ClassDef(line=kw.line, col=kw.col, name=name)
        while not self.at("DEDENT") and not self.at("EOF"):
            guard = self.i
            if self.at("NEWLINE"):
                self.next()
                continue
            try:
                if self.at_kw("def"):
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
            if pt.value == "self" and not params and not self.at_op(":"):
                params.append(A.Param(line=pt.line, col=pt.col, name="self", ann=None))
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
        return self._parse_type_ext()        # parse_ext.py: dotted names, T[A, B], A | B, "Forward"

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
                stmts.append(self.parse_statement())
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
                val = self.parse_expr()
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
        if self.at("NAME", "global") and self.toks[self.i + 1].kind == "NAME":
            return self._parse_global()
        return self.parse_simple()

    def parse_try(self) -> A.TryExcept:
        t = self.expect("KEYWORD", "try")
        self.expect("OP", ":")
        body = self.parse_block()
        handlers: List[A.ExceptHandler] = []
        while self.at_kw("except"):
            ht = self.next()
            exc_name = None
            bind = None
            if not self.at_op(":"):
                exc_name = self.expect("NAME").value
                if self.cur.kind == "NAME" and self.cur.value == "as":
                    self.next()
                    bind = self.expect("NAME").value
            self.expect("OP", ":")
            hbody = self.parse_block()
            handlers.append(A.ExceptHandler(line=ht.line, col=ht.col,
                                            exc_name=exc_name, bind=bind, body=hbody))
        if not handlers:
            self.error("'try' block requires at least one 'except' clause")
            raise _Panic()
        return A.TryExcept(line=t.line, col=t.col, body=body, handlers=handlers)

    def parse_raise(self) -> A.Raise:
        t = self.expect("KEYWORD", "raise")
        name = self.expect("NAME").value
        msg = None
        if self.at_op("("):
            self.next()
            if not self.at_op(")"):
                msg = self.parse_expr()
            self.expect("OP", ")")
        self.expect("NEWLINE")
        return A.Raise(line=t.line, col=t.col, exc_name=name, message=msg)

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
        var = self.expect("NAME").value
        self.expect("KEYWORD", "in")
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
        return A.ForEach(line=t.line, col=t.col, var=var, iter=it,
                         body=self.parse_block())

    def parse_simple(self) -> A.Node:
        t = self.cur
        # annotated declaration:  name : T = expr
        if self.at("NAME") and self.toks[self.i + 1].kind == "OP" \
                and self.toks[self.i + 1].value == ":":
            nm = self.next()
            self.next()                       # ':'
            ann = self.parse_type()
            self.expect("OP", "=")
            val = self.parse_expr()
            self.expect("NEWLINE")
            return A.Assign(line=nm.line, col=nm.col,
                            target=A.Name(nm.line, nm.col, id=nm.value),
                            ann=ann, value=val)

        first = self.parse_expr()

        if self.at_op("="):
            self.next()
            val = self.parse_expr()
            self.expect("NEWLINE")
            if not isinstance(first, (A.Name, A.Subscript, A.Attribute)):
                self.error("invalid assignment target")
                raise _Panic()
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
            nxt = bp if op in RIGHT_ASSOC else bp + 0.01      # BPs may be fractional (| ^ &)
            right = self.parse_expr(nxt)
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
        if self.at_op("-", "+"):
            self.next()
            return A.UnaryOp(t.line, t.col, op=t.value, operand=self.parse_unary())
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
                idx = self.parse_expr()
                self.expect("OP", "]")
                node = A.Subscript(t.line, t.col, value=node, index=idx)
            elif self.at_op("."):
                t = self.next()
                m = self.expect("NAME").value
                if self.at_op("("):
                    self.next()
                    args, kwargs = self._call_args()
                    node = A.MethodCall(t.line, t.col, recv=node, method=m, args=args, kwargs=kwargs)
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
        if t.kind == "STRING":
            self.next(); return A.StrLit(t.line, t.col, value=t.value)
        if t.kind == "FSTRING":
            self.next(); return self._fstring(t)
        if t.kind == "KEYWORD" and t.value in ("True", "False"):
            self.next(); return A.BoolLit(t.line, t.col, value=(t.value == "True"))
        if t.kind == "KEYWORD" and t.value == "None":
            self.next(); return A.NoneLit(t.line, t.col)
        if t.kind == "NAME":
            if t.value == "isinstance" and self.toks[self.i + 1].kind == "OP" and self.toks[self.i + 1].value == "(":
                return self._parse_isinstance()
            self.next()
            if self.at_op("("):
                self.next()
                args, kwargs = self._call_args()
                return A.Call(t.line, t.col, func=t.value, args=args, kwargs=kwargs)
            return A.Name(t.line, t.col, id=t.value)
        if self.at_op("("):
            self.next()
            e = self.parse_expr()
            self.expect("OP", ")")
            e.paren = True                             # (a < b) < c is NOT a chain
            return e
        if self.at_op("["):
            self.next()
            elts = []
            while not self.at_op("]"):
                elts.append(self.parse_expr())
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
                if not keys and not self.at_op(":"):
                    return self._set_lit_rest(t, k)
                self.expect("OP", ":")
                v = self.parse_expr()
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
_ESC = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"', "0": "\0"}


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
        else:
            if kwargs:
                self.error("positional argument follows keyword argument")
                raise _Panic()
            args.append(self.parse_expr())
        if self.at_op(","):
            self.next()
        else:
            break
    self.expect("OP", ")")
    return args, kwargs


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
            lit += _ESC.get(raw[i + 1], "\\" + raw[i + 1])
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
            _fstring_fail(self, tok, "f-string self-documenting fields {x=} are outside the PySub subset")
        if conv not in (None, "s"):
            _fstring_fail(self, tok, f"f-string conversion '!{conv}' is outside the PySub subset; use str()")
        if spec and "{" in spec:
            _fstring_fail(self, tok, "nested format specs in f-strings are outside the PySub subset")
        if lit:
            parts.append(A.StrLit(tok.line, tok.col, value=lit))
            lit = ""
        e = _sub_expr(self, expr_text, tok)
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


Parser._call_args = _call_args
Parser._is_main_guard = _is_main_guard
Parser._fstring = _fstring
from .parse_ext import install as _install_ext  # noqa: E402  (PySub 1.3 syntax: imports, types, sets, global)
_install_ext(Parser, _Panic, Diagnostic)


def parse(src: str, filename: str = "<input>"):
    p = Parser(tokenize(src, filename), filename)
    mod = p.parse_module()
    return mod, p.errors
