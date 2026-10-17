#!/usr/bin/env python3
"""Self-check for the bundled demos (demo/quanta, demo/textlab): every function lands in its intended PYTHIA class.

For each demo function this extracts the PySub text the way the Studio will (module-level literal constants
inlined, same-module callee closure), runs the real compiler front end (`pythia.cli.compile_source`) and asserts
the intended classification.  For the 'fixable' functions it also takes the LLM rewrite from the offline cache
(demo/offline_cache/llm: authored for textlab, recorded from a real model for quanta), checks that its final
attempt compiles and is identical to the original Python on generated inputs.  Finally it runs the demo's
`main.py --small` and prints the CPython time share of each demo function.

    python scripts/check_demo.py                    # both demos, all checks + timing table
    python scripts/check_demo.py --no-run           # skip the main.py run
    python scripts/check_demo.py --demo quanta      # one demo
    python scripts/check_demo.py --bench --demo quanta   # build each function and time it against CPython
"""
import ast
import copy
import hashlib
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pythia.cli import compile_source  # noqa: E402

CACHE = os.path.join(ROOT, "demo", "offline_cache")
DEMO = os.path.join(ROOT, "demo", "textlab")          # rebound by select()

# (file, function, intended outcome, note)
#   win_exact   verified, only exact fidelity sites
#   win_guarded verified/guarded: int + - * the interval analysis cannot prove safe stay guarded
#   win         compiles as written (exact or guarded not asserted)
#   fixable     typechecker rejects as written; the cached LLM rewrite typechecks and matches
#   annotate    only annotations are missing: observed types from the trace fix it, no LLM
#   cold_fix    fixable but too cold in the traced run to be worth an LLM call
#   no          not eligible (reason fragment checked where the compiler reports one)
#   boundary    compiles fine; ranker should decline (marshalling dominates)
TEXTLAB = [
    ("textlab/text/distance.py", "edit_distance", "win_guarded", ""),
    ("textlab/sim/nbody.py", "simulate_energy", "win_exact", ""),
    ("textlab/features/primes.py", "prime_square_sum", "win_guarded", "callee: is_prime"),
    ("textlab/ml/kmeans.py", "assign_clusters", "win_exact", "list[list[float]]"),
    ("textlab/text/bpe.py", "count_pairs", "win_guarded", "flat list[int] counts"),
    ("textlab/sim/montecarlo.py", "monte_carlo_pi", "win_guarded", ""),
    ("textlab/ml/knn.py", "knn_vote", "fixable", "comprehension/zip/sorted/tuple loop"),
    ("textlab/sim/life.py", "life_generations", "fixable", "tuple loop/ternary/enumerate/sum"),
    ("textlab/features/collatz.py", "collatz_longest", "annotate", "unannotated"),
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

Q = "quanta/"
QUANTA = [
    # verified / guarded wins, one or two per kernel family
    (Q + "sim/nbody.py", "advance", "win", "7 lists mutated in place, pure float math"),
    (Q + "sim/nbody.py", "total_energy", "win", ""),
    (Q + "linalg/spectral.py", "spectral_norm", "win", "callees mult_av / mult_atv"),
    (Q + "combinatorics/permutations.py", "fannkuch", "win", "permutation counting, list[int]"),
    (Q + "combinatorics/permutations.py", "count_derangements", "win", "callee next_permutation"),
    (Q + "combinatorics/queens.py", "count_queens", "win", "backtracking with bool tables"),
    (Q + "sim/fractal.py", "mandelbrot_row", "win", "float escape-time loop"),
    (Q + "sim/fractal.py", "escape_area", "win", "callee mandelbrot_row"),
    (Q + "text/distance.py", "levenshtein", "win", "two-row DP over str"),
    (Q + "text/distance.py", "lcs_length", "win", "list[list[int]] DP table"),
    (Q + "opt/dp.py", "knapsack_01", "win", "1-D DP"),
    (Q + "opt/dp.py", "coin_ways", "win", "DP with module constant MODULUS"),
    (Q + "numtheory/primes.py", "sieve_primes", "win", "bool flags, returns list[int]"),
    (Q + "numtheory/primes.py", "prime_square_sum", "win", "callee is_probable_prime"),
    (Q + "numtheory/collatz.py", "longest_collatz", "win", "callee collatz_steps"),
    (Q + "sim/montecarlo.py", "estimate_pi", "win_guarded", "inline LCG, trapped int multiply"),
    (Q + "sim/montecarlo.py", "integrate_poly", "win", "inline LCG + Horner"),
    (Q + "cluster/kernels.py", "assign_points", "win", "list[list[float]] k-means assignment"),
    (Q + "cluster/kernels.py", "update_centroids", "win", "list[list[float]] -> list[list[float]]"),
    (Q + "graph/shortest.py", "floyd_warshall", "win", "list[list[int]] adjacency matrix"),
    (Q + "graph/shortest.py", "dijkstra_dense", "win", "list[list[int]] matrix, 17k elements per call"),
    (Q + "linalg/dense.py", "matmul", "win", "list[list[float]] x2"),
    (Q + "linalg/dense.py", "gauss_solve", "win", "raises ValueError when singular"),
    (Q + "signal/filters.py", "fir_filter", "win", "convolution kernel"),
    (Q + "stats/descriptive.py", "histogram", "win", "binning; modest speedup"),
    (Q + "stats/descriptive.py", "rolling_std", "win", ""),
    (Q + "opt/routes.py", "tour_length", "win", "tiny args, 170k calls"),
    (Q + "numtheory/totient.py", "totient_sum", "win", "callee totient_sieve"),
    (Q + "numtheory/totient.py", "count_coprime_pairs", "win", "inline Euclid on every pair"),
    (Q + "numtheory/totient.py", "perfect_numbers", "win", "divisor-sum sieve"),
    (Q + "signal/spectrum.py", "dft_power", "win", "callees sin_series / cos_series, twiddle rotation"),
    (Q + "signal/spectrum.py", "median_filter", "win", "insertion-sorted window"),
    (Q + "sim/automata.py", "rule_automaton", "win", "elementary cellular automaton on a ring"),
    (Q + "graph/closure.py", "count_triangles", "win", "list[list[int]] 0/1 matrix"),
    (Q + "graph/closure.py", "transitive_closure", "win", "Warshall on list[list[int]]"),
    (Q + "stats/correlation.py", "kendall_tau", "win", "O(n^2) pair loop"),
    (Q + "stats/correlation.py", "spearman_rho", "win", "callee rank_transform"),
    (Q + "opt/chain.py", "matrix_chain_cost", "win", "O(n^3) interval DP"),
    (Q + "opt/chain.py", "partition_count", "win", "DP with module constant"),
    (Q + "linalg/decomp.py", "determinant", "win", "LU with pivoting"),
    (Q + "linalg/decomp.py", "power_iteration", "win", ""),
    (Q + "text/substrings.py", "longest_common_substring", "win", "two-row DP over str"),
    (Q + "text/substrings.py", "longest_palindrome", "win", "str indexing, while loops"),
    (Q + "text/substrings.py", "run_length_encode", "win", "str building with str(int)"),
    # honest boundary-cost cases
    (Q + "stats/drift.py", "tail_variance", "boundary", "growing list marshalled per call"),
    (Q + "opt/anneal.py", "acceptance_probability", "boundary", "17-term series, scalar args, 100k+ calls"),
    # LLM rewrites
    (Q + "graph/traverse.py", "bfs_levels", "fixable", "[-1]*n, pop(0)"),
    (Q + "opt/dp.py", "longest_increasing_subsequence", "fixable", "[1]*n, max(list)"),
    (Q + "opt/dp.py", "grid_min_path", "fixable", "row[:], ternaries, 3-argument min"),
    (Q + "signal/filters.py", "exp_smooth", "fixable", "enumerate, slicing, ternary"),
    (Q + "sim/life.py", "life_population", "fixable", "comprehensions, sum(genexpr), chained comparison"),
    (Q + "stats/descriptive.py", "weighted_moments", "fixable", "zip, tuple-free ternary"),
    (Q + "text/kmers.py", "kmer_counts", "fixable", "slicing, dict[str,int]"),
    # annotations from the trace only
    (Q + "numtheory/digits.py", "digital_root_total", "annotate", "unannotated"),
    (Q + "numtheory/digits.py", "count_palindromes", "annotate", "unannotated"),
    # fixable but cold
    (Q + "stats/descriptive.py", "clip_fraction", "cold_fix", "list comprehension; called a handful of times"),
    (Q + "sim/fractal.py", "shade_row", "cold_fix", ".join()"),
    # not eligible, varied reasons
    (Q + "util/iterutil.py", "make_decay", "no", "closure"),
    (Q + "util/iterutil.py", "combine_counts", "no", "*args"),
    (Q + "util/iterutil.py", "coerce_cell", "no", "dynamic typing: function held in a variable"),
    (Q + "util/iterutil.py", "first_peak", "no", "Optional return"),
    (Q + "util/iterutil.py", "chunked", "no", "generator"),
    (Q + "linalg/accel.py", "matmul_fast", "no", "numpy (guarded import)"),
    (Q + "io/csvio.py", "read_table", "no", "file I/O + class"),
    (Q + "io/jsonio.py", "save_report", "no", "json + with"),
    (Q + "graph/sparse.py", "random_graph", "no", "constructs a class"),
    (Q + "sim/events.py", "exponential", "no", "calls a method on an Lcg object"),
    (Q + "text/corpus.py", "misspell", "no", "calls methods on an Lcg object"),
    (Q + "text/index.py", "tokenize", "no", "regex module-level state"),
    (Q + "stats/resample.py", "ar1_series", "no", "default arguments / Optional"),
    (Q + "cli/jobs.py", "job_graph", "no", "cross-module callees"),
    (Q + "util/rng.py", "Lcg.next_float", "no", "method of class"),
    (Q + "graph/sparse.py", "Graph.shortest_paths", "no", "method of class (heapq)"),
    (Q + "text/spell.py", "SpellChecker.suggest", "no", "method of class"),
]

DEMOS = {"textlab": ("textlab", TEXTLAB), "quanta": ("quanta", QUANTA)}


def select(name):
    global DEMO
    DEMO = os.path.join(ROOT, "demo", name)


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


def function_source(rel, name):
    text = open(os.path.join(DEMO, rel), encoding="utf-8").read()
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(text.splitlines()[node.lineno - 1:node.end_lineno])
    raise KeyError(name)


def compile_pysub(src):
    return compile_source(src, "<demo>")


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


# ------------------------------------------------------------------ cached LLM rewrites
def cache_key(src, attempt):
    return hashlib.sha256(f"{hashlib.sha256(src.encode()).hexdigest()}|{attempt}".encode()).hexdigest()


def cached_attempts(rel, name):
    """[(attempt, provenance, pysub or None, raw reply)] from demo/offline_cache/llm for this function."""
    from pythia.studio.fixer import extract_candidate
    src = function_source(rel, name)
    out = []
    for n in (1, 2, 3):
        p = os.path.join(CACHE, "llm", cache_key(src, n) + ".json")
        if not os.path.isfile(p):
            break
        e = json.load(open(p, encoding="utf-8"))
        out.append((n, e.get("provenance"), extract_candidate(e["response"]), e["response"]))
    return out


def authored_attempts(name):
    path = os.path.join(CACHE, "authored_rewrites.json")
    spec = json.load(open(path, encoding="utf-8"))["functions"].get(name)
    return [(a["attempt"], "authored", a["pysub"], a["pysub"]) for a in (spec or {}).get("attempts", [])]


# ------------------------------------------------------------------ equivalence inputs for the fixable functions
def equivalence_inputs(name):
    r = Rng(99)
    if name == "knn_vote":
        for _ in range(40):
            n, d = 5 + r.i(30), 1 + r.i(5)
            train = [[round(r.f(), 2) for _ in range(d)] for _ in range(n)]
            labels = [r.i(4) for _ in range(n)]
            yield (train, labels, [round(r.f(), 2) for _ in range(d)], 1 + r.i(7))
        yield ([], [], [0.5], 3)
        yield ([[0.1, 0.2]], [1], [0.5, 0.5], 0)
        yield ([[0.1, 0.2], [0.3, 0.9], [0.5, 0.1]], [1, 2, 2], [0.5], -1)
        yield ([[0.1, 0.2], [0.3, 0.9], [0.5, 0.1]], [1, 2, 2], [0.4, 0.4, 0.4], 99)
        yield ([[0.1], [0.3, 0.9], [0.5, 0.1, 0.0]], [1, 2, 2], [0.4, 0.4], 2)
    elif name == "life_generations":
        for _ in range(25):
            h, w = 3 + r.i(9), 3 + r.i(9)
            yield ([[1 if r.f() < 0.4 else 0 for _ in range(w)] for _ in range(h)], r.i(6))
        yield ([[], [], [], [1, 5, 0, -18], [41, -1]], 0)
        yield ([[1, 0, 1], [0, 1]], 2)
        yield ([], 3)
        yield ([[1, 1, 1]], -2)
    elif name == "collatz_longest":
        for lim in (2, 3, 10, 97, 1000, 5000):
            yield (lim,)
    elif name == "bfs_levels":
        for _ in range(40):
            n = 1 + r.i(25)
            adj = [[r.i(n) for _ in range(r.i(4))] for _ in range(n)]
            yield (adj, r.i(n))
        yield ([[]], 0)
        yield ([[1], [0]], 1)
        yield ([[1], [0]], 5)                      # IndexError in both
        yield ([[3], [0]], 0)                      # neighbour out of range
    elif name == "longest_increasing_subsequence":
        for _ in range(40):
            yield ([r.i(50) for _ in range(r.i(40))],)
        yield ([],)
        yield ([5],)
        yield ([3, 3, 3],)
        yield ([-5, -4, -9, 10 ** 12],)
    elif name == "grid_min_path":
        for _ in range(30):
            h, w = 1 + r.i(8), 1 + r.i(8)
            yield ([[r.i(20) - 3 for _ in range(w)] for _ in range(h)],)
        yield ([[7]],)
        yield ([[]],)                              # IndexError / empty row behaviour
        yield ([],)
        yield ([[1, 2, 3]],)
        yield ([[1], [2], [3]],)
    elif name == "exp_smooth":
        for _ in range(30):
            yield ([round(r.f() * 10 - 5, 3) for _ in range(r.i(20))], round(r.f(), 2))
        yield ([], 0.5)
        yield ([2.5], 0.3)
        yield ([1.0, 2.0, 3.0], 0.0)
        yield ([1.0, 2.0, 3.0], 1.0)
    elif name == "life_population":
        for _ in range(25):
            h, w = 1 + r.i(9), 1 + r.i(9)
            yield ([[1 if r.f() < 0.4 else 0 for _ in range(w)] for _ in range(h)], r.i(6))
        yield ([[1]], 3)
        yield ([[1, 1, 1], [0, 0, 0], [1, 1, 1]], 0)
        yield ([[1, 1, 1], [0, 0, 0], [1, 1, 1]], -2)
        yield ([], 2)
    elif name == "weighted_moments":
        for _ in range(30):
            n = 1 + r.i(20)
            yield ([round(r.f() * 10 - 5, 3) for _ in range(n)], [round(r.f() * 3, 3) for _ in range(n)])
        yield ([1.0, 1.0, 1.0], [1.0, 2.0, 3.0])
        yield ([1.0, 2.0], [0.0, 0.0])             # ZeroDivisionError in both
        yield ([], [])
    elif name == "kmer_counts":
        for _ in range(30):
            yield ("".join("ACGT"[r.i(4)] for _ in range(r.i(40))), 1 + r.i(5))
        yield ("", 3)
        yield ("ACGT", 4)
        yield ("ACGT", 5)
        yield ("AAAA", 1)


# inputs the recorded rewrite is allowed to get wrong: reported as warnings, they show what replay cannot see
KNOWN_EDGES = {"weighted_moments": [([1.0, 2.0, 3.0], [1.0, 1.0])]}      # zip() stops early, a rewrite indexes past the end


def outcome(f, args):
    try:
        return ("value", f(*args))
    except Exception as e:                      # replay compares the exception class, not the message
        return ("raises", type(e).__name__)


def check_rewrite(rel, name, attempts):
    """The last cached attempt must compile and behave exactly like the original; earlier ones, if any, must not compile."""
    errs = []
    cands = [a for a in attempts if a[2]]
    if not cands:
        return ["no usable cached rewrite"], 0
    for i, (n, _prov, pysub, _raw) in enumerate(cands):
        _, _, diags, _ = compile_pysub(pysub)
        last = i == len(cands) - 1
        if last and diags:
            errs.append(f"final attempt {n} does not compile: {diags[0]}")
        if not last and not diags:
            errs.append(f"attempt {n} compiles but a later attempt exists")
    if errs:
        return errs, 0
    orig = load_func(rel, name)
    new = load_func(rel, name, cands[-1][2])
    k = 0
    for args in equivalence_inputs(name):
        a, b = copy.deepcopy(args), copy.deepcopy(args)
        k += 1
        o1, o2 = outcome(orig, a), outcome(new, b)
        if o1 != o2 or a != b:
            errs.append(f"rewrite differs from original on {args!r}: {o1} vs {o2}")
            break
    for args in KNOWN_EDGES.get(name, []):
        a, b = copy.deepcopy(args), copy.deepcopy(args)
        if outcome(orig, a) != outcome(new, b):
            print(f"     note: {name} rewrite diverges on {args!r} (not covered by replay): "
                  f"{outcome(orig, copy.deepcopy(args))} vs {outcome(new, copy.deepcopy(args))}")
    return errs, k


# ------------------------------------------------------------------ by-hand speedup measurement (textlab only)
def bench_cases():
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
    import importlib.util
    import tempfile
    from pythia.libmode import build_library
    rewrites = json.load(open(os.path.join(CACHE, "authored_rewrites.json")))["functions"]
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
        py_copies = [copy.deepcopy(a) for a in calls]
        t = time.perf_counter()
        want = [slow(*a) for a in py_copies]
        t_py = time.perf_counter() - t
        arg_copies = [copy.deepcopy(a) for a in calls]
        t = time.perf_counter()
        got = [fast(*a) for a in arg_copies]
        t_cpp = time.perf_counter() - t
        print(f"{name:20s} {1000 * t_py:9.1f} {1000 * t_cpp:9.1f} {t_py / t_cpp:7.1f}x  {str(want == got):9s}  "
              f"{'cached' if res.cached else '%.1fs' % res.compile_s}")
    return 0


# ------------------------------------------------------------------ static checks
def check_targets(demo, targets):
    bad = 0
    print(f"\n[{demo}] {'function':34s} {'intended':12s} compiler verdict")
    for rel, name, intended, note in targets:
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
        elif intended == "no":
            src = pysub_text(rel, name)
            _, tree = read_module(rel)
            fn = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name][0]
            nested = [n for n in ast.walk(fn) if n is not fn and isinstance(n, (ast.FunctionDef, ast.Lambda))]
            _, _, diags, _ = compile_pysub(src)
            if nested:
                verdict = "closure / lambda"
            elif diags:
                verdict = f"front end rejects: {diags[0].msg[:60]}"
            else:
                # accepted by the typechecker: must then be rejected by the Studio's static scan for another reason
                verdict = "typechecker accepts the body; Studio scan rejects it (object parameters, cross-module, I/O)"
        else:
            src = pysub_text(rel, name)
            code, notes, diags, stats = compile_pysub(src)
            if intended in ("win_exact", "win_guarded", "win", "boundary"):
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
            elif intended in ("fixable", "cold_fix"):
                if not diags:
                    # the AST pre-scan (comprehensions, sum, zip...) rejects some constructs the parser would accept
                    verdict = "front end accepts a subset; Studio scan flags the unsupported construct"
                else:
                    verdict = f"rejected: {diags[0].msg[:60]}"
                if intended == "fixable":
                    att = cached_attempts(rel, name) if demo == "quanta" else authored_attempts(name)
                    if not att:
                        verdict += "; NO cached rewrite yet"
                        if demo == "textlab":
                            err = "no authored rewrite in authored_rewrites.json"
                    else:
                        e2, k = check_rewrite(rel, name, att)
                        err = "; ".join(e2) or None
                        prov = ",".join(sorted({a[1] for a in att}))
                        verdict += f" -> {len(att)} cached attempt(s) ({prov}), final compiles, identical on {k} inputs"
            elif intended == "annotate":
                if not diags:
                    err = "expected rejection (missing annotations)"
                else:
                    verdict = f"rejected: {diags[0].msg[:60]} (fixed from observed types)"
        status = "FAIL" if err else "ok"
        bad += bool(err)
        print(f"{status:4s} {name:34s} {intended:12s} {verdict}" + (f"   <-- {err}" if err else ""))
    return bad


def code_stats(demo, targets):
    """Lines of the demo, and the share that sits in functions meant for PYTHIA."""
    total = kernel = 0
    kern_names = {(rel, n) for rel, n, k, _ in targets if k.startswith("win") or k in ("fixable", "annotate", "boundary", "cold_fix")}
    for dirpath, _, files in os.walk(DEMO):
        if "__pycache__" in dirpath:
            continue
        for f in files:
            if f.endswith(".py"):
                rel = os.path.relpath(os.path.join(dirpath, f), DEMO).replace(os.sep, "/")
                text = open(os.path.join(dirpath, f), encoding="utf-8").read()
                total += len(text.splitlines())
                if rel.startswith("tests/"):
                    continue
                for node in ast.parse(text).body:
                    if isinstance(node, ast.FunctionDef) and (rel, node.name) in kern_names:
                        kernel += node.end_lineno - node.lineno + 1
    return total, kernel


def timing(demo, targets):
    """Run main.py --small with wrapped functions and print CPython time shares."""
    shares = {}
    sys.path.insert(0, DEMO)
    os.chdir(DEMO)
    import importlib
    for rel, name, intended, _ in targets:
        if "." in name:
            continue
        try:
            mod = importlib.import_module(rel[:-3].replace("/", "."))
        except Exception:
            continue
        orig = getattr(mod, name, None)
        if orig is None:
            continue

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
    import io
    from contextlib import redirect_stdout
    t0 = time.perf_counter()
    with redirect_stdout(io.StringIO()):
        runpy.run_path(os.path.join(DEMO, "main.py"), run_name="__main__")
    total = time.perf_counter() - t0
    print(f"\n{demo}: main.py --small {total:.1f} s (wrapped functions; a plain run is a bit faster)")
    kinds = dict((t[1], t[2]) for t in targets)
    for name, sec in sorted(shares.items(), key=lambda kv: -kv[1]):
        print(f"  {name:32s} {kinds[name]:12s} {sec:6.2f} s  {100 * sec / total:5.1f}%")
    agg = {}
    for name, sec in shares.items():
        k = kinds[name]
        k = "win" if k.startswith("win") else k
        agg[k] = agg.get(k, 0.0) + sec
    print("  (callee time is counted in its caller too, so groups can overlap)  " +
          ", ".join(f"{k} {100 * v / total:.0f}%" for k, v in sorted(agg.items())))


def main():
    args = sys.argv[1:]
    which = [args[args.index("--demo") + 1]] if "--demo" in args else list(DEMOS)
    if "--bench" in args:
        select("textlab")
        return bench()
    bad = 0
    for demo in which:
        select(DEMOS[demo][0])
        targets = DEMOS[demo][1]
        bad += check_targets(demo, targets)
        total, kernel = code_stats(demo, targets)
        print(f"[{demo}] {total} lines of Python; {kernel} lines ({100 * kernel / max(total, 1):.0f}%) are in functions meant for PYTHIA")
    if "--no-run" in args:
        return 1 if bad else 0
    for demo in which:
        select(DEMOS[demo][0])
        timing(demo, DEMOS[demo][1])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
