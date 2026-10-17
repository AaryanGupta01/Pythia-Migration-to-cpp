"""Export: accelerated project (folder or zip) + PYTHIA_REPORT.md + build_accel.sh."""
from __future__ import annotations

import dataclasses
import difflib
import json
import math
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import splice
from .models import FunctionRecord, Workspace

IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".pytest_cache", ".mypy_cache",
                                ".venv", "venv", "node_modules", ".DS_Store")

BUILD_SH = r'''#!/usr/bin/env bash
# Rebuilds the compiled PYTHIA modules for THIS machine from the saved C++ sources.
# Needs: a C++17 compiler (c++), python3 and pybind11 (pip install pybind11).
set -euo pipefail
cd "$(dirname "$0")/_pythia_accel"
EXT="$(python3 -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')"
INC="$(python3 -m pybind11 --includes)"
mkdir -p lib
for cpp in src/pythia_*.cpp; do
  name="$(basename "$cpp" .cpp)"
  echo "building $name"
  c++ -std=c++17 -O3 -fPIC -fvisibility=hidden -w -shared $INC -Isrc "$cpp" src/pyrt.cpp -o "lib/$name$EXT"
done
echo "done: $(ls lib | wc -l) module(s) in _pythia_accel/lib"
'''


def included(r: FunctionRecord) -> bool:
    return r.status in ("verified", "guarded") and r.decision != "rejected"


def export(ws: Workspace, records: List[FunctionRecord], dest: Optional[Path], zip: bool = False,
           job: Optional[Dict[str, Any]] = None) -> Path:
    name = f"{ws.name}-accelerated"
    if dest is None:
        dest = ws.root / "exports" / (name + (".zip" if zip else ""))
    dest = Path(dest)
    out_dir = dest.with_suffix("") if zip and dest.suffix == ".zip" else dest
    if zip:
        out_dir = ws.root / "exports" / ("_stage_" + name)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ws.work, out_dir, ignore=IGNORE)
    xws = dataclasses.replace(ws, work=out_dir)

    keep = [r for r in records if included(r)]
    for r in records:
        if not included(r):
            try:
                splice.revert(xws, r)
            except splice.SpliceError:
                pass
    accel = out_dir / "_pythia_accel"
    if keep:
        (accel / "src").mkdir(parents=True, exist_ok=True)
        runtime = splice.RUNTIME
        for f in list(runtime.glob("*.hpp")) + list(runtime.glob("*.h")) + [runtime / "pyrt.cpp"]:
            shutil.copy(f, accel / "src" / f.name)
        for r in keep:
            cpp = (r.build or {}).get("cpp_path")
            mod = (r.build or {}).get("module")
            if cpp and Path(cpp).exists() and mod:
                shutil.copy(cpp, accel / "src" / f"{mod}.cpp")
        sh = out_dir / "build_accel.sh"
        sh.write_text(BUILD_SH, encoding="utf-8", newline="\n")
        try:
            sh.chmod(0o755)
        except OSError:
            pass
    elif accel.exists():
        shutil.rmtree(accel)
    (out_dir / "PYTHIA_REPORT.md").write_text(report_md(job or {"name": ws.name}, records), encoding="utf-8")

    if not zip:
        return out_dir
    base = str(dest.with_suffix(""))
    path = shutil.make_archive(base, "zip", root_dir=out_dir.parent, base_dir=out_dir.name)
    shutil.rmtree(out_dir, ignore_errors=True)
    return Path(path)


def count_files(p: Path) -> int:
    if p.is_file():
        import zipfile
        with zipfile.ZipFile(p) as z:
            return len(z.namelist())
    return sum(1 for f in p.rglob("*") if f.is_file())


# ---------------------------------------------------------------- report
def geomean(xs: List[float]) -> Optional[float]:
    xs = [x for x in xs if x and x > 0]
    return math.exp(sum(math.log(x) for x in xs) / len(xs)) if xs else None


def _x(v: Optional[float]) -> str:
    return "-" if v is None else f"{v:.1f}x"


def report_md(job: Dict[str, Any], records: List[FunctionRecord]) -> str:
    recs = sorted(records, key=lambda r: (-(r.share or 0), -r.score.get("total", 0), r.id))
    acc = [r for r in recs if included(r)]
    gm = geomean([r.speedup for r in acc if r.speedup])
    e2e = job.get("e2e")
    L: List[str] = []
    L.append(f"# PYTHIA report: {job.get('name', '')}")
    L.append("")
    L.append("*The LLM suggests, the compiler proves.* Every compiled function below was replayed against the "
             "original Python before being accepted.")
    L.append("")
    L.append("## Headline")
    L.append("")
    if e2e and e2e.get("ok"):
        L.append(f"- End-to-end `{e2e.get('cmd')}`: **{_x(e2e.get('speedup'))}** "
                 f"({e2e.get('before_s'):.2f}s -> {e2e.get('after_s'):.2f}s), "
                 f"output {'identical' if e2e.get('output_match') else 'DIFFERS'}")
    elif e2e:
        L.append(f"- End-to-end run did not complete cleanly (`{e2e.get('cmd')}`).")
    L.append(f"- Accelerated functions: **{len(acc)}** of {len(recs)} analysed; geometric-mean per-function speedup "
             f"**{_x(gm)}**")
    counts: Dict[str, int] = {}
    for r in recs:
        counts[r.status] = counts.get(r.status, 0) + 1
    L.append("- Status counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    L.append("")
    L.append("## Functions")
    L.append("")
    L.append("| Function | Status | Decision | Speedup | Replay | Time share | Calls |")
    L.append("|---|---|---|---|---|---|---|")
    for r in recs:
        rp = r.replay
        replay = f"{rp['matched']}/{rp['total']}" if rp else "-"
        sp = _x(r.speedup) if r.speedup else (f"{_x(r.probe_speedup)} (probe)" if r.probe_speedup else "-")
        share = f"{r.share * 100:.1f}%" if r.share is not None else "-"
        L.append(f"| `{r.id}` | {r.status} | {r.decision} | {sp} | {replay} | {share} | {r.calls if r.calls is not None else '-'} |")
    L.append("")
    other = [r for r in recs if r.status in ("fixable", "not_eligible", "declined", "failed")]
    if other:
        L.append("## Not accelerated")
        L.append("")
        for r in other:
            L.append(f"- `{r.id}` **{r.status}**: {r.reason or 'no reason recorded'}")
            fm = (r.replay or {}).get("first_mismatch")
            if r.status == "failed" and fm:
                L.append(f"  - counterexample: args `{fm['args']}`: python `{fm['python']}`, compiled `{fm['cpp']}` ({fm['kind']})")
        L.append("")
    fid = [(r, f) for r in recs for f in r.fidelity if included(r)]
    if fid:
        L.append("## Fidelity notes")
        L.append("")
        L.append("Places where compiled semantics are not identical to CPython (all within accelerated functions).")
        L.append("")
        for r, f in fid:
            L.append(f"- `{r.id}` line {f.get('line')}: **{f.get('cls')}** ({f.get('severity')}). "
                     f"{f.get('detail', '')} {('Mitigation: ' + f['mitigation']) if f.get('mitigation') else ''}".rstrip())
        L.append("")
    rew = [r for r in recs if r.rewrites and included(r)]
    if rew:
        L.append("## LLM rewrites (Python -> PySub)")
        L.append("")
        for r in rew:
            fin = next((w for w in reversed(r.rewrites) if w.get("ok")), r.rewrites[-1])
            L.append(f"### `{r.id}`  ({len(r.rewrites)} attempt(s), source: {fin.get('source')})")
            L.append("")
            d = "".join(difflib.unified_diff((r.sources.get("original") or "").splitlines(True),
                                             (fin.get("pysub") or "").splitlines(True), "original", "pysub"))
            L.append("```diff")
            L.append(d.rstrip() or "(identical)")
            L.append("```")
            L.append("")
    L.append("## Reproducing")
    L.append("")
    L.append("Compiled modules live in `_pythia_accel/lib`. On another machine run `./build_accel.sh` "
             "(needs a C++17 compiler and `pip install pybind11`). If a module cannot be loaded the original "
             "Python function runs unchanged; set `PYTHIA_ACCEL=0` to disable acceleration.")
    L.append("")
    L.append(f"_Generated {time.strftime('%Y-%m-%d %H:%M')} by PYTHIA Studio._")
    return "\n".join(L) + "\n"
