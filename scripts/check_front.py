#!/usr/bin/env python3
"""Throwaway assert-based check for the Studio analyzer front half (ingest, scan, annotate, rank, fixer).
Run (WSL):  ~/pythia-venv/bin/python scripts/check_front.py
"""
import base64
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pythia.studio import fixer as fixer_mod                                   # noqa: E402
from pythia.studio.annotate import annotate, resolve_type                      # noqa: E402
from pythia.studio.ingest import ingest                                        # noqa: E402
from pythia.studio.llm import OfflineCache, ScriptedClient, make_client, write_cache_entry  # noqa: E402
from pythia.studio.pysub_rules import check_source, rules_text                 # noqa: E402
from pythia.studio.rank import rank                                            # noqa: E402
from pythia.studio.scan import extract_pysub, scan_workspace                   # noqa: E402

PROJECT = '''\
import numpy as np
from typing import List
from other.helpers import external

MAXLEN = 50
SCALE = 2 * 3
NAMES = ["a", "b"]


def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance."""
    n = len(a)
    m = len(b)
    prev: list[int] = []
    for j in range(m + 1):
        prev.append(j)
    for i in range(1, n + 1):
        cur: list[int] = [i]
        for j in range(1, m + 1):
            c = 1
            if a[i - 1] == b[j - 1]:
                c = 0
            cur.append(min(min(prev[j] + 1, cur[j - 1] + 1), prev[j - 1] + c))
        prev = cur
    return prev[m] + MAXLEN - MAXLEN


def scale(x: int) -> int:
    return x * SCALE


def scaled_sum(xs: List[int]) -> int:
    t = 0
    for x in xs:
        t += scale(x)
    return t


def calls_fixable_helper(n: int) -> int:
    return unannotated(n, 2) + 1


def unannotated(a, b):
    s = 0
    for i in range(a):
        s += i * b
    return s


def multiline(
    a,
    xs: list,
    b,
):
    return a


def listcomp(xs: list[int]) -> int:
    ys = [x * x for x in xs]
    t = 0
    for y in ys:
        t += y
    return t


def enumerated(xs: list[int]) -> int:
    t = 0
    for i, x in enumerate(xs):
        t += i * x
    return t


def ternary(a: int, b: int) -> int:
    return a if a > b else b


def with_numpy(xs: list[float]) -> float:
    return np.sum(xs)


def closure(n: int) -> int:
    def inner(k: int) -> int:
        return k + n
    return inner(3)


def file_io(p: str) -> int:
    f = open(p)
    return len(f.read())


def retype(n: int) -> int:
    x = 1
    x = "s"
    return n


def reads_global(n: int) -> int:
    return n + len(NAMES)


def other_module(n: int) -> int:
    return external(n)


def star(*args: int) -> int:
    return 0


class Box:
    def get(self, x: int) -> int:
        return x
'''


def ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok:", msg)


def emitter(log):
    return lambda t, d, stage=None, caption=None: log.append((t, d))


def main():
    home = Path(tempfile.mkdtemp(prefix="pythia_home_"))
    src = Path(tempfile.mkdtemp(prefix="pythia_proj_"))

    print("[ingest]")
    (src / "pkg").mkdir()
    (src / "pkg" / "m.py").write_text(PROJECT)
    (src / "broken.py").write_text("def (:\n")
    (src / ".gitignore").write_text("ignored.py\nbuild_out/\n")
    (src / "ignored.py").write_text("x = 1\n")
    (src / "venv").mkdir()
    (src / "venv" / "v.py").write_text("x = 1\n")
    (src / "big.dat").write_bytes(b"0" * (5 * 1024 * 1024 + 1))
    log = []
    ws = ingest({"kind": "folder", "path": str(src)}, home, emitter(log))
    skipped = {s["path"]: s["reason"] for s in ws.skipped}
    ok(ws.py_files == ["broken.py", "pkg/m.py"], f"py files indexed: {ws.py_files}")
    ok("ignored.py" in skipped and "venv/" in skipped and "big.dat" in skipped, f"skips recorded: {skipped}")
    ok((ws.original / "pkg/m.py").read_text() == (ws.work / "pkg/m.py").read_text(), "original == work")
    ok([t for t, _ in log][-1] == "ingest.done" and any(t == "ingest.progress" for t, _ in log), "progress+done events")
    ok((src / "ignored.py").exists() and (src / "big.dat").exists(), "user's source untouched")

    ws_s = ingest({"kind": "snippet", "code": "def f(x: int) -> int:\n    return x\n", "name": "snip"}, home)
    ok(ws_s.py_files == ["snip.py"], "snippet -> snip.py")
    ws_f = ingest({"kind": "file", "filename": "up.py", "content_b64": base64.b64encode(b"x = 1\n").decode()}, home)
    ok(ws_f.py_files == ["up.py"], "file(b64) -> up.py")

    repo = Path(tempfile.mkdtemp(prefix="pythia_repo_"))
    g = ["git", "-c", "user.email=a@b.c", "-c", "user.name=t"]
    subprocess.run(g + ["init", "-q", str(repo)], check=True)
    (repo / "a.py").write_text("def f(x: int) -> int:\n    return x + 1\n")
    subprocess.run(g + ["-C", str(repo), "add", "."], check=True)
    subprocess.run(g + ["-C", str(repo), "commit", "-q", "-m", "init"], check=True)
    ws_g = ingest({"kind": "git", "url": repo.as_uri()}, home)
    ok(ws_g.py_files == ["a.py"] and not (ws_g.original / ".git").exists(), "git file:// clone -> workspace (no .git)")

    print("[scan]")
    ev = []
    recs = scan_workspace(ws, emitter(ev))
    by = {r.name if "." not in r.qualname else r.qualname: r for r in recs}
    ok(ev[-1][0] == "scan.done" and sum(t == "scan.function" for t, _ in ev) == len(recs), "scan events")
    ok(not any(r.file == "broken.py" for r in recs), "unparsable file skipped (no crash)")
    ok(any(t == "log" for t, _ in ev), "skip was logged")
    for n in ("edit_distance", "scale", "scaled_sum"):
        ok(by[n].eligibility == "verifiable" and by[n].status == "pending" and by[n].reason is None, f"{n} verifiable")
    for n, frag in [("unannotated", "missing annotations"), ("multiline", "missing annotations"),
                    ("listcomp", "list comprehension"), ("enumerated", "enumerate"), ("ternary", "conditional expression"),
                    ("calls_fixable_helper", "unannotated")]:
        ok(by[n].eligibility == "fixable" and by[n].status == "fixable" and frag in by[n].reason, f"{n} fixable: {by[n].reason}")
    for n, frag in [("with_numpy", "numpy"), ("closure", "closure"), ("file_io", "file I/O"),
                    ("retype", "changes type from int to str"), ("reads_global", "NAMES"),
                    ("other_module", "another module"), ("star", "*args"), ("Box.get", "method of class Box")]:
        ok(by[n].eligibility == "not_eligible" and by[n].status == "not_eligible" and frag in by[n].reason,
           f"{n} not eligible: {by[n].reason}")
    r = by["edit_distance"]
    ok((r.line, r.end_line, r.col) == (10, 25, 0) and r.sources["original"].startswith("def edit_distance")
       and r.sources["original"].rstrip().endswith("return prev[m] + MAXLEN - MAXLEN"), "location + verbatim source")
    ok(r.metrics["loop_depth"] == 2 and r.metrics["uses_globals"] == ["MAXLEN"] and "len" in r.metrics["calls"]
       and r.metrics["size_lines"] == 16, f"metrics {r.metrics}")
    ok(by["with_numpy"].metrics["imports"] == ["numpy"], "imports metric")
    ok(any("unexpected" in d["msg"] or "expected" in d["msg"] for d in by["unannotated"].diagnostics),
       "diagnostics carry typechecker/parse errors")

    print("[extract_pysub]")
    e = extract_pysub(by["edit_distance"], ws)
    lines = e.source.split("\n")
    ok(e.ok and lines[0].startswith("def edit_distance") and e.uses == ["MAXLEN"], "ok, starts at line 1, const used")
    ok('"""' not in e.source and "MAXLEN" not in e.source, "docstring stripped, const inlined")
    ok(lines[15].strip() == "return prev[m] + 50 - 50", "target line numbering preserved")
    e = extract_pysub(by["scaled_sum"], ws)
    ok(e.ok and e.helpers == ["scale"] and "list[int]" in e.source and "List" not in e.source and "x * 6" in e.source,
       "callee pulled in, typing.List normalised, SCALE inlined")
    ok(extract_pysub(by["listcomp"], ws).diagnostics, "unfixed function yields diagnostics")

    print("[annotate]")
    t = {"calls": 10, "arg_types": ["int", "int"], "ret_type": "int"}
    a = annotate(by["unannotated"], t)
    ok(a is not None and a.split("\n")[0] == "def unannotated(a: int, b: int) -> int:", f"annotated: {a.splitlines()[0]}")
    ok(len(a.split("\n")) == len(by["unannotated"].sources["original"].split("\n")), "line count preserved")
    ok(extract_pysub(by["unannotated"], ws, annotated_src=a).ok, "annotated source typechecks")
    a = annotate(by["unannotated"], {"arg_types": ["int", "int|float"], "ret_type": "int|float"})
    ok(a.split("\n")[0] == "def unannotated(a: int, b: float) -> float:", "int/float promotion -> float")
    a = annotate(by["multiline"], {"arg_types": ["int", "list[list[int]]", "float"], "ret_type": "int"})
    ok(a is not None and "    a: int," in a and "    xs: list[list[int]]," in a and "    b: float," in a and ") -> int:" in a
       and len(a.split("\n")) == len(by["multiline"].sources["original"].split("\n")), f"multi-line signature handled")
    ok(annotate(by["edit_distance"], {"arg_types": ["str", "str"], "ret_type": "int"}) is None, "fully annotated -> None")
    ok(annotate(by["unannotated"], None) is None, "no trace -> None")
    ok(resolve_type("dict[str, int|float]") == "dict[str, float]" and resolve_type("list[bool]") == "list[bool]"
       and resolve_type("tuple[int,int]") is None and resolve_type("list[?]") is None, "type string resolution")

    print("[rank]")
    prof = {"total_s": 10.0}
    pr = {
        by["edit_distance"].id: {"calls": 1200, "cum_s": 6.0, "self_s": 6.0, "avg_arg_elems": 40.0, "avg_ret_elems": 1.0},
        by["scaled_sum"].id: {"calls": 300, "cum_s": 1.0, "self_s": 0.9, "avg_arg_elems": 200.0, "avg_ret_elems": 1.0},
        # tiny compute, huge arguments, called very often -> marshalling dominates
        by["scale"].id: {"calls": 2_000_000, "cum_s": 0.4, "self_s": 0.4, "avg_arg_elems": 5000.0, "avg_ret_elems": 5000.0},
        by["unannotated"].id: {"calls": 50, "cum_s": 2.0, "self_s": 2.0, "avg_arg_elems": 1.0, "avg_ret_elems": 1.0},
    }
    prof.update(pr)
    rv = rank(list(recs), prof, emitter(ev))
    ok(ev[-1][0] == "rank.done" and len(ev[-1][1]["ranking"]) == len(recs), "rank.done emitted for all")
    ok(rv[0].name == "edit_distance" and rv[0].score["basis"] == "trace" and abs(rv[0].share - 0.6) < 1e-6,
       f"hot verifiable ranks first (share {rv[0].share})")
    sc = by["scale"]
    ok(sc.status == "declined" and "marshalling" in sc.reason and "saved" in sc.reason, f"boundary case declined: {sc.reason}")
    ok(sc.score["boundary_penalty"] > 0.5 and sc.score["notes"], "declined score breakdown filled")
    ok(by["unannotated"].status == "fixable", "annotation-fixable hot function not declined")
    names = [r.name for r in rv]
    ok(names.index("scale") > names.index("scaled_sum") and all(r.eligibility == "not_eligible" for r in rv[-8:]),
       "order: eligible, then declined, then not eligible")
    ok(by["with_numpy"].score["eligibility_factor"] == 0.0 and by["with_numpy"].score["total"] == 0.0, "not eligible scores 0")
    for r in recs:  # reset for static ranking
        r.trace, r.share, r.calls = None, None, None
        if r.status == "declined":
            r.status, r.reason = "pending", None
    rs = rank(list(recs), None)
    ok(rs[0].name == "edit_distance" and rs[0].score["basis"] == "static", f"static heuristic ranks nested-loop first ({rs[0].name})")

    print("[fixer]")
    rec = by["listcomp"]
    rec.trace = {"arg_types": ["list[int]"], "ret_type": "int"}
    bad = "```python\ndef listcomp(xs: list[int]) -> int:\n    return sum([x * x for x in xs])\n```"
    good = ("Here you go:\n```python\ndef listcomp(xs: list[int]) -> int:\n    t = 0\n    for x in xs:\n"
            "        t += x * x\n    return t\n```")
    fake = ScriptedClient([bad, good])
    ev2 = []
    res = fixer_mod.Fixer(fake, offline=False).fix(rec, ws, emitter(ev2))
    ok(res.ok and len(res.attempts) == 2 and not res.attempts[0]["ok"] and res.attempts[1]["ok"], "attempt 1 rejected, attempt 2 passes")
    ok("sum" in res.attempts[0]["error"] and rec.rewrites == res.attempts and rec.line_map_ok is False, "typechecker error recorded")
    ok("sum" in fake.calls[1]["messages"][-1]["content"], "diagnostics fed back to the LLM")
    types = [t for t, _ in ev2]
    ok(types.count("fix.attempt") == 2 and types[-1] == "fix.done" and "agent.step" in types, f"events {types}")
    ok(check_source(res.pysub) == [], "final PySub typechecks")
    # three failures -> not ok with reason
    rec2 = by["enumerated"]
    rec2.sources["pysub"] = None
    res = fixer_mod.Fixer(ScriptedClient([bad.replace("listcomp", "enumerated")] * 3)).fix(rec2, ws)
    ok(not res.ok and len(res.attempts) == 3 and "3 attempt" in res.reason, f"3 failures -> {res.reason[:70]}")
    # disabled
    res = fixer_mod.Fixer(None).fix(by["ternary"], ws)
    ok(res.disabled and not res.ok, "no client -> disabled")
    # offline cache round trip
    cache = Path(tempfile.mkdtemp(prefix="pythia_cache_"))
    src_after = by["ternary"].sources["original"]
    write_cache_entry(cache, src_after, 1,
                      "```python\ndef ternary(a: int, b: int) -> int:\n    if a > b:\n        return a\n    return b\n```")
    cl = make_client("claude-sonnet-5-5", cache)
    ok(isinstance(cl, OfflineCache), "make_client(offline dir) -> OfflineCache")
    ev3 = []
    res = fixer_mod.Fixer(cl, offline=True, cache_dir=cache).fix(by["ternary"], ws, emitter(ev3))
    ok(res.ok and res.attempts[0]["source"] == "cache", "offline cache entry served")
    res = fixer_mod.Fixer(cl, offline=True).fix(by["enumerated"], ws)
    ok(not res.ok and "no cached LLM response" in res.reason, "cache miss -> clear reason")
    import os
    os.environ.pop("ANTHROPIC_API_KEY", None)
    ok(make_client("claude-sonnet-5-5") is None, "no key, not offline -> None")
    ok(fixer_mod.cache_key("x", 1) != fixer_mod.cache_key("x", 2), "cache_key depends on attempt")

    print("[rules]")
    rt = rules_text()
    ok(".append()" in rt and "get" in rt and "ZeroDivisionError" in rt and "range" in rt, "rules text extracted from compiler source")
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
