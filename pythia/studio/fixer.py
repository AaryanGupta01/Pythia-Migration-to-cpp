"""LLM fixer: rewrite a FIXABLE function into valid PySub, feeding typechecker errors back (<= 3 attempts).

The LLM suggests, the compiler proves: a candidate is accepted only if the real parser+typechecker accept the
extracted module. Replay (B2) is the second gate. The LLM never writes C++.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .llm import LLMError, cache_key, write_cache_entry   # noqa: F401  (re-exported helpers)
from .models import FunctionRecord, Workspace
from .pysub_rules import rules_text
from .scan import extract_pysub

MAX_ATTEMPTS = 3
_FENCE = re.compile(r"```[ \t]*(?:python|py|pysub)?[ \t]*\n(.*?)```", re.S | re.I)

SYSTEM_TMPL = """You are the rewrite step of PYTHIA, a Python-to-C++ compiler for a typed Python subset called PySub.
Rewrite ONE Python function into valid PySub with exactly the same observable behaviour: same return values,
same exceptions, same mutation of list/dict arguments, same integer and float semantics. Do not optimise or
restructure beyond what PySub requires. You never write C++.

{rules}

OUTPUT FORMAT
  * Reply with ONE fenced ```python block and nothing that needs parsing outside it.
  * The block holds the rewritten target function followed by any helper functions it needs
    (helpers must be valid PySub too). No imports, no module-level statements, no classes unless required.
  * Keep the target's name and its parameter names and order. Annotate every parameter and the return type.
  * Write module-level constants as literals inside the function; functions cannot see module globals.
"""


@dataclass
class FixResult:
    ok: bool
    pysub: Optional[str]
    attempts: List[dict] = field(default_factory=list)
    reason: Optional[str] = None
    disabled: bool = False

    def to_dict(self) -> dict:
        return {"ok": self.ok, "pysub": self.pysub, "attempts": self.attempts, "reason": self.reason}


def extract_candidate(reply: str) -> Optional[str]:
    """The last fenced block that defines a function (models sometimes show scratch work first)."""
    blocks = [b.strip("\n") for b in _FENCE.findall(reply)]
    good = [b for b in blocks if re.search(r"^\s*def\s+\w+", b, re.M)]
    return (good or blocks or [None])[-1]


def _fmt_diags(diags: List[dict], src: str, limit: int = 10) -> str:
    lines = src.split("\n")
    out = []
    for d in diags[:limit]:
        where = f" (in `{d['fn']}`)" if d.get("fn") else ""
        out.append(f"  line {d['line']}:{d['col']}: {d['kind']}: {d['msg']}{where}")
        if 1 <= d["line"] <= len(lines) and lines[d["line"] - 1].strip():
            out.append(f"      {lines[d['line'] - 1].strip()}")
    if len(diags) > limit:
        out.append(f"  ... and {len(diags) - limit} more")
    return "\n".join(out)


def _numbered(src: str) -> str:
    return "\n".join(f"{i + 1:3}| {l}" for i, l in enumerate(src.split("\n")))


def _check_signature(rec: FunctionRecord, cand: str) -> Optional[str]:
    try:
        tree = ast.parse(cand)
    except SyntaxError:
        return None                                   # let the PySub parser report it with its own wording
    fns = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    if rec.name not in fns:
        return f"the block must define a function named `{rec.name}`"
    try:
        orig = ast.parse(rec.sources.get("original") or "").body[0]
        want = [a.arg for a in orig.args.args]
    except Exception:
        return None
    got = [a.arg for a in fns[rec.name].args.args]
    if got != want:
        return f"`{rec.name}` must keep its parameters ({', '.join(want)}); you wrote ({', '.join(got)})"
    extra = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.ClassDef))]
    if extra:
        return "the block must contain only function definitions (no imports or module-level statements)"
    return None


class Fixer:
    def __init__(self, llm, offline: bool = False, cache_dir: Optional[Path] = None):
        self.llm, self.offline = llm, offline
        self.cache_dir = Path(cache_dir) if cache_dir else None

    @property
    def enabled(self) -> bool:
        return self.llm is not None

    # -------------------------------------------------------------- prompt
    def _first_prompt(self, rec: FunctionRecord, ws: Workspace, base_src: str, ext) -> str:
        parts = ["Rewrite this function into PySub.", "",
                 f"Original Python function `{rec.name}` from {rec.file}:", "```python", base_src, "```", ""]
        info = rec.private.get("modinfo")
        if ext.helpers and info is not None:
            parts += ["It calls these same-module helpers (they must be valid PySub as well; include a rewritten "
                      "copy in your block only if they need changes):"]
            for h in ext.helpers:
                parts += ["```python", info.func_text(h), "```"]
            parts.append("")
        if ext.uses and info is not None:
            parts.append("Module-level constants (already inlined below; write them as literals): "
                         + ", ".join(f"{n} = {info.consts[n]!r}" for n in ext.uses if n in info.consts))
            parts.append("")
        t = rec.trace or {}
        if t.get("arg_types") is not None:
            parts.append(f"Observed at runtime: argument types {t.get('arg_types')}, return type {t.get('ret_type')}"
                         + (f", typical sizes: args ~{t.get('avg_arg_elems')} elements, result ~{t.get('avg_ret_elems')}"
                            if t.get("avg_arg_elems") is not None else "") + ".")
            parts.append("")
        parts += ["The PySub compiler currently sees this module (line numbers shown) and reports:",
                  "```", _numbered(ext.source.rstrip("\n")), "```", "Typechecker output:",
                  _fmt_diags(ext.diagnostics, ext.source) or "  (no diagnostics)", "",
                  "Reply with the single fenced python block."]
        return "\n".join(parts)

    # -------------------------------------------------------------- main loop
    def fix(self, rec: FunctionRecord, ws: Workspace, emit=None) -> FixResult:
        emit = emit or (lambda *a, **k: None)
        if self.llm is None:
            return FixResult(False, None, [], "LLM fixer disabled — set ANTHROPIC_API_KEY", disabled=True)
        base_src = rec.sources.get("annotated") or rec.sources.get("original") or ""
        ext0 = extract_pysub(rec, ws, annotated_src=rec.sources.get("annotated"))
        if ext0.ok:                                           # nothing left to fix (e.g. annotation was enough)
            return FixResult(True, base_src, [], None)
        system = SYSTEM_TMPL.format(rules=rules_text())
        messages: List[Dict[str, str]] = [{"role": "user", "content": self._first_prompt(rec, ws, base_src, ext0)}]
        step = f"fix:{rec.id}"
        attempts: List[dict] = []
        last_err = None
        for n in range(1, MAX_ATTEMPTS + 1):
            emit("agent.step", {"step_id": step, "fn_id": rec.id, "state": "running",
                                "title": f"Rewriting `{rec.name}` into PySub (attempt {n}/{MAX_ATTEMPTS})",
                                "detail": last_err}, stage="fix")
            src_kind = getattr(self.llm, "source", "api")
            cand, err, reply = "", None, None
            try:
                reply = self.llm.complete(system, messages, function_source=base_src, attempt=n)
            except LLMError as e:
                err = str(e)
            if reply is not None:
                cand = extract_candidate(reply) or ""
                if not cand:
                    err = "reply contained no fenced ```python code block"
                else:
                    err = _check_signature(rec, cand)
                    if err is None:
                        ext = extract_pysub(rec, ws, override_src=cand)
                        if not ext.ok:
                            err = _fmt_diags(ext.diagnostics, ext.source, 8).strip()
            ok = err is None
            attempts.append({"attempt": n, "source": src_kind, "pysub": cand, "error": err, "ok": ok})
            emit("fix.attempt", {"id": rec.id, "attempt": n, "source": src_kind, "ok": ok, "error": err,
                                 "pysub": cand}, stage="fix",
                 caption=(f"LLM rewrite of `{rec.name}` passed the PySub typechecker" if ok else
                          f"Typechecker rejected the rewrite: {(err or '').splitlines()[0][:110]}"
                          + (" -> asking the LLM again" if n < MAX_ATTEMPTS and reply is not None else "")))
            if ok:
                break
            last_err = err
            if reply is None:                                  # API down / cache miss: another turn cannot help
                break
            messages += [{"role": "assistant", "content": reply},
                         {"role": "user", "content": "The PySub typechecker rejected that attempt:\n" + err +
                          "\n\nFix every error and reply with the complete corrected fenced python block."}]
        rec.rewrites = attempts
        if attempts[-1]["ok"]:
            res = FixResult(True, attempts[-1]["pysub"], attempts, None)
            rec.sources["pysub"] = res.pysub
            rec.line_map_ok = False
            emit("agent.step", {"step_id": step, "fn_id": rec.id, "state": "done",
                                "title": f"`{rec.name}` rewritten into valid PySub",
                                "detail": f"accepted on attempt {len(attempts)}"}, stage="fix")
        else:
            first = (attempts[-1]["error"] or "").splitlines()[0]
            res = FixResult(False, None, attempts,
                            f"LLM could not produce valid PySub after {len(attempts)} attempt(s); last error: {first}")
            emit("agent.step", {"step_id": step, "fn_id": rec.id, "state": "failed",
                                "title": f"`{rec.name}`: no valid PySub rewrite", "detail": res.reason}, stage="fix")
        emit("fix.done", {"id": rec.id, "ok": res.ok, "reason": res.reason}, stage="fix")
        return res
