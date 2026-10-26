#!/usr/bin/env python3
"""Hunt 4: compute-heavy pure-Python repos (language speed comparisons, benchmark-game kernels, Advent of Code, Euler, prime sieves).
GitHub repo search -> shallow clone -> REAL scanner (scripts/measure_coverage.py) -> count eligible functions that loop -> time runnable scripts.
Output: evidence/hunt4.json, ranked.   Run: PYTHONUTF8=1 <bundled python> hunt4.py"""
import ast
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PY = r"C:\Users\visha\AppData\Local\pythia-dev\python\python.exe"
DEST = Path(r"C:\Users\visha\AppData\Local\pythia-dev\demo-repos5")
DEST.mkdir(exist_ok=True)
QUERIES = ["python vs c++ performance", "python vs rust speed", "python vs c speed comparison", "programming language speed comparison",
           "language benchmark fibonacci", "fannkuch", "spectral norm", "nbody simulation python", "benchmarks game", "python performance benchmark",
           "cython vs python", "pypy benchmark", "advent of code 2023 python", "advent of code 2022 python", "advent of code 2024 python",
           "project euler python", "sorting algorithms comparison", "prime sieve", "primes drag race", "monte carlo pi", "mandelbrot benchmark",
           "matrix multiplication benchmark", "algorithm performance comparison", "python speed test", "collatz benchmark"]
SKIP = ("thealgorithms", "keon", "donnemartin", "prakhar1989", "joeyajames", "dsalgo")
BADIMP = ("numpy", "numba", "pygame", "tkinter", "matplotlib", "pandas", "scipy", "torch", "cython", "jax", "taichi")


def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pythia-hunt", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


repos = {}
for q in QUERIES:
    try:
        d = api("https://api.github.com/search/repositories?q=" + urllib.parse.quote(f"{q} language:python stars:0..200 size:5..6000 fork:false") + "&per_page=20")
        for it in d.get("items", []):
            if not any(s in it["full_name"].lower() for s in SKIP):
                repos.setdefault(it["full_name"], {"stars": it["stargazers_count"], "lic": (it.get("license") or {}).get("spdx_id"), "q": q})
    except Exception as e:  # noqa: BLE001
        print("search failed", q, e, flush=True)
    time.sleep(6.5)
print(len(repos), "repos", flush=True)


def loops(src):
    out = set()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and any(isinstance(x, (ast.For, ast.While)) for x in ast.walk(n)):
            out.add(n.name)
    return out


def examine(item):
    name, m = item
    d = DEST / name.replace("/", "__")
    if not d.exists():
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{name}", str(d)], capture_output=True, text=True, timeout=240)
        if r.returncode:
            return None
    pys = [p for p in d.rglob("*.py") if not any(x.startswith(".") or x in ("venv", "site-packages", "node_modules") for x in p.parts)]
    if not (1 <= len(pys) <= 150):
        return None
    loopfn = {}
    for p in pys:
        s = p.read_text(encoding="utf-8", errors="replace")
        if any(f"import {b}" in s or f"from {b}" in s for b in BADIMP):
            continue
        for f in loops(s):
            loopfn[f"{p.relative_to(d).as_posix()}::{f}"] = True
    if len(loopfn) < 3:
        return None
    j = d.parent / (d.name + ".cov.json")
    try:
        subprocess.run([PY, str(ROOT / "scripts" / "measure_coverage.py"), str(d), "--json", str(j)], capture_output=True, text=True, timeout=240,
                       env={**__import__("os").environ, "PYTHONUTF8": "1"})
        cov = json.loads(j.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None
    good = [c["id"] for c in cov if c["eligibility"] in ("verifiable", "fixable") and c["id"] in loopfn]
    if len(good) < 3:
        return None
    runs = []
    for p in pys:
        s = p.read_text(encoding="utf-8", errors="replace")
        if any(f"import {b}" in s or f"from {b}" in s for b in BADIMP) or "input(" in s:
            continue
        if "__main__" not in s and not any(isinstance(n, ast.Expr) and isinstance(getattr(n, "value", None), ast.Call)
                                           for n in (ast.parse(s).body if s.strip() else [])):
            continue
        t0 = time.time()
        try:
            r = subprocess.run([PY, "-X", "utf8", p.name], cwd=p.parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
                               timeout=45, stdin=subprocess.DEVNULL)
            sec = time.time() - t0
            if r.returncode == 0 and (r.stdout or "").strip() and sec >= 1.5:
                r2 = subprocess.run([PY, "-X", "utf8", p.name], cwd=p.parent, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                    timeout=60, stdin=subprocess.DEVNULL)
                runs.append({"script": p.relative_to(d).as_posix(), "sec": round(sec, 1), "det": r2.stdout == r.stdout})
        except Exception:  # noqa: BLE001
            pass
    return {"repo": name, **m, "dir": str(d), "py_files": len(pys), "eligible_loop_funcs": len(good), "examples": good[:8], "runs": runs}


rows = []
with ThreadPoolExecutor(5) as ex:
    for r in ex.map(examine, list(repos.items())):
        if r:
            rows.append(r)
            print(f"{r['repo']:45s} stars={r['stars']:3d} lic={r['lic']} eligible_loop_funcs={r['eligible_loop_funcs']:3d} runnable={[(x['script'], x['sec'], 'det' if x['det'] else 'NONDET') for x in r['runs']][:3]}", flush=True)
rows.sort(key=lambda r: (bool(r["runs"]), r["eligible_loop_funcs"]), reverse=True)
(HERE / "evidence" / "hunt4.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
print("done", len(rows), flush=True)
