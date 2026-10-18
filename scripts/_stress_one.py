#!/usr/bin/env python3
"""Worker for scripts/stress.py: one source file through the Playground path, no LLM.
Prints one JSON line {file, stage, detail, ...}.  stage:
  blocked   uses something with no compiled equivalent (random, files, libraries, ...)  [out of scope]
  convert   the in-house converter crashed
  typecheck PySub rejected the (converted) program                                        [a gap]
  build     the generated C++ failed to compile                                           [a BUG]
  differs   compiled output != CPython output                                             [a BUG]
  same      identical output                                                              [success]
  pyfail    the original itself fails under CPython (needs input/args)                    [skipped]
"""
import json
import re
import sys
import tempfile
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
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
from pythia.studio import explain  # noqa: E402
from pythia.studio.server import playground  # noqa: E402

syn = explain.syntax_error(src)
if syn:
    done("skip", "not valid Python 3")
blocks = explain.blockers(src)
if blocks:
    done("blocked", "; ".join(b["what"] for b in blocks)[:200])
try:
    from pythia.convert import to_pysub
    r = to_pysub(src, "", run=False, check=False)
    conv = r.source
    out["problems"] = r.problems[:3]
except Exception as e:
    done("convert", f"{type(e).__name__}: {e}", tb=traceback.format_exc()[-400:])
c = playground.compile_snippet(conv)
if not c["ok"]:
    d = c["diagnostics"][0]
    from pythia.studio.reasons import explain as why
    try:
        msg = why(c["diagnostics"], conv)[1] or d["msg"]
    except Exception:
        msg = d["msg"]
    done("typecheck", f"line {d['line']}: {d['msg']}", reason=str(msg)[:200], line=d["line"],
         srcline=(conv.splitlines()[d["line"] - 1].strip()[:120] if 0 < d["line"] <= len(conv.splitlines()) else ""))
try:
    run = playground.run_snippet(conv, Path(tempfile.gettempdir()) / "pythia-stress-cache", "", reference=src)
except Exception as e:
    done("build", f"{type(e).__name__}: {e}")
if not run.get("ok"):
    err = run.get("error") or ""
    done("build" if "internal error" in err else "convert", err[:300])
py, cp = run["python"], run["cpp"]
if py.get("exception") and py["exception"] != "TimeoutError" and (cp or {}).get("exception") == py["exception"] \
        and py["stdout"] == cp["stdout"]:
    done("same", f"both raise {py['exception']}", py_ms=py["time_ms"], cpp_ms=cp["time_ms"])
if run["same"]:
    done("same", "", py_ms=py["time_ms"], cpp_ms=cp["time_ms"])
if py.get("timed_out"):
    done("skip", "original timed out")
done("differs", (run.get("explain") or "")[:200], py_out=py["stdout"][:150], cpp_out=cp["stdout"][:150],
     py_exc=py.get("exception"), cpp_exc=cp.get("exception"))
