"""Whole-file conversion of ONE source file, no LLM: the unit of work of files mode and of scripts/stress.py.

    python -m pythia.studio.filework <file> [<root>]      prints one JSON line

stage / status of the result:
  skip       unreadable, not Python 3, or too long                                     (status "skipped")
  blocked    uses something with no compiled equivalent (random, files, numpy, ...)    (status "not_eligible")
  typecheck  the converter could not produce valid PySub                               (status "not_eligible")
  build      generated C++ failed to compile                                           (status "failed"  - a bug)
  differs    compiled output != CPython output                                         (status "failed"  - a bug)
  limit      same logic, but a documented PySub limit shows (64-bit ints, ASCII ...)   (status "failed")
  same       the program's own run printed identical output                            (status "verified")
  driven     entry-less code verified on generated inputs                              (status "verified")
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

MAX_LINES = 600


def convert_file(path: Path, root: Optional[Path] = None) -> Dict[str, Any]:
    os.environ["GROQ_API_KEY"] = ""              # whole-file conversion never involves a model
    os.environ["ANTHROPIC_API_KEY"] = ""
    from .. import driver
    from . import converter, explain
    from .server import playground
    rel = path.relative_to(root).as_posix() if root else path.name
    out: Dict[str, Any] = {"file": rel}

    def done(stage: str, status: str, detail: str = "", **kw) -> Dict[str, Any]:
        out.update(stage=stage, status=status, detail=str(detail)[:400], **kw)
        return out
    try:
        src = path.read_text(encoding="utf-8")
    except Exception as e:
        return done("skip", "skipped", f"unreadable: {e}")
    if src.count("\n") > MAX_LINES:
        return done("skip", "skipped", f"longer than {MAX_LINES} lines")
    src = driver.normalize(src)
    out["original"] = src
    if explain.syntax_error(src):
        return done("skip", "skipped", "not valid Python 3")
    blocks = explain.blockers(src)
    if blocks:
        return done("blocked", "not_eligible", "; ".join(b["what"] for b in blocks),
                    reason="; ".join(f"{b['what']}: {b['why']}. {b['fix'].capitalize()}." for b in blocks))
    cache = Path(tempfile.gettempdir()) / "pythia-file-cache"

    def verify(code, sin, orig):
        return playground.run_snippet(code, cache, sin, orig)
    try:
        res = converter.convert(src, {}, playground.compile_snippet, "", verify)
    except Exception as e:
        return done("convert", "failed", f"{type(e).__name__}: {e}", tb=traceback.format_exc()[-500:])
    if res.get("ok"):
        code = res["source"]
        comp = playground.compile_snippet(code)
        v = res.get("verified")
        extra = dict(source=code, cpp=comp.get("cpp") if comp.get("ok") else None, fidelity=comp.get("fidelity") or [],
                     cpp_line_map=comp.get("cpp_line_map") or {}, changes=res.get("changes") or [],
                     timing=res.get("timing"))
        if v:
            return done("driven", "verified", v["note"], calls=v["calls"], functions=v["functions"],
                        skipped=v.get("skipped"), driver=v.get("driver"), **extra)
        return done("same", "verified", "already PySub" if res.get("already") else "identical output", **extra)
    err = (res.get("error") or "")
    err = err.replace("The in-house converter could not finish this program: ", "")
    err = err.replace("the PySub type checker still reports ", "").split(". The AI converter")[0]
    if res.get("limit"):
        return done("limit", "failed", err, reason=err)
    if "failed to compile (internal error)" in err:
        return done("build", "failed", err, reason=err)
    if "different results" in err or "prints something different" in err or "prints different" in err:
        return done("differs", "failed", err, reason=err)
    return done("typecheck", "not_eligible", err, reason=err, problems=res.get("problems") or [],
                skipped=res.get("skipped"))


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    path = Path(argv[0])
    root = Path(argv[1]) if len(argv) > 1 else None
    try:
        r = convert_file(path, root)
    except Exception as e:                      # never leave the parent without an answer
        r = {"file": path.name, "stage": "convert", "status": "failed", "detail": f"{type(e).__name__}: {e}"}
    sys.stdout.write("\n@@RESULT " + json.dumps(r) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
