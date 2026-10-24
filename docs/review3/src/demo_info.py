"""Demo-dependent content for the report and the viva guide (numbers come from evidence/studio_jobs.json and evidence/demo_pick.json)."""
from __future__ import annotations

import json
from pathlib import Path

from fig_common import FIG
from report_data import EV, fx, geomean

STUDIO_NOTES = {
    "V": "<b>Studio shell.</b> <code>pipeline.py</code> runs the ten stages; <code>server/app.py</code> and <code>bus.py</code> carry REST calls and the WebSocket event stream; the React UI, the launcher and the Windows installer. <i>Explain:</i> how a click becomes a job, what an event is, and what Splice does to the files.",
    "R": "<b>In-house type inference and eligibility.</b> <code>convert/infer.py</code> (evidence and fixpoint), <code>types.py</code> (the lattice), <code>search.py</code> (guessing), <code>scan.py</code> and <code>reasons.py</code> (the compiler as judge, plain-English reasons). <i>Explain:</i> why a function is eligible, how types are inferred with no LLM, and why <code>coin_change</code> is refused.",
    "J": "<b>Fidelity and the boundary.</b> The fidelity gutter and panel, <code>libmode.py</code> and <code>pyrt_bridge.hpp</code> (copy in, copy out, <code>FallbackError</code>, <code>OverflowError</code>, the arena), <code>rank.py</code> (the boundary-cost model). <i>Explain:</i> why a long list is slow to pass, what the arena frees, what D1 and D13 mean in practice.",
    "A": "<b>Verification and measurement.</b> <code>replay.py</code>, <code>_replay_worker.py</code>, <code>codec.py</code> (the comparison), <code>bench.py</code> (median speedup, end to end), <code>stress.py</code>, <code>property_test.py</code>, the oracle and CI. <i>Explain:</i> how “verified” is decided, why floats compare bit for bit, and why the threshold is 1.1x.",
}


def _load(name, default=None):
    p = EV / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def build(F):
    jobs = F["studio_jobs"]
    pick = _load("demo_pick.json") or {}
    D = {"studio_notes": STUDIO_NOTES, "screens": [], "numbers_row": "", "fn_name": "?", "repo_name": "?", "journey_html": "<p>(pending)</p>",
         "demo_html": "<p>(pending)</p>", "textlab_before": "?", "textlab_after": "?", "textlab_e2e": "?", "abstract_studio": "", "conclusion_studio": "",
         "stress_text": "pending", "stress_short": "pending", "latency_text": ""}
    by = {j["label"]: j for j in jobs}
    tl = next((j for j in jobs if j["base_label"] == "textlab" and "cold" in j["label"]), None) or by.get("textlab")
    if tl and tl.get("e2e"):
        D["textlab_before"] = f"{tl['e2e']['before_s']:.1f}"
        D["textlab_after"] = f"{tl['e2e']['after_s']:.1f}"
        D["textlab_e2e"] = f"{tl['e2e']['speedup']:.1f}"
    extra = _load("demo_extra.json") or {}
    D.update(extra)
    sh = FIG / "shots"
    D["screens"] = [(sh / f"{n}.png", c, k, 16.0) for n, c, k in [
        ("welcome", "Welcome screen: open a folder, clone a GitHub URL, drop a file, open the playground or replay a sample run.", "s_welcome"),
        ("run_stepper", "A finished project run: the ten-stage pipeline stepper, ranked hotspots, agent narration and the end-to-end card.", "s_run"),
        ("diff", "Diff view with the fidelity gutter: one decorator line added above the original function, the body untouched.", "s_diff"),
        ("three_way", "Three-way view: Python, PySub and generated C++, with fidelity notes in the gutter.", "s_three"),
        ("journey", "The function journey: sixteen steps from original source to splice.", "s_journey"),
        ("stage_rank", "Rank stage inspector: score breakdown per function.", "s_rank"),
        ("playground", "Playground: convert, compile and compare against CPython.", "s_play"),
        ("report", "Report page.", "s_report")]]
    try:
        import demo_journey
        D.update(demo_journey.make(F, D, pick, jobs))
    except ImportError:
        pass
    return D
