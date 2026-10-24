"""Figure 3.1 - what changed between Review 2 and Review 3."""
from fig_common import *

W, H = 1400, 600
b = []
NEW, OLD = LAYER["studio"], LAYER["core"]


def box(x, y, w, h, ic, label, sub, color, dashed=False):
    st = f'stroke-dasharray="5 4"' if dashed else ""
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" fill="{tint(color, .08)}" stroke="{color}" stroke-width="1.6" {st}/>'
         + icon(ic, x + w / 2 - 13, y + 11, 26, color)
         + text(x + w / 2, y + 56, label, 15.5, 650, INK))
    for i, ln in enumerate(sub.split("\n")):
        s += text(x + w / 2, y + 74 + i * 15, ln, 12.5, 500, INK3, mono=True)
    return s


# lane titles
b.append(text(30, 40, "REVIEW 2  ·  a command-line transpiler", 17, 750, OLD, "start", extra='letter-spacing="1"'))
b.append(text(30, 62, "you hand it typed PySub; you get C++17. 17/17 positive and 20/20 negative oracle programs; PyDict and PySet runtime libraries; C11 to C++17 migration.", 14, 500, INK2, "start"))
x = 30
r2 = [("file-code", "typed PySub", "every function\nannotated"), ("scroll-text", "lexer + parser", "INDENT/DEDENT\nPratt"),
      ("badge-check", "type checker", "bidirectional"), ("layers", "lowering", "fidelity notes"),
      ("ruler", "guard elision", "intervals"), ("binary", "C++17 emitter", ""), ("terminal", "g++ -> binary", "run vs CPython")]
for i, (ic, lab, sub) in enumerate(r2):
    xx = 30 + i * 192
    b.append(box(xx, 85, 160, 100, ic, lab, sub, OLD))
    if i:
        b.append(arrow(f"M{xx - 30},135 H{xx - 3}", INK3, w=1.8))

b.append(f'<line x1="30" y1="222" x2="1370" y2="222" stroke="{LINE}" stroke-width="1.5"/>')
b.append(f'<path d="M700 210 l10 12 l10 -12" fill="none" stroke="{INK3}" stroke-width="2"/>')
b.append(text(30, 262, "REVIEW 3  ·  PYTHIA Studio, a desktop app for whole projects", 17, 750, NEW, "start", extra='letter-spacing="1"'))
b.append(text(30, 284, "you hand it ordinary Python (snippet, file, folder or GitHub URL); it finds the slow parts, converts what it can, proves each one against CPython, and splices it in.", 14, 500, INK2, "start"))

r3 = [("github", "any Python", "snippet · file\nfolder · URL", True), ("scan-search", "scan", "compiler is\nthe judge", True),
      ("activity", "trace + rank", "sys.monitoring\nhotspots", True), ("brain-circuit", "infer types", "in-house,\nno LLM", True),
      ("badge-check", "R2 compiler", "reused and\nextended", False), ("plug", "pybind11 module", "marshalling\n.so / .pyd", True),
      ("shield-check", "replay verify", "recorded calls\nvs CPython", True), ("git-merge", "splice + report", "diff, fidelity,\nspeedups", True)]
for i, (ic, lab, sub, new) in enumerate(r3):
    xx = 30 + i * 168
    col = NEW if new else OLD
    b.append(box(xx, 310, 142, 110, ic, lab, sub, col, dashed=False))
    if i:
        b.append(arrow(f"M{xx - 24},365 H{xx - 3}", INK3, w=1.8))
    b.append(f'<rect x="{xx + 8}" y="{310 - 11}" width="{44 if new else 62}" height="20" rx="10" fill="{col}"/>'
             + text(xx + 8 + (22 if new else 31), 310 + 3.5, "NEW" if new else "REUSED", 11.5, 700, "#fff"))

# why
b.append(f'<rect x="30" y="455" width="1340" height="120" rx="14" fill="{tint(NEW, .07)}" stroke="{tint(NEW, .5)}" stroke-width="1.4"/>')
b.append(text(52, 485, "WHY WE PIVOTED", 14.5, 750, NEW, "start", extra='letter-spacing="1.2"'))
for i, ln in enumerate(["A plain transpiler needs the program written in a typed subset first. Real developers already have an untyped project and want",
                        "the slow parts faster without rewriting it. So Review 3 moves up a level: repo-level scan, rank, convert, verify, splice, and every",
                        "step is visible. The WebAssembly back end promised in Review 2 was dropped in favour of this (see Section 3.4)."]):
    b.append(text(52, 512 + i * 21, ln, 14.5, 500, INK, "start"))

out = FIG / "fig_whatchanged.svg"
out.write_text(svg_doc(W, H, "".join(b)), encoding="utf-8")
render_png(out, FIG / "fig_whatchanged.png", 3)
print("ok")
