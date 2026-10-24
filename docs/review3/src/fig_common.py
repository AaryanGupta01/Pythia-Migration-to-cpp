"""Shared helpers for the hand-built SVG figures (Lucide icons, palette, PNG rendering with headless Edge)."""
from __future__ import annotations

import html
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIG = HERE / "figures"
FIG.mkdir(exist_ok=True)
WEB = ROOT / "studio" / "web" / "node_modules"
ICONS = WEB / "lucide-react" / "dist" / "esm" / "icons"
FONT_INTER = (WEB / "@fontsource-variable/inter/files/inter-latin-wght-normal.woff2").as_uri()
FONT_MONO = (WEB / "@fontsource-variable/jetbrains-mono/files/jetbrains-mono-latin-wght-normal.woff2").as_uri()

# One accent per layer; the indigo is the app's own accent (studio/web/src/index.css, light theme).
INK, INK2, INK3 = "#14171f", "#4f5664", "#7c8391"
LINE, PAPER = "#d9dce4", "#ffffff"
ACCENT = "#584bf0"
LAYER = {
    "ui":      "#7a5af8",
    "inputs":  "#64748b",
    "studio":  "#584bf0",
    "core":    "#0e8f8f",
    "runtime": "#c2710c",
    "verify":  "#15935f",
    "outputs": "#475569",
}
OK, WARN, BAD = "#0f8f60", "#b26f08", "#cd372e"


def tint(hex_: str, a: float) -> str:
    """Blend hex with white: a=0 white, a=1 colour."""
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(round(255 - (255 - c) * a) for c in (r, g, b))


_icon_cache: dict[str, str] = {}


def icon_nodes(name: str) -> str:
    """Inner SVG of a Lucide icon (24x24 viewBox, stroke based)."""
    if name in _icon_cache:
        return _icon_cache[name]
    src = (ICONS / f"{name}.js").read_text(encoding="utf-8")
    body = src[src.index("createLucideIcon("):]
    out = []
    for tag, attrs in re.findall(r'\[\s*"(\w+)"\s*,\s*\{(.*?)\}\s*\]', body, flags=re.S):
        kv = re.findall(r'(\w+)\s*:\s*"([^"]*)"', attrs)
        a = " ".join(f'{"stroke-linecap" if k == "strokeLinecap" else k}="{v}"' for k, v in kv if k != "key")
        out.append(f"<{tag} {a}/>")
    _icon_cache[name] = "".join(out)
    return _icon_cache[name]


def icon(name: str, x: float, y: float, size: float, color: str, sw: float = 1.8) -> str:
    s = size / 24
    return (f'<g transform="translate({x:.1f} {y:.1f}) scale({s:.4f})" fill="none" stroke="{color}" '
            f'stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">{icon_nodes(name)}</g>')


def esc(t: str) -> str:
    return html.escape(t, quote=False)


def text(x, y, s, size=16, weight=600, fill=INK, anchor="middle", mono=False, extra="") -> str:
    fam = "JetBrains Mono, monospace" if mono else "Inter, sans-serif"
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}" {extra}>{esc(s)}</text>')


def svg_doc(w: int, h: int, body: str, defs: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<defs><marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M1 1 L9 5 L1 9 z" fill="{INK2}"/></marker>{defs}</defs>'
            f'<rect width="{w}" height="{h}" fill="{PAPER}"/>{body}</svg>')


def badge(x, y, n, color=INK, r=13) -> str:
    return (f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'
            + text(x, y + 5.2, str(n), 15, 700, "#fff"))


def tile(x, y, w, h, ic, label, sub, color, label_size=16, sub_size=13) -> str:
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="11" fill="{PAPER}" stroke="{tint(color, .45)}" stroke-width="1.4"/>',
           icon(ic, x + w / 2 - 14, y + 11, 28, color)]
    out.append(text(x + w / 2, y + 58, label, label_size, 650, INK))
    for i, line in enumerate(sub.split("\n")):
        out.append(text(x + w / 2, y + 76 + i * (sub_size + 2), line, sub_size, 500, INK3, mono=True))
    return "".join(out)


def group(x, y, w, h, title, color, note="") -> str:
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{tint(color, .07)}" stroke="{tint(color, .5)}" stroke-width="1.5"/>',
           f'<rect x="{x}" y="{y}" width="7" height="{h}" rx="3.5" fill="{color}" clip-path="inset(0 0 0 0)"/>',
           text(x + 24, y + 28, title, 15.5, 750, color, "start", extra='letter-spacing="1.3"')]
    if note:
        out.append(text(x + w - 16, y + 28, note, 13.5, 500, INK3, "end", mono=True))
    return "".join(out)


def arrow(d: str, color=INK2, dash=False, both=False, w=2.2) -> str:
    ds = ' stroke-dasharray="6 5"' if dash else ""
    start = ' marker-start="url(#ah)"' if both else ""
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{w}"{ds} stroke-linejoin="round" '
            f'marker-end="url(#ah)"{start}/>')


def render_png(svg_path: Path, png_path: Path, scale: float = 3.0, width_px: int | None = None) -> None:
    """Rasterise an SVG with Edge (fonts via @font-face) at `scale`x device pixels."""
    from playwright.sync_api import sync_playwright
    svg = svg_path.read_text(encoding="utf-8")
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    w, h = int(m.group(1)), int(m.group(2))
    page_html = (f'<html><head><style>@font-face{{font-family:Inter;src:url("{FONT_INTER}");font-weight:100 900}}'
                 f'@font-face{{font-family:"JetBrains Mono";src:url("{FONT_MONO}");font-weight:100 800}}'
                 f'html,body{{margin:0;background:#fff}}svg{{display:block}}</style></head><body>{svg}</body></html>')
    tmp = svg_path.with_suffix(".html")
    tmp.write_text(page_html, encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=scale)
        pg.goto(tmp.as_uri())
        pg.wait_for_timeout(400)
        pg.evaluate("document.fonts.ready")
        pg.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": w, "height": h})
        b.close()
    tmp.unlink()
