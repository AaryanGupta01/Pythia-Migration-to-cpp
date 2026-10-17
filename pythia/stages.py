"""
PYTHIA :: Stage dump -- every compiler stage as JSON-safe data (for the Studio
"journey" view).  Read-only observer: it runs the same pipeline as the CLI
(lex -> parse -> typecheck -> lower -> elide_guards -> emit) and snapshots
each stage; it changes no compiler behaviour.

    from pythia.stages import dump_stages
    d = dump_stages(src)      # {"ok","diagnostics","tokens","ast","typed_ast","pir","cpp",...}
"""
import dataclasses
import math
from typing import Any, Optional

from . import ast_nodes as A
from .emit_cpp import emit
from .lexer import LexError, tokenize
from .lower import lower
from .optimize import elide_guards
from .parser import Parser
from .typecheck import typecheck


def _scalar(v: Any) -> Any:
    if isinstance(v, float) and not math.isfinite(v):
        return str(v)
    if isinstance(v, (bool, int, float, str)) or v is None:
        return v
    return str(v)                     # Ty and friends


def node_to_dict(n: A.Node) -> dict:
    """Node = {"t","line","col","ty","attrs":{scalars},"kids":{field: Node | [Node]}}"""
    attrs: dict = {}
    kids: dict = {}
    for f in dataclasses.fields(n):
        if f.name in ("line", "col", "ty"):
            continue
        v = getattr(n, f.name)
        if isinstance(v, A.Node):
            kids[f.name] = node_to_dict(v)
        elif isinstance(v, list):
            items = [node_to_dict(x) for x in v if isinstance(x, A.Node)]
            if items:
                kids[f.name] = items
        elif isinstance(v, dict):
            if v:
                attrs[f.name.rstrip("_")] = {str(k): _scalar(x) for k, x in v.items()}
        elif v is not None:
            attrs[f.name] = _scalar(v)
    ty = getattr(n, "ty", None)
    return {"t": type(n).__name__, "line": n.line, "col": n.col,
            "ty": None if ty is None else str(ty), "attrs": attrs, "kids": kids}


def _diag(d) -> dict:
    return {"line": d.line, "col": d.col, "kind": d.kind, "msg": d.msg}


def dump_stages(src: str, filename: str = "<input>") -> dict:
    out: dict = {"ok": False, "diagnostics": [], "tokens": [], "ast": None, "typed_ast": None,
                 "pir": None, "cpp": None, "fidelity": [], "guard_elision": None}
    try:
        toks = tokenize(src, filename)
    except LexError as e:
        out["diagnostics"] = [{"line": e.line, "col": e.col, "kind": "SyntaxError", "msg": e.msg}]
        return out
    out["tokens"] = [{"kind": t.kind, "value": t.value, "line": t.line, "col": t.col} for t in toks]

    p = Parser(toks, filename)
    mod = p.parse_module()
    out["ast"] = node_to_dict(mod)               # snapshot before typecheck annotates the tree
    if p.errors:
        out["diagnostics"] = [_diag(d) for d in p.errors]
        return out

    tc, errs = typecheck(mod, filename)
    out["typed_ast"] = node_to_dict(mod)         # snapshot before lower() rewrites the tree
    if errs:
        out["diagnostics"] = [_diag(d) for d in sorted(errs, key=lambda x: (x.line, x.col))]
        return out

    notes = lower(mod, tc)
    stats = elide_guards(mod)
    out["pir"] = node_to_dict(mod)
    out["cpp"] = emit(mod, tc, filename.replace("\\", "/").rsplit("/", 1)[-1])
    out["fidelity"] = [dataclasses.asdict(n) for n in notes]
    out["guard_elision"] = {"elided": stats.elided, "kept": stats.kept}
    out["ok"] = True
    return out
