"""
PYTHIA :: Driver
Owner: Member 1 (Vishal Vivek) -- pipeline wiring, diagnostics formatting

    python -m pythia.cli prog.py -o build/prog.c --fidelity
    python -m pythia.cli prog.py --run
"""
import argparse
import os
import subprocess
import sys
import shutil

from .parser import parse
from .typecheck import typecheck
from .lower import lower
from .optimize import elide_guards
from .emit_cpp import emit
from .lexer import LexError

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from .paths import RUNTIME as _RUNTIME  # noqa: E402  (wheel or checkout)
RUNTIME = str(_RUNTIME)


def render(diags, src_lines, path):
    out = []
    for d in sorted(diags, key=lambda x: (x.line, x.col)):
        out.append(f"{path}:{d.line}:{d.col}: {d.kind}: {d.msg}")
        if 1 <= d.line <= len(src_lines):
            line = src_lines[d.line - 1].rstrip("\n")
            out.append(f"    {line}")
            out.append("    " + " " * max(0, d.col - 1) + "^")
    return "\n".join(out)


def compile_source(src: str, path: str):
    """Returns (c_code, fidelity_notes, diagnostics, opt_stats)."""
    try:
        mod, syn_errs = parse(src, path)
    except LexError as e:
        from .parser import Diagnostic
        return None, [], [Diagnostic(e.msg, e.line, e.col, "SyntaxError")], None
    if syn_errs:
        return None, [], syn_errs, None
    tc, ty_errs = typecheck(mod, path)
    if ty_errs:
        return None, [], ty_errs, None
    notes = lower(mod, tc)
    opt_stats = elide_guards(mod)
    code = emit(mod, tc, os.path.basename(path))
    return code, notes, [], opt_stats


def lib_main(a, src: str) -> int:
    import json
    from .libmode import build_library
    funcs = [f.strip() for f in a.lib.split(",") if f.strip()]
    out_dir = a.out or os.path.join("build", "lib")
    r = build_library(src, funcs, out_dir, modname=a.modname, filename=a.source,
                      build=not a.no_build)
    if a.json:
        print(json.dumps(r.to_dict()))
    elif r.diagnostics:
        print(render([_Diag(d) for d in r.diagnostics],
                     src.splitlines(), a.source), file=sys.stderr)
        print(f"\n{len(r.diagnostics)} error(s); no output written.", file=sys.stderr)
    elif not r.ok:
        print(r.error, file=sys.stderr)
    else:
        print(f"wrote {r.cpp_path}")
        if r.so_path:
            print(f"built {r.so_path}" + (" (cache hit)" if r.cached else f" in {r.compile_s}s"))
        print("exposed: " + ", ".join(f"{e['name']}({', '.join(e['params'])}) -> {e['ret']}"
                                       for e in r.exposed))
    if r.diagnostics:
        return 2
    if not r.ok:
        return 3 if (r.error or "").startswith(("C++", "no C++")) else 2
    return 0


class _Diag:
    def __init__(self, d):
        self.line, self.col, self.kind, self.msg = d["line"], d["col"], d["kind"], d["msg"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="pythia",
                                 description="Typed Python-subset -> C transpiler")
    ap.add_argument("source")
    ap.add_argument("-o", "--out", help="output .c path")
    ap.add_argument("--fidelity", action="store_true",
                    help="print the Semantic Fidelity Report")
    ap.add_argument("--build", action="store_true", help="compile with c++17")
    ap.add_argument("--run", action="store_true", help="compile and execute")
    ap.add_argument("--emit-only", action="store_true", help="print C to stdout")
    ap.add_argument("--lib", help="library mode: comma-separated functions to expose "
                    "to Python (with --out <dir>)")
    ap.add_argument("--modname", help="library mode: extension module name")
    ap.add_argument("--no-build", action="store_true", help="library mode: write .cpp only")
    ap.add_argument("--json", action="store_true", help="library mode: print LibResult as JSON")
    a = ap.parse_args(argv)

    src = open(a.source, encoding="utf-8").read()
    if a.lib is not None:
        return lib_main(a, src)
    code, notes, errs, opt_stats = compile_source(src, a.source)

    if errs:
        print(render(errs, src.splitlines(), a.source), file=sys.stderr)
        print(f"\n{len(errs)} error(s); no output written.", file=sys.stderr)
        return 2

    if a.emit_only:
        sys.stdout.write(code)

    stem = os.path.splitext(os.path.basename(a.source))[0]
    outdir = os.path.dirname(a.out) if a.out else os.path.join("build", stem)
    os.makedirs(outdir or ".", exist_ok=True)
    cpath = a.out or os.path.join(outdir, stem + ".cpp")
    with open(cpath, "w", encoding="utf-8") as f:
        f.write(code)

    if a.fidelity:
        exact = sum(1 for n in notes if n.severity == "exact")
        guarded = sum(1 for n in notes if n.severity == "guarded")
        diverg = sum(1 for n in notes if n.severity == "divergent")
        print("=" * 68)
        print("SEMANTIC FIDELITY REPORT")
        print(f"  {exact} exact   {guarded} guarded   {diverg} divergent")
        total_ops = (opt_stats.elided + opt_stats.kept) if opt_stats else 0
        if total_ops:
            print(f"  guard elision: {opt_stats.elided}/{total_ops} int +/-/* "
                  f"sites proven safe by interval analysis and unguarded")
        print("=" * 68)
        for n in notes:
            print(n)
            print()

    if a.build or a.run:
        for fn in ("pyrt.cpp", "pyrt.hpp"):
            shutil.copy(os.path.join(RUNTIME, fn), outdir)
        binpath = os.path.join(outdir, stem)
        cc = ["c++", "-std=c++17", "-O2", "-flto", "-I", outdir, cpath,
              os.path.join(outdir, "pyrt.cpp"), "-o", binpath]
        r = subprocess.run(cc, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr, file=sys.stderr)
            print("internal error: generated C++ failed to compile", file=sys.stderr)
            return 3
        if a.run:
            return subprocess.run([binpath]).returncode

    if not a.emit_only:
        print(f"wrote {cpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
