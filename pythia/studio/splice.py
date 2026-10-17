"""Splice compiled functions into the workspace copy (`work/`).

The original function body is never touched: one decorator line is added above
the `def`, plus (once per file) a guarded import near the top.  Reversible by
deleting those lines.  See CONTRACTS §7.
"""
from __future__ import annotations

import ast
import difflib
import re
import shutil
from pathlib import Path
from typing import List, Optional

from .models import FunctionRecord, Workspace

RUNTIME = Path(__file__).resolve().parents[2] / "runtime"
SHIM_DIR = RUNTIME / "pythia_accel"
GUARD = ["try:  # pythia-accel",
         "    from _pythia_accel import accelerated as _pythia_accelerated",
         "except ImportError:",
         "    def _pythia_accelerated(*_a, **_k):",
         "        return lambda f: f"]
DECORATOR = "_pythia_accelerated"


class SpliceError(Exception):
    pass


def _read(p: Path):
    try:
        text = p.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as ex:
        raise SpliceError(f"cannot read {p.name}: {ex}")
    return text, ("\r\n" if "\r\n" in text else "\n")


def _find_def(tree: ast.Module, name: str):
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name:
            return n
    raise SpliceError(f"top-level function {name!r} not found in the workspace copy")


def _our_decorators(node):
    return [d for d in node.decorator_list
            if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == DECORATOR]


def _drop_lines(lines: List[str], first: int, last: int) -> None:      # 1-based inclusive
    del lines[first - 1:last]


def _remove_guard(lines: List[str]) -> None:
    for i, ln in enumerate(lines):
        if ln.strip() == GUARD[0] and [l.strip() for l in lines[i:i + 5]] == [g.strip() for g in GUARD]:
            del lines[i:i + 5]
            return


def _insert_guard(text: str, eol: str) -> str:
    if "from _pythia_accel import accelerated as _pythia_accelerated" in text:
        return text
    tree = ast.parse(text)
    lines = text.splitlines(keepends=True)
    after = 0
    for i, n in enumerate(tree.body):
        if i == 0 and isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            after = n.end_lineno
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            after = n.end_lineno
        else:
            break
    if after == 0:                                   # skip shebang / coding cookie
        while after < min(2, len(lines)) and re.match(r"#!|#.*coding[:=]", lines[after]):
            after += 1
    if after and not lines[after - 1].endswith(("\n", "\r")):
        lines[after - 1] += eol
    lines[after:after] = [g + eol for g in GUARD]
    return "".join(lines)


def install(ws: Workspace, modname: str, so_path) -> None:
    dst = ws.work / "_pythia_accel"
    (dst / "lib").mkdir(parents=True, exist_ok=True)
    shutil.copy(SHIM_DIR / "__init__.py", dst / "__init__.py")
    if so_path:
        shutil.copy(so_path, dst / "lib" / Path(so_path).name)


def _diff(ws: Workspace, rel: str, new: str) -> str:
    try:
        old = (ws.original / rel).read_text(encoding="utf-8")
    except OSError:
        old = ""
    return "".join(difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                        fromfile=f"a/{rel}", tofile=f"b/{rel}"))


def apply(ws: Workspace, rec: FunctionRecord, modname: str, so_path) -> dict:
    """Idempotent.  Returns (and stores in rec.splice) {"applied": True, "diff": ...}."""
    path = ws.work / rec.file
    text, eol = _read(path)
    try:
        node = _find_def(ast.parse(text), rec.name)
    except SyntaxError as ex:
        raise SpliceError(f"{rec.file} does not parse: {ex}")
    mine = _our_decorators(node)
    want = f'@{DECORATOR}("{modname}", "{rec.name}")'
    if not (len(mine) == 1 and [getattr(a, "value", None) for a in mine[0].args] == [modname, rec.name]):
        lines = text.splitlines(keepends=True)
        for d in reversed(mine):
            _drop_lines(lines, d.lineno, d.end_lineno)
        tree_lines = "".join(lines)
        node = _find_def(ast.parse(tree_lines), rec.name)
        lines = tree_lines.splitlines(keepends=True)
        lines.insert(node.lineno - 1, " " * node.col_offset + want + eol)
        text = _insert_guard("".join(lines), eol)
        try:
            ast.parse(text)
            compile(text, rec.file, "exec")
        except (SyntaxError, ValueError) as ex:
            raise SpliceError(f"spliced {rec.file} would not parse: {ex}")
        path.write_bytes(text.encode("utf-8"))
    install(ws, modname, so_path)
    rec.splice = {"applied": True, "diff": _diff(ws, rec.file, text)}
    return rec.splice


def revert(ws: Workspace, rec: FunctionRecord) -> dict:
    """Idempotent.  Removes the decorator (and the guard when no accelerated function remains)."""
    path = ws.work / rec.file
    text, eol = _read(path)
    node = _find_def(ast.parse(text), rec.name)
    mine = _our_decorators(node)
    if mine:
        lines = text.splitlines(keepends=True)
        mod = mine[0].args[0].value if mine[0].args and isinstance(mine[0].args[0], ast.Constant) else None
        for d in reversed(mine):
            _drop_lines(lines, d.lineno, d.end_lineno)
        text = "".join(lines)
        if f"@{DECORATOR}(" not in text:
            lines = text.splitlines(keepends=True)
            _remove_guard(lines)
            text = "".join(lines)
        ast.parse(text)
        path.write_bytes(text.encode("utf-8"))
        if mod:
            for so in (ws.work / "_pythia_accel" / "lib").glob(f"{mod}*"):
                so.unlink()
    prev = (rec.splice or {}).get("diff", "")
    rec.splice = {"applied": False, "diff": prev}
    return rec.splice
