"""Mock Engine: the full CONTRACTS section 5 facade with scripted but realistic data.

Used for UI development and tests (`PYTHIA_ENGINE=mock`). It analyses a fixed demo project
("textlab", ~90 functions in 11 files). Function sources come from `mock_data.FILES`; line
numbers, metrics, C++ and fidelity notes are *derived* (stdlib `ast`, and the real PYTHIA
front-end when importable), so every record is internally consistent.

Job options understood here (besides the contract ones): `fast` (no sleeping, for tests),
`pace_ms` (> 0: sleep that long between events), `duration_s` (default pacing target, 36 s).
"""
from __future__ import annotations

import ast
import base64
import copy
import difflib
import hashlib
import io
import json
import math
import os
import platform
import re
import shutil
import sys
import threading
import time
import tokenize
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..models import JOURNEY_KEYS, SUMMARY_FIELDS
from . import mock_data as D

TRACE_TOTAL_S = 14.62
MODEL = "claude-sonnet-5-5"
SHIM = ("try:\n    from _pythia_accel import accelerated as _pythia_accelerated\n"
        "except ImportError:\n    def _pythia_accelerated(*_a, **_k):\n        return lambda f: f\n")

EXTRA_FILES = {
    "README.md": "# textlab\n\nA small pure-Python text/ML toolkit used as the PYTHIA Studio demo project.\n\n"
                 "    python main.py --small\n",
    "requirements.txt": "numpy>=1.26\n",
    "data/corpus.txt": "".join(f"document {i}: the quick brown fox jumps over the lazy dog {i % 17}\n"
                                for i in range(60)),
    "textlab/__init__.py": "", "textlab/text/__init__.py": "", "textlab/ml/__init__.py": "",
    "textlab/sim/__init__.py": "", "textlab/num/__init__.py": "", "textlab/util/__init__.py": "",
    "textlab/features/__init__.py": "", "textlab/io/__init__.py": "", "textlab/matrix/__init__.py": "",
    "textlab/pipeline/__init__.py": "",
}

# --------------------------------------------------------------------------------------------
# Stage dump (also backs POST /api/stages when pythia.stages is unavailable)
# --------------------------------------------------------------------------------------------
_UNSUPPORTED = {ast.ListComp: "list comprehension", ast.DictComp: "dict comprehension",
                ast.SetComp: "set comprehension", ast.GeneratorExp: "generator expression",
                ast.Lambda: "lambda", ast.Yield: "yield", ast.With: "with statement",
                ast.JoinedStr: "f-string", ast.Import: "import statement", ast.ImportFrom: "import statement"}


def _compile(src: str, name: str = "<mock>"):
    """-> (cpp|None, notes[list of dict], errs[list of dict]); empty result if the compiler is unavailable."""
    try:
        from pythia.cli import compile_source
    except Exception:
        return None, [], []
    try:
        code, notes, errs, _ = compile_source(src, name)
    except Exception as e:  # compiler crash: surface as a diagnostic, never crash the mock
        return None, [], [dict(line=1, col=1, kind="InternalError", msg=str(e))]
    if errs:
        return None, [], [dict(line=d.line, col=d.col, kind=d.kind, msg=d.msg) for d in errs]
    nd = [dict(line=n.line, col=n.col, cls=n.cls, detail=n.detail, mitigation=n.mitigation, severity=n.severity)
          for n in notes]
    return code, nd, []


def _split_cpp(code: str) -> str:
    """Functions only (strip banner and main)."""
    a = code.find('#include "pyrt.hpp"')
    b = code.find("int main(void)")
    body = code[a + len('#include "pyrt.hpp"'):b if b > 0 else len(code)]
    return body.strip("\n") + "\n"


def _infer(n: ast.AST, env: Dict[str, str]) -> Optional[str]:
    if isinstance(n, ast.Constant):
        v = n.value
        return {bool: "bool", int: "int", float: "float", str: "str"}.get(type(v))
    if isinstance(n, ast.Name):
        return env.get(n.id)
    if isinstance(n, (ast.Compare, ast.BoolOp)) or (isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)):
        return "bool"
    if isinstance(n, ast.BinOp):
        a, b = _infer(n.left, env), _infer(n.right, env)
        if isinstance(n.op, ast.Div) or "float" in (a, b):
            return "float"
        return a or b
    if isinstance(n, ast.UnaryOp):
        return _infer(n.operand, env)
    if isinstance(n, ast.Subscript):
        t = _infer(n.value, env) or ""
        m = re.match(r"list\[(.*)\]$", t)
        return m.group(1) if m else ("str" if t == "str" else None)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        f = n.func.id
        if f in ("len", "int", "ord"):
            return "int"
        if f == "float":
            return "float"
        if f in ("abs", "min", "max") and n.args:
            return _infer(n.args[0], env)
        if f == "range":
            return "range"
    if isinstance(n, ast.List):
        return "list[%s]" % (_infer(n.elts[0], env) or "int") if n.elts else "list[int]"
    return None


def _node(n: ast.AST, mode: str, env: Dict[str, str]) -> Dict[str, Any]:
    """mode: ast | typed | pir"""
    t = type(n).__name__
    attrs: Dict[str, Any] = {}
    kids: Dict[str, Any] = {}
    for fld, val in ast.iter_fields(n):
        if fld in ("ctx", "type_comment", "kind", "type_params"):
            continue
        if isinstance(val, ast.AST):
            if isinstance(val, (ast.operator, ast.cmpop, ast.boolop, ast.unaryop)):
                attrs[fld] = type(val).__name__
            else:
                kids[fld] = _node(val, mode, env)
        elif isinstance(val, list):
            items = []
            for x in val:
                if isinstance(x, ast.AST):
                    if isinstance(x, (ast.operator, ast.cmpop, ast.boolop, ast.unaryop)):
                        items.append({"t": type(x).__name__, "line": getattr(n, "lineno", 0), "col": 0, "ty": None, "attrs": {}, "kids": {}})
                    else:
                        items.append(_node(x, mode, env))
            if items:
                kids[fld] = items
        elif val is not None:
            attrs[fld] = val if isinstance(val, (int, float, str, bool)) else repr(val)
    ty = None
    if mode != "ast" and isinstance(n, ast.expr):
        ty = _infer(n, env)
    if mode == "typed" and isinstance(n, ast.arg) and n.annotation is not None:
        env[n.arg] = ast.unparse(n.annotation)
        ty = env[n.arg]
    node = {"t": t, "line": getattr(n, "lineno", 0), "col": getattr(n, "col_offset", 0) + 1, "ty": ty,
            "attrs": attrs, "kids": kids}
    if mode == "pir" and isinstance(n, ast.BinOp):
        lt, rt = _infer(n.left, env), _infer(n.right, env)
        node["attrs"]["no_guard"] = bool(isinstance(n.right, ast.Constant) and isinstance(n.right.value, int)
                                         and abs(n.right.value) < 1000 and not isinstance(n.op, ast.Mult))
        if lt == "int" and rt == "float":
            l = kids["left"]
            kids["left"] = {"t": "Coerce", "line": l["line"], "col": l["col"], "ty": "float",
                            "attrs": {"from": "int", "to": "float"}, "kids": {"value": l}}
    return node


def stage_dump(source: str, filename: str = "<input>") -> Dict[str, Any]:
    """Stand-in for pythia.stages.dump_stages built on stdlib tokenize/ast (+ the real compiler if present)."""
    out: Dict[str, Any] = {"ok": True, "diagnostics": [], "tokens": [], "ast": None, "typed_ast": None,
                           "pir": None, "cpp": "", "fidelity": [], "guard_elision": {"elided": 0, "kept": 0},
                           "mock": True}
    try:
        tree = ast.parse(source, filename)
    except SyntaxError as e:
        out["ok"] = False
        out["diagnostics"].append({"line": e.lineno or 1, "col": e.offset or 1, "kind": "SyntaxError", "msg": e.msg})
        return out
    try:
        for tk in tokenize.generate_tokens(io.StringIO(source).readline):
            k = tokenize.tok_name.get(tk.type, str(tk.type))
            if k in ("NL", "COMMENT", "ENDMARKER"):
                continue
            out["tokens"].append({"kind": k, "value": tk.string, "line": tk.start[0], "col": tk.start[1] + 1})
    except (tokenize.TokenError, IndentationError):
        pass
    for n in ast.walk(tree):
        what = _UNSUPPORTED.get(type(n))
        if what:
            out["ok"] = False
            out["diagnostics"].append({"line": getattr(n, "lineno", 1), "col": getattr(n, "col_offset", 0) + 1,
                                       "kind": "SyntaxError", "msg": f"{what} is outside the PySub subset"})
    out["ast"] = _node(tree, "ast", {})
    out["typed_ast"] = _node(tree, "typed", {})
    out["pir"] = _node(tree, "pir", {})
    code, notes, errs = _compile(source, filename)
    if code:
        out["cpp"] = _split_cpp(code)
        out["fidelity"] = notes
        kept = sum(1 for n in notes if n["cls"].startswith("D1"))
        out["guard_elision"] = {"elided": max(0, 2 * kept // 3), "kept": kept}
    elif not out["diagnostics"] and errs:
        out["ok"] = False
        out["diagnostics"] = [dict(d) for d in errs]
    if not out["cpp"]:
        out["cpp"] = "// (no C++ emitted: the source is outside the PySub subset)\n"
    return out


# --------------------------------------------------------------------------------------------
# Static project model
# --------------------------------------------------------------------------------------------
def _h(s: str) -> int:
    return int(hashlib.sha256(s.encode()).hexdigest()[:8], 16)


def _collect(rel: str, text: str) -> List[Dict[str, Any]]:
    tree = ast.parse(text)
    lines = text.splitlines()
    consts: Dict[str, bool] = {}
    imports: Dict[str, str] = {}
    for st in tree.body:
        if isinstance(st, ast.Assign):
            for t in st.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = True
        elif isinstance(st, ast.Import):
            for a in st.names:
                imports[a.asname or a.name.split(".")[0]] = a.name
        elif isinstance(st, ast.ImportFrom):
            for a in st.names:
                imports[a.asname or a.name] = f"{st.module}.{a.name}"
    out: List[Dict[str, Any]] = []

    def visit(node, prefix):
        for ch in node.body:
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
                q = prefix + ch.name
                out.append(_info(rel, ch, q, lines, consts, imports))
                visit(ch, q + ".<locals>.")
            elif isinstance(ch, ast.ClassDef):
                visit(ch, prefix + ch.name + ".")
    visit(tree, "")
    return out


def _info(rel, fn, qual, lines, consts, imports) -> Dict[str, Any]:
    nodes = list(ast.walk(fn))
    stored = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    stored |= {a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)}
    loaded = {n.id for n in nodes if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}

    def depth(n, d=0):
        best = d
        for c in ast.iter_child_nodes(n):
            nd = d + 1 if isinstance(c, (ast.For, ast.While)) else d
            best = max(best, depth(c, nd))
        return best
    arith = sum(isinstance(n, (ast.BinOp, ast.AugAssign)) for n in nodes)
    calls = sorted({n.func.id for n in nodes if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)})
    return {
        "id": f"{rel}::{qual}", "file": rel, "name": fn.name, "qualname": qual,
        "line": fn.lineno, "end_line": fn.end_lineno, "col": fn.col_offset,
        "source": "\n".join(lines[fn.lineno - 1:fn.end_lineno]) + "\n",
        "node": fn,
        "metrics": {"size_lines": fn.end_lineno - fn.lineno + 1, "loop_depth": depth(fn),
                    "arith_density": round(arith / max(1, len(nodes)), 2), "calls": calls,
                    "imports": sorted(loaded & set(imports)), "uses_globals": sorted((loaded & set(consts)) - stored)},
    }


def _sig_types(fn: ast.AST, src_ok: bool = True):
    args = [ast.unparse(a.annotation) if a.annotation else None for a in fn.args.args]
    return args, (ast.unparse(fn.returns) if fn.returns else None)


def _strip_doc(src: str) -> str:
    """Blank out the docstring (PySub has none) while preserving the line count."""
    try:
        fn = ast.parse(src).body[0]
        d = fn.body[0]
    except (SyntaxError, IndexError, AttributeError):
        return src
    if isinstance(d, ast.Expr) and isinstance(getattr(d, "value", None), ast.Constant) and isinstance(d.value.value, str):
        lines = src.splitlines()
        for k in range(d.lineno - 1, d.end_lineno):
            lines[k] = ""
        return "\n".join(lines) + "\n"
    return src


def _annotate_header(src: str, types) -> str:
    """Insert observed types into the `def` line of an unannotated function."""
    tree = ast.parse(src)
    fn = tree.body[0]
    names = [a.arg for a in fn.args.args]
    ats, rt = types
    head = f"def {fn.name}(" + ", ".join(f"{n}: {t}" for n, t in zip(names, ats)) + f") -> {rt}:"
    lines = src.splitlines()
    lines[0] = head
    return "\n".join(lines) + "\n"


def _cpp_line_map(pysub: str, cpp: str, name: str) -> Dict[str, List[int]]:
    """Approximate pysub-line -> cpp-line map (the real one comes from libmode)."""
    cl = cpp.splitlines()
    start = next((i for i, l in enumerate(cl) if l.startswith("static") and f"f_{name}(" in l and l.rstrip().endswith("{")), None)
    if start is None:
        return {}
    end = next((i for i in range(len(cl) - 1, start, -1) if cl[i].startswith("}")), len(cl) - 1)
    body = cl[start + 1:end]
    try:
        blank = body.index("")
    except ValueError:
        blank = -1
    first = start + 2 + blank if blank >= 0 else start + 1
    body_idx = [i + 1 for i in range(first, end) if cl[i].strip()]      # 1-based cpp line numbers
    pl = pysub.splitlines()
    stmts = [i + 1 for i, l in enumerate(pl) if i > 0 and l.strip() and not l.strip().startswith(('"""', "#", "else", "elif"))]
    m: Dict[str, List[int]] = {"1": [start + 1]}
    if not stmts or not body_idx:
        return m
    per = max(1, math.ceil(len(body_idx) / len(stmts)))
    for k, s in enumerate(stmts):
        chunk = body_idx[k * per:(k + 1) * per]
        if chunk:
            m[str(s)] = [chunk[0], chunk[-1]] if len(chunk) > 1 else chunk
    return m


_SFX = {"int": "i64", "float": "f64", "bool": "bool", "str": "str"}
_CT = {"int": "int64_t", "float": "double", "bool": "bool", "str": "std::string"}


def _wrapper(mod: str, fn_name: str, pysub: str) -> str:
    """Plausible pybind11 glue text (the real one comes from libmode)."""
    fn = next(n for n in ast.parse(pysub).body if isinstance(n, ast.FunctionDef) and n.name == fn_name)
    mutated = {t.value.id for n in ast.walk(fn) for t in ([n.target] if isinstance(n, ast.AugAssign) else getattr(n, "targets", []))
               if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name)}
    mutated |= {n.func.value.id for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("append", "pop") and isinstance(n.func.value, ast.Name)}
    params, conv, call, wb = [], [], [], []
    for a in fn.args.args:
        t = ast.unparse(a.annotation) if a.annotation else "int"
        depth, base = t.count("list["), t.replace("list[", "").replace("]", "")
        if depth:
            params.append(f"py::list {a.arg}")
            conv.append(f"auto c_{a.arg} = to_native_list{depth}_{_SFX.get(base, 'i64')}({a.arg});")
            if a.arg in mutated:
                wb.append(f"write_back({a.arg}, c_{a.arg});   // mutation fidelity: caller's list updated in place")
        elif t == "str":
            params.append(f"const std::string &{a.arg}")
            conv.append(f"if (!is_ascii({a.arg})) throw FallbackError(\"non-ASCII str\");")
            conv.append(f"PyStr *c_{a.arg} = pystr_from({a.arg});")
        else:
            params.append(f"{_CT.get(t, 'int64_t')} {a.arg}")
            conv.append(f"auto c_{a.arg} = {a.arg};")
        call.append(f"c_{a.arg}")
    rt = ast.unparse(fn.returns) if fn.returns else "None"
    lines = ["// pybind11 glue generated by PYTHIA library mode", "#include <pybind11/pybind11.h>", '#include "pyrt.hpp"',
             "namespace py = pybind11;", "", f"PYBIND11_MODULE({mod}, m) {{",
             '    static py::exception<std::runtime_error> FallbackError(m, "FallbackError");',
             f'    m.def("{fn_name}", []({", ".join(params)}) {{', "        arena_begin();"]
    lines += ["        " + c for c in conv]
    lines.append(f"        {'' if rt == 'None' else 'auto r = '}f_{fn_name}({', '.join(call)});")
    lines += ["        " + w for w in wb]
    if rt == "None":
        ret = "py::none()"
    elif "list[" in rt:
        ret = f"from_native_list{rt.count('list[')}_{_SFX.get(rt.replace('list[', '').replace(']', ''), 'i64')}(r)"
    else:
        ret = "r" if rt != "str" else "from_pystr(r)"
    lines += ["        arena_end();", f"        return {ret};", "    });", "}", ""]
    return "\n".join(lines)


class Project:
    """All derived data for the demo project. Built once per process."""

    def __init__(self) -> None:
        self.files: Dict[str, str] = dict(D.FILES)
        self.extra: Dict[str, str] = dict(EXTRA_FILES)
        self.records: Dict[str, Dict[str, Any]] = {}
        self.order: List[str] = []            # scan order (file, then position)
        self.scan_reason: Dict[str, Optional[str]] = {}
        self.module: Dict[str, str] = {}
        self.warnings: List[str] = []
        infos = []
        for rel in sorted(self.files):
            infos += _collect(rel, self.files[rel])
        raw = sum((D.META.get(i["id"], {}).get("share") or 0.0) for i in infos)
        self.share_scale = 0.93 / raw
        for i in infos:
            self.records[i["id"]] = self._build(i)
            self.order.append(i["id"])
        # file text with function line numbers known; decorated work versions are made on demand

    # -- one record -------------------------------------------------------------------------
    def _build(self, i: Dict[str, Any]) -> Dict[str, Any]:
        meta = D.META.get(i["id"], {})
        st = meta.get("st", "verified")
        elig = meta.get("elig") or ("verifiable" if st in ("verified", "guarded", "declined", "failed") else "not_eligible")
        attempts = meta.get("attempts") or []
        fail_fix = bool(meta.get("fail"))
        src = i["source"]
        fn = i["node"]
        qual = i["qualname"]
        eligible_compile = st in ("verified", "guarded", "declined", "failed")
        calls = meta.get("calls")
        share = meta.get("share")
        share = round(share * self.share_scale, 4) if share is not None else None
        types = meta.get("types")

        # --- eligibility diagnostics (real compiler messages where possible)
        diag: List[Dict[str, Any]] = []
        if elig == "fixable":
            probe_src = _strip_doc(_annotate_header(src, types) if types else src)
            _, _, errs = _compile(probe_src)
            diag = [dict(d, phase="eligibility") for d in errs[:2]]
            if not diag:
                diag = [dict(line=1, col=1, kind="TypeError", msg="rejected as written (compiler unavailable for details)", phase="eligibility")]
        elif elig == "not_eligible":
            diag = [self._place(src, kind, msg) for (_l, _c, kind, msg) in (meta.get("diag") or [])]
        reason = meta.get("reason")
        self.scan_reason[i["id"]] = reason if elig != "verifiable" or st in ("declined", "failed") else None

        # --- sources
        annotated = meta.get("annotated")
        if annotated is None and elig == "verifiable":
            annotated = _strip_doc(_annotate_header(src, types) if types else src)
            if annotated == src:
                annotated = None
        pysub = None
        rewrites: List[Dict[str, Any]] = []
        for k, cand in enumerate(attempts, 1):
            cand = _strip_doc(cand)
            cc, _n, errs = _compile(cand)
            last = k == len(attempts)
            if errs:
                err = "line {line}: {kind}: {msg}".format(**errs[0])
                rewrites.append(dict(attempt=k, source="api", pysub=cand, error=err, ok=False))
            elif cc is None and not _compile_available():
                rewrites.append(dict(attempt=k, source="api", pysub=cand, error=None, ok=last and not fail_fix))
            elif last and not fail_fix:
                rewrites.append(dict(attempt=k, source="api", pysub=cand, error=None, ok=True))
            else:
                err = meta.get("replay_err") or "replay mismatch: the rewrite typechecks but returns different values than the original"
                if i["name"] == "normalize_text":
                    err = "replay mismatch: normalize_text('A\\u00a0 B') is 'a b' in CPython but 'a\\u00a0 b' after the rewrite"
                elif i["name"] == "percentile":
                    err = "replay mismatch: percentile([3.0, 1.0, 2.0], 0.5) is 2.0 in CPython but 1.0 (input is never sorted)"
                elif i["name"] == "kmeans_fit":
                    err = "signature changed: the original returns (centroids, inertia); the rewrite returns only centroids"
                rewrites.append(dict(attempt=k, source="api", pysub=cand, error=err, ok=False))
        for w in rewrites:
            m = re.match(r"line (\d+): (\w+): (.*)$", w["error"] or "")
            if m:
                diag.append(dict(line=int(m.group(1)), col=1, kind=m.group(2), msg=m.group(3), phase="fix"))
        if attempts and not fail_fix:
            pysub = attempts[-1]
        elif eligible_compile:
            pysub = meta.get("pysub") or annotated or src
        build_src = pysub

        # --- compiler artifacts
        cpp = wrapper = build = None
        cmap: Dict[str, List[int]] = {}
        fid_notes: List[Dict[str, Any]] = []
        if build_src and eligible_compile:
            code, notes, errs = _compile(build_src, i["file"])
            if errs:
                self.warnings.append(f"{i['id']}: pysub does not compile: {errs[0]}")
            if code:
                cpp = _split_cpp(code)
                cmap = _cpp_line_map(build_src, cpp, i["name"])
                fid_notes = notes if st == "guarded" else [n for n in notes if not n["cls"].startswith("D1")]
            else:
                cpp = f"// (C++ preview unavailable: PYTHIA front-end not importable)\n// {i['name']}\n"
            mod = "pythia_" + hashlib.sha256((cpp or build_src).encode()).hexdigest()[:8]
            self.module[i["id"]] = mod
            wrapper = _wrapper(mod, i["name"], build_src) if _is_plain(build_src) else None
            hh = _h(i["id"])
            cs = round(3.2 + (hh % 55) / 10, 1)
            build = {"ok": True, "module": mod, "so": f"lib/{mod}.cpython-314-x86_64-linux-gnu.so",
                     "cached": hh % 4 == 0, "compile_s": 0.0 if hh % 4 == 0 else cs,
                     "log": (f"[cache] hit sha256:{hashlib.sha256(mod.encode()).hexdigest()[:16]}\n" if hh % 4 == 0 else
                             f"c++ -std=c++17 -O3 -shared -fPIC -I runtime $(python -m pybind11 --includes) {mod}.cpp pyrt.o -o {mod}.so\n"
                             f"built in {cs:.1f}s\n")}
        # --- replay / bench / splice
        total = min(500, calls or 0) if calls else 0
        replay = bench = splice = None
        speedup = probe = None
        status = st
        if st in ("verified", "guarded"):
            replay = {"total": total, "matched": total, "exc_matches": meta.get("exc", 0),
                      "first_mismatch": None}
            sp = meta.get("speedup") or 2.0
            hh = _h(i["id"] + "b")
            py_ms = round(40 + (hh % 9000) / 10 * max(1.0, min(sp, 30)) / 10, 1)
            bench = {"py_ms": py_ms, "cpp_ms": round(py_ms / sp, 2), "speedup": sp, "calls_timed": min(200, total), "repeats": 5}
            speedup = sp
            splice = {"applied": True, "diff": self._diff(i)}
        elif st == "failed":
            mm = meta["mismatch"]
            replay = {"total": total, "matched": int(total * 0.834), "exc_matches": 0, "first_mismatch": dict(mm)}
        elif st == "declined":
            probe = meta["probe"]
            hh = _h(i["id"] + "b")
            py_ms = round(8 + (hh % 400) / 10, 1)
            bench = {"py_ms": py_ms, "cpp_ms": round(py_ms / probe, 2), "speedup": probe, "calls_timed": 200, "repeats": 5}
        ret_t = types[1] if types else (_sig_types(fn)[1])
        arg_t = types[0] if types else [a or "int" for a in _sig_types(fn)[0]]
        ae = meta.get("arg_elems")
        trace = None
        if calls:
            cum = round((share or 0.0) * TRACE_TOTAL_S, 3)
            trace = {"calls": calls, "cum_s": cum, "self_s": round(cum * 0.94, 3), "share": share, "arg_types": arg_t,
                     "ret_type": ret_t or "None", "samples": min(500, calls),
                     "avg_arg_elems": ae if ae is not None else round(6 + (_h(i["id"]) % 300) / 10, 1),
                     "avg_ret_elems": meta.get("ret_elems", 1.0)}
        # --- score
        m = i["metrics"]
        static = round(min(1.0, 0.2 * m["loop_depth"] + 1.4 * m["arith_density"] + m["size_lines"] / 150), 2)
        ef = {"verifiable": 1.0, "fixable": 0.7, "not_eligible": 0.0}[elig]
        eb = float(meta.get("speedup") or meta.get("probe") or 1.0)
        bp = float(meta.get("boundary", 0.0))
        base = share if share is not None else static * 0.05
        total_s = max(0.0, min(1.0, (base ** 0.55) * ef * (0.4 + 0.6 * min(1.0, eb / 60)) / 0.48 - bp))
        if elig != "not_eligible":
            total_s = max(total_s, 0.01)
        notes_s = []
        if share is not None:
            notes_s.append(f"{share * 100:.1f}% of the {TRACE_TOTAL_S:.1f} s traced run, {calls:,} calls")
        else:
            notes_s.append("not exercised by the trace: ranked on static heuristics only")
        if elig == "fixable":
            notes_s.append("needs an LLM rewrite: weighted x0.7")
        if st == "declined":
            notes_s.append(meta["reason"])
        elif elig != "not_eligible":
            notes_s.append(f"expected benefit ~{eb:.0f}x from loop depth {m['loop_depth']} and arithmetic density {m['arith_density']}")
        score = {"total": round(total_s, 3), "trace_share": share, "static_heuristic": static, "eligibility_factor": ef,
                 "expected_benefit": round(eb, 1), "boundary_penalty": bp,
                 "basis": "trace" if share is not None else "static", "notes": notes_s}

        rec = {
            "id": i["id"], "file": i["file"], "name": i["name"], "qualname": qual,
            "line": i["line"], "end_line": i["end_line"], "col": i["col"],
            "status": status, "eligibility": elig, "reason": None, "decision": "pending",
            "score": score, "share": share, "calls": calls, "speedup": speedup, "probe_speedup": probe,
            "metrics": m, "trace": trace,
            "sources": {"original": src, "annotated": annotated, "pysub": pysub, "cpp": cpp, "wrapper_cpp": wrapper},
            "line_map_ok": not bool(attempts), "cpp_line_map": cmap,
            "rewrites": rewrites, "diagnostics": diag, "fidelity": fid_notes,
            "build": build, "replay": replay, "bench": bench, "splice": splice,
        }
        if st in ("declined", "failed", "not_eligible"):
            rec["reason"] = reason
        rec["journey"] = self._journey(rec, meta, elig, fail_fix)
        return rec

    @staticmethod
    def _place(src: str, kind: str, msg: str) -> Dict[str, Any]:
        """Locate a diagnostic in the function text (line/col relative to the function)."""
        hints = re.findall(r"'([^']+)'", msg) + [w for k, w in (("with", "with "), ("yield", "yield"), ("nested", "def "),
                                                              ("generator", " for "), ("tuple", ","), ("variadic", "*"),
                                                              ("import", "import "), ("method", "def "), ("type changes", "return"),
                                                              ("return type", "return"), ("math", "math"), ("Counter", "Counter"),
                                                              ("np", "np"), ("hashlib", "hashlib"), ("argparse", "argparse"),
                                                              ("run_pipeline", "run_pipeline")) if k in msg]
        for h in hints:
            for n, line in enumerate(src.splitlines(), 1):
                c = line.find(h)
                if c >= 0:
                    return {"line": n, "col": c + 1, "kind": kind, "msg": msg, "phase": "eligibility"}
        return {"line": 1, "col": 1, "kind": kind, "msg": msg, "phase": "eligibility"}

    def _diff(self, i: Dict[str, Any]) -> str:
        text = self.files[i["file"]]
        new = decorate(text, [(i["line"], self.module.get(i["id"]), i["name"])])
        return "".join(difflib.unified_diff(text.splitlines(True), new.splitlines(True), f"a/{i['file']}", f"b/{i['file']}"))

    def _journey(self, rec, meta, elig, fail_fix) -> List[Dict[str, Any]]:
        st = rec["status"]
        tr, rw = rec["trace"], rec["rewrites"]
        src = rec["sources"]
        J: Dict[str, Dict[str, Any]] = {}

        def node(k, state, summary=None, reason=None, title=None):
            J[k] = {"key": k, "title": title or _TITLES[k], "state": state, "summary": summary, "reason": reason}
        node("original", "done", f"{rec['metrics']['size_lines']} lines at {rec['file']}:{rec['line']}")
        if tr:
            node("observed_types", "done", f"({', '.join(tr['arg_types'])}) -> {tr['ret_type']} from {tr['calls']:,} calls")
        else:
            node("observed_types", "skipped", reason="never called during the trace run")
        if elig == "verifiable":
            node("eligibility", "done", "typechecker accepts the function" + (" after auto-annotation" if src["annotated"] else " as written"))
        elif elig == "fixable":
            node("eligibility", "done", "rejected as written; fixable", reason=None)
        else:
            node("eligibility", "failed", "not convertible", reason=rec["reason"])
        dead = f"not eligible: {rec['reason']}" if elig == "not_eligible" else None
        if elig == "fixable":
            ok = bool(rw) and rw[-1]["ok"]
            node("rewrites", "done" if ok else "failed", f"{len(rw)} attempt{'s' if len(rw) != 1 else ''}",
                 None if ok else (rec["reason"] or "all rewrite attempts failed"))
            node("pysub", "done" if ok else "failed", "LLM rewrite accepted" if ok else None,
                 None if ok else "no PySub candidate survived typecheck and replay")
        elif elig == "verifiable":
            node("rewrites", "skipped", reason="no rewrite needed")
            node("pysub", "done", "auto-annotated PySub" if src["annotated"] else "original source is already PySub")
        else:
            node("rewrites", "skipped", reason=dead)
            node("pysub", "skipped", reason=dead)
        if src["pysub"]:
            for k, s in (("tokens", "token stream"), ("ast", "parse tree"), ("typed_ast", "typed tree"), ("pir", "lowered IR with guards")):
                node(k, "done", s)
            node("cpp", "done", f"{len((src['cpp'] or '').splitlines())} lines of C++17")
            node("wrapper", "done", "pybind11 module glue")
            b = rec["build"]
            node("build", "done", f"{b['module']}.so, " + ("cache hit" if b["cached"] else f"{b['compile_s']:.1f} s"))
        else:
            why = dead or rec["reason"] or "no PySub produced"
            for k in ("tokens", "ast", "typed_ast", "pir", "cpp", "wrapper", "build"):
                node(k, "skipped", reason=why)
        if st in ("verified", "guarded"):
            r = rec["replay"]
            node("replay", "done", f"{r['matched']}/{r['total']} calls match" + (f", {r['exc_matches']} exception cases" if r["exc_matches"] else ""))
            b = rec["bench"]
            node("benchmark", "done", f"{b['py_ms']:.1f} ms -> {b['cpp_ms']:.2f} ms, {b['speedup']:.1f}x")
            node("splice", "done", "@_pythia_accelerated decorator added")
        elif st == "failed":
            r = rec["replay"]
            node("replay", "failed", f"{r['matched']}/{r['total']} calls match", rec["reason"])
            node("benchmark", "skipped", reason="auto-rejected after replay mismatch")
            node("splice", "skipped", reason="auto-rejected after replay mismatch")
        elif st == "declined":
            node("replay", "skipped", reason="probe build only: never spliced")
            b = rec["bench"]
            node("benchmark", "done", f"probe: {b['py_ms']:.1f} ms -> {b['cpp_ms']:.2f} ms, {b['speedup']:.2f}x")
            node("splice", "skipped", reason=rec["reason"])
        else:
            w = dead or rec["reason"] or "not compiled"
            node("replay", "skipped", reason=w)
            node("benchmark", "skipped", reason=w)
            node("splice", "skipped", reason=w)
        node("status", "failed" if st in ("failed", "not_eligible") else "done", st.replace("_", " "), rec["reason"] if st != "verified" else None)
        return [J[k] for k in JOURNEY_KEYS]


_TITLES = {"original": "Original Python", "observed_types": "Observed types", "eligibility": "Eligibility check",
           "rewrites": "LLM rewrite attempts", "pysub": "Final PySub", "tokens": "Tokens", "ast": "AST",
           "typed_ast": "Typed AST", "pir": "PIR", "cpp": "Generated C++", "wrapper": "pybind11 wrapper",
           "build": "Build", "replay": "Oracle replay", "benchmark": "Benchmark", "splice": "Splice", "status": "Status"}


def _compile_available() -> bool:
    try:
        import pythia.cli  # noqa: F401
        return True
    except Exception:
        return False


def _is_plain(src: str) -> bool:
    try:
        ast.parse(src)
        return True
    except SyntaxError:
        return False


def decorate(text: str, items) -> str:
    """Splice simulation: add the guarded import after the module docstring and a decorator per function.
    items = [(def_line, modname, fn_name)]"""
    lines = text.splitlines(True)
    for ln, mod, name in sorted(items, reverse=True):
        lines.insert(ln - 1, f'@_pythia_accelerated("{mod}", "{name}")\n')
    if items:
        tree = ast.parse(text)
        at = 0
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(getattr(tree.body[0], "value", None), ast.Constant) \
                and isinstance(tree.body[0].value.value, str):
            at = tree.body[0].end_lineno
        lines[at:at] = (["\n"] if at else []) + [SHIM, "\n"]
    return "".join(lines)


_PROJECT: Optional[Project] = None
_PLOCK = threading.Lock()


def project() -> Project:
    global _PROJECT
    with _PLOCK:
        if _PROJECT is None:
            _PROJECT = Project()
        return _PROJECT


# --------------------------------------------------------------------------------------------
# Job state + event script
# --------------------------------------------------------------------------------------------
PHASE_KEYS = {"scan": ["original", "eligibility"], "trace": ["observed_types"], "rank": [], "fix": ["rewrites", "pysub"],
              "compile": ["pysub", "tokens", "ast", "typed_ast", "pir", "cpp", "wrapper", "build"],
              "verify": ["replay"], "bench": ["benchmark"], "splice": ["splice"], "finish": list(JOURNEY_KEYS)}


class _Job:
    def __init__(self, job_id: str, ws_id: str, name: str, input_kind: str, options: dict):
        self.id, self.ws, self.name, self.kind, self.options = job_id, ws_id, name, input_kind, options
        self.state = "running"
        self.started = time.time()
        self.finished: Optional[float] = None
        self.summary: Optional[dict] = None
        self.recs: Dict[str, Dict[str, Any]] = {}
        self.spliced: set = set()
        self.cancel = threading.Event()
        self.lock = threading.RLock()
        self.emit: Optional[Callable] = None
        self.thread: Optional[threading.Thread] = None

    def public(self) -> dict:
        return {"job_id": self.id, "workspace_id": self.ws, "name": self.name, "state": self.state,
                "options": self.options, "started": self.started, "finished": self.finished, "summary": self.summary}


def summarize(rec: dict) -> dict:
    d = {k: rec.get(k) for k in SUMMARY_FIELDS}
    d["score"] = {"total": rec["score"].get("total", 0.0)}
    d["loop_depth"] = rec["metrics"].get("loop_depth", 0)
    d["size_lines"] = rec["metrics"].get("size_lines", 0)
    return d


def _counts(recs) -> dict:
    c = {k: 0 for k in ("verified", "guarded", "fixable", "not_eligible", "failed", "declined")}
    for r in recs:
        if r["status"] in c:
            c[r["status"]] += 1
    return c


def _geomean(xs):
    xs = [x for x in xs if x and x > 0]
    return round(math.exp(sum(math.log(x) for x in xs) / len(xs)), 2) if xs else None


class MockEngine:
    def __init__(self, home: Optional[str] = None):
        self.home = Path(home or os.environ.get("PYTHIA_HOME") or Path.home() / ".pythia-studio").expanduser()
        (self.home / "jobs").mkdir(parents=True, exist_ok=True)
        self._jobs: Dict[str, _Job] = {}
        self._ws_job: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._settings = {"offline": False, "model": MODEL, "api_key_set": False}
        sp = self.home / "settings.json"
        if sp.exists():
            try:
                self._settings.update(json.loads(sp.read_text(encoding="utf-8")))
            except Exception:
                pass
        self.project = project()
        for w in self.project.warnings:
            print("[mock-engine] warning:", w, file=sys.stderr)
        self._load_jobs()

    # -- persistence ------------------------------------------------------------------------
    def _jobdir(self, job_id: str) -> Path:
        return self.home / "jobs" / job_id

    def _save_job(self, j: _Job) -> None:
        d = self._jobdir(j.id)
        d.mkdir(parents=True, exist_ok=True)
        data = j.public()
        data.update(mock=True, input_kind=j.kind,
                    decisions={f: r["decision"] for f, r in j.recs.items() if r["decision"] != "pending"})
        (d / "job.json").write_text(json.dumps(data), encoding="utf-8")

    def _load_jobs(self) -> None:
        for p in sorted((self.home / "jobs").glob("*/job.json")):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if not d.get("mock"):
                    continue
                j = _Job(d["job_id"], d["workspace_id"], d["name"], d.get("input_kind", "demo"), d.get("options", {}))
                j.state = d["state"] if d["state"] != "running" else "failed"   # interrupted by a restart
                j.started, j.finished, j.summary = d["started"], d.get("finished"), d.get("summary")
                if j.state == "failed" and not j.summary:
                    j.summary = None
                for fid in self.project.order:
                    r = copy.deepcopy(self.project.records[fid])
                    r["decision"] = d.get("decisions", {}).get(fid, "pending")
                    if r["splice"]:
                        r["splice"]["applied"] = r["decision"] != "rejected"
                    j.recs[fid] = r
                    if r["status"] in ("verified", "guarded"):
                        j.spliced.add(fid)
                self._jobs[j.id] = j
                self._ws_job[j.ws] = j.id
            except Exception as e:
                print("[mock-engine] could not load", p, e, file=sys.stderr)

    # -- facade ----------------------------------------------------------------------------
    def env(self) -> dict:
        return {"compiler": {"found": True, "name": "g++", "version": "15.2.0", "hint": None}, "pybind11": True,
                "python": platform.python_version(), "platform": sys.platform,
                "llm": {"enabled": True, "model": self._settings["model"], "hint": None},
                "offline_available": True, "offline": bool(self._settings["offline"]),
                "wsl": "microsoft" in platform.release().lower(), "mock": True}

    def settings(self) -> dict:
        return dict(self._settings)

    def update_settings(self, patch: dict) -> dict:
        for k, v in (patch or {}).items():
            if k == "api_key":
                self._settings["api_key_set"] = bool(v)          # write-only, never stored
            elif k in ("offline", "model"):
                self._settings[k] = v
            else:
                raise ValueError(f"unknown setting '{k}'")
        (self.home / "settings.json").write_text(json.dumps(self._settings), encoding="utf-8")
        return self.settings()

    def start_job(self, input: dict, options: dict, emit) -> str:
        kind = (input or {}).get("kind")
        if kind not in ("snippet", "file", "folder", "git", "demo"):
            raise ValueError(f"unknown input kind {kind!r}")
        name = (input.get("name") or input.get("filename") or "").rsplit(".", 1)[0] if kind in ("snippet", "file") else ""
        if kind == "folder":
            name = Path(input.get("path") or "").name
        elif kind == "git":
            name = (input.get("url") or "").rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
        name = name or D.PROJECT_NAME
        opts = {"trace_cmd": D.TRACE_CMD, "trace_timeout_s": 60, "offline": bool(self._settings["offline"]),
                "llm": True, "model": self._settings["model"], "pace_ms": 0}
        opts.update(options or {})
        job = _Job(uuid.uuid4().hex[:8], uuid.uuid4().hex[:8], name, kind, opts)
        job.emit = emit
        with self._lock:
            self._jobs[job.id] = job
            self._ws_job[job.ws] = job.id
        self._save_job(job)
        job.thread = threading.Thread(target=self._run, args=(job,), name=f"mock-job-{job.id}", daemon=True)
        job.thread.start()
        return job.id

    def cancel(self, job_id: str) -> None:
        self._job(job_id).cancel.set()

    def _job(self, job_id: str) -> _Job:
        try:
            return self._jobs[job_id]
        except KeyError:
            raise KeyError(f"unknown job '{job_id}'") from None

    def job(self, job_id: str) -> dict:
        return self._job(job_id).public()

    def jobs(self) -> List[dict]:
        return sorted((j.public() for j in self._jobs.values()), key=lambda d: -d["started"])

    def recent(self) -> List[dict]:
        out = []
        for j in sorted(self._jobs.values(), key=lambda j: -j.started):
            if any(o["workspace_id"] == j.ws for o in out):
                continue
            out.append({"workspace_id": j.ws, "ws_id": j.ws, "name": j.name, "origin": f"mock://{j.name}",
                        "input_kind": j.kind, "job_id": j.id, "opened": j.started, "state": j.state,
                        "functions": len(j.recs), "summary": j.summary})
        return out

    def functions(self, job_id: str) -> List[dict]:
        j = self._job(job_id)
        with j.lock:
            return [summarize(r) for r in j.recs.values()]

    def function(self, job_id: str, fid: str, stages: bool = False) -> dict:
        j = self._job(job_id)
        with j.lock:
            if fid not in j.recs:
                raise KeyError(f"unknown function '{fid}'")
            r = copy.deepcopy(j.recs[fid])
        if stages:
            r["stages"] = stage_dump(r["sources"]["pysub"] or r["sources"]["original"], r["file"])
        return r

    def decide(self, job_id: str, fid: str, decision: str) -> dict:
        if decision not in ("accepted", "rejected", "pending"):
            raise ValueError("decision must be accepted, rejected or pending")
        j = self._job(job_id)
        with j.lock:
            if fid == "all":
                targets = [f for f, r in j.recs.items() if r["status"] in ("verified", "guarded")]
            elif fid in j.recs:
                if j.recs[fid]["status"] not in ("verified", "guarded"):
                    raise ValueError("only verified or guarded functions can be accepted or rejected")
                targets = [fid]
            else:
                raise KeyError(f"unknown function '{fid}'")
            for f in targets:
                r = j.recs[f]
                r["decision"] = decision
                if r["splice"]:
                    r["splice"]["applied"] = decision != "rejected"
            out = [summarize(j.recs[f]) for f in targets]
        self._save_job(j)
        return {"functions": out}

    # -- files ------------------------------------------------------------------------------
    def _all_files(self) -> Dict[str, str]:
        d = dict(self.project.extra)
        d.update(self.project.files)
        return d

    def _job_for_ws(self, ws_id: str) -> Optional[_Job]:
        jid = self._ws_job.get(ws_id)
        return self._jobs.get(jid) if jid else None

    def _work_text(self, j: Optional[_Job], rel: str) -> str:
        text = self._all_files()[rel]
        if j is None or not rel.endswith(".py"):
            return text
        items = []
        with j.lock:
            for f, r in j.recs.items():
                if r["file"] == rel and f in j.spliced and r["status"] in ("verified", "guarded") and r["decision"] != "rejected":
                    items.append((r["line"], self.project.module[f], r["name"]))
        return decorate(text, items) if items else text

    def tree(self, ws_id: str) -> List[dict]:
        j = self._job_for_ws(ws_id)
        if j is None:
            raise KeyError(f"unknown workspace '{ws_id}'")
        bad: Dict[str, List[int]] = {}
        with j.lock:
            for f, r in j.recs.items():
                b = bad.setdefault(r["file"], [0, 0])
                if (r["share"] or 0) >= 0.02 and r["eligibility"] != "not_eligible":
                    b[0] += 1
                if f in j.spliced and r["status"] in ("verified", "guarded") and r["decision"] != "rejected":
                    b[1] += 1
        root: Dict[str, Any] = {}
        for p in sorted(self._all_files()):
            cur = root
            parts = p.split("/")
            for k, part in enumerate(parts):
                cur = cur.setdefault(part, {} if k < len(parts) - 1 else None)

        def build(d: dict, prefix: str) -> List[dict]:
            out = []
            for name in sorted(d, key=lambda n: (d[n] is None, n.lower())):
                path = prefix + name
                if d[name] is None:
                    h, a = bad.get(path, [0, 0])
                    out.append({"path": path, "name": name, "type": "file", "badges": {"hotspots": h, "accelerated": a}})
                else:
                    ch = build(d[name], path + "/")
                    out.append({"path": path, "name": name, "type": "dir", "children": ch,
                                "badges": {"hotspots": sum(c["badges"]["hotspots"] for c in ch),
                                           "accelerated": sum(c["badges"]["accelerated"] for c in ch)}})
            return out
        return build(root, "")

    def read_file(self, ws_id: str, rel: str, version: str = "work") -> dict:
        files = self._all_files()
        if ws_id not in self._ws_job:
            raise KeyError(f"unknown workspace '{ws_id}'")
        if rel not in files:
            raise FileNotFoundError(f"no such file '{rel}'")
        content = self._work_text(self._job_for_ws(ws_id), rel) if version == "work" else files[rel]
        lang = {"py": "python", "md": "markdown", "txt": "plaintext"}.get(rel.rsplit(".", 1)[-1], "plaintext")
        return {"path": rel, "content": content, "language": lang, "size": len(content.encode())}

    def file_diff(self, job_id: str, rel: str) -> dict:
        j = self._job(job_id)
        files = self._all_files()
        if rel not in files:
            raise FileNotFoundError(f"no such file '{rel}'")
        return {"original": files[rel], "modified": self._work_text(j, rel)}

    # -- report / export ----------------------------------------------------------------------
    def _final_summary(self, j: _Job) -> dict:
        with j.lock:
            recs = list(j.recs.values())
        c = _counts(recs)
        sps = [r["speedup"] for r in recs if r["status"] in ("verified", "guarded") and r["decision"] != "rejected"]
        e2e = D.E2E
        return {"functions": len(recs), **c, "e2e_speedup": round(e2e["before_s"] / e2e["after_s"], 2),
                "geomean_speedup": _geomean(sps)}

    def report(self, job_id: str) -> dict:
        j = self._job(job_id)
        with j.lock:
            recs = [copy.deepcopy(r) for r in j.recs.values()]
        s = self._final_summary(j)
        done = [r for r in recs if r["status"] in ("verified", "guarded")]
        done.sort(key=lambda r: -(r["speedup"] or 0))
        md = [f"# PYTHIA report: {j.name}", "",
              f"**{s['e2e_speedup']:.2f}x end-to-end** (`{D.TRACE_CMD}`: {D.E2E['before_s']:.2f} s -> {D.E2E['after_s']:.2f} s), "
              f"geometric-mean function speedup {s['geomean_speedup']}x.", "",
              f"{s['functions']} functions analysed: {s['verified']} verified, {s['guarded']} guarded, {s['fixable']} fixable, "
              f"{s['not_eligible']} not eligible, {s['failed']} failed, {s['declined']} declined.", "",
              "## Accelerated functions", "", "| Function | Status | Speedup | Replays | Decision |", "|---|---|---|---|---|"]
        for r in done:
            md.append(f"| `{r['id']}` | {r['status']} | {r['speedup']:.1f}x | {r['replay']['matched']}/{r['replay']['total']} | {r['decision']} |")
        md += ["", "## Declined and failed", ""]
        for r in recs:
            if r["status"] in ("declined", "failed"):
                md.append(f"* `{r['id']}` ({r['status']}): {r['reason']}")
        md += ["", "## LLM rewrites", ""]
        for r in recs:
            if r["rewrites"] and r["rewrites"][-1]["ok"]:
                diff = "".join(difflib.unified_diff(r["sources"]["original"].splitlines(True), r["rewrites"][-1]["pysub"].splitlines(True),
                                                    "original", "pysub"))
                md += [f"### `{r['id']}`", "", "```diff", diff.rstrip(), "```", ""]
        fid = {"exact": 0, "guarded": 0, "divergent": 0}
        for r in recs:
            for n in r["fidelity"]:
                fid[n["severity"]] += 1
        md += ["## Fidelity notes", "", f"{fid['exact']} exact, {fid['guarded']} guarded, {fid['divergent']} divergent sites across accelerated functions.", ""]
        js = {"name": j.name, "job_id": j.id, "summary": s, "e2e": dict(D.E2E, cmd=D.TRACE_CMD),
              "fidelity": fid, "functions": [dict(summarize(r), replay=r["replay"], bench=r["bench"]) for r in recs]}
        return {"markdown": "\n".join(md) + "\n", "json": js}

    def export(self, job_id: str, dest: Optional[str], zip: bool) -> str:
        j = self._job(job_id)
        base = Path(dest).expanduser() if dest else self.home / "exports" / j.id
        if base.exists() and not base.is_dir():
            raise ValueError(f"'{base}' is not a folder")
        root = base / f"{j.name}-accelerated"
        k = 1
        while root.exists():                       # never overwrite or delete anything
            k += 1
            root = base / f"{j.name}-accelerated-{k}"
        n = 0
        for rel in self._all_files():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(self._work_text(j, rel), encoding="utf-8", newline="\n")
            n += 1
        acc = root / "_pythia_accel"
        (acc / "lib").mkdir(parents=True, exist_ok=True)
        (acc / "__init__.py").write_text('"""Mock shim: loads lib/<module>*.so by path, falls back to the original function."""\n'
                                         "def accelerated(mod, fn):\n    return lambda f: f\n", encoding="utf-8")
        mods = []
        with j.lock:
            recs = [r for r in j.recs.values() if r["status"] in ("verified", "guarded") and r["decision"] != "rejected"]
        for r in recs:
            mod = self.project.module[r["id"]]
            mods.append(mod)
            (acc / "lib" / f"{mod}.so").write_bytes(b"\x7fELF mock")
            (acc / "src").mkdir(exist_ok=True)
            (acc / "src" / f"{mod}.cpp").write_text((r["sources"]["cpp"] or "") + "\n" + (r["sources"]["wrapper_cpp"] or ""), encoding="utf-8")
            n += 2
        (root / "PYTHIA_REPORT.md").write_text(self.report(job_id)["markdown"], encoding="utf-8")
        (root / "build_accel.sh").write_text("#!/bin/sh\nset -e\ncd \"$(dirname \"$0\")/_pythia_accel\"\nfor f in src/*.cpp; do\n"
                                             "  m=$(basename \"$f\" .cpp)\n  c++ -std=c++17 -O3 -shared -fPIC $(python3 -m pybind11 --includes) "
                                             "-I ../runtime \"$f\" -o \"lib/$m$(python3-config --extension-suffix)\"\ndone\n", encoding="utf-8", newline="\n")
        n += 2
        path = root
        if zip:
            path = Path(shutil.make_archive(str(root), "zip", root.parent, root.name))
        if j.emit:
            j.emit("stage", {"stage": "export", "state": "done", "summary": f"{n} files", "progress": 1.0}, stage="export")
            j.emit("export.done", {"path": str(path), "zip": bool(zip), "files": n}, stage="export",
                   caption="Exported the accelerated project with its report and rebuild script")
        return str(path)

    def list_dir(self, path: str) -> dict:
        from .app import fs_list
        return fs_list(path)

    # -- job runner --------------------------------------------------------------------------
    def _run(self, job: _Job) -> None:
        try:
            steps = self._script(job)
            opts = job.options
            fast = bool(opts.get("fast"))
            pace = float(opts.get("pace_ms") or 0) / 1000.0
            total_w = sum(s["w"] for s in steps) or 1.0
            scale = float(opts.get("duration_s", 36)) / total_w
            for s in steps:
                if job.cancel.is_set():
                    break
                if s.get("apply"):
                    with job.lock:
                        s["apply"]()
                if s["type"]:
                    data = s["data"]() if callable(s["data"]) else s["data"]
                    job.emit(s["type"], data, stage=s.get("stage"), caption=s.get("caption"))
                if not fast:
                    dt = pace if pace > 0 else s["w"] * scale
                    if dt > 0 and job.cancel.wait(dt):
                        break
            if job.cancel.is_set():
                job.state = "cancelled"
                job.emit("log", {"stream": "system", "level": "warn", "text": "job cancelled by user"})
                job.summary = self._final_summary(job)
            else:
                job.state = "done"
                job.summary = self._final_summary(job)
        except Exception as e:  # pragma: no cover
            job.state = "failed"
            job.emit("error", {"where": "mock-engine", "message": f"{type(e).__name__}: {e}", "fatal": True})
            with job.lock:
                job.summary = self._final_summary(job)
        job.finished = time.time()
        self._save_job(job)
        job.emit("job.done", {"state": job.state, "summary": job.summary}, caption=f"Analysis {job.state}")

    # -- the script ------------------------------------------------------------------------
    def _script(self, job: _Job) -> List[dict]:
        P = self.project
        S: List[dict] = []

        def add(type_, data=None, stage=None, caption=None, w=1.0, apply=None):
            S.append({"type": type_, "data": data, "stage": stage, "caption": caption, "w": w, "apply": apply})

        def stage(name, state, summary=None, progress=None, caption=None, w=1.0):
            add("stage", {"stage": name, "state": state, "summary": summary, "progress": progress}, name, caption, w)

        def step(sid, fid, title, state, detail, w=0.05):
            add("agent.step", {"step_id": sid, "fn_id": fid, "title": title, "state": state, "detail": detail}, None, None, w)

        final = P.records
        order = P.order
        n_py = sum(1 for p in {**P.files, **P.extra} if p.endswith(".py"))
        n_files = len(P.files) + len(P.extra)

        # reveal helper (mutates job.recs; runs under job.lock)
        def reveal(fid, phase):
            f, r = final[fid], job.recs[fid]
            J = {n["key"]: n for n in f["journey"]}
            keys = PHASE_KEYS[phase]
            if phase == "scan":
                pass
            elif phase == "trace":
                r["share"], r["calls"], r["trace"] = f["share"], f["calls"], copy.deepcopy(f["trace"])
                r["sources"]["annotated"] = f["sources"]["annotated"]
            elif phase == "rank":
                r["score"] = copy.deepcopy(f["score"])
                if f["status"] == "declined":
                    r["status"], r["reason"] = "declined", f["reason"]
            elif phase == "fix":
                r["rewrites"] = copy.deepcopy(f["rewrites"])
                r["diagnostics"] = copy.deepcopy(f["diagnostics"])
                ok = bool(f["rewrites"]) and f["rewrites"][-1]["ok"]
                r["line_map_ok"] = False
                if ok:
                    r["sources"]["pysub"], r["status"], r["reason"] = f["sources"]["pysub"], "pending", None
                else:
                    r["status"], r["reason"] = "not_eligible", f["reason"]
            elif phase == "compile":
                for k in ("pysub", "cpp", "wrapper_cpp"):
                    r["sources"][k] = f["sources"][k]
                r["cpp_line_map"], r["fidelity"], r["build"] = f["cpp_line_map"], copy.deepcopy(f["fidelity"]), copy.deepcopy(f["build"])
                r["line_map_ok"] = f["line_map_ok"]
            elif phase == "verify":
                r["replay"] = copy.deepcopy(f["replay"])
                if f["status"] in ("verified", "guarded", "failed"):
                    r["status"], r["reason"] = f["status"], f["reason"]
            elif phase == "bench":
                r["bench"], r["speedup"], r["probe_speedup"] = copy.deepcopy(f["bench"]), f["speedup"], f["probe_speedup"]
            elif phase == "splice":
                r["splice"] = copy.deepcopy(f["splice"])
                job.spliced.add(fid)
            elif phase == "finish":
                r["status"], r["reason"], r["speedup"] = f["status"], f["reason"], f["speedup"]
            for k in keys:
                if k in J:
                    r["journey"][JOURNEY_KEYS.index(k)] = dict(J[k])

        def make_scan_state(fid):
            f = copy.deepcopy(final[fid])
            el = f["eligibility"]
            f.update(status="fixable" if el == "fixable" else ("not_eligible" if el == "not_eligible" else "pending"),
                     reason=P.scan_reason[fid], decision="pending", share=None, calls=None, speedup=None, probe_speedup=None,
                     trace=None, line_map_ok=True, cpp_line_map={}, rewrites=[], fidelity=[], build=None, replay=None,
                     bench=None, splice=None)
            f["score"] = {"total": 0.0, "trace_share": None, "static_heuristic": final[fid]["score"]["static_heuristic"],
                          "eligibility_factor": final[fid]["score"]["eligibility_factor"], "expected_benefit": 1.0,
                          "boundary_penalty": 0.0, "basis": "static", "notes": []}
            f["sources"] = {"original": f["sources"]["original"], "annotated": None, "pysub": None, "cpp": None, "wrapper_cpp": None}
            f["journey"] = [{"key": k, "title": _TITLES[k], "state": "pending", "summary": None, "reason": None} for k in JOURNEY_KEYS]
            return f

        def add_scan(fid):
            job.recs[fid] = make_scan_state(fid)
            reveal(fid, "scan")

        # ---- job.start / ingest
        add("job.start", {"job_id": job.id, "workspace_id": job.ws, "name": job.name, "input_kind": job.kind, "options": job.options},
            caption=f"Starting analysis of {job.name}", w=1)
        stage("ingest", "running", None, 0.0, "Copying the project into a private workspace", 1)
        phases = [("copy", 0.25), ("copy", 0.6), ("index", 0.9), ("index", 1.0)]
        if job.kind == "git":
            phases = [("clone", 0.3)] + phases
        for ph, fr in phases:
            add("ingest.progress", {"phase": ph, "files": int(n_files * fr), "bytes": int(184_000 * fr),
                                    "current": sorted(P.files)[min(len(P.files) - 1, int(fr * len(P.files)))],
                                    "message": {"copy": "copying files", "clone": f"git clone --depth 1 {job.name}", "index": "indexing Python files"}[ph]},
                "ingest", None, 2)
        skipped = [{"path": ".git/", "reason": "version-control metadata"}, {"path": "venv/", "reason": "virtual environment"},
                   {"path": "data/embeddings.npy", "reason": "larger than 5 MB"}, {"path": "__pycache__/", "reason": "bytecode cache"}]
        add("ingest.done", {"workspace_id": job.ws, "name": job.name, "files": n_files, "py_files": n_py, "skipped": skipped}, "ingest",
            f"Ingested {n_files} files ({n_py} Python)", 1)
        stage("ingest", "done", f"{n_files} files", 1.0, None, 1)

        # ---- scan
        stage("scan", "running", None, 0.0, "Parsing every function and running the PYTHIA typechecker on each", 1)
        step("scan", None, "Static scan", "running", "parsing modules")
        N = len(order)
        for k, fid in enumerate(order, 1):
            add("scan.function", lambda fid=fid: {"function": summarize(job.recs[fid])}, "scan", None, 0.45,
                apply=(lambda fid=fid: add_scan(fid)))
            if k % 15 == 0:
                stage("scan", "running", f"{k} functions", k / N, None, 0.1)
        el = [final[f]["eligibility"] for f in order]
        sc = {"functions": N, "verifiable": el.count("verifiable"), "fixable": el.count("fixable"), "not_eligible": el.count("not_eligible")}
        add("scan.done", sc, "scan", f"{N} functions: {sc['verifiable']} convertible as written, {sc['fixable']} fixable, {sc['not_eligible']} not eligible", 1)
        step("scan", None, "Static scan", "done", f"{N} functions, {sc['verifiable']} verifiable, {sc['fixable']} fixable, {sc['not_eligible']} not eligible")
        stage("scan", "done", f"{N} functions", 1.0, None, 1)

        # ---- trace
        called = [f for f in order if final[f]["calls"]]
        total_calls = sum(final[f]["calls"] for f in called)
        stage("trace", "running", None, 0.0, f"Running `{job.options.get('trace_cmd') or D.TRACE_CMD}` under the tracer", 1)
        step("trace", None, "Trace run", "running", f"python {D.TRACE_CMD.split(' ', 1)[1]}")
        tails = ["loading corpus: 4000 documents", "tokenising... 31,882 tokens", "dedup: comparing 4000 x 4000 pairs", "dedup: kept 3125 documents",
                 "kmeans k=4: iteration 9/20", "simulating 64 bodies, 400 steps", "kmeans converged, inertia 9120.442", "final inertia 9120.442"]
        for k in range(1, 9):
            fr = k / 8
            add("trace.progress", {"calls": int(total_calls * fr * fr), "functions_seen": int(len(called) * min(1, fr * 1.4)),
                                   "elapsed_s": round(TRACE_TOTAL_S * fr, 2), "stdout_tail": "\n".join(tails[:k])}, "trace", None, 2.2)
            if k in (3, 6):
                add("log", {"stream": "trace", "level": "info", "text": tails[k - 1]}, "trace", None, 0.1)
            if k == 4:
                add("error", {"where": "trace", "message": "could not record samples for tfidf_matrix: arguments larger than 1 MB were skipped",
                              "fatal": False}, "trace", None, 0.3)
        profile = sorted(({"id": f, "calls": final[f]["calls"], "cum_s": final[f]["trace"]["cum_s"], "share": final[f]["share"]} for f in called),
                         key=lambda x: -x["cum_s"])
        add("trace.done", {"total_s": TRACE_TOTAL_S, "exit_code": 0, "timed_out": False, "calls": total_calls, "profile": profile}, "trace",
            f"Recorded {total_calls:,} calls across {len(called)} functions", 1,
            apply=lambda: [reveal(f, "trace") for f in order if f in job.recs])
        step("trace", None, "Trace run", "done", f"{total_calls:,} calls recorded in {TRACE_TOTAL_S:.1f} s")
        stage("trace", "done", f"{total_calls:,} calls", 1.0, None, 1)

        # ---- rank
        stage("rank", "running", None, None, "Scoring hotspots by trace share, eligibility and expected benefit", 1)
        ranked = sorted(order, key=lambda f: (-final[f]["score"]["total"], f))
        ranking = [{"id": f, "rank": k, "score": final[f]["score"],
                    "status": final[f]["status"] if final[f]["status"] == "declined" else ("fixable" if final[f]["eligibility"] == "fixable" else final[f]["eligibility"].replace("verifiable", "pending")),
                    "reason": final[f]["reason"] if final[f]["status"] == "declined" else P.scan_reason[f]} for k, f in enumerate(ranked, 1)]
        add("rank.done", {"ranking": ranking}, "rank",
            f"Top hotspot: {final[ranked[0]]['name']} ({final[ranked[0]]['share'] * 100:.0f}% of runtime)", 2,
            apply=lambda: [reveal(f, "rank") for f in order])
        for fid in ranked:
            if final[fid]["status"] == "declined":
                step(f"fn:{fid}", fid, final[fid]["name"], "info", "ranker declined: " + final[fid]["reason"])
        step("rank", None, "Hotspot ranking", "done", f"{sum(1 for f in order if final[f]['eligibility'] != 'not_eligible')} candidates ranked")
        stage("rank", "done", f"top: {final[ranked[0]]['name']}", 1.0, None, 1)

        cand = [f for f in ranked if final[f]["eligibility"] != "not_eligible"]
        fixable = [f for f in cand if final[f]["eligibility"] == "fixable"]

        # ---- fix
        stage("fix", "running", None, 0.0, "Asking the LLM to rewrite fixable functions into PySub (the compiler checks every answer)", 1)
        for k, fid in enumerate(fixable, 1):
            f = final[fid]
            sid = f"fn:{fid}"
            first = f["diagnostics"][0]["msg"] if f["diagnostics"] else f["reason"]
            step(sid, fid, f["name"], "running", "typechecker rejected: " + (f["reason"] or first), 0.2)
            for w in f["rewrites"]:
                cap = (f"Typechecker rejected `{f['name']}`: {f['reason']} -> asking the LLM for a PySub rewrite" if w["attempt"] == 1
                       else f"Attempt {w['attempt']}: feeding the error back to the LLM")
                add("fix.attempt", {"id": fid, "attempt": w["attempt"], "source": "cache" if job.options.get("offline") else "api",
                                    "ok": w["ok"], "error": w["error"], "pysub": w["pysub"]}, "fix", cap, 6)
                step(sid, fid, f["name"], "running", f"attempt {w['attempt']}: " + ("PySub accepted" if w["ok"] else w["error"]), 0.05)
            ok = bool(f["rewrites"]) and f["rewrites"][-1]["ok"]
            add("fix.done", {"id": fid, "ok": ok, "reason": None if ok else f["reason"]}, "fix",
                (f"`{f['name']}` rewritten into valid PySub" if ok else f"`{f['name']}` stays out: {f['reason']}"), 0.5,
                apply=(lambda fid=fid: reveal(fid, "fix")))
            if not ok:
                step(sid, fid, f["name"], "failed", f["reason"], 0.05)
                add("scan.function", (lambda fid=fid: {"function": summarize(job.recs[fid])}), "fix", None, 0.05)
            stage("fix", "running", f"{k}/{len(fixable)}", k / len(fixable), None, 0.05)
        nfix = sum(1 for f in fixable if final[f]["rewrites"] and final[f]["rewrites"][-1]["ok"])
        stage("fix", "done", f"{nfix}/{len(fixable)}", 1.0, None, 1)

        # ---- compile
        todo = [f for f in cand if final[f]["sources"]["pysub"]]
        stage("compile", "running", None, 0.0, "Transpiling PySub to C++17 and building pybind11 modules", 1)
        for k, fid in enumerate(todo, 1):
            f = final[fid]
            b = f["build"]
            add("log", {"stream": "build", "level": "info", "text": b["log"].splitlines()[0]}, "compile", None, 0.1)
            add("compile.done", {"id": fid, "ok": True, "cached": b["cached"], "compile_s": b["compile_s"], "module": b["module"],
                                 "error": None, "diagnostics": []}, "compile",
                f"Built {f['name']}" + (" (cache hit)" if b["cached"] else f" in {b['compile_s']:.1f} s"), 0.3 if b["cached"] else 0.8 + b["compile_s"] / 6,
                apply=(lambda fid=fid: reveal(fid, "compile")))
            step(f"fn:{fid}", fid, f["name"], "running", "PySub ok -> C++ ok", 0.03)
            if k % 8 == 0:
                stage("compile", "running", f"{k}/{len(todo)}", k / len(todo), None, 0.05)
        stage("compile", "done", f"{len(todo)}/{len(todo)}", 1.0, None, 1)

        # ---- verify
        vtodo = [f for f in todo if final[f]["status"] != "declined"]
        stage("verify", "running", None, 0.0, "Replaying recorded calls through CPython and the compiled module", 1)
        for k, fid in enumerate(vtodo, 1):
            f = final[fid]
            r = f["replay"]
            add("verify.result", {"id": fid, "status": f["status"], "total": r["total"], "matched": r["matched"],
                                  "first_mismatch": r["first_mismatch"]}, "verify",
                (f"{f['name']}: {r['matched']}/{r['total']} replays match" if f["status"] != "failed"
                 else f"{f['name']}: replay mismatch, auto-rejected with a counterexample"), 0.7,
                apply=(lambda fid=fid: reveal(fid, "verify")))
            if f["status"] == "failed":
                step(f"fn:{fid}", fid, f["name"], "failed", f"replay mismatch on {r['first_mismatch']['args']}: {r['first_mismatch']['python']} vs {r['first_mismatch']['cpp']}", 0.05)
                add("scan.function", (lambda fid=fid: {"function": summarize(job.recs[fid])}), "verify", None, 0.03)
            else:
                step(f"fn:{fid}", fid, f["name"], "running", f"PySub ok -> C++ ok -> {r['matched']}/{r['total']} replays match", 0.03)
            if k % 8 == 0:
                stage("verify", "running", f"{k}/{len(vtodo)}", k / len(vtodo), None, 0.05)
        nv = sum(1 for f in vtodo if final[f]["status"] in ("verified", "guarded"))
        stage("verify", "done", f"{nv}/{len(vtodo)}", 1.0, None, 1)

        # ---- benchmark + splice
        btodo = [f for f in todo if final[f]["bench"]]
        stage("benchmark", "running", None, 0.0, "Timing Python vs C++ on the replayed arguments", 1)
        for k, fid in enumerate(btodo, 1):
            f = final[fid]
            b = f["bench"]
            probe = f["status"] == "declined"
            add("bench.result", {"id": fid, "py_ms": b["py_ms"], "cpp_ms": b["cpp_ms"], "speedup": b["speedup"], "calls_timed": b["calls_timed"],
                                 "probe": probe}, "benchmark",
                (f"{f['name']}: {b['speedup']:.1f}x" if not probe else f"{f['name']}: probe {b['speedup']:.2f}x, the ranker was right to decline"), 0.6,
                apply=(lambda fid=fid: reveal(fid, "bench")))
            if probe:
                step(f"fn:{fid}", fid, f["name"], "done", f"declined: probe measured {b['speedup']:.2f}x (boundary cost)", 0.03)
            else:
                step(f"fn:{fid}", fid, f["name"], "done", f"PySub ok -> C++ ok -> {f['replay']['matched']}/{f['replay']['total']} replays match -> {b['speedup']:.1f}x", 0.03)
            add("scan.function", (lambda fid=fid: {"function": summarize(job.recs[fid])}), "benchmark", None, 0.03)
            if k % 8 == 0:
                stage("benchmark", "running", f"{k}/{len(btodo)}", k / len(btodo), None, 0.05)
        stage("splice", "running", None, 0.0, "Splicing verified functions into the workspace copy", 1)
        acc = [f for f in ranked if final[f]["status"] in ("verified", "guarded")]
        by_file: Dict[str, List[str]] = {}
        for f in acc:
            by_file.setdefault(final[f]["file"], []).append(f)
        add("splice.ready", {"files": [{"path": p, "functions": fs} for p, fs in sorted(by_file.items())], "functions": len(acc)}, "splice",
            f"{len(acc)} functions spliced into {len(by_file)} files; originals are untouched", 2,
            apply=lambda: [reveal(f, "splice") for f in acc])
        stage("splice", "done", f"{len(acc)} functions", 1.0, None, 1)
        add("log", {"stream": "system", "level": "info", "text": f"running `{D.TRACE_CMD}` against the accelerated copy"}, "benchmark", None, 0.2)
        add("bench.e2e", {"cmd": D.TRACE_CMD, "before_s": D.E2E["before_s"], "after_s": D.E2E["after_s"],
                          "speedup": round(D.E2E["before_s"] / D.E2E["after_s"], 2), "output_match": True, "ok": True}, "benchmark",
            f"End to end: {D.E2E['before_s']:.1f} s -> {D.E2E['after_s']:.1f} s with identical output", 4)
        stage("benchmark", "done", f"{D.E2E['before_s'] / D.E2E['after_s']:.1f}x end to end", 1.0, None, 1)
        add(None, None, None, None, 0.1, apply=lambda: [reveal(f, "finish") for f in order])
        for f in acc:
            step(f"fn:{f}", f, final[f]["name"], "done", f"{final[f]['speedup']:.1f}x, verified" if final[f]["status"] == "verified" else f"{final[f]['speedup']:.1f}x, guarded", 0.02)
        if job.options.get("export"):          # export is user-triggered by default; this makes the stream cover every event type
            stage("export", "running", None, None, "Writing the accelerated project", 1)
            add(None, None, None, None, 1.0, apply=lambda: self.export(job.id, None, True))
        else:
            stage("export", "idle", None, None, None, 0.5)
        return S
