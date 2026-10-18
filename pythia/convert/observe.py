"""Run the original program once on the given stdin under sys.setprofile and record the runtime types of every
function's arguments and locals (and the module's globals). Used only to fill holes static inference left open.
Also returns the program's stdout/exception, so the converter can check its output against the original."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

from .types import join

BOOT = r'''
import sys, json, runpy
path, out = sys.argv[1], sys.argv[2]
obs, counts = {}, {}

def desc(v, d=0):
    if d > 4:
        return None
    t = type(v)
    if v is None: return "None"
    if t in (bool, int, float, str): return t.__name__
    if t in (list, set, frozenset):
        return ["list" if t is list else "set", [desc(x, d + 1) for x in list(v)[:20]]]
    if t is dict:
        items = list(v.items())[:20]
        return ["dict", [desc(k, d + 1) for k, _ in items], [desc(x, d + 1) for _, x in items]]
    if t is tuple:
        return ["tuple", [desc(x, d + 1) for x in v]] if len(v) <= 8 else None
    if getattr(t, "__module__", None) == "__main__":
        return ["cls", t.__qualname__]
    return None

def prof(frame, event, arg):
    if event != "return":
        return
    co = frame.f_code
    if co.co_filename != path:
        return
    q = co.co_qualname
    if q.endswith(">") and q != "<module>":
        return
    n = counts.get(q, 0)
    if n >= 300:
        return
    counts[q] = n + 1
    rec = obs.setdefault(q, {})
    try:
        for name, v in list(frame.f_locals.items()):
            t = desc(v)
            if t is not None:
                s = json.dumps(t)
                bucket = rec.setdefault(name, [])
                if s not in bucket and len(bucket) < 8:
                    bucket.append(s)
    except Exception:
        pass

sys.setprofile(prof)
try:
    runpy.run_path(path, run_name="__main__")
except BaseException as e:
    sys.setprofile(None)
    sys.stderr.write("\n%s: %s\n" % (type(e).__name__, e))
    status = type(e).__name__
else:
    status = None
sys.setprofile(None)
with open(out, "w", encoding="utf-8") as f:
    json.dump({"obs": obs, "exc": status}, f)
'''


def _conv(j):
    if isinstance(j, str):
        return j
    if j is None:
        return None
    k = j[0]
    if k in ("list", "set"):
        r = None
        for x in j[1]:
            r = join(r, _conv(x))
        return (k, r)
    if k == "dict":
        a = b = None
        for x in j[1]:
            a = join(a, _conv(x))
        for x in j[2]:
            b = join(b, _conv(x))
        return ("dict", a, b)
    if k == "tuple":
        return ("tuple", tuple(_conv(x) for x in j[1]))
    if k == "cls":
        return ("cls", j[1])
    return None


PLAIN = r'''
import sys, runpy
try:
    runpy.run_path(sys.argv[1], run_name="__main__")
except BaseException as e:
    sys.stdout.flush()
    sys.stderr.write("\n@@EXC %s\n" % type(e).__name__)
'''


def run_plain(source: str, stdin: str = "", timeout: float = 10.0) -> Optional[Dict]:
    """Run under CPython (same harness as observe, minus the profiler): {'stdout', 'exception'} or None."""
    tmp = Path(tempfile.mkdtemp(prefix="pythia-run-"))
    try:
        prog, boot = tmp / "prog.py", tmp / "boot.py"
        prog.write_text(source, encoding="utf-8")
        boot.write_text(PLAIN, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", str(boot), str(prog)], input=stdin or "", capture_output=True,
                               text=True, timeout=timeout, cwd=str(tmp), errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        except subprocess.TimeoutExpired:
            return None
        exc = [ln[6:].strip() for ln in r.stderr.splitlines() if ln.startswith("@@EXC ")]
        return {"stdout": r.stdout, "exception": exc[-1] if exc else None}
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def observe(source: str, stdin: str = "", timeout: float = 10.0) -> Optional[Dict]:
    """{'types': {('var', qual, name): type}, 'stdout': str, 'exception': str|None, 'timed_out': bool} or None."""
    tmp = Path(tempfile.mkdtemp(prefix="pythia-obs-"))
    try:
        prog, out, boot = tmp / "prog.py", tmp / "obs.json", tmp / "boot.py"
        prog.write_text(source, encoding="utf-8")
        boot.write_text(BOOT, encoding="utf-8")
        try:
            r = subprocess.run([sys.executable, "-I", str(boot), str(prog), str(out)], input=stdin or "",
                               capture_output=True, text=True, timeout=timeout, cwd=str(tmp), errors="replace",
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        except subprocess.TimeoutExpired:
            return {"types": {}, "stdout": None, "exception": None, "timed_out": True}
        if not out.exists():
            return None
        data = json.loads(out.read_text(encoding="utf-8"))
        types = {}
        for qual, names in data["obs"].items():
            for name, ts in names.items():
                t = None
                for s in ts:
                    t = join(t, _conv(json.loads(s)))
                if t is not None:
                    types[("var", qual, name)] = t
        return {"types": types, "stdout": r.stdout, "exception": data.get("exc"), "timed_out": False}
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
