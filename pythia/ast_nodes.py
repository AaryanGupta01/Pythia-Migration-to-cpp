"""
PYTHIA :: Abstract Syntax Tree
Owner: Member 1 (Vishal Vivek)

Every node carries (line, col) so that every downstream diagnostic --
type errors, lowering warnings, fidelity notes -- can point at real source.
The `ty` field is filled in later by the type checker (Member 2), turning
the AST into a Typed AST (TAST) without a separate tree.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Any


@dataclass
class Node:
    line: int = 0
    col: int = 0
    ty: Any = None            # populated by typecheck.py


# ------------------------------------------------------------------ types
@dataclass
class TypeExpr(Node):
    name: str = ""                    # 'int' | 'float' | 'bool' | 'str' | 'list' | 'dict' | 'None'
    param: Optional["TypeExpr"] = None    # list[T] ; dict[K, V] key
    param2: Optional["TypeExpr"] = None   # dict[K, V] value
    params: List["TypeExpr"] = field(default_factory=list)   # tuple[T1, T2, ...] elements


# ------------------------------------------------------------ expressions
@dataclass
class IntLit(Node):
    value: int = 0


@dataclass
class FloatLit(Node):
    value: float = 0.0


@dataclass
class StrLit(Node):
    value: str = ""


@dataclass
class BoolLit(Node):
    value: bool = False


@dataclass
class NoneLit(Node):
    pass


@dataclass
class Coerce(Node):
    """Inserted by lower.py: an explicit widening the source left implicit."""
    value: Optional[Node] = None
    to: Any = None


@dataclass
class Name(Node):
    id: str = ""


@dataclass
class ListLit(Node):
    elts: List[Node] = field(default_factory=list)


@dataclass
class TupleLit(Node):
    """(a, b), a, b, (a,), () -- also the target of an unpacking assignment before the parser desugars it."""
    elts: List[Node] = field(default_factory=list)


@dataclass
class BinOp(Node):
    op: str = ""
    left: Optional[Node] = None
    right: Optional[Node] = None
    no_guard: bool = False    # set by optimize.py when overflow is proven impossible


@dataclass
class UnaryOp(Node):
    op: str = ""
    operand: Optional[Node] = None


@dataclass
class BoolOp(Node):
    op: str = ""                      # 'and' | 'or'
    values: List[Node] = field(default_factory=list)


@dataclass
class IfExp(Node):
    test: Optional[Node] = None       # body if test else orelse
    body: Optional[Node] = None
    orelse: Optional[Node] = None


@dataclass
class Compare(Node):
    op: str = ""                      # includes 'in' and 'not in'
    left: Optional[Node] = None
    right: Optional[Node] = None


@dataclass
class DictLit(Node):
    keys: List[Node] = field(default_factory=list)
    values: List[Node] = field(default_factory=list)


@dataclass
class Attribute(Node):
    value: Optional[Node] = None
    attr: str = ""


@dataclass
class TryExcept(Node):
    body: List[Node] = field(default_factory=list)
    handlers: List["ExceptHandler"] = field(default_factory=list)


@dataclass
class ExceptHandler(Node):
    exc_name: Optional[str] = None    # e.g. "IndexError"; None = bare except
    bind: Optional[str] = None        # 'as e'
    body: List[Node] = field(default_factory=list)


@dataclass
class Raise(Node):
    exc_name: str = ""
    message: Optional[Node] = None


@dataclass
class Keyword(Node):
    """name=value in a call (PySub allows print(sep=, end=), sorted(reverse=) and list.sort(reverse=))."""
    name: str = ""
    value: Optional[Node] = None


@dataclass
class Call(Node):
    func: str = ""
    args: List[Node] = field(default_factory=list)
    kwargs: List["Keyword"] = field(default_factory=list)


@dataclass
class MethodCall(Node):
    recv: Optional[Node] = None
    method: str = ""
    args: List[Node] = field(default_factory=list)
    kwargs: List["Keyword"] = field(default_factory=list)


@dataclass
class Subscript(Node):
    value: Optional[Node] = None
    index: Optional[Node] = None


# ------------------------------------------------------------- statements
@dataclass
class Assign(Node):
    target: Optional[Node] = None     # Name or Subscript
    ann: Optional[TypeExpr] = None
    value: Optional[Node] = None
    declares: bool = False            # set by typecheck: first binding in scope


@dataclass
class AugAssign(Node):
    target: Optional[Node] = None
    op: str = ""
    value: Optional[Node] = None


@dataclass
class ExprStmt(Node):
    value: Optional[Node] = None


@dataclass
class Return(Node):
    value: Optional[Node] = None


@dataclass
class If(Node):
    test: Optional[Node] = None
    body: List[Node] = field(default_factory=list)
    orelse: List[Node] = field(default_factory=list)


@dataclass
class While(Node):
    test: Optional[Node] = None
    body: List[Node] = field(default_factory=list)


@dataclass
class ForRange(Node):
    var: str = ""
    start: Optional[Node] = None
    stop: Optional[Node] = None
    step: Optional[Node] = None
    body: List[Node] = field(default_factory=list)


@dataclass
class ForEach(Node):
    var: str = ""
    iter: Optional[Node] = None
    body: List[Node] = field(default_factory=list)


@dataclass
class Pass(Node):
    pass


@dataclass
class Break(Node):
    pass


@dataclass
class Continue(Node):
    pass


@dataclass
class Param(Node):
    name: str = ""
    ann: Optional[TypeExpr] = None


@dataclass
class FuncDef(Node):
    name: str = ""
    params: List[Param] = field(default_factory=list)
    ret: Optional[TypeExpr] = None
    body: List[Node] = field(default_factory=list)
    locals_: dict = field(default_factory=dict)   # filled by typecheck


@dataclass
class ClassField(Node):
    name: str = ""
    ann: Optional[TypeExpr] = None


@dataclass
class ClassDef(Node):
    name: str = ""
    fields: List[ClassField] = field(default_factory=list)
    methods: List[FuncDef] = field(default_factory=list)


@dataclass
class Module(Node):
    funcs: List[FuncDef] = field(default_factory=list)
    classes: List[ClassDef] = field(default_factory=list)
    main: List[Node] = field(default_factory=list)
    globals_: dict = field(default_factory=dict)
