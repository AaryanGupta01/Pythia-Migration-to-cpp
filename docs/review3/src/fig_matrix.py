"""Figure 4.1 - comparison matrix against existing tools (cells follow each tool's official documentation)."""
from fig_common import *

W, ROWH, HEAD = 1000, 58, 96
COLS = ["Readable\noutput", "Checked\nvs CPython", "Reports\ndivergence", "Whole repo\nautomatic", "Unconvert-\nible code\nstill runs", "No LLM or\ninternet", "Visual\nstage app"]
Y, H_, N = 2, 1, 0       # yes / partly / no ; None = not applicable or not assessed
# tool, output, input, [7 cells]
ROWS = [
    ("Cython", "C/C++ extension module", "Python + C type declarations", [N, N, N, N, Y, Y, N]),
    ("Numba", "JIT machine code (in memory)", "Python + @jit, NumPy style", [None, N, N, N, N, Y, N]),
    ("PyPy", "alternative interpreter + JIT", "unmodified Python", [None, N, N, Y, H_, Y, N]),
    ("mypyc", "C extension module", "type-annotated Python", [N, N, N, H_, Y, Y, N]),
    ("Nuitka", "C program linked to libpython", "any Python source", [N, N, N, Y, Y, Y, N]),
    ("Codon", "native executable (LLVM)", "Python-like, not drop-in", [N, N, N, N, H_, Y, N]),
    ("Pythran", "C++ native module", "Python subset + export comments", [None, N, N, N, N, Y, N]),
    ("Shed Skin", "C++ program or module", "implicitly typed Python 3 subset", [None, N, N, N, N, Y, N]),
    ("LPython", "LLVM / C / C++ / WASM (alpha)", "type-annotated Python subset", [None, N, N, N, N, Y, N]),
    ("LLM translation", "C++ source text", "any Python", [Y, N, N, N, N, N, N]),
    ("PYTHIA", "readable C++17 + pybind11 module", "untyped Python, supported subset", [Y, Y, Y, Y, Y, Y, Y]),
]
X0, XT, XI = 24, 24, 252
XS = 440
CW = (W - XS - 18) / 7
b = []
b.append(f'<rect x="12" y="10" width="{W - 24}" height="{HEAD + ROWH * len(ROWS) + 38}" rx="14" fill="#fff" stroke="{LINE}" stroke-width="1.4"/>')
b.append(text(XT, 52, "TOOL  ·  OUTPUT", 13.5, 750, INK3, "start", extra='letter-spacing="1"'))
b.append(text(XI + 4, 52, "INPUT IT NEEDS", 13.5, 750, INK3, "start", extra='letter-spacing="1"'))
for i, c in enumerate(COLS):
    cx = XS + CW * i + CW / 2
    for j, ln in enumerate(c.split("\n")):
        b.append(text(cx, 28 + j * 16, ln, 12.4, 700, INK2))
b.append(f'<line x1="24" y1="{HEAD - 8}" x2="{W - 24}" y2="{HEAD - 8}" stroke="{LINE}" stroke-width="1.5"/>')


def sym(cx, cy, v, color):
    if v is None:
        return text(cx, cy + 5, "–", 18, 600, INK3)
    r = 11
    if v == Y:
        return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}"/><path d="M{cx - 5},{cy} l4,4.5 l7,-8.5" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
    if v == H_:
        return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{color}" stroke-width="2"/>'
                f'<path d="M{cx},{cy - r} A{r},{r} 0 0 0 {cx},{cy + r} z" fill="{color}"/>')
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#fff" stroke="{tint(INK3, .7)}" stroke-width="2"/>'


for ri, (tool, out, inp, cells) in enumerate(ROWS):
    y = HEAD + ri * ROWH
    me = tool == "PYTHIA"
    if me:
        b.append(f'<rect x="18" y="{y - 2}" width="{W - 36}" height="{ROWH}" rx="10" fill="{tint(ACCENT, .09)}" stroke="{tint(ACCENT, .5)}" stroke-width="1.3"/>')
    elif ri % 2:
        b.append(f'<rect x="18" y="{y - 2}" width="{W - 36}" height="{ROWH}" rx="8" fill="#f7f8fb"/>')
    b.append(text(XT, y + 22, tool, 17, 750 if me else 650, ACCENT if me else INK, "start"))
    b.append(text(XT, y + 42, out, 12.8, 500, INK3, "start"))
    import textwrap
    for li, ln in enumerate(textwrap.wrap(inp, 27)[:2]):
        b.append(text(XI + 4, y + 22 + li * 20, ln, 13.6, 550, INK2, "start"))
    for ci, v in enumerate(cells):
        b.append(sym(XS + CW * ci + CW / 2, y + 26, v, ACCENT if me else INK2))
H = HEAD + ROWH * len(ROWS) + 58
b.append(text(24, H - 22, "● yes     ◐ partly / with caveats     ○ no     – not applicable or not assessed", 12.8, 500, INK3, "start"))
out = FIG / "fig_matrix.svg"
out.write_text(svg_doc(W, H + 10, "".join(b)), encoding="utf-8")
render_png(out, FIG / "fig_matrix.png", 3)
print("ok")
