"""Figure: one function's journey (real data from evidence/journey.json)."""
import json
from fig_common import *
j = json.load(open(HERE / "evidence" / "journey.json")); r = j["rec"]; st = j["stages"]
tr, bn, rp, bd = r["trace"], r["bench"], r["replay"], r["build"]
W, H = 1400, 640
b = []
steps = [
 ("file-code", "1 Python", "def collatz_sequence_len(\n  n: int) -> int:\n  while n != 1: ...", LAYER["inputs"]),
 ("activity", "2 Trace", f"{tr['calls']:,} calls\n{100*tr['share']:.0f}% of run time\n(int) -> int", LAYER["studio"]),
 ("badge-check", "3 PySub", "type-checks as\nwritten; nothing\nto annotate", LAYER["core"]),
 ("scroll-text", "4 Tokens", f"{len(st['tokens'])} tokens\nNEWLINE INDENT\n... DEDENT", LAYER["core"]),
 ("layers", "5 AST / PIR", "typed tree, every\nnode has a type;\nimplicit casts explicit", LAYER["core"]),
 ("ruler", "6 Guards", f"{st['guard_elision']['kept']} checked ops kept\n{st['guard_elision']['elided']} elided\n{len(r['fidelity'])} fidelity notes", LAYER["core"]),
 ("binary", "7 C++17", "int64_t loop with\npy_mod_i64 and\npy_add_i64", LAYER["core"]),
 ("hammer", "8 Build", f"pybind11 .pyd\ng++ -O3 -flto\n{bd['compile_s']:.1f} s", LAYER["runtime"]),
 ("shield-check", "9 Replay", f"{rp['matched']}/{rp['total']} calls\nmatched CPython\n(source: {rp['source']})", LAYER["verify"]),
 ("timer", "10 Speedup", f"{bn['py_ms']:.2f} ms to {bn['cpp_ms']:.3f} ms\n{bn['speedup']:.1f}x faster\nspliced in", LAYER["verify"]),
]
cw, gx = 250, 20
for i, (ic, t, sub, col) in enumerate(steps):
    r_, c_ = divmod(i, 5)
    x, y = 30 + c_ * (cw + gx + 2), 40 + r_ * 300
    b.append(f'<rect x="{x}" y="{y}" width="{cw}" height="230" rx="14" fill="{tint(col,.07)}" stroke="{col}" stroke-width="1.6"/>')
    b.append(icon(ic, x + 18, y + 18, 32, col)); b.append(text(x + 62, y + 43, t, 21, 750, INK, "start"))
    for k, ln in enumerate(sub.split("\n")):
        b.append(text(x + 20, y + 100 + k * 30, ln, 16, 500, INK2, "start", mono=True))
    if c_ < 4: b.append(arrow(f"M{x+cw+2},{y+115} H{x+cw+gx+1}", INK2))
b.append(arrow("M155,270 V310 H155 V340", INK3, w=0)); b.pop()
b.append(text(700, 612, f"{j['repo']} @ {j['sha']}  ·  {j['rec']['id']}  ·  entry command: {j['cmd']}", 14, 500, INK3))
out = FIG / "fig_journey.svg"; out.write_text(svg_doc(W, H, "".join(b)), encoding="utf-8")
render_png(out, FIG / "fig_journey.png", 3); print("ok")
