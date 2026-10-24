#!/usr/bin/env python3
"""Captures Studio screenshots with Playwright (Edge) from a RUNNING server.
Usage: python shots.py --base http://127.0.0.1:8797 --job JOBID --fn "FUNCTION_ID" --out figures/shots [--tag name]"""
import argparse
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--base", default="http://127.0.0.1:8797")
ap.add_argument("--job", required=True)
ap.add_argument("--fn", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--tag", default="")
ap.add_argument("--only", default="")
ap.add_argument("--dark", action="store_true")
a = ap.parse_args()
out = Path(a.out)
out.mkdir(parents=True, exist_ok=True)
tag = a.tag + "_" if a.tag else ""
W, H = 1600, 1000


def snap(pg, name, wait=900):
    pg.wait_for_timeout(wait)
    pg.screenshot(path=str(out / f"{tag}{name}.png"))
    print("shot", name, flush=True)


with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    ctx = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, color_scheme="light")
    ctx.add_init_script("try{localStorage.setItem('theme','light')}catch(e){}")
    pg = ctx.new_page()
    want = set(filter(None, a.only.split(",")))

    def on(n):
        return not want or n in want

    if on("welcome"):
        pg.goto(a.base + "/")
        pg.wait_for_load_state("domcontentloaded")
        snap(pg, "welcome", 1800)
    def light():
        if not a.dark:
            try:
                pg.locator('button[aria-label="Switch to light theme"]').first.click(timeout=2000)
                pg.wait_for_timeout(400)
            except Exception:
                pass

    pg.goto(f"{a.base}/?job={a.job}")
    pg.wait_for_load_state("domcontentloaded")
    pg.wait_for_timeout(2500)
    light()
    if on("run"):
        snap(pg, "run_stepper", 1200)
    short = a.fn.split("::")[-1]
    pg.get_by_text(short, exact=True).first.click()
    pg.wait_for_timeout(2500)
    if on("diff"):
        for lab in ("Diff",):
            try:
                pg.get_by_role("tab", name=lab, exact=True).first.click(timeout=3000)
            except Exception:
                pass
        snap(pg, "diff", 1500)
    if on("three"):
        try:
            pg.get_by_role("tab", name="Three-way", exact=True).first.click(timeout=3000)
        except Exception:
            pass
        snap(pg, "three_way", 2200)
    if on("journey"):
        try:
            pg.get_by_role("tab", name="Journey", exact=True).first.click(timeout=3000)
        except Exception:
            pass
        snap(pg, "journey", 2200)
    if on("stage"):
        pg.locator('[aria-label^="Rank stage"]').first.click()
        snap(pg, "stage_rank", 2500)
    if on("playground"):
        pg.get_by_label("Playground", exact=True).first.click()
        snap(pg, "playground", 2800)
    if on("report"):
        pg.get_by_label("Report", exact=True).first.click()
        snap(pg, "report", 2800)
    b.close()
