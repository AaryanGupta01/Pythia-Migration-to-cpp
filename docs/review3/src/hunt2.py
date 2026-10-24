#!/usr/bin/env python3
"""Second demo hunt: GitHub search -> shallow clone -> static screen (no numpy/pygame/input, module-level functions with loops)
-> time each runnable script. Output: evidence/hunt2.json. Run with the bundled Python (needs only the stdlib)."""
import ast
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEST = Path(r"C:\Users\visha\AppData\Local\pythia-dev\demo-repos3")
DEST.mkdir(exist_ok=True)
PY = r"C:\Users\visha\AppData\Local\pythia-dev\python\python.exe"
TOPICS = ["nbody", "mandelbrot", "sudoku-solver", "n-queens", "game-of-life", "knapsack", "primes", "collatz", "levenshtein", "sorting-algorithms",
          "dynamic-programming", "traveling-salesman", "maze-solver", "monte-carlo", "simulation", "ray-tracer", "cellular-automata", "brainfuck-interpreter",
          "number-theory", "algorithms", "matrix-multiplication", "knights-tour", "pathfinding", "huffman-coding", "lcs", "fibonacci", "cryptography", "sha256", "bitboard"]
BAD = ("numpy", "pygame", "tkinter", "matplotlib", "PIL", "cv2", "torch", "tensorflow", "pandas", "scipy", "flask", "django", "requests", "kivy", "turtle", "curses", "sdl2")


def api(url):
    req = urllib.request.Request(url, headers={"User-Agent": "pythia-hunt", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


seen = {}
for d_ in DEST.iterdir():
    seen[d_.name.replace("__", "/", 1)] = {"stars": -1, "size": 0, "license": None, "topic": "cached"}
for t in ([] if seen else TOPICS):
    q = f"topic:{t} language:python stars:0..60 size:30..900 fork:false"
    try:
        d = api("https://api.github.com/search/repositories?q=" + urllib.parse.quote(q) + "&sort=updated&per_page=12")
    except Exception as e:  # noqa: BLE001
        print("search failed", t, e, flush=True)
        time.sleep(8)
        continue
    for it in d.get("items", []):
        seen.setdefault(it["full_name"], {"stars": it["stargazers_count"], "size": it["size"], "license": (it.get("license") or {}).get("spdx_id"), "topic": t})
    time.sleep(6.5)
print(len(seen), "repos found", flush=True)

rows = []
for name, meta in seen.items():
    d = DEST / name.replace("/", "__")
    if not d.exists():
        r = subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{name}", str(d)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            continue
    files = [p for p in d.rglob("*.py") if ".git" not in p.parts and "venv" not in p.parts and "site-packages" not in p.parts]
    if not (1 <= len(files) <= 40):
        continue
    txt = {p: p.read_text(encoding="utf-8", errors="replace") for p in files}
    if any(b in t for t in txt.values() for b in BAD) or any("input(" in t for t in txt.values()):
        continue
    nfun = nloop = ncls = 0
    for p, t in txt.items():
        try:
            tree = ast.parse(t)
        except SyntaxError:
            nfun = -999
            break
        for n in tree.body:
            if isinstance(n, ast.FunctionDef):
                nfun += 1
                nloop += any(isinstance(x, (ast.For, ast.While)) for x in ast.walk(n))
            elif isinstance(n, ast.ClassDef):
                ncls += 1
    if nfun < 4 or nloop < 3:
        continue
    lines = sum(t.count("\n") for t in txt.values())
    rows.append({"repo": name, **meta, "files": len(files), "lines": lines, "funcs": nfun, "loop_funcs": nloop, "classes": ncls, "dir": str(d)})
    print(f"{name:45s} stars={meta['stars']:3d} files={len(files):2d} lines={lines:5d} funcs={nfun:3d} loopfuncs={nloop:3d} cls={ncls} lic={meta['license']}", flush=True)

# time runnable scripts
for r in rows:
    d = Path(r["dir"])
    runs = []
    for p in sorted(d.rglob("*.py")):
        if ".git" in p.parts:
            continue
        t = p.read_text(encoding="utf-8", errors="replace")
        if "__main__" not in t or "argparse" in t or "sys.argv" in t:
            continue
        t0 = time.time()
        try:
            res = subprocess.run([PY, "-X", "utf8", p.name], cwd=p.parent, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=25, stdin=subprocess.DEVNULL)
            ok = res.returncode == 0 and (res.stdout or "").strip() != ""
            runs.append({"script": str(p.relative_to(d)), "sec": round(time.time() - t0, 1), "ok": ok, "out": (res.stdout or "")[:60]})
        except subprocess.TimeoutExpired:
            runs.append({"script": str(p.relative_to(d)), "sec": 25, "ok": False, "out": "TIMEOUT"})
    r["runs"] = [x for x in runs if x["ok"] and x["sec"] >= 1.0]
    if r["runs"]:
        print("RUNNABLE", r["repo"], r["runs"][:3], flush=True)
(HERE / "evidence" / "hunt2.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
print("done", len(rows))
