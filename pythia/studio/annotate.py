"""Auto-annotation: turn trace-observed arg/return types into PySub annotations.

annotate(rec, trace) -> annotated function source (same line count) or None.
Only touches the signature (params, return) plus const-inlining / typing.List normalisation; the body is
never edited, so line numbers are preserved. Multi-line signatures are handled token-wise.
"""
from __future__ import annotations

import io
import re
import tokenize
from typing import List, Optional, Tuple

from .models import FunctionRecord
from .pysub_rules import check_source

_SCALARS = {"int", "float", "bool", "str"}
_BARE = {"list", "dict", "List", "Dict"}


# ---------------------------------------------------------------- type-string parsing
def _split_top(s: str, sep: str) -> List[str]:
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip() for x in out if x.strip()]


def _parse(s: str):
    s = s.strip()
    if "|" in s and len(_split_top(s, "|")) > 1:
        return ("union", [_parse(p) for p in _split_top(s, "|")])
    m = re.fullmatch(r"(?:Union|typing\.Union)\[(.*)\]", s)
    if m:
        return ("union", [_parse(p) for p in _split_top(m.group(1), ",")])
    m = re.fullmatch(r"(\w+)\[(.*)\]", s)
    if m:
        head, inner = m.group(1).lower(), _split_top(m.group(2), ",")
        if head == "list" and len(inner) == 1:
            return ("list", _parse(inner[0]))
        if head == "dict" and len(inner) == 2:
            return ("dict", _parse(inner[0]), _parse(inner[1]))
        return ("unknown",)
    s = {"NoneType": "None", "Int": "int", "Float": "float", "String": "str"}.get(s, s)
    if s in _SCALARS or s == "None":
        return ("name", s)
    if s.lower() in ("list", "dict"):
        return ("unknown",)          # element types were never observed (empty container)
    return ("unknown",)


def _resolve(t) -> Optional[str]:
    k = t[0]
    if k == "name":
        return t[1]
    if k == "list":
        e = _resolve(t[1])
        return f"list[{e}]" if e and e != "None" else None
    if k == "dict":
        kk, vv = _resolve(t[1]), _resolve(t[2])
        return f"dict[{kk}, {vv}]" if kk and vv and kk in ("int", "str") and vv in _SCALARS else None
    if k == "union":
        members = []
        for m in t[1]:                                   # flatten nested unions
            members += m[1] if m[0] == "union" else [m]
        kinds = {m[0] for m in members}
        if kinds == {"name"}:
            names = {m[1] for m in members}
            if names <= {"int", "float", "bool"}:
                return "float" if "float" in names else "int" if "int" in names else "bool"
            return next(iter(names)) if len(names) == 1 else None
        if kinds == {"list"}:
            return _resolve(("list", ("union", [m[1] for m in members])))
        if kinds == {"dict"}:
            return _resolve(("dict", ("union", [m[1] for m in members]), ("union", [m[2] for m in members])))
        return None
    return None


def resolve_type(s: Optional[str]) -> Optional[str]:
    """Observed type string -> PySub annotation text, or None if it cannot be expressed."""
    if not s:
        return None
    try:
        r = _resolve(_parse(s))
    except Exception:
        return None
    if r is None:
        return None
    if check_source(f"def _f(x: {r}) -> None:\n    pass\n"):
        return None
    return r


# ---------------------------------------------------------------- signature surgery
def _significant(toks):
    return [t for t in toks if t.type not in (tokenize.NL, tokenize.COMMENT, tokenize.NEWLINE)]


def _signature_edits(text: str, arg_types: List[str], ret_type: Optional[str],
                     need_none_ret: bool = False) -> Tuple[List[tuple], List[str]]:
    """Return ([(row, col0, col1, replacement)], unresolved_names)."""
    toks = list(tokenize.generate_tokens(io.StringIO(text).readline))
    i = next(k for k, t in enumerate(toks) if t.type == tokenize.NAME and t.string == "def")
    j = next(k for k in range(i, len(toks)) if toks[k].type == tokenize.OP and toks[k].string == "(")
    depth, k, segs, cur = 0, j, [], []
    while True:
        t = toks[k]
        if t.type == tokenize.OP and t.string in "([{":
            depth += 1
            if depth > 1:
                cur.append(t)
        elif t.type == tokenize.OP and t.string in ")]}":
            depth -= 1
            if depth == 0:
                break
            cur.append(t)
        elif t.type == tokenize.OP and t.string == "," and depth == 1:
            segs.append(cur)
            cur = []
        else:
            cur.append(t)
        k += 1
    close = toks[k]
    if _significant(cur):
        segs.append(cur)
    segs = [_significant(s) for s in segs if _significant(s)]
    if len(segs) != len(arg_types):
        raise ValueError("parameter count differs from trace")
    edits: List[tuple] = []
    unresolved: List[str] = []
    for seg, obs in zip(segs, arg_types):
        name = seg[0]
        if name.type != tokenize.NAME:
            raise ValueError("unsupported parameter form")
        has_ann = len(seg) > 1 and seg[1].string == ":"
        if has_ann:
            rest = seg[2:]
            ann = []
            for t in rest:
                if t.type == tokenize.OP and t.string == "=":
                    break
                ann.append(t)
            if len(ann) == 1 and ann[0].string in _BARE:
                r = resolve_type(obs)
                if r is None:
                    unresolved.append(name.string)
                else:
                    edits.append((ann[0].start[0], ann[0].start[1], ann[0].end[1], r))
        else:
            r = resolve_type(obs)
            if r is None or r == "None":
                unresolved.append(name.string)
            else:
                edits.append((name.end[0], name.end[1], name.end[1], f": {r}"))
    # return annotation
    nxt = [t for t in toks[k + 1:] if t.type not in (tokenize.NL, tokenize.COMMENT)][:1]
    if nxt and nxt[0].type == tokenize.OP and nxt[0].string == "->":
        after = _significant(toks[toks.index(nxt[0]) + 1:])
        ann = []
        for t in after:
            if t.type == tokenize.OP and t.string == ":":
                break
            ann.append(t)
        if len(ann) == 1 and ann[0].string in _BARE:
            r = resolve_type(ret_type)
            if r is None or r == "None":
                unresolved.append("return")
            else:
                edits.append((ann[0].start[0], ann[0].start[1], ann[0].end[1], r))
    elif ret_type is not None:
        is_none = ret_type.strip() in ("None", "NoneType")
        r = "None" if is_none else resolve_type(ret_type)
        if is_none and not need_none_ret:
            pass                                    # `-> None` is implicit in PySub; nothing to add
        elif r is None:
            unresolved.append("return")
        else:
            edits.append((close.end[0], close.end[1], close.end[1], f" -> {r}"))
    return edits, unresolved


def annotate(rec: FunctionRecord, trace: Optional[dict]) -> Optional[str]:
    """Annotated source for `rec` from observed types, or None (no trace / nothing to add / cannot parse)."""
    if not trace or "." in rec.qualname:
        return None
    arg_types = trace.get("arg_types")
    if arg_types is None:
        return None
    text = rec.sources.get("original") or ""
    try:
        own = rec.private.get("own")
        edits, unresolved = _signature_edits(text, list(arg_types), trace.get("ret_type"),
                                             need_none_ret=own is not None and "return" in own.missing)
    except (ValueError, StopIteration, tokenize.TokenError, IndentationError, SyntaxError):
        return None
    rec.private["annotate_unresolved"] = unresolved
    if not edits:
        return None
    lines = text.split("\n")
    for row, c0, c1, rep in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        l = lines[row - 1]
        lines[row - 1] = l[:c0] + rep + l[c1:]
    out = "\n".join(lines)
    info = rec.private.get("modinfo")
    if info is not None:                                   # const-inline + typing.List -> list
        from .scan import prep_text
        out, _ = prep_text(out, info.consts, strip_doc=False)
    return out
