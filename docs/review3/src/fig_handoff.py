"""Viva guide figure: who passes what to whom (compiler phases, plus the PROPOSED Studio split)."""
from fig_common import *

W, H = 1080, 560
M = {"V": "#2563eb", "R": "#059669", "J": "#d97706", "A": "#7c3aed"}
b = []
cols = [
    ("V", "Vishal", "Front end", "file-code", "lexer.py  parser.py\nast_nodes.py  cli.py", "Studio shell", "pipeline.py, server,\nweb UI, installer"),
    ("R", "Rujuta", "Type system", "badge-check", "typecheck.py\nnegative corpus, PyDict", "Type inference", "convert/ inference,\nscan.py reasons"),
    ("J", "Jahnavi", "Lowering, runtime", "layers", "lower.py  optimize.py\npyrt  PySet", "Fidelity + bridge", "fidelity gutter,\nlibmode marshalling"),
    ("A", "Aaryan", "Emitter + oracle", "binary", "emit_c.py  oracle.py\nfuzz.py  CI", "Verification", "replay.py, bench.py,\nstress, property tests"),
]
CW, GAP, X0 = 206, 70, 24
for i, (k, name, phase, ic, files, st_t, st_f) in enumerate(cols):
    x = X0 + i * (CW + GAP)
    c = M[k]
    b.append(f'<rect x="{x}" y="20" width="{CW}" height="470" rx="16" fill="{tint(c, .07)}" stroke="{tint(c, .55)}" stroke-width="1.5"/>')
    b.append(f'<rect x="{x}" y="20" width="{CW}" height="54" rx="16" fill="{c}"/><rect x="{x}" y="50" width="{CW}" height="24" fill="{c}"/>')
    b.append(text(x + 16, 54, name, 21, 750, "#fff", "start"))
    b.append(text(x + CW - 14, 54, f"M{i + 1}", 14, 600, "#ffffffcc", "end", mono=True))
    # compiler card
    b.append(f'<rect x="{x + 12}" y="92" width="{CW - 24}" height="168" rx="12" fill="#fff" stroke="{tint(c, .5)}" stroke-width="1.3"/>')
    b.append(text(x + 24, 116, "REVIEW 1 AND 2", 11.5, 750, c, "start", extra='letter-spacing="1.2"'))
    b.append(icon(ic, x + 24, 128, 28, c))
    b.append(text(x + 62, 148, phase, 16, 700, INK, "start"))
    for j, ln in enumerate(files.split("\n")):
        b.append(text(x + 24, 190 + j * 19, ln, 11.8, 500, INK2, "start", mono=True))
    # studio card (proposed)
    b.append(f'<rect x="{x + 12}" y="276" width="{CW - 24}" height="158" rx="12" fill="#fff" stroke="{c}" stroke-width="1.3" stroke-dasharray="6 5"/>')
    b.append(text(x + 24, 300, "REVIEW 3, PROPOSED", 11.5, 750, c, "start", extra='letter-spacing="1.2"'))
    b.append(text(x + 24, 330, st_t, 16, 700, INK, "start"))
    for j, ln in enumerate(st_f.split("\n")):
        b.append(text(x + 24, 358 + j * 19, ln, 11.8, 500, INK2, "start", mono=True))
    b.append(text(x + 24, 418, "agree before the viva", 11.8, 600, INK3, "start", extra='font-style="italic"'))
    if i < 3:
        ax = x + CW + 3
        b.append(arrow(f"M{ax},170 H{ax + GAP - 6}", INK, w=2.4))
        label = ["AST", "typed AST", "PIR"][i]
        b.append(f'<rect x="{ax - 2}" y="130" width="{GAP - 2}" height="22" rx="11" fill="{INK}"/>')
        b.append(text(ax + GAP / 2 - 3, 145.5, label, 10.6, 700, "#fff"))
b.append(f'<rect x="24" y="504" width="1032" height="44" rx="12" fill="{tint(ACCENT, .08)}" stroke="{tint(ACCENT, .5)}" stroke-width="1.2"/>')
b.append(icon("git-merge", 36, 515, 24, ACCENT))
b.append(text(70, 532, "Everyone ships through one gate: the oracle must stay at 78/78 and 88/88, and replay must agree before anything is spliced.", 14.2, 600, INK, "start"))
out = FIG / "fig_handoff.svg"
out.write_text(svg_doc(W, H, "".join(b)), encoding="utf-8")
render_png(out, FIG / "fig_handoff.png", 3)
print("ok")
