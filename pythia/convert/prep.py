"""Source-to-source preparation steps that run before type inference.

split_tuple_assigns:  `a, b, c = 0, [], {}`  ->  three statements, so each variable can be typed and annotated on its own
(`order: list[int] = []`), which an unpacked tuple cannot express. Exact only when no target is read by a LATER
right-hand element (otherwise it is a simultaneous swap like `a, b = b, a + b`, which stays as it is).
"""
from __future__ import annotations

import ast
from typing import List, Tuple


def _loaded(n: ast.AST) -> set:
    return {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}


def split_tuple_assigns(source: str) -> Tuple[str, int]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, 0
    lines = source.split("\n")
    edits: List[Tuple[int, int, List[str]]] = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Tuple)
                and isinstance(n.value, ast.Tuple)):
            continue
        tg, val = n.targets[0].elts, n.value.elts
        if len(tg) != len(val) or len(tg) < 2 or not all(isinstance(t, ast.Name) for t in tg) \
                or any(isinstance(v, ast.Starred) for v in val):
            continue
        names = [t.id for t in tg]
        if len(set(names)) != len(names):
            continue
        if any(_loaded(val[j]) & set(names[:j]) for j in range(1, len(val))):
            continue                                              # simultaneous assignment: keep the tuple
        first, last = lines[n.lineno - 1], lines[n.end_lineno - 1]
        if first[:n.col_offset].strip() or last[n.end_col_offset:].strip().lstrip("#") not in ("",) \
                and not last[n.end_col_offset:].strip().startswith("#"):
            continue                                              # not a statement of its own on these lines
        indent = first[:n.col_offset]
        segs = [ast.get_source_segment(source, v) for v in val]
        if any(s is None for s in segs):
            continue
        new = [f"{indent}{t} = {s}" for t, s in zip(names, segs)]
        new[-1] += last[n.end_col_offset:]                        # keep a trailing comment
        edits.append((n.lineno - 1, n.end_lineno, new))
    for a, b, new in sorted(edits, key=lambda e: -e[0]):
        lines[a:b] = new
    return "\n".join(lines), len(edits)
