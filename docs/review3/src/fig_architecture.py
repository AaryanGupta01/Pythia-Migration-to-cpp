"""Figure 6.1 - PYTHIA architecture (hand-built SVG, Lucide icons). Run: python fig_architecture.py"""
from fig_common import *

W, H = 1400, 940
L = LAYER
b = []


def row_item(x, y, w, ic, label, color):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="42" rx="9" fill="{PAPER}" stroke="{tint(color, .45)}" stroke-width="1.2"/>'
            + icon(ic, x + 12, y + 9, 24, color) + text(x + 48, y + 26.5, label, 15.5, 600, INK, "start"))


# ---- interface band
b.append(group(30, 20, 1340, 152, "INTERFACE", L["ui"], "studio/web  ·  pythia/studio/server"))
for x, ic, lab, sub in [(60, "layout-dashboard", "React + Monaco UI", "TypeScript · Vite · Tailwind"),
                        (390, "server", "FastAPI + WebSocket bus", "server/app.py · bus.py"),
                        (720, "app-window", "App-window launcher", "launcher.py (Edge/Chrome --app)"),
                        (1050, "package", "Windows installer", "packaging/windows (Inno Setup)")]:
    b.append(tile(x, 58, 290, 100, ic, lab, sub, L["ui"]))

# ---- inputs
b.append(group(30, 214, 270, 266, "INPUTS", L["inputs"]))
for i, (ic, lab) in enumerate([("code", "Snippet"), ("file-code", "Python file"), ("folder-open", "Folder"),
                               ("github", "GitHub URL"), ("history", "Demo / saved run")]):
    b.append(row_item(48, 252 + i * 44, 234, ic, lab, L["inputs"]))

# ---- studio engine (10 stages)
SX, SY, TW, TH, GAP = 330, 214, 124, 100, 18
b.append(group(SX, SY, 736, 266, "STUDIO ENGINE", L["studio"], "pythia/studio/"))
stages = [("folder-input", "Ingest", "ingest.py"), ("scan-search", "Scan", "scan.py"), ("activity", "Trace", "trace.py"),
          ("gauge", "Rank", "rank.py"), ("wrench", "Fix", "annotate.py\ninfer.py"),
          ("hammer", "Compile", "pipeline.py"), ("shield-check", "Verify", "replay.py"), ("timer", "Benchmark", "bench.py"),
          ("git-merge", "Splice", "splice.py"), ("package-open", "Export", "export.py")]
pos = {}
for i, (ic, lab, sub) in enumerate(stages):
    r, c = divmod(i, 5)
    x, y = SX + 22 + c * (TW + GAP), SY + 38 + r * (TH + 14)
    pos[lab] = (x, y)
    b.append(tile(x, y, TW, TH, ic, lab, sub, L["studio"], 16, 12.5))
    b.append(text(x + 10, y + 17, f"{i + 1:02d}", 11.5, 600, INK3, "start", mono=True))
    if c < 4:
        b.append(arrow(f"M{x + TW + 2},{y + 50} H{x + TW + GAP - 2}", tint(L['studio'], .8), w=1.8))
fx, fy = pos["Fix"]
cx, cy = pos["Compile"]
b.append(arrow(f"M{fx + TW // 2},{fy + TH + 1} V{fy + TH + 7} H{cx + TW // 2} V{cy - 1}", tint(L['studio'], .8), w=1.8))

# ---- outputs
b.append(group(1096, 214, 274, 266, "OUTPUTS", L["outputs"]))
for i, (ic, lab) in enumerate([("folder-open", "Accelerated project copy"), ("file-diff", "Diff, original vs spliced"),
                               ("scroll-text", "Semantic Fidelity Report"), ("file-text", "PYTHIA_REPORT.md"),
                               ("package-open", "C++17 source, .so / .pyd")]):
    b.append(row_item(1114, 252 + i * 44, 238, ic, lab, L["outputs"]))

# ---- compiler core
CX, CY = 30, 522
b.append(group(CX, CY, 526, 380, "COMPILER CORE", L["core"], "pythia/"))
core = [("brain-circuit", "Converter", "convert/\nto_pysub"), ("scroll-text", "Lexer", "lexer.py\nINDENT/DEDENT"),
        ("braces", "Parser", "parser.py\nPratt + RD"),
        ("badge-check", "Type checker", "typecheck.py\nbidirectional"), ("layers", "Lowering", "lower.py\nPIR + notes"),
        ("ruler", "Guard elision", "optimize.py\nintervals"),
        ("binary", "C++17 emitter", "emit_c.py"), ("plug", "Library mode", "libmode.py\npybind11 glue"),
        ("file-search", "Fidelity report", "FidelityNote\nD1 .. D14")]
for i, (ic, lab, sub) in enumerate(core):
    r, c = divmod(i, 3)
    b.append(tile(CX + 22 + c * 166, CY + 38 + r * 114, 150, TH, ic, lab, sub, L["core"], 16, 12.5))

# ---- runtime and bridge
RX = 586
b.append(group(RX, CY, 360, 380, "RUNTIME AND BRIDGE", L["runtime"], "runtime/"))
rt = [("cpu", "pyrt", "pyrt.hpp/.cpp"), ("boxes", "Containers", "pydict.hpp\npyset.hpp"),
      ("plug", "pybind11 bridge", "pyrt_bridge.hpp"), ("zap", "Accel shim", "pythia_accel/"),
      ("hammer", "Toolchain", "toolchain.py\ng++ -O3, MinGW"), ("database", "Build cache", "content-addressed\n.so / .pyd")]
for i, (ic, lab, sub) in enumerate(rt):
    r, c = divmod(i, 2)
    b.append(tile(RX + 22 + c * 166, CY + 38 + r * 114, 150, TH, ic, lab, sub, L["runtime"], 16, 12.5))

# ---- verification
VX = 976
b.append(group(VX, CY, 394, 380, "VERIFICATION", L["verify"], "tools/ · scripts/"))
vf = [("shield-check", "Replay worker", "_replay_worker.py"), ("git-compare", "Diff. oracle", "tools/oracle.py\n78 + 88 programs"),
      ("list-checks", "Basics + snippets", "check_basics.py\ncheck_snippets.py"), ("flask-conical", "Property + fuzz", "property_test.py\nfuzz.py"),
      ("bug", "Stress harness", "stress.py"), ("scale", "Verdict", "same result,\nelse rejected")]
for i, (ic, lab, sub) in enumerate(vf):
    r, c = divmod(i, 2)
    b.append(tile(VX + 22 + c * 174, CY + 38 + r * 114, 160, TH, ic, lab, sub, L["verify"], 16, 12.5))

# ---- numbered flow arrows
D = INK
b.append(arrow("M165,174 V212", D)); b.append(badge(165, 193, 1))
b.append(arrow(f"M300,{SY + 88} H{SX + 24}", D)); b.append(badge(315, SY + 70, 2))
b.append(arrow("M440,468 V556", D, both=True)); b.append(badge(440, 500, 3))
b.append(arrow(f"M556,{CY + 88} H{RX + 24}", D)); b.append(badge(571, CY + 70, 4))
b.append(arrow(f"M946,{CY + 88} H{VX + 24}", D)); b.append(badge(961, CY + 70, 5))
vx, vy = pos["Verify"]
b.append(arrow(f"M1156,{CY} V501 H{vx + TW // 2} V{vy + TH + 1}", D)); b.append(badge(860, 501, 6))
sx, sy = pos["Export"]
b.append(arrow(f"M{sx + TW + 2},{sy + 50} H1114", D)); b.append(badge(1081, sy + 31, 7))
b.append(arrow("M545,214 V174", D, both=True)); b.append(badge(545, 194, 8))

body = "".join(b)
svg = svg_doc(W, H, body)
out = FIG / "fig_architecture.svg"
out.write_text(svg, encoding="utf-8")
render_png(out, FIG / "fig_architecture.png", 3)
print("ok", out)
