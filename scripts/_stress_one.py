#!/usr/bin/env python3
"""Worker for scripts/stress.py: one source file through the app's conversion path, no LLM.
Prints one JSON line {file, stage, detail, ...}.  stage:
  skip      unreadable / not Python 3 / too long
  blocked   uses something with no compiled equivalent (random, files, libraries, ...)  [out of scope]
  typecheck the converter could not produce valid PySub                                    [a gap]
  build     the generated C++ failed to compile                                            [a BUG]
  differs   compiled output != CPython output                                              [a BUG]
  limit     identical logic, but a documented PySub limit (64-bit ints, ASCII ...) shows
  same      identical output on the program's own run                                      [success]
  driven    entry-less code verified on generated inputs                                   [success]
"""
import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, ROOT.as_posix())
os.environ["GROQ_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
f, base = Path(sys.argv[1]), Path(sys.argv[2])
rel = f.relative_to(base).as_posix()
out = {"file": rel}


def done(stage, detail="", **kw):
    out.update(stage=stage, detail=str(detail)[:300], **kw)
    print(json.dumps(out), flush=True)
    sys.exit(0)


try:
    src = f.read_text(encoding="utf-8")
except Exception as e:
    done("skip", f"unreadable: {e}")
if src.count("\n") > 450:
    done("skip", "longer than 450 lines")
from pythia import driver  # noqa: E402
from pythia.studio import converter, explain  # noqa: E402
from pythia.studio.server import playground  # noqa: E402

src = driver.normalize(src)
if explain.syntax_error(src):
    done("skip", "not valid Python 3")
blocks = explain.blockers(src)
if blocks:
    done("blocked", "; ".join(b["what"] for b in blocks)[:200])
cache = Path(tempfile.gettempdir()) / "pythia-stress-cache"
verify = lambda code, sin, orig: playground.run_snippet(code, cache, sin, orig)  # noqa: E731
try:
    res = converter.convert(src, {}, playground.compile_snippet, "", verify)
except Exception as e:
    done("convert", f"{type(e).__name__}: {e}", tb=traceback.format_exc()[-400:])
if res.get("ok"):
    v = res.get("verified")
    if v:
        done("driven", v["note"], calls=v["calls"], functions=v["functions"], skipped=v.get("skipped"))
    done("same", "already PySub" if res.get("already") else "")
err = res.get("error") or ""
if res.get("limit"):
    done("limit", err)
if "failed to compile (internal error)" in err:
    done("build", err)
if "prints different" in err or "different results" in err or "prints something different" in err:
    done("differs", err)
err = err.replace("The in-house converter could not finish this program: ", "")
err = err.replace("the PySub type checker still reports ", "")
done("typecheck", err.split(". The AI converter")[0], reason=err.split(". The AI converter")[0])
