#!/usr/bin/env python3
"""Builds docs/review3/PYTHIA_Viva_Guide.pdf from HTML (Chromium print). Run: python build_viva.py"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from fig_common import FIG, FONT_INTER, FONT_MONO  # noqa: E402
import report_data  # noqa: E402
import report_tables  # noqa: E402
import viva_a, viva_b, viva_c  # noqa: E402
import demo_info  # noqa: E402

OUT = HERE.parent / "PYTHIA_Viva_Guide.pdf"


def main():
    F = report_tables.extend(report_data.load())
    D = demo_info.build(F)
    css = (HERE / "viva_style.css").read_text(encoding="utf-8")
    fonts = (f'@font-face{{font-family:Inter;src:url("{FONT_INTER}");font-weight:100 900}}'
             f'@font-face{{font-family:"JetBrains Mono";src:url("{FONT_MONO}");font-weight:100 800}}')
    toc = [("1", "PYTHIA in 60 seconds"), ("2", "The whole flow, step by step"), ("3", "What changed since Review 2"),
           ("4", "Who did what, and how it fits"), ("5", "“Open the codebase” cheat sheet"), ("6", "Tools we chose, and why"),
           ("7", "Limitations and comebacks"), ("8", "The value this adds"), ("9", "Likely viva questions"),
           ("10", "Live demo script and backup plan"), ("11", "Glossary")]
    cover = f"""
<div class="cover">
<div class="badge">Internal · not for submission</div>
<div class="kicker">BCSE307L · COMPILER DESIGN · TEAM 2 · A15</div>
<h1>PYTHIA<br>Viva Guide</h1>
<div class="sub">Everything the four of us need to explain the project in plain words, point at our own code, and answer the hard questions.</div>
<div class="toc">{''.join(f'<div><span class="n">{n}</span>{t}</div>' for n, t in toc)}</div>
<div class="meta">Vishal Vivek 24BCE2377 · Rujuta Mangesh Kulkarni 24BDS0459 · Koliparthy Venkata Jahnavi 24BDS0132 · Aaryan Gupta 24BDS0134<br>
Repository commit <code>{F['git']['head']}</code> · measured on {report_tables.DATE} · every number here is from a command we ran (report, Appendix F)</div>
</div>"""
    body = "".join([viva_a.sec1(F, D), viva_a.sec2(F, D), viva_a.sec3(F, D), viva_a.sec4(F, D), viva_b.sec5(F, D),
                    viva_b.sec6(F, D), viva_b.sec7(F, D), viva_c.sec8(F, D), viva_c.sec9(F, D), viva_c.sec10(F, D), viva_c.sec11(F, D)])
    html = f"<!doctype html><html><head><meta charset='utf-8'><title>PYTHIA Viva Guide</title><style>{fonts}{css}</style></head><body>{cover}{body}</body></html>"
    h = HERE / "viva_guide.html"
    h.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(channel="msedge")
        pg = b.new_page()
        pg.goto(h.as_uri())
        pg.wait_for_timeout(800)
        pg.evaluate("document.fonts.ready")
        pg.pdf(path=str(OUT), format="A4", print_background=True, display_header_footer=True,
               margin={"top": "16mm", "bottom": "18mm", "left": "15mm", "right": "15mm"},
               header_template="<span></span>",
               footer_template="<div style='width:100%;font-size:8px;color:#7c8391;font-family:Inter,Arial;padding:0 15mm;display:flex;justify-content:space-between'>"
                               "<span>PYTHIA Viva Guide · Team 2 · A15 (internal)</span><span>Page <span class='pageNumber'></span> of <span class='totalPages'></span></span></div>")
        b.close()
    import fitz
    print("pages:", len(fitz.open(OUT)), OUT)


if __name__ == "__main__":
    main()
