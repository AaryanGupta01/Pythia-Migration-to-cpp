#!/usr/bin/env python3
"""Collects repo-derived facts (LOC, test counts, git stats, symbol line numbers) into evidence/facts.json.
Run from anywhere: python collect_facts.py"""
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "evidence" / "facts.json"


def loc(path: Path) -> int:
    return sum(1 for l in path.read_text(encoding="utf-8", errors="replace").splitlines() if l.strip())


def group(globs):
    n, files = 0, []
    for g in globs:
        for p in sorted(ROOT.glob(g)):
            if p.is_file() and "__pycache__" not in str(p):
                c = loc(p)
                n += c
                files.append((p.relative_to(ROOT).as_posix(), c))
    return {"loc": n, "files": files}


def git(*a):
    return subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True, encoding="utf-8").stdout


F = {}
F["loc"] = {
    "frontend": group(["pythia/lexer.py", "pythia/parser.py", "pythia/parse_ext.py", "pythia/parse_iter.py",
                       "pythia/parse_types.py", "pythia/ast_nodes.py"]),
    "types": group(["pythia/typecheck.py", "pythia/types_ext.py", "pythia/classes_ext.py", "pythia/builtins_ext.py",
                    "pythia/tuples.py", "pythia/comprehensions.py"]),
    "lower_opt": group(["pythia/lower.py", "pythia/optimize.py"]),
    "emit_lib": group(["pythia/emit_c.py", "pythia/emit_ext.py", "pythia/lib_ext.py", "pythia/libmode.py",
                       "pythia/classes_lib.py", "pythia/toolchain.py", "pythia/cli.py", "pythia/driver.py", "pythia/stages.py"]),
    "convert": group(["pythia/convert/*.py"]),
    "studio_backend": group(["pythia/studio/*.py", "pythia/studio/server/app.py", "pythia/studio/server/bus.py",
                             "pythia/studio/server/playground.py"]),
    "studio_mock": group(["pythia/studio/server/mock_*.py"]),
    "runtime": group(["runtime/pyrt.hpp", "runtime/pyrt.cpp", "runtime/pydict.hpp", "runtime/pyset.hpp",
                      "runtime/pyrt_bridge.hpp", "runtime/pythia_accel/*.py"]),
    "runtime_c11_legacy": group(["runtime/pyrt.c", "runtime/pyrt.h"]),
    "web": group(["studio/web/src/*.ts", "studio/web/src/*.tsx", "studio/web/src/lib/*", "studio/web/src/mock/*"]),
    "tools_scripts": group(["tools/*.py", "scripts/*.py"]),
    "tests_pos": group(["tests/positive/*.py"]),
    "tests_neg": group(["tests/negative/*.py"]),
    "packaging": group(["packaging/windows/*"]),
}
F["tests"] = {
    "positive": len(list((ROOT / "tests/positive").glob("*.py"))),
    "negative": len(list((ROOT / "tests/negative").glob("*.py"))),
    "basics": len(re.findall(r"^#@@ ", "".join(p.read_text(encoding="utf-8") for p in (ROOT / "scripts/basics").glob("*.py")), re.M)),
    "snippets": len(re.findall(r"^#@@ ", "".join(p.read_text(encoding="utf-8") for p in (ROOT / "scripts/snippets").glob("*.py")), re.M)),
}
F["git"] = {
    "commits": int(git("rev-list", "--count", "HEAD").strip()),
    "head": git("rev-parse", "--short", "HEAD").strip(),
    "shortlog": git("shortlog", "-sn", "HEAD").strip().splitlines(),
    "first": git("log", "--reverse", "--format=%h %ad %an", "--date=short").splitlines()[0],
    "last": git("log", "-1", "--format=%h %ad", "--date=short").strip(),
}

SYMS = {
    "lexer": ("pythia/lexer.py", [r"class Lexer", r"    def tokenize"]),
    "parser": ("pythia/parser.py", [r"class Parser", r"    def parse_block", r"    def parse_expr", r"    def parse_atom"]),
    "ast": ("pythia/ast_nodes.py", [r"class Node"]),
    "typecheck": ("pythia/typecheck.py", [r"def widens_to", r"def join", r"class Scope", r"class TypeChecker", r"    def check_expr", r"    def synth\(", r"    def synth_call", r"    def check_assign"]),
    "lower": ("pythia/lower.py", [r"class FidelityNote", r"class Lowerer", r"    def check_binop", r"def lower"]),
    "optimize": ("pythia/optimize.py", [r"class GuardElider", r"    def eval", r"    def block", r"def elide_guards"]),
    "emit": ("pythia/emit_c.py", [r"class Emitter", r"    def emit_module"]),
    "libmode": ("pythia/libmode.py", [r"def build_library", r"def generate"]),
    "cli": ("pythia/cli.py", [r"def compile_source", r"def main"]),
    "convert": ("pythia/convert/__init__.py", [r"def to_pysub", r"class ConvertResult"]),
    "infer": ("pythia/convert/infer.py", [r"class Engine", r"def infer"]),
    "types": ("pythia/convert/types.py", [r"def join"]),
    "search": ("pythia/convert/search.py", [r"def best_assignment"]),
    "observe": ("pythia/convert/observe.py", [r"def "]),
    "scan": ("pythia/studio/scan.py", [r"def scan_workspace", r"def extract_pysub", r"def analyze"]),
    "pipeline": ("pythia/studio/pipeline.py", [r"class Pipeline", r"    def _run", r"    def do_trace", r"    def do_rank", r"    def do_fix", r"    def fix_one", r"    def do_compile", r"    def do_verify", r"    def do_bench", r"    def do_splice"]),
    "rank": ("pythia/studio/rank.py", [r"def static_heuristic", r"MARSHAL_S_PER_ELEM", r"COLD_SHARE"]),
    "replay": ("pythia/studio/replay.py", [r"MIN_CALLS", r"def "]),
    "worker": ("pythia/studio/_replay_worker.py", [r"def "]),
    "tracer": ("pythia/studio/_tracer_boot.py", [r"sys\.monitoring|mon = "]),
    "splice": ("pythia/studio/splice.py", [r"GUARD", r"DECORATOR"]),
    "app": ("pythia/studio/server/app.py", [r"def create_app|app = FastAPI"]),
    "bus": ("pythia/studio/server/bus.py", [r"class "]),
    "launcher": ("pythia/studio/launcher.py", [r"def main", r"def _probe"]),
    "oracle": ("tools/oracle.py", [r"def run_positive", r"def run_negative", r"def build_and_run"]),
    "fuzz": ("tools/fuzz.py", [r"def "]),
    "stress": ("scripts/stress.py", [r"def "]),
    "pyrt": ("runtime/pyrt.hpp", [r"struct PyStr|class PyStr", r"py_floordiv|inline int64_t py_floordiv", r"PyList"]),
    "bridge": ("runtime/pyrt_bridge.hpp", [r"template"]),
    "pydict": ("runtime/pydict.hpp", [r"class PyDict|struct PyDict"]),
    "pyset": ("runtime/pyset.hpp", [r"class PySet|struct PySet"]),
}
lines = {}
for k, (rel, pats) in SYMS.items():
    p = ROOT / rel
    txt = p.read_text(encoding="utf-8", errors="replace").splitlines()
    d = {}
    for pat in pats:
        for i, l in enumerate(txt, 1):
            if re.match(pat, l) or re.search(pat, l) and pat.startswith("("):
                d[pat.strip()] = i
                break
        else:
            for i, l in enumerate(txt, 1):
                if re.search(pat, l):
                    d[pat.strip()] = i
                    break
    lines[k] = {"file": rel, "lines": d}
F["symbols"] = lines
OUT.write_text(json.dumps(F, indent=1))
tot = {k: v["loc"] for k, v in F["loc"].items()}
print(json.dumps({"loc": tot, "tests": F["tests"], "git": {k: F["git"][k] for k in ("commits", "head", "shortlog")}}, indent=1))
