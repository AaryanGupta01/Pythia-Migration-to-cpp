#!/usr/bin/env python3
"""Hunt 3: 'management-system' style programs (library, inventory, bank, student, ...). GitHub search -> download single files -> run each through
the REAL in-house converter + C++ build + CPython comparison (same path as scripts/check_basics.py) on a few canned stdin scripts.
Output: evidence/hunt3.json.  Run:  PYTHONUTF8=1 python hunt3.py   (bundled interpreter)"""
import json
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
os.environ["GROQ_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""
from pythia.studio import converter  # noqa: E402
from pythia.studio.server import playground  # noqa: E402

DEST = Path(r"C:\Users\visha\AppData\Local\pythia-dev\demo-repos4")
DEST.mkdir(exist_ok=True)
QUERIES = ["library management system", "library management", "book management system", "inventory management system", "bank management system",
           "student management system", "hospital management", "hotel management", "employee management system", "parking management", "contact book",
           "grade calculator", "todo list cli", "vending machine", "atm simulator", "restaurant billing", "gym management", "quiz game", "tic tac toe"]
BAD = ("tkinter", "pygame", "flask", "django", "numpy", "pandas", "matplotlib", "requests", "sqlite3", "mysql", "PyQt", "kivy", "turtle", "curses", "pickle", "random", "datetime", "time.sleep", "os.system", "csv", "json", "open(")
STDINS = ["", "1\n", "1\n2\n3\n4\n5\n6\n", "1\nA\nB\nC\n2\n3\n1\n2\n4\n", "5\n3\n2\n1\n"]
cache = Path(tempfile.gettempdir()) / "pythia-hunt3-cache"


def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pythia-hunt", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def raw(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "pythia-hunt"}), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


repos = {}
for q in QUERIES:
    try:
        d = api("https://api.github.com/search/repositories?q=" + urllib.parse.quote(f"{q} language:python stars:0..80 size:2..800 fork:false") + "&sort=updated&per_page=15")
    except Exception as e:  # noqa: BLE001
        print("search failed", q, e, flush=True)
        time.sleep(10)
        continue
    for it in d.get("items", []):
        repos.setdefault(it["full_name"], {"stars": it["stargazers_count"], "lic": (it.get("license") or {}).get("spdx_id"), "branch": it["default_branch"]})
    time.sleep(6.5)
print(len(repos), "repos", flush=True)

import subprocess
cands = []
def grab(item):
    name, m = item
    d = DEST / name.replace("/", "__")
    if not d.exists():
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{name}", str(d)], capture_output=True, text=True, timeout=180)
        if r.returncode:
            return []
    out = []
    for p in sorted(d.rglob("*.py"))[:80]:
        if ".git" in p.parts or "test" in p.name.lower():
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not (1500 < len(src) < 40000) or any(b in src for b in BAD) or "input(" not in src or len(src.splitlines()) < 60:
            continue
        out.append({"repo": name, **m, "path": p.relative_to(d).as_posix(), "src": src, "lines": len(src.splitlines())})
    return out[:6]
with ThreadPoolExecutor(6) as ex:
    for r in ex.map(grab, list(repos.items())):
        cands += r
print(len(cands), "candidate files", flush=True)


def trial(c):
    src = c["src"]
    verify = lambda code, sin, orig: playground.run_snippet(code, cache, sin, orig)  # noqa: E731
    out = {"repo": c["repo"], "path": c["path"], "lines": c["lines"], "stars": c["stars"], "lic": c["lic"], "status": "?"}
    for stdin in STDINS:
        try:
            res = converter.convert(src, {}, playground.compile_snippet, stdin, verify)
        except Exception as e:  # noqa: BLE001
            out["status"] = "CRASH " + type(e).__name__
            return out
        if not res.get("ok"):
            out["status"] = "NOCONV"
            out["why"] = (res.get("error") or "")[:160]
            return out
        run = playground.run_snippet(res["source"], cache, stdin, reference=src)
        if run.get("ok") and not run.get("python_only") and run.get("same"):
            out.update(status="OK", stdin=stdin, py_ms=run["python"]["time_ms"], cpp_ms=run["cpp"]["time_ms"], out_lines=len(run["python"]["stdout"].splitlines()))
            if out["out_lines"] >= 6:
                return out
        elif run.get("ok") and not run.get("same") and not run.get("python_only"):
            out.update(status="DIFFERS", stdin=stdin)
            return out
    return out


results = []
with ThreadPoolExecutor(4) as ex:
    for r in ex.map(trial, cands):
        results.append(r)
        if r["status"] == "OK":
            print("OK", r["repo"], r["path"], r["lines"], "lines", r.get("out_lines"), "out lines", r.get("py_ms"), "ms ->", r.get("cpp_ms"), "ms", flush=True)
        elif r["status"].startswith("DIFF") or r["status"].startswith("CRASH"):
            print(r["status"], r["repo"], r["path"], flush=True)
(HERE / "evidence" / "hunt3.json").write_text(json.dumps([{k: v for k, v in c.items() if k != "src"} for c in cands], indent=1), encoding="utf-8")
(HERE / "evidence" / "hunt3_results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
print("done", sum(r["status"] == "OK" for r in results), "ok of", len(results), flush=True)
