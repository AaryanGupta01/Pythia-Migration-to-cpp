"""
PYTHIA :: Phase 1 -- Lexical Analysis
Owner: Member 1 (Vishal Vivek)

Hand-written scanner for PySub. Implements the Python "off-side rule":
significant indentation is converted into explicit INDENT / DEDENT tokens
so that the downstream parser can use an ordinary block grammar.
"""
from dataclasses import dataclass
from typing import List, Optional

KEYWORDS = {
    "def", "return", "if", "elif", "else", "while", "for", "in", "range",
    "and", "or", "not", "True", "False", "None", "pass", "break", "continue",
    "try", "except", "raise", "class",
}

# Multi-character operators must be tried longest-first.
OPERATORS = [
    "**=", "//=", "<<=", ">>=", "==", "!=", "<=", ">=", "**", "//", "->", "<<", ">>",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=",
    "+", "-", "*", "/", "%", "<", ">", "=", "(", ")", "[", "]", "{", "}",
    ",", ":", ".", "&", "|", "^", "~",
]
# set algebra / `T | None` annotations (two-character forms must precede one-character ones)
OPERATORS[:0] = [op for op in ("|=", "&=", "^=") if op not in OPERATORS]
OPERATORS += [op for op in ("|", "&", "^") if op not in OPERATORS]
OPERATORS += ["@"]                     # decorators (classes_ext): @staticmethod, @classmethod, @property, @dataclass


@dataclass
class Token:
    kind: str          # INT FLOAT STRING NAME KEYWORD OP NEWLINE INDENT DEDENT EOF
    value: str
    line: int
    col: int

    def __repr__(self) -> str:
        return f"{self.kind}({self.value!r})@{self.line}:{self.col}"


class LexError(Exception):
    def __init__(self, msg: str, line: int, col: int):
        super().__init__(msg)
        self.msg, self.line, self.col = msg, line, col


class Lexer:
    def __init__(self, src: str, filename: str = "<input>"):
        self.src = src.replace("\t", "    ")
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.col = 1
        self.indents: List[int] = [0]
        self.tokens: List[Token] = []
        self.paren_depth = 0

    # ---- low level helpers -------------------------------------------------
    def _peek(self, k: int = 0) -> str:
        i = self.pos + k
        return self.src[i] if i < len(self.src) else ""

    def _advance(self, n: int = 1) -> str:
        out = self.src[self.pos:self.pos + n]
        for ch in out:
            if ch == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
        self.pos += n
        return out

    def _emit(self, kind: str, value: str, line: int, col: int) -> None:
        self.tokens.append(Token(kind, value, line, col))

    # ---- main loop ---------------------------------------------------------
    def tokenize(self) -> List[Token]:
        at_line_start = True
        while self.pos < len(self.src):
            if at_line_start and self.paren_depth == 0:
                if not self._handle_indentation():
                    continue          # blank / comment-only line: skip entirely
                at_line_start = False
                continue

            ch = self._peek()

            if ch == "#":
                while self._peek() and self._peek() != "\n":
                    self._advance()
                continue

            if ch == "\n":
                ln, cl = self.line, self.col
                self._advance()
                if self.paren_depth == 0:
                    if self.tokens and self.tokens[-1].kind != "NEWLINE":
                        self._emit("NEWLINE", "\\n", ln, cl)
                    at_line_start = True
                continue

            if ch in " \r":
                self._advance()
                continue

            if ch == "\\" and self._peek(1) == "\n":   # explicit line join
                self._advance(2)
                continue

            if ch.isdigit() or (ch == "." and self._peek(1).isdigit()):
                self._lex_number()
                continue

            if ch.isalpha() or ch == "_":
                self._lex_name()
                continue

            if ch in "\"'":
                self._lex_string()
                continue

            if not self._lex_operator():
                raise LexError(f"unexpected character {ch!r}", self.line, self.col)

        # end of file: close any open blocks
        if self.tokens and self.tokens[-1].kind != "NEWLINE":
            self._emit("NEWLINE", "\\n", self.line, self.col)
        while len(self.indents) > 1:
            self.indents.pop()
            self._emit("DEDENT", "", self.line, self.col)
        self._emit("EOF", "", self.line, self.col)
        return self.tokens

    # ---- the off-side rule -------------------------------------------------
    def _handle_indentation(self) -> bool:
        """Measure leading whitespace; emit INDENT/DEDENT. Returns False for
        blank or comment-only lines (which carry no indentation meaning)."""
        start_line, start_col = self.line, self.col
        width = 0
        while self._peek() == " ":
            self._advance()
            width += 1

        if self._peek() in ("", "\n", "#"):
            # blank or comment-only line -> consume it, no tokens
            while self._peek() and self._peek() != "\n":
                self._advance()
            if self._peek() == "\n":
                self._advance()
            return False

        cur = self.indents[-1]
        if width > cur:
            self.indents.append(width)
            self._emit("INDENT", " " * width, start_line, start_col)
        elif width < cur:
            while len(self.indents) > 1 and width < self.indents[-1]:
                self.indents.pop()
                self._emit("DEDENT", "", start_line, start_col)
            if width != self.indents[-1]:
                raise LexError(
                    "unindent does not match any outer indentation level",
                    start_line, start_col)
        return True

    # ---- token scanners ----------------------------------------------------
    def _lex_number(self) -> None:
        ln, cl = self.line, self.col
        buf = ""
        is_float = False
        if self._peek() == "0" and self._peek(1) != "" and self._peek(1) in "xXbBoO":
            base = {"x": 16, "b": 2, "o": 8}[self._peek(1).lower()]      # 0xFF / 0b101 / 0o17, underscores allowed
            self._advance(2)
            digs = ""
            while self._peek() != "" and (self._peek().isalnum() or self._peek() == "_"):
                digs += self._advance()
            try:
                if digs.startswith("_") or digs.endswith("_") or "__" in digs or not digs:
                    raise ValueError
                self._emit("INT", str(int(digs.replace("_", ""), base)), ln, cl)
            except ValueError:
                raise LexError("invalid number literal", ln, cl)
            return
        while self._peek().isdigit() or self._peek() == "_":
            c = self._advance()
            if c != "_":
                buf += c
        if self._peek() == "." and self._peek(1) != ".":
            is_float = True
            buf += self._advance()
            while self._peek().isdigit() or self._peek() == "_":
                c = self._advance()
                if c != "_":
                    buf += c
        if self._peek() in "eE" and (self._peek(1).isdigit() or
                                     (self._peek(1) in "+-" and self._peek(2).isdigit())):
            is_float = True
            buf += self._advance()
            if self._peek() in "+-":
                buf += self._advance()
            while self._peek().isdigit():
                buf += self._advance()
        self._emit("FLOAT" if is_float else "INT", buf, ln, cl)

    def _lex_name(self) -> None:
        ln, cl = self.line, self.col
        if self._peek() in "fF" and self._peek(1) in "\"'":
            self._advance()
            self._lex_fstring(ln, cl)
            return
        buf = ""
        while self._peek().isalnum() or self._peek() == "_":
            buf += self._advance()
        self._emit("KEYWORD" if buf in KEYWORDS else "NAME", buf, ln, cl)

    def _lex_fstring(self, ln: int, cl: int) -> None:
        """f"..." is kept raw (escapes and {expr[:spec]} fields intact) as one FSTRING token; the parser
        splits it into literal and expression parts. Inside a field brackets nest and quotes of the other
        kind are allowed, as in Python 3.11."""
        quote = self._advance()
        triple = self.src.startswith(quote * 2, self.pos)
        if triple:
            self._advance(2)
        buf, depth = "", 0
        while True:
            c = self._peek()
            if c == "":
                raise LexError("unterminated f-string", ln, cl)
            if c == "\n" and not triple and depth == 0:
                raise LexError("unterminated f-string (newline in string)", ln, cl)
            if depth == 0 and c == quote and (not triple or self.src.startswith(quote * 3, self.pos)):
                self._advance(3 if triple else 1)
                break
            if c == "\\" and depth == 0:
                buf += self._advance() + self._advance()
                continue
            if c == "{":
                if depth == 0 and self._peek(1) == "{":
                    buf += self._advance(2)
                    continue
                depth += 1
            elif c == "}" and depth > 0:
                depth -= 1
            elif c in "\"'" and depth > 0:              # a nested string inside a field
                q = self._advance()
                buf += q
                while self._peek() and self._peek() != q:
                    buf += self._advance()
                if not self._peek():
                    raise LexError("unterminated string inside an f-string field", ln, cl)
            buf += self._advance()
        self._emit("FSTRING", buf, ln, cl)

    _SIMPLE_ESC = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"',
                   "a": "\a", "b": "\b", "f": "\f", "v": "\v", "\n": ""}

    def _escape(self, ln: int, cl: int) -> str:
        # The text for a backslash escape (the backslash is already consumed): simple, hex, octal and unicode
        # escapes; an unknown escape keeps its backslash, as in Python.
        esc = self._advance()
        if esc in self._SIMPLE_ESC:
            return self._SIMPLE_ESC[esc]
        if esc in "xuU":
            n = {"x": 2, "u": 4, "U": 8}[esc]
            digs = self.src[self.pos:self.pos + n]
            if len(digs) != n or any(d not in "0123456789abcdefABCDEF" for d in digs):
                raise LexError(f"invalid \\{esc} escape", ln, cl)
            self._advance(n)
            try:
                return chr(int(digs, 16))
            except (ValueError, OverflowError):
                raise LexError(f"invalid \\{esc} escape", ln, cl)
        if esc in "01234567":
            digs = esc
            while len(digs) < 3 and self._peek() != "" and self._peek() in "01234567":
                digs += self._advance()
            return chr(int(digs, 8))
        return "\\" + esc

    def _lex_string(self) -> None:
        ln, cl = self.line, self.col
        quote = self._advance()
        triple = self.src.startswith(quote * 2, self.pos)
        if triple:                                         # """docstrings""" and multi-line strings
            self._advance(2)
        buf = ""
        while True:
            c = self._peek()
            if c == "":
                raise LexError("unterminated string literal", ln, cl)
            if c == "\n" and not triple:
                raise LexError("unterminated string literal (newline in string)", ln, cl)
            if c == quote and triple:
                if self.src.startswith(quote * 3, self.pos):
                    self._advance(3)
                    break
                buf += self._advance()
                continue
            if c == "\\":
                self._advance()
                buf += self._escape(ln, cl)
                continue
            if c == quote:
                self._advance()
                break
            buf += self._advance()
        self._emit("STRING", buf, ln, cl)

    def _lex_operator(self) -> bool:
        ln, cl = self.line, self.col
        for op in OPERATORS:
            if self.src.startswith(op, self.pos):
                self._advance(len(op))
                if op in "([{":
                    self.paren_depth += 1
                elif op in ")]}":
                    self.paren_depth = max(0, self.paren_depth - 1)
                self._emit("OP", op, ln, cl)
                return True
        return False


def tokenize(src: str, filename: str = "<input>") -> List[Token]:
    return Lexer(src, filename).tokenize()
