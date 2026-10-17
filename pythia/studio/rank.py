"""Hotspot ranking.

score.total = base x eligibility_factor x benefit_norm x (1 - boundary_penalty)
  base              trace time share when a trace exists (else a static heuristic: loop depth/arith/size)
  expected_benefit  estimated compiled speedup of the compute (1.5x .. 40x from the static heuristic)
  boundary_penalty  marshal / (marshal + saving), where marshal = calls x (per-call + per-element cost x
                    (avg_arg_elems + avg_ret_elems)) and saving = traced seconds x (1 - 1/benefit)
A function whose predicted net saving (saving - marshal) is negative is `declined` with the numbers shown.

Calibration knobs (measure with the bench step and adjust): MARSHAL_S_PER_ELEM, CALL_OVERHEAD_S.
"""
from __future__ import annotations

import math
import re
from typing import List, Optional

from .models import FunctionRecord

MARSHAL_S_PER_ELEM = 4e-9       # pybind11 list/str element copy in + out
CALL_OVERHEAD_S = 1.5e-6        # fixed cost of one boundary crossing
ELIGIBILITY_FACTOR = {"verifiable": 1.0, "fixable": 0.6, "not_eligible": 0.0}
MAX_SPEEDUP = 40.0
COLD_SHARE = 0.002              # below 0.2% of the traced runtime a function is "cold": no build, no LLM call


def static_heuristic(m: dict) -> float:
    depth = min(int(m.get("loop_depth", 0)), 3) / 3.0
    arith = min(float(m.get("arith_density", 0.0)) / 0.4, 1.0)
    size = min(int(m.get("size_lines", 0)) / 40.0, 1.0)
    return round(0.45 * depth + 0.35 * arith + 0.20 * size, 4)


def expected_benefit(h: float) -> float:
    return round(1.5 + (MAX_SPEEDUP - 1.5) * h, 2)


def _profile_entry(rec: FunctionRecord, prof: Optional[dict]) -> Optional[dict]:
    if rec.trace:
        return rec.trace
    if not prof:
        return None
    per = prof.get("per_fn", prof)
    e = per.get(rec.id) if isinstance(per, dict) else None
    return e if isinstance(e, dict) else None


def _total_s(prof: Optional[dict], recs) -> float:
    if prof:
        for k in ("total_s", "_total_s"):
            if isinstance(prof.get(k), (int, float)) and prof[k] > 0:
                return float(prof[k])
        per = prof.get("per_fn", prof)
        s = sum(float(e.get("self_s") or 0) for e in per.values() if isinstance(e, dict))
        if s > 0:
            return s
    return sum(float((r.trace or {}).get("self_s") or 0) for r in recs)


def _has_container_params(rec: FunctionRecord) -> bool:
    m = re.search(r"def\s+\w+\s*\((.*?)\)\s*(?:->|:)", rec.sources.get("original") or "", re.S)
    return bool(m and re.search(r":\s*(list|dict|str|List|Dict)\b", m.group(1)))


def rank(records: List[FunctionRecord], trace_profile: Optional[dict] = None, emit=None) -> List[FunctionRecord]:
    have_trace = bool(trace_profile) or any(r.trace for r in records)
    total_s = _total_s(trace_profile, records) if have_trace else 0.0
    for r in records:
        notes: List[str] = []
        h = static_heuristic(r.metrics)
        eff = ELIGIBILITY_FACTOR.get(r.eligibility, 0.0)
        s_est = expected_benefit(h)
        e = _profile_entry(r, trace_profile) if have_trace else None
        share = None
        if e is not None:
            if r.trace is None:
                r.trace = dict(e)
            cum = float(e.get("cum_s") or 0.0)
            slf = float(e.get("self_s") or cum)
            share = e.get("share")
            if share is None:
                share = round(slf / total_s, 4) if total_s > 0 else 0.0
            r.trace.setdefault("share", share)
            r.share, r.calls = float(share), int(e.get("calls") or 0)
        base_trace = float(share) if (have_trace and share is not None) else (0.0 if have_trace else None)
        base = base_trace if base_trace is not None else h
        penalty, net = 0.0, None
        if e is not None and r.calls:
            calls = r.calls
            py_s = float(e.get("cum_s") or e.get("self_s") or 0.0)
            saving = py_s * (1 - 1 / s_est)
            elems = float(e.get("avg_arg_elems") or 0) + float(e.get("avg_ret_elems") or 0)
            marshal = calls * (CALL_OVERHEAD_S + elems * MARSHAL_S_PER_ELEM)
            net = saving - marshal
            penalty = marshal / (marshal + saving) if (marshal + saving) > 0 else 0.0
            notes.append(f"traced {calls} calls, {py_s:.3f}s in Python; est. {s_est:.1f}x on compute -> saves ~{saving:.3f}s")
            notes.append(f"boundary cost ~{marshal:.3f}s ({calls} calls x ~{elems:.0f} elements marshalled)")
        elif have_trace:
            notes.append("not called during the traced run -> no measured benefit")
        else:
            if _has_container_params(r) and r.metrics.get("loop_depth", 0) <= 1:
                penalty = 0.2
                notes.append("takes list/str/dict arguments with little looping: marshalling may eat the gain (no trace to confirm)")
            notes.append("no trace: ranked by static heuristic (loop depth, arithmetic density, size)")
        total = base * eff * (math.log2(max(s_est, 1.0)) / math.log2(MAX_SPEEDUP)) * (1.0 - penalty)
        if r.eligibility == "fixable":
            notes.append("needs a fix first (annotation or LLM rewrite): eligibility factor 0.6")
        elif r.eligibility == "not_eligible":
            notes.append(f"not eligible: {r.reason}")
        r.score = {"total": round(total, 4), "trace_share": base_trace, "static_heuristic": h,
                   "eligibility_factor": eff, "expected_benefit": s_est,
                   "boundary_penalty": round(penalty, 4), "basis": "trace" if have_trace else "static",
                   "notes": notes}
        declinable = r.eligibility == "verifiable" or (
            r.eligibility == "fixable" and r.private.get("fix_kind") == "annotations")
        if net is not None and net < 0 and declinable and r.status in ("pending", "fixable"):
            r.status = "declined"
            r.reason = (f"Declined: marshalling ~{marshal:.3f}s ({calls} calls x ~{elems:.0f} elements) exceeds "
                        f"the ~{saving:.3f}s of compute saved (est. {s_est:.1f}x on {py_s:.3f}s) -> net {net:+.3f}s")
            r.score["notes"].append(r.reason)

        # cold code: with a trace in hand, don't spend a build or an LLM call on functions that barely run
        if have_trace and (r.share or 0.0) < COLD_SHARE and r.eligibility != "not_eligible" \
                and r.status in ("pending", "fixable"):
            note = f"Cold: {(r.share or 0.0) * 100:.2f}% of the traced runtime ({r.calls or 0} calls)"
            r.private["cold"] = True
            if r.eligibility == "verifiable":
                r.status, r.reason = "declined", note + "; the saving would be negligible, so it is not compiled"
            else:
                r.reason = (r.reason or "needs a fix").rstrip(".") + f" [{note}; LLM rewrite skipped]"
            r.score["notes"].append(note)

    def key(r: FunctionRecord):
        cls = 2 if r.eligibility == "not_eligible" else 1 if r.status == "declined" else 0
        return (cls, -r.score["total"], -(r.share or 0.0), r.id)

    ordered = sorted(records, key=key)
    if emit:
        emit("rank.done", {"ranking": [{"id": r.id, "rank": i + 1, "score": r.score, "status": r.status,
                                        "reason": r.reason} for i, r in enumerate(ordered)]},
             stage="rank", caption=f"Ranked {len(ordered)} functions"
             + (" by traced time share" if have_trace else " by static heuristic"))
    return ordered
