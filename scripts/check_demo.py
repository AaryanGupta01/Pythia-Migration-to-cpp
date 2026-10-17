#!/usr/bin/env python3
"""Self-check for demo/textlab: every function lands in its intended PYTHIA class.

For each demo function this extracts the PySub text the way the Studio will (module-level
literal constants inlined, same-module callee closure), runs the real compiler front end
(`pythia.cli.compile_source`) and asserts the intended classification. For the 'fixable'
functions it also runs the authored PySub rewrite against the original Python and checks the
results are identical. Finally it runs `main.py --small` and prints the CPython time share of
each demo function.

    python scripts/check_demo.py            # all checks + timing table
    python scripts/check_demo.py --no-run   # skip the main.py run
"""
import ast
import copy
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "demo", "textlab")
sys.path.insert(0, ROOT)
from pythia.cli import compile_source  # noqa: E402

# (file, function, intended outcome, note)
#   win_exact   verified, only exact fidelity sites
#   win_guarded verified/guarded: int + - * the interval analysis cannot prove safe stay guarded
#   fixable     typechecker rejects as written; authored rewrite typechecks and matches
#   no          not eligible (reason fragment checked where the compiler reports one)
#   boundary    compiles fine; ranker should decline (marshalling dominates)
TARGETS = [
    ("textlab/text/distance.py", "edit_distance", "win_guarded", ""),
    ("textlab/sim/nbody.py", "simulate_energy", "win_exact", ""),
    ("textlab/features/primes.py", "prime_square_sum", "win_guarded", "callee: is_prime"),
    ("textlab/ml/kmeans.py", "assign_clusters", "win_exact", "list[list[float]]"),
    ("textlab/text/bpe.py", "count_pairs", "win_guarded", "flat list[int] counts"),
    ("textlab/sim/montecarlo.py", "monte_carlo_pi", "win_guarded", ""),
    ("textlab/ml/knn.py", "knn_vote", "fixable", "comprehension/zip/sorted/tuple loop"),
    ("textlab/sim/life.py", "life_generations", "fixable", "tuple loop/ternary/enumerate/sum"),
    ("textlab/features/collatz.py", "collatz_longest", "fixable", "unannotated"),
    ("textlab/signal/window.py", "window_energy", "boundary", "5000-float list per call"),
    ("textlab/ml/embed.py", "normalize_rows", "no", "numpy"),
    ("textlab/ml/schedule.py", "make_lr_schedule", "no", "closure"),
    ("textlab/util/parse.py", "parse_number", "no", "dynamic typing"),
    ("textlab/util/parse.py", "summarize", "no", "*args"),
    ("textlab/text/corpus.py", "load_corpus", "no", "file I/O"),
    ("textlab/text/vocab.py", "Vocab.train", "no", "method of class"),
    ("textlab/util/rng.py", "Rng.next_float", "no", "method of class"),
    ("textlab/ml/kmeans.py", "KMeans.fit", "no", "method of class"),
    ("textlab/text/corpus.py", "CorpusBuilder.make_words", "no", "method of class"),
]


def read_module(rel):
    src = open(os.path.join(DEMO, rel), encoding="utf-8").read()
    return src, ast.parse(src)


def module_constants(tree):
    out = {}
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) \
                and isinstance(n.value, ast.Constant):
            out[n.targets[0].id] = n.value.value
    return out


class Inline(ast.NodeTransformer):
    def __init__(self, consts):
        self.consts = consts

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load) and node.id in self.consts:
            return ast.copy_location(ast.Constant(self.consts[node.id]), node)
        return node


def strip_doc(fn):
    if fn.body and isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) \
            and isinstance(fn.body[0].value.value, str):
        fn.body = fn.body[1:] or [ast.Pass()]
    return fn


def pysub_text(rel, name):
    """Standalone PySub text for module-level `name` plus its same-module callee closure."""
    _, tree = read_module(rel)
    consts = module_constants(tree)
    funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    todo, seen = [name], []
    while todo:
        f = todo.pop()
        if f in seen or f not in funcs:
            continue
        seen.append(f)
        for c in ast.walk(funcs[f]):
            if isinstance(c, ast.Call) and isinstance(c.func, ast.Name):
                todo.append(c.func.id)
    parts = []
    for f in reversed(seen):
        node = copy.deepcopy(funcs[f])
        node = Inline(consts).visit(node)
        parts.append(ast.unparse(strip_doc(node)))
    return "\n\n".join(parts) + "\n"


def compile_pysub(src):
    code, notes, diags, stats = compile_source(src, "<demo>")
    return code, notes, diags, stats


def load_func(rel, name, src=None):
    """Import the function from the demo package (or exec an override source)."""
    if src is not None:
        ns = {}
        exec(compile(src, "<rewrite>", "exec"), ns)
        return ns[name]
    mod = rel[:-3].replace("/", ".")
    sys.path.insert(0, DEMO)
    try:
        import importlib
        return getattr(importlib.import_module(mod), name)
    finally:
        sys.path.pop(0)


class Rng:
    def __init__(self, seed):
        self.s = seed

    def f(self):
        self.s = (self.s * 1103515245 + 12345) % 2147483648
        return self.s / 2147483648.0

    def i(self, n):
        return int(self.f() * n)


def equivalence_inputs(name):
    r = Rng(99)
    if name == "knn_vote":
        for _ in range(40):
            n, d = 5 + r.i(30), 1 + r.i(5)
            train = [[round(r.f(), 2) for _ in range(d)] for _ in range(n)]
            labels = [r.i(4) for _ in range(n)]
            yield (train, labels, [round(r.f(), 2) for _ in range(d)], 1 + r.i(7))
        # edge cases the replay oracle also probes: empty/ragged data, k = 0, negative k, k > n
        yield ([], [], [0.5], 3)
        yield ([[0.1, 0.2]], [1], [0.5, 0.5], 0)
        yield ([[0.1, 0.2], [0.3, 0.9], [0.5, 0.1]], [1, 2, 2], [0.5], -1)
        yield ([[0.1, 0.2], [0.3, 0.9], [0.5, 0.1]], [1, 2, 2], [0.4, 0.4, 0.4], 99)
        yield ([[0.1], [0.3, 0.9], [0.5, 0.1, 0.0]], [1, 2, 2], [0.4, 0.4], 2)
    elif name == "life_generations":
        for _ in range(25):
            h, w = 3 + r.i(9), 3 + r.i(9)
            yield ([[1 if r.f() < 0.4 else 0 for _ in range(w)] for _ in range(h)], r.i(6))
        yield ([[], [], [], [1, 5, 0, -18], [41, -1]], 0)          # ragged, gens = 0 (found by the oracle)
        yield ([[1, 0, 1], [0, 1]], 2)
        yield ([], 3)
        yield ([[1, 1, 1]], -2)
    elif name == "collatz_longest":
        for lim in (2, 3, 10, 97, 1000, 5000):
            yield (lim,)


def outcome(f, args):
    try:
        return ("value", f(*args))
    except Exception as e:                      # replay compares the exception class, not the message
        return ("raises", type(e).__name__)


def check_rewrite(rel, name, rewrites):
    final = rewrites[-1]
    errs = []
    for i, att in enumerate(rewrites):
        _, _, diags, _ = compile_pysub(att["pysub"])
        ok = not diags
        if ok != att["ok"]:
            errs.append(f"attempt {i + 1}: expected ok={att['ok']} but compiler says ok={ok}")
        if not ok and not att.get("error"):
            errs.append(f"attempt {i + 1}: missing error text (compiler: {diags[0]})")
    orig = load_func(rel, name)
    new = load_func(rel, name, final["pysub"])
    n = 0
    for args in equivalence_inputs(name):
        a, b = copy.deepcopy(args), copy.deepcopy(args)
        n += 1
        if outcome(orig, a) != outcome(new, b) or a != b:
            errs.append(f"rewrite differs from original on {args!r}: {outcome(orig, copy.deepcopy(args))} vs {outcome(new, copy.deepcopy(args))}")
            break
    return errs, n


def bench_cases():
    """(file, function, args factory, repeat, uses_authored_rewrite) for a by-hand speedup measurement."""
    r = Rng(5)
    letters = "abcdefghijklmnopqrstuvwxyz"
    words = ["".join(letters[r.i(26)] for _ in range(16)) for _ in range(400)]
    pts = [[r.f() * 10 for _ in range(4)] for _ in range(3000)]
    cents = [list(p) for p in pts[:16]]
    sig = [r.f() - 0.5 for _ in range(5000)]
    nb = [[r.f() for _ in range(100)] for _ in range(5)]
    grid = [[1 if r.f() < 0.3 else 0 for _ in range(80)] for _ in range(80)]
    train = pts[:900]
    return [
        ("textlab/text/distance.py", "edit_distance", [(words[i], words[i + 1]) for i in range(399)] * 3, False),
        ("textlab/sim/nbody.py", "simulate_energy", [(nb[0], nb[1], nb[2], nb[3], nb[4], 20, 0.01)], False),
        ("textlab/features/primes.py", "prime_square_sum", [(60000, 1000003)], False),
        ("textlab/ml/kmeans.py", "assign_clusters", [(pts, cents)] * 5, False),
        ("textlab/text/bpe.py", "count_pairs", [([r.i(60) for _ in range(60000)], 128)] * 5, False),
        ("textlab/sim/montecarlo.py", "monte_carlo_pi", [(500000, 12345)], False),
        ("textlab/ml/knn.py", "knn_vote", [(train, [i % 6 for i in range(900)], pts[900 + q], 5) for q in range(60)], True),
        ("textlab/sim/life.py", "life_generations", [(grid, 20)], True),
        ("textlab/features/collatz.py", "collatz_longest", [(60000,)], True),
        ("textlab/signal/window.py", "window_energy", [(sig, k, 128) for k in range(2000)], False),
    ]


def bench():
    """Build each function with pythia.libmode.build_library and compare against CPython on the same inputs."""
    import importlib.util
    import tempfile
    from pythia.libmode import build_library
    rewrites = json.load(open(os.path.join(DEMO, "..", "offline_cache", "authored_rewrites.json")))["functions"]
    out = tempfile.mkdtemp(prefix="demo-bench-")
    print(f"{'function':20s} {'py ms':>9s} {'c++ ms':>9s} {'speedup':>8s}  identical  build")
    for rel, name, calls, rewritten in bench_cases():
        src = rewrites[name]["attempts"][-1]["pysub"] if rewritten else pysub_text(rel, name)
        res = build_library(src, [name], out, modname=f"bench_{name}")
        if not res.ok:
            print(f"{name:20s} build failed: {res.error or res.diagnostics}")
            continue
        spec = importlib.util.spec_from_file_location(res.modname, res.so_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fast, slow = getattr(mod, name), load_func(rel, name)
        py_copies = [copy.deepcopy(a) for a in calls]       # copies are made outside the timed region
        t = time.perf_counter()
        want = [slow(*a) for a in py_copies]
        t_py = time.perf_counter() - t
        arg_copies = [copy.deepcopy(a) for a in calls]
        t = time.perf_counter()
        got = [fast(*a) for a in arg_copies]
        t_cpp = time.perf_counter() - t
        same = want == got
        print(f"{name:20s} {1000 * t_py:9.1f} {1000 * t_cpp:9.1f} {t_py / t_cpp:7.1f}x  {str(same):9s}  "
              f"{'cached' if res.cached else '%.1fs' % res.compile_s}")
    return 0


def main():
    if "--bench" in sys.argv:
        return bench()
    no_run = "--no-run" in sys.argv
    rewrites = json.load(open(os.path.join(DEMO, "..", "offline_cache", "authored_rewrites.json")))
    bad = 0
    print(f"{'function':34s} {'intended':12s} {'compiler verdict'}")
    for rel, name, intended, note in TARGETS:
        err = None
        verdict = ""
        if "." in name:                      # class methods: v1 handles module-level functions only
            _, tree = read_module(rel)
            cls, meth = name.split(".")
            found = any(isinstance(c, ast.ClassDef) and c.name == cls and
                        any(isinstance(m, ast.FunctionDef) and m.name == meth for m in c.body)
                        for c in tree.body)
            verdict = "method of class " + cls
            err = None if found else "method not found"
        elif intended == "no" and name in ("make_lr_schedule",):
            _, tree = read_module(rel)
            fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][0]
            nested = [n for n in ast.walk(fn) if isinstance(n, ast.FunctionDef) and n is not fn]
            verdict = "closure: nested def " + nested[0].name if nested else ""
            err = None if nested else "no nested def"
        else:
            src = pysub_text(rel, name)
            code, notes, diags, stats = compile_pysub(src)
            if intended in ("win_exact", "win_guarded", "boundary"):
                if diags:
                    err = f"expected to compile, got {diags[0]}"
                else:
                    sev = [n.severity for n in notes if n.line]   # ignore the global D7 (never-freed memory) note
                    g, d = sev.count("guarded"), sev.count("divergent")
                    el = (stats.elided, stats.kept) if stats else (0, 0)
                    verdict = f"compiles; {sev.count('exact')} exact {g} guarded {d} divergent; guards elided {el[0]}/{sum(el)}"
                    if intended == "win_guarded" and not (g or el[1]):
                        err = "expected guarded sites (int overflow traps) but found none"
                    if intended == "win_exact" and (g or el[1]):
                        err = "expected fully exact/elided but found guarded sites"
            elif intended == "fixable":
                if not diags and name != "collatz_longest":
                    err = "expected typechecker to reject the original"
                else:
                    verdict = f"rejected: {diags[0].msg[:60]}" if diags else "accepted"
                if name == "collatz_longest":      # no annotations -> parser rejects
                    verdict = f"rejected: {diags[0].msg[:60]}" if diags else "accepted"
                    err = None if diags else "expected rejection (missing annotations)"
                att = rewrites["functions"].get(name, {}).get("attempts")
                if err is None and not att:
                    err = "no authored rewrite in authored_rewrites.json"
                if err is None:
                    e2, n = check_rewrite(rel, name, att)
                    err = "; ".join(e2) or None
                    verdict += f" -> {len(att)} authored attempt(s), final compiles, identical on {n} inputs"
            elif intended == "no":
                if not diags:
                    err = "expected the compiler front end to reject it"
                else:
                    verdict = f"rejected: {diags[0].msg[:70]}"
        status = "FAIL" if err else "ok"
        if err:
            bad += 1
        print(f"{status:4s} {name:30s} {intended:12s} {verdict}" + (f"   <-- {err}" if err else ""))
    if no_run:
        return 1 if bad else 0

    # timing: run main.py --small in-process with wrappers to get per-function CPython time shares
    shares = {}
    sys.path.insert(0, DEMO)
    os.chdir(DEMO)
    import importlib
    for rel, name, intended, _ in TARGETS:
        if "." in name:
            continue
        mod = importlib.import_module(rel[:-3].replace("/", "."))
        orig = getattr(mod, name)

        def wrap(f, key):
            def w(*a, **k):
                t = time.perf_counter()
                try:
                    return f(*a, **k)
                finally:
                    shares[key] = shares.get(key, 0.0) + time.perf_counter() - t
            return w
        setattr(mod, name, wrap(orig, name))
    sys.argv = ["main.py", "--small"]
    import runpy
    t0 = time.perf_counter()
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        runpy.run_path(os.path.join(DEMO, "main.py"), run_name="__main__")
    total = time.perf_counter() - t0
    print(f"\nmain.py --small: {total:.1f} s (wrapped functions; plain run is a bit faster)")
    for rel, name, intended, _ in TARGETS:
        if name in shares:
            print(f"  {name:20s} {intended:12s} {shares[name]:6.2f} s  {100 * shares[name] / total:5.1f}%")
    wins = sum(v for k, v in shares.items() if dict((t[1], t[2]) for t in TARGETS)[k].startswith("win"))
    print(f"  verified wins together: {100 * wins / total:.0f}% of runtime")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
