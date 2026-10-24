"""Result charts (matplotlib), styled to match the report figures. Run: python charts.py"""
import json
import statistics as st
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
EV, FIG = HERE / "evidence", HERE / "figures"
INK, INK2, INK3, LINE, ACC = "#14171f", "#4f5664", "#7c8391", "#d9dce4", "#584bf0"
OK, WARN, BAD = "#0f8f60", "#b26f08", "#cd372e"
for f in ("Segoe UI", "Inter", "Calibri", "DejaVu Sans"):
    if any(f == x.name for x in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = f
        break
plt.rcParams.update({"axes.edgecolor": LINE, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "font.size": 9.5, "axes.titleweight": "bold",
                     "axes.titlesize": 10.5, "axes.titlecolor": INK})


def clean(ax, grid="x"):
    ax.grid(axis=grid, color=LINE, lw=0.7)
    ax.set_axisbelow(True)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(LINE)


def short(k):
    return k.split("_", 1)[1] if "_" in k else k


def bench():
    p = EV / "bench_kernels.json"
    if not p.exists():
        return
    rows = [r for r in json.load(open(p))["rows"] if "speedup" in r]
    rows.sort(key=lambda r: r["speedup"])
    fig, (a, b) = plt.subplots(1, 2, figsize=(9.2, 3.7), gridspec_kw={"width_ratios": [1.15, 1]})
    names = [short(r["kernel"]) for r in rows]
    a.barh(names, [r["speedup"] for r in rows], color=ACC, height=0.55)
    a.set_xscale("log")
    a.axvline(1, color=INK3, lw=1)
    for i, r in enumerate(rows):
        a.text(r["speedup"] * 1.08, i, (f"{r['speedup']:.1f}x" if r["speedup"] >= 1 else f"{r['speedup']:.2f}x"), va="center", color=INK, fontsize=9)
    a.set_title("Speedup over CPython (median of runs)", loc="left")
    a.set_xlabel("times faster, log scale")
    a.set_xlim(0.015, max(r["speedup"] for r in rows) * 3)
    clean(a)
    g = [r["elision_gain"] for r in rows]
    cols = [ACC if x >= 1.03 else INK3 for x in g]
    b.barh(names, [x - 1 for x in g], left=1, color=cols, height=0.55)
    b.axvline(1, color=INK3, lw=1)
    for i, r in enumerate(rows):
        e, k = r.get("elided"), r.get("kept")
        b.text(max(g[i], 1) + 0.02, i, f"{g[i]:.2f}x  ({e} elided, {k} kept)", va="center", color=INK, fontsize=8.3)
    b.set_title("Gain from guard elision", loc="left")
    b.set_xlabel("time without pass / time with pass")
    b.set_yticklabels([])
    b.set_xlim(0.9, max(g) + 0.9)
    clean(b)
    fig.tight_layout()
    fig.savefig(FIG / "chart_bench.png", dpi=300)
    plt.close(fig)


def fidelity():
    p = EV / "fidelity_stats.json"
    if not p.exists():
        return
    d = json.load(open(p))
    fig, (a, b) = plt.subplots(1, 2, figsize=(8.8, 3.0), gridspec_kw={"width_ratios": [1.6, 1]})
    cl = d["classes"]
    ks = list(cl)
    a.bar(ks, [cl[k] for k in ks], color=ACC, width=0.6)
    for i, k in enumerate(ks):
        a.text(i, cl[k] + 8, str(cl[k]), ha="center", fontsize=8.5, color=INK)
    a.set_title("Notes by divergence class", loc="left")
    a.set_ylabel("notes")
    clean(a, "y")
    sv = d["severity"]
    names = ["exact", "guarded", "divergent"]
    vals = [sv.get(n, 0) for n in names]
    b.bar(names, vals, color=[OK, WARN, BAD], width=0.6)
    tot = sum(vals)
    for i, v in enumerate(vals):
        b.text(i, v + 10, f"{v}\n{100 * v / tot:.1f}%", ha="center", fontsize=8.5, color=INK)
    b.set_title("Notes by severity", loc="left")
    b.set_ylim(0, max(vals) * 1.25)
    clean(b, "y")
    fig.tight_layout()
    fig.savefig(FIG / "chart_fidelity.png", dpi=300)
    plt.close(fig)


def studio():
    p = EV / "studio_jobs.json"
    if not p.exists():
        return
    jobs = json.load(open(p))
    items = []
    for j in jobs:
        if "before" in j["label"]:
            continue
        for f in j.get("functions", []):
            if f.get("speedup"):
                items.append((j["label"], f["name"], f["speedup"], f["status"]))
    if not items:
        return
    labels = sorted({i[0] for i in items})
    fig, ax = plt.subplots(figsize=(9.0, max(3.0, 0.23 * len(items) + 0.9)))
    items.sort(key=lambda t: (labels.index(t[0]), t[2]))
    shades = [ACC, "#8b82f5", "#3a8f8f", "#c2710c", "#6b7280"]
    ys = []
    for i, (lab, name, sp, status) in enumerate(items):
        ax.barh(i, sp, color=shades[labels.index(lab) % len(shades)], height=0.6)
        ax.text(sp * 1.06, i, f"{sp:.1f}x", va="center", fontsize=8, color=INK)
        ys.append(f"{name}")
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels(ys, fontsize=8)
    ax.set_xscale("log")
    ax.axvline(1, color=INK3, lw=1)
    ax.set_xlabel("replay-verified speedup over CPython, log scale")
    ax.set_xlim(0.9, max(i[2] for i in items) * 2)
    for k, lab in enumerate(labels):
        ax.barh([-1], [0], color=shades[k % len(shades)], label=lab)
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    clean(ax)
    fig.tight_layout()
    fig.savefig(FIG / "chart_studio.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    fidelity()
    bench()
    studio()
    print("charts ok")
