"""
PYTHIA :: PySub 1.3 syntax extensions (installed onto parser.Parser)

  * imports:      `import M [as a]`, `from M import a [as b], ...`, `from __future__ import annotations`
                  (which modules are allowed is decided by the type checker: types_ext.ALLOWED_IMPORTS)
  * annotations:  dotted names (typing.List), any number of subscript arguments, `A | B` unions and
                  quoted forward references ("Node"); normalised to PySub types in types_ext
  * `global a, b`
  * set literals  {a, b}
  * isinstance(x, (T1, T2))  -- the tuple form, as a syntax special case
"""
from typing import List
from . import ast_nodes as A
from .lexer import LexError, tokenize


def install(Parser, Panic, Diagnostic) -> None:

    def _at_import(self) -> bool:
        return (self.at("NAME") and self.cur.value in ("import", "from")
                and self.toks[self.i + 1].kind == "NAME")

    def _dotted(self) -> str:
        name = self.expect("NAME").value
        while self.at_op("."):
            self.next()
            name += "." + self.expect("NAME").value
        return name

    def _parse_import(self) -> A.Import:
        t = self.next()
        if t.value == "import":
            imp = A.Import(line=t.line, col=t.col, module=_dotted(self))
            if self.at("NAME", "as"):
                self.next()
                imp.alias = self.expect("NAME").value
            if self.at_op(","):
                self.error("import one module per line in PySub")
                raise Panic()
            self.expect("NEWLINE")
            return imp
        imp = A.Import(line=t.line, col=t.col, module=_dotted(self))
        if not self.at("NAME", "import"):
            self.error("expected 'import'")
            raise Panic()
        self.next()
        paren = self.at_op("(")
        if paren:
            self.next()
        while True:
            if self.at_op("*"):
                self.error("`from ... import *` is outside the PySub subset; name what you import")
                raise Panic()
            imp.names.append(self.expect("NAME").value)
            alias = None
            if self.at("NAME", "as"):
                self.next()
                alias = self.expect("NAME").value
            imp.asnames.append(alias)
            if not self.at_op(","):
                break
            self.next()
            if paren and self.at_op(")"):
                break
        if paren:
            self.expect("OP", ")")
        self.expect("NEWLINE")
        return imp

    def _parse_global(self) -> A.Global:
        t = self.next()
        g = A.Global(line=t.line, col=t.col, names=[self.expect("NAME").value])
        while self.at_op(","):
            self.next()
            g.names.append(self.expect("NAME").value)
        self.expect("NEWLINE")
        return g

    def _type_atom(self) -> A.TypeExpr:
        t = self.cur
        if t.kind == "STRING":                       # "Node": a forward reference
            self.next()
            try:
                sub = Parser(tokenize(t.value.strip() + "\n", self.filename), self.filename)
                te = sub.parse_type()
                ok = not sub.errors and sub.at("NEWLINE")
            except (LexError, Panic):
                ok = False
            if not ok:
                self.errors.append(Diagnostic(f"invalid type in string annotation {t.value!r}", t.line, t.col))
                raise Panic()
            _relocate_type(te, t.line, t.col)
            te.quoted = True
            return te
        if t.kind == "KEYWORD" and t.value == "None":
            self.next()
            return A.TypeExpr(line=t.line, col=t.col, name="None")
        if t.kind != "NAME":
            self.error(f"expected a type but found {t.value or t.kind!r}")
            raise Panic()
        te = A.TypeExpr(line=t.line, col=t.col, name=_dotted(self))
        te.args = None
        if self.at_op("["):
            self.next()
            args: List[A.TypeExpr] = [_type_arg(self)]
            while self.at_op(","):
                self.next()
                args.append(_type_arg(self))
            self.expect("OP", "]")
            te.args = args
            te.params = list(args)                   # tuple[T1, T2, ...] (tuples.py)
            te.param = args[0]
            te.param2 = args[1] if len(args) > 1 else None
        return te

    def _type_arg(self) -> A.TypeExpr:
        if self.at_op("."):                          # tuple[T, ...]: parsed so the checker can reject it clearly
            d = self.cur
            for _ in range(3):
                self.expect("OP", ".")
            return A.TypeExpr(line=d.line, col=d.col, name="...")
        return self.parse_type()

    def _parse_type_ext(self) -> A.TypeExpr:
        te = _type_atom(self)
        if not self.at_op("|"):
            return te
        u = A.TypeExpr(line=te.line, col=te.col, name="|")
        u.args = [te]
        while self.at_op("|"):
            self.next()
            u.args.append(_type_atom(self))
        return u

    def _parse_isinstance(self) -> A.Call:
        t = self.next()
        self.expect("OP", "(")
        x = self.parse_expr()
        self.expect("OP", ",")
        if self.at_op("("):                          # isinstance(x, (int, float)): a tuple of types
            p = self.next()
            elts = [self.parse_expr()]
            while self.at_op(","):
                self.next()
                if self.at_op(")"):
                    break
                elts.append(self.parse_expr())
            self.expect("OP", ")")
            cls = A.ListLit(p.line, p.col, elts=elts)
            cls.tuple_syntax = True
        else:
            cls = self.parse_expr()
        if self.at_op(","):
            self.next()
        self.expect("OP", ")")
        return A.Call(t.line, t.col, func="isinstance", args=[x, cls])

    def _set_lit_rest(self, t, first: A.Node) -> A.SetLit:
        elts = [first]
        while self.at_op(","):
            self.next()
            if self.at_op("}"):
                break
            elts.append(self.parse_expr())
        self.expect("OP", "}")
        return A.SetLit(t.line, t.col, elts=elts)

    Parser._at_import = _at_import
    Parser._parse_import = _parse_import
    Parser._parse_global = _parse_global
    Parser._parse_type_ext = _parse_type_ext
    Parser._parse_isinstance = _parse_isinstance
    Parser._set_lit_rest = _set_lit_rest


def _relocate_type(te, line: int, col: int) -> None:
    if te is None:
        return
    te.line, te.col = line, col
    for a in (getattr(te, "args", None) or []):
        _relocate_type(a, line, col)
