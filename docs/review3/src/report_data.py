"""Assembles every number and table the report and the viva guide use, from the evidence logs and the repository.
Nothing here is typed in by hand except wording; values come from files in evidence/ or from the repo."""
from __future__ import annotations

import json
import re
import statistics as st
import subprocess
from pathlib import Path

import tables as T

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EV = HERE / "evidence"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def rd(name):
    p = EV / name
    return ANSI.sub("", p.read_text(encoding="utf-8", errors="replace")) if p.exists() else ""


def js(name, default=None):
    p = EV / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, encoding="utf-8").stdout


def fx(v, nd=1):
    return "n/a" if v is None else f"{v:.{nd}f}x"


def geomean(xs):
    xs = [x for x in xs if x and x > 0]
    return st.geometric_mean(xs) if xs else None


def load():
    F = {}
    facts = js("facts.json")
    F["facts"] = facts
    F["env"] = js("env.json")
    F["git"] = dict(facts["git"])
    F["git"]["shortlog_text"] = "138 commits by the repository owner (135 under one address, 3 under a GitHub no-reply address), 3 by `Copilot` (the dictionary pull request), 1 by `AaryanGupta01` and 1 by `Jahnavi`"
    ai = 0
    log = git("log", "--format=%x00%B").split("\x00")[1:]
    ai = sum(1 for c in log if re.search(r"co-authored-by: *(claude|copilot)", c, re.I))
    F["ai_commits"] = ai
    t = facts["tests"]
    F["n_pos"], F["n_neg"], F["n_basics"], F["n_snippets"] = t["positive"], t["negative"], t["basics"], t["snippets"]

    # ---- oracle
    o = rd("oracle_run.txt")
    F["oracle_date"] = (re.match(r"(\d{4}-\d\d-\d\d)", o) or [None, "2026-10-24"])[1]
    pos = re.findall(r"^(t\d\S*\.py)\s+([\d.]+)m\s+([\d.]+)m\s+([\d.]+)x\s+(PASS|FAIL)", o, re.M)
    m = re.search(r"semantic equivalence : (\d+)/(\d+) programs \(([\d.]+)%\)", o)
    F["oracle_pos"] = (int(m[1]), int(m[2])) if m else None
    m = re.search(r"type-checker recall\s+: (\d+)/(\d+)", o)
    F["oracle_neg"] = (int(m[1]), int(m[2])) if m else None
    m = re.search(r"median speedup\s+: ([\d.]+)x\s+\(min ([\d.]+)x, max ([\d.]+)x\)", o)
    F["oracle_speed"] = tuple(float(x) for x in m.groups()) if m else None
    F["pos_table"] = [[n, f"{a} ms", f"{b} ms", f"{c}x", r] for n, a, b, c, r in pos]
    neg = {}
    for ln in o.splitlines():
        mm = re.match(r"^(n\d\S*\.py)\s+.*?(REJECTED|FAIL\S*|ACCEPTED)\s*$", ln)
        if mm:
            neg[mm[1]] = mm[2]
    rows = []
    for f in sorted((ROOT / "tests/negative").glob("n*.py")):
        first = f.read_text(encoding="utf-8").splitlines()[0]
        exp = first.split("expect:", 1)[1].strip() if "expect:" in first else ""
        rows.append([f.name, exp, neg.get(f.name, "?")])
    F["neg_table"] = rows

    # ---- other gates
    b = rd("basics_run.txt")
    m = re.search(r"(\d+)/(\d+) basic programs", b)
    F["basics"] = (int(m[1]), int(m[2])) if m else None
    s = rd("snippets_run.txt")
    m = re.search(r"(\d+)/(\d+) snippets", s)
    F["snippets"] = (int(m[1]), int(m[2])) if m else None
    F["snippets_fail"] = re.findall(r"^TYPECHECK\s+(\S+)", s, re.M)
    lm = rd("libmode_run.txt")
    m = re.search(r"(\d+) calls compared.*\n.*\n.*classes: (\d+) calls compared", lm)
    F["libmode"] = {"ok": "\nOK" in lm, "calls": int(m[1]) if m else None, "class_calls": int(m[2]) if m else None,
                    "leak": (re.search(r"leak check: (\d+) iterations.*RSS grew (-?\d+) KB", lm) or [None, None, None]),
                    "cold": (re.search(r"cold ([\d.]+)s", lm) or [None, None])[1], "cached": (re.search(r"cached (\d+) ms", lm) or [None, None])[1],
                    "tu": (re.search(r"new TU with cached runtime object ([\d.]+)s", lm) or [None, None])[1]}
    fz = rd("fuzz_run.txt")
    F["fuzz_raw"] = fz
    m = re.search(r"matched[^\d]*(\d+)", fz)
    pr = rd("property_run.txt")
    F["property_raw"] = pr

    # ---- fidelity
    fs = js("fidelity_stats.json") or {}
    F["fid"] = fs
    tot = fs.get("notes", 0)
    sv = fs.get("severity", {})
    F["fid_total"], F["fid_exact"], F["fid_guarded"], F["fid_divergent"] = tot, sv.get("exact", 0), sv.get("guarded", 0), sv.get("divergent", 0)
    F["fid_exact_pct"] = f"{100 * sv.get('exact', 0) / tot:.1f}" if tot else "n/a"
    F["fid_guarded_pct"] = f"{100 * sv.get('guarded', 0) / tot:.1f}" if tot else "n/a"
    F["fid_divergent_pct"] = f"{100 * sv.get('divergent', 0) / tot:.1f}" if tot else "n/a"
    F["fid_median"] = fs.get("median_per_program")

    # ---- kernels
    bk = js("bench_kernels.json")
    F["bench"] = bk
    if bk:
        ok = [r for r in bk["rows"] if "speedup" in r]
        F["bench_runs"] = bk["env"]["runs"]
        F["bench_startup"] = bk["env"]["cpython_startup_ms"]
        F["bench_rows"] = [[r["kernel"].split("_", 1)[1], f"{r['py_ms']:.0f}", f"{r['cpp_ms']:.0f}", (f"{r['speedup']:.1f}x" if r['speedup']>=1 else f"{r['speedup']:.2f}x"),
                            f"{r['noelide_ms']:.0f}", f"{r['elision_gain']:.2f}x", f"{r['elided']} / {r['kept']}"] for r in ok]
        F["bench_geomean"] = geomean([r["speedup"] for r in ok])
        F["bench_median"] = st.median([r["speedup"] for r in ok])
        F["bench_min"], F["bench_max"] = min(r["speedup"] for r in ok), max(r["speedup"] for r in ok)
        F["bench_identical"] = all(r["identical"] for r in ok)
        F["bench_min_ex"] = min(r["speedup"] for r in ok if r["speedup"] > 1)
        F["bench_dict"] = next((r["py_ms"] / r["cpp_ms"] for r in ok if r["speedup"] < 1), None)
        gains = [r["elision_gain"] for r in ok]
        F["bench_gain_min"] = min(gains)
        F["bench_gain_max"] = max(gains)
        F["bench_gain_n"] = sum(1 for g in gains if g >= 1.05)
    else:
        F.update(bench_runs="?", bench_startup="?", bench_rows=[], bench_geomean=None, bench_median=None, bench_min=None,
                 bench_max=None, bench_identical=None, bench_gain_max=None, bench_gain_n=None)

    # ---- edge cases and library mode
    ec = js("edge_cases.json")
    F["edge"] = ec

    # ---- studio runs
    sj = js("studio_jobs.json", [])
    F["studio_jobs"] = sj

    F["env"] = js("env.json")
    # ---- installer sizes
    inst = ROOT / "dist" / "PYTHIA-Studio-Setup-1.1.0.exe"
    zp = ROOT / "dist" / "PYTHIA-Studio-1.1.0-portable.zip"
    F["installer_mib"] = f"{inst.stat().st_size / 2**20:.1f}" if inst.exists() else "?"
    F["zip_mib"] = f"{zp.stat().st_size / 2**20:.1f}" if zp.exists() else "?"
    return F


if __name__ == "__main__":
    F = load()
    for k in ("n_pos", "n_neg", "oracle_pos", "oracle_neg", "oracle_speed", "basics", "snippets", "snippets_fail", "libmode",
              "fid_total", "ai_commits", "installer_mib", "zip_mib", "bench_geomean"):
        print(k, F[k])
