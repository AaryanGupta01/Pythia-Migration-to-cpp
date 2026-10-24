"""Figure 7.1 - the fix-and-verify ladder."""
from fig_common import *

W, H = 1000, 470
S, C, V = LAYER["studio"], LAYER["core"], LAYER["verify"]
b = []


def card(x, y, w, h, ic, title, sub, color, dashed=False):
    st = 'stroke-dasharray="6 5"' if dashed else ""
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{tint(color, .07)}" stroke="{color}" stroke-width="1.6" {st}/>'
         + icon(ic, x + 14, y + 14, 26, color) + text(x + 52, y + 33, title, 15.5, 700, INK, "start"))
    for i, ln in enumerate(sub.split("\n")):
        s += text(x + 14, y + 62 + i * 17, ln, 12.8, 500, INK2, "start")
    return s


b.append(text(24, 30, "A FUNCTION THE TYPE CHECKER REJECTED AS WRITTEN", 13.5, 750, INK3, "start", extra='letter-spacing="1"'))
rungs = [("eye", "1  Annotate from observed types", "types the tracer saw at run time\nannotate.py", S, False),
         ("brain-circuit", "2  Infer from usage", "doctests, call sites, assignments,\nwhole-program fixpoint (convert/)", S, False),
         ("sparkles", "3  LLM rewrite (optional)", "only if a key is configured; at most\n3 attempts, errors fed back", LAYER["runtime"], True)]
for i, (ic, t, sub, col, dash) in enumerate(rungs):
    y = 48 + i * 100
    b.append(card(24, y, 300, 88, ic, t, sub, col, dash))
    b.append(arrow(f"M324,{y + 44} H372", INK2))

# compiler gate
b.append(f'<rect x="376" y="48" width="130" height="288" rx="14" fill="{tint(C, .09)}" stroke="{C}" stroke-width="1.6"/>')
b.append(icon("badge-check", 428, 62, 26, C))
for i, ln in enumerate(["Compiler", "gate"]):
    b.append(text(441, 112 + i * 19, ln, 16, 700, INK))
for i, ln in enumerate(["PySub parser", "+ type checker", "accept or", "reject with", "a reason"]):
    b.append(text(441, 168 + i * 18, ln, 12.8, 500, INK2))

# downstream chain
chain = [("hammer", "Compile", "C++17 + pybind11\n-> .so / .pyd", C), ("shield-check", "Replay", "recorded calls vs\nCPython, floats bitwise", V),
         ("timer", "Benchmark", "median speedup\nkept if >= 1.1x", V), ("git-merge", "Splice", "one decorator line;\nbody untouched", S)]
x = 536
for i, (ic, t, sub, col) in enumerate(chain):
    xx = 536 + (i % 2) * 230
    yy = 62 + (i // 2) * 140
    b.append(card(xx, yy, 205, 116, ic, t, sub, col))
b.append(arrow("M506,120 H532", INK2))
b.append(arrow("M741,120 H766", INK2))
b.append(arrow("M870,180 V198 H640 V204", INK2, w=0))     # placeholder removed below
b.pop()
b.append(arrow("M900,178 V202 H638 V202", INK2, w=0))
b.pop()
b.append(arrow("M770,178 V190 H640 V202", INK2))
b.append(arrow("M741,260 H766", INK2))

# failure box
b.append(f'<rect x="24" y="350" width="952" height="96" rx="14" fill="{tint(BAD, .06)}" stroke="{BAD}" stroke-width="1.5"/>')
b.append(icon("octagon-x", 44, 366, 28, BAD))
b.append(text(84, 388, "Any rung or gate can fail, and failure is a normal outcome, not an error", 16, 700, INK, "start"))
for i, ln in enumerate(["The function stays plain Python and the UI shows the reason in English, for example: \"int on some runs, float on others\", \"uses numpy\",",
                        "\"object of type X\", or \"measured speedup below 1.1x\". Nothing that failed a gate is ever spliced."]):
    b.append(text(84, 412 + i * 19, ln, 13.4, 500, INK2, "start"))
for x0 in (174, 441):
    b.append(arrow(f"M{x0},{336 if x0 == 441 else 336} V348", BAD, dash=True, w=1.8))
out = FIG / "fig_ladder.svg"
out.write_text(svg_doc(W, H, "".join(b)), encoding="utf-8")
render_png(out, FIG / "fig_ladder.png", 3)
print("ok")
