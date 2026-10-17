"""The benchmark suite: one function per domain, each filling a section of the report.

Every job derives its inputs from the seed in `Settings` through the deterministic Lcg, so two runs
(or a run before and after an optimisation) must print exactly the same numbers.
"""
from __future__ import annotations

import logging
import os
import tempfile
from typing import Callable, Dict, List

from quanta.cluster.kernels import assign_points
from quanta.cluster.kmeans import KMeans, make_blobs
from quanta.combinatorics.permutations import count_derangements, fannkuch
from quanta.combinatorics.queens import count_queens
from quanta.config import Settings
from quanta.graph.closure import count_triangles, degree_histogram, transitive_closure
from quanta.graph.shortest import dijkstra_dense, eccentricity_sum, floyd_warshall
from quanta.graph.sparse import farthest_node, random_graph
from quanta.graph.traverse import bfs_levels
from quanta.io.csvio import column_means, describe_columns, read_table, write_table
from quanta.io.report import Report, bar, format_table
from quanta.linalg.accel import column_norms, have_numpy, matmul_fast
from quanta.linalg.builders import diagonally_dominant, random_matrix, residual_norm
from quanta.linalg.decomp import determinant, power_iteration
from quanta.linalg.dense import gauss_solve, matmul
from quanta.linalg.spectral import spectral_norm
from quanta.numtheory.collatz import longest_collatz, peak_value
from quanta.numtheory.digits import count_palindromes, digital_root_total
from quanta.numtheory.primes import prime_gap_record, prime_square_sum, twin_prime_count
from quanta.numtheory.totient import count_coprime_pairs, perfect_numbers, totient_sum
from quanta.opt.anneal import TourAnnealer
from quanta.opt.chain import matrix_chain_cost, max_subarray, partition_count, rod_cutting
from quanta.opt.dp import coin_ways, grid_min_path, knapsack_01, longest_increasing_subsequence
from quanta.signal.filters import convolve, exp_smooth, fir_filter, hann_taps, moving_average
from quanta.signal.spectrum import dft_power, dominant_bin, median_filter
from quanta.sim.automata import density, rule_automaton
from quanta.sim.events import simulate_queue
from quanta.sim.fractal import escape_area, mandelbrot_row, shade_row
from quanta.sim.life import life_population, life_step
from quanta.sim.montecarlo import estimate_pi, integrate_poly, walk_endpoints
from quanta.sim.system import System
from quanta.stats.descriptive import (autocorrelation, clip_fraction, histogram, rolling_std,
                                      weighted_moments)
from quanta.stats.correlation import kendall_tau, spearman_rho
from quanta.stats.drift import tail_variance
from quanta.stats.resample import ar1_series, confidence_interval
from quanta.stats.table import make_sales_table, normalise_column, revenue_by_region
from quanta.text.corpus import (edit_line, make_dictionary, make_dna, make_document, make_lines,
                                misspell)
from quanta.text.distance import hamming, lcs_length
from quanta.text.index import InvertedIndex, top_terms
from quanta.text.kmers import gc_content, kmer_counts, longest_run
from quanta.text.spell import SpellChecker
from quanta.text.substrings import longest_common_substring, longest_palindrome, run_length_encode
from quanta.util.rng import Lcg

log = logging.getLogger(__name__)

Job = Callable[[Settings, Report], None]


def job_sim(cfg: Settings, rep: Report) -> None:
    """N-body orbits, a Mandelbrot view, Monte-Carlo estimates, a service queue and the Game of Life."""
    s = cfg.scale
    sec = rep.section("simulation")

    system = System.outer_planets()
    rep.record(sec, "initial energy", system.energy())
    done = 0
    while done < s.nbody_steps:
        system.advance(0.01, s.nbody_chunk)
        done += s.nbody_chunk
        rep.record(sec, "energy @%d" % done, system.energy())
    rep.record(sec, "neptune distance", system.distance_from_sun(4))

    rows = [mandelbrot_row(py, s.mandel_width, s.mandel_height, s.mandel_iter) for py in range(s.mandel_height)]
    art = [shade_row(rows[py][::6], s.mandel_iter) for py in range(0, s.mandel_height, 11)]
    print("\n".join(art))
    rep.record(sec, "mandelbrot interior", sum(1 for row in rows for v in row if v >= s.mandel_iter))
    rep.record(sec, "mandelbrot quarter area", escape_area(s.mandel_width // 2, s.mandel_height // 2, 200))

    rep.record(sec, "pi estimate", estimate_pi(s.pi_samples, cfg.seed))
    rep.record(sec, "integral x^3-2x", integrate_poly([0.0, -2.0, 0.0, 1.0], 0.0, 2.0, s.pi_samples // 4, cfg.seed + 1))
    ends = walk_endpoints(s.walkers, s.walk_steps, cfg.seed + 2)
    reach = int(3.0 * s.walk_steps ** 0.5) + 1
    spread = histogram([float(e) for e in ends], 8, -float(reach), float(reach))
    rep.record(sec, "walk histogram", " ".join(str(c) for c in spread))

    stats = simulate_queue(s.queue_customers, 3, 2.4, 1.0, cfg.seed + 3)
    rep.record(sec, "queue mean wait", stats.mean_wait)
    rep.record(sec, "queue utilisation", stats.utilisation)

    rng = Lcg(cfg.seed + 4)
    grid = [[1 if rng.next_float() < 0.35 else 0 for _ in range(s.life_size)] for _ in range(s.life_size)]
    cur = grid
    for _ in range(s.life_generations):
        cur = life_step(cur)
    alive = sum(map(sum, cur))
    rep.record(sec, "life population", "%d -> %d" % (sum(map(sum, grid)), alive))
    rep.record(sec, "life cross-check", life_population(grid, s.life_generations) == alive)

    seed_row = [1 if rng.next_float() < 0.5 else 0 for _ in range(s.automaton_cells)]
    for rule in (30, 110):
        final = rule_automaton(seed_row, rule, s.automaton_steps)
        rep.record(sec, "rule %d density" % rule, density(final))


def job_puzzles(cfg: Settings, rep: Report) -> None:
    """Combinatorial search and number theory."""
    s = cfg.scale
    sec = rep.section("puzzles")
    rep.record(sec, "fannkuch(%d)" % s.fannkuch_n, fannkuch(s.fannkuch_n))
    rep.record(sec, "queens(%d)" % s.queens_n, count_queens(s.queens_n))
    rep.record(sec, "derangements(8)", count_derangements(8))
    rep.record(sec, "twin primes", twin_prime_count(s.sieve_limit))
    rep.record(sec, "max prime gap", prime_gap_record(s.sieve_limit // 3))
    rep.record(sec, "prime square sum", prime_square_sum(s.prime_count, 1000003))
    best = longest_collatz(s.collatz_limit)
    rep.record(sec, "longest collatz", best)
    rep.record(sec, "collatz peak", peak_value(best))
    rep.record(sec, "digital roots", digital_root_total(s.digit_limit))
    rep.record(sec, "palindromes", count_palindromes(s.digit_limit))
    rep.record(sec, "totient sum", totient_sum(s.totient_limit))
    rep.record(sec, "coprime pairs", count_coprime_pairs(s.coprime_limit))
    rep.record(sec, "perfect numbers", " ".join(str(n) for n in perfect_numbers(s.perfect_limit)))


def job_text(cfg: Settings, rep: Report) -> None:
    """Spell correction, line diffs, DNA statistics and a tiny search index."""
    s = cfg.scale
    sec = rep.section("text")
    rng = Lcg(cfg.seed + 10)
    dictionary = make_dictionary(rng, s.dictionary_words)
    queries = [misspell(rng, rng.choice(dictionary)) for _ in range(s.queries)]
    checker = SpellChecker(dictionary)
    rep.record(sec, "dictionary words", len(dictionary))
    rep.record(sec, "corrected queries", checker.correct_all(queries))

    old_lines = make_lines(rng, dictionary, s.diff_lines, 160)
    new_lines = [edit_line(rng, line) for line in old_lines]
    kept = sum(lcs_length(a, b) for a, b in zip(old_lines, new_lines))
    total = sum(len(a) for a in old_lines)
    rep.record(sec, "diff similarity", kept / total)
    rep.record(sec, "hamming total", sum(hamming(a, b) for a, b in zip(old_lines, new_lines)))
    rep.record(sec, "shared substrings", sum(longest_common_substring(a, b) for a, b in zip(old_lines, new_lines)))
    rep.record(sec, "palindromes in text", max(longest_palindrome(" ".join(new_lines)[i:i + 2000])
                                               for i in range(0, 6000, 2000)))
    rep.record(sec, "encoded run", run_length_encode("aaabccdddd" * 3))

    reads = [make_dna(rng, s.dna_length) for _ in range(s.dna_reads)]
    counts: Dict[str, int] = {}
    for read in reads:
        for kmer, n in kmer_counts(read, 3).items():
            counts[kmer] = counts.get(kmer, 0) + n
    rep.record(sec, "mean gc content", sum(gc_content(r) for r in reads) / len(reads))
    rep.record(sec, "longest run", max(longest_run(r) for r in reads))
    common = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    rep.record(sec, "top 3-mers", ", ".join("%s:%d" % kv for kv in common))

    index = InvertedIndex()
    for _ in range(s.corpus_docs):
        index.add(make_document(rng, dictionary, 120))
    hits = index.search(" ".join(dictionary[:3]), 3)
    rep.record(sec, "index terms", len(index.postings))
    rep.record(sec, "search hits", " ".join(str(h) for h in hits))
    rep.record(sec, "frequent terms", " ".join(top_terms(index, 4)))


def job_graph(cfg: Settings, rep: Report) -> None:
    """Shortest paths on dense and sparse graphs, traversal and components."""
    s = cfg.scale
    sec = rep.section("graph")
    rng = Lcg(cfg.seed + 20)
    no_edge = 1000000000

    radius = diameter = triangles = reachable = 0
    degrees = [0]
    for _ in range(s.graph_batches):
        g = random_graph(rng, s.graph_nodes, 2)
        m = g.to_matrix(no_edge)
        radius += eccentricity_sum(m)
        diameter = max(diameter, max(max(row) for row in floyd_warshall(m)))
        flags = [[1 if 0 < w < no_edge else 0 for w in row] for row in m]
        triangles += count_triangles(flags)
        reachable += sum(map(sum, transitive_closure(flags)))
        degrees = degree_histogram(flags)
    rep.record(sec, "eccentricity sum", radius)
    rep.record(sec, "diameter", diameter)
    rep.record(sec, "triangles", triangles)
    rep.record(sec, "reachable pairs", reachable)
    rep.record(sec, "degree histogram", " ".join(str(c) for c in degrees[:8]))

    big = random_graph(rng, s.dense_nodes, 6)
    dense = big.to_matrix(no_edge)
    total = 0
    for src in range(s.dense_sources):
        total += sum(dijkstra_dense(dense, src * 7 % s.dense_nodes))
    rep.record(sec, "dense dijkstra total", total)

    sparse = random_graph(rng, s.sparse_nodes, 3)
    dist = sparse.shortest_paths(0)
    rep.record(sec, "sparse edges", sparse.edge_count)
    rep.record(sec, "sparse farthest", farthest_node(dist))
    rep.record(sec, "components", len(sparse.components()))

    adjacency = sparse.to_adjacency_lists()
    depth = 0
    for src in range(s.bfs_sources):
        depth += max(bfs_levels(adjacency, src * 13 % s.sparse_nodes))
    rep.record(sec, "bfs depth total", depth)


def job_linalg(cfg: Settings, rep: Report) -> None:
    """Matrix products, linear solves and a power iteration."""
    s = cfg.scale
    sec = rep.section("linalg")
    rng = Lcg(cfg.seed + 30)
    a = random_matrix(rng, s.matmul_size, s.matmul_size)
    b = random_matrix(rng, s.matmul_size, s.matmul_size)
    c = a
    for _ in range(s.matmul_rounds):
        c = matmul(c, b)
        peak = max(abs(v) for row in c for v in row)
        c = [[v / peak for v in row] for row in c]
    rep.record(sec, "matmul checksum", sum(c[i][i] for i in range(len(c))))
    if cfg.use_numpy and have_numpy():
        gap = max(abs(x - y) for r1, r2 in zip(matmul_fast(a, b), matmul(a, b)) for x, y in zip(r1, r2))
        rep.record(sec, "numpy agrees", gap < 1e-9)
    rep.record(sec, "column norm max", max(column_norms(c)))

    worst = 0.0
    dets = 0.0
    for _ in range(s.solve_count):
        system = diagonally_dominant(rng, s.solve_size)
        rhs = rng.floats(s.solve_size, -1.0, 1.0)
        worst = max(worst, residual_norm(system, gauss_solve(system, rhs), rhs))
        dets += determinant(system) > 0.0
    rep.record(sec, "solve residual < 1e-9", worst < 1e-9)
    rep.record(sec, "positive determinants", int(dets))
    rep.record(sec, "dominant eigenvalue", power_iteration(system, 40))
    rep.record(sec, "spectral norm", spectral_norm(s.spectral_n, s.spectral_iters))


def job_optimise(cfg: Settings, rep: Report) -> None:
    """Clustering, annealing and dynamic programming."""
    s = cfg.scale
    sec = rep.section("optimisation")
    rng = Lcg(cfg.seed + 40)

    points = make_blobs(rng, s.cluster_points, 8, 4)
    model = KMeans(8, 8)
    fits = [model.fit(points, r) for r in range(s.cluster_restarts)]
    best = min(fits, key=lambda f: f.inertia)
    rep.record(sec, "kmeans best inertia", best.inertia)
    rep.record(sec, "kmeans cluster sizes", [best.labels.count(c) for c in range(8)])
    rep.record(sec, "labels stable", assign_points(points, best.centroids) == best.labels)

    xs, ys = rng.floats(s.anneal_cities), rng.floats(s.anneal_cities)
    result = TourAnnealer(xs, ys, cfg.seed).run(s.anneal_steps)
    rep.record(sec, "tour improvement", result.improvement)
    rep.record(sec, "tour accepted moves", result.accepted)

    value = 0
    for _ in range(s.knapsack_runs):
        weights = [3 + rng.next_int(40) for _ in range(s.knapsack_items)]
        values = [10 + rng.next_int(90) for _ in range(s.knapsack_items)]
        value += knapsack_01(weights, values, s.knapsack_capacity)
    rep.record(sec, "knapsack value", value)
    rep.record(sec, "coin ways", sum(coin_ways([1, 2, 5, 10, 25, 50], 4000 * (k + 1)) for k in range(s.dp_rounds)))
    rep.record(sec, "increasing subsequence", sum(longest_increasing_subsequence(rng.ints(1500, 1000))
                                                  for _ in range(s.dp_rounds)))
    rep.record(sec, "matrix chain", sum(matrix_chain_cost([5 + rng.next_int(60) for _ in range(s.chain_length + 1)])
                                        for _ in range(s.dp_rounds)))
    rep.record(sec, "partitions", partition_count(s.partition_n))
    rep.record(sec, "rod cutting", rod_cutting([1 + 2 * k + rng.next_int(5) for k in range(40)], 4000))
    rep.record(sec, "max subarray", max_subarray([rng.next_int(21) - 10 for _ in range(50000)]))
    paths = 0
    field = [rng.ints(100, 20) for _ in range(100 + s.path_grids)]
    for g in range(s.path_grids):
        paths += grid_min_path(field[g:g + 100])
    rep.record(sec, "cheapest paths", paths)


def job_signals(cfg: Settings, rep: Report) -> None:
    """Filtering, smoothing, descriptive statistics, drift detection and a CSV round trip."""
    s = cfg.scale
    sec = rep.section("signals and statistics")
    rng = Lcg(cfg.seed + 50)
    taps = hann_taps(s.signal_taps)

    energy = peak = tail = autocorr = rolling = clipped = smooth_peak = 0.0
    dominant = 0
    moments = [0.0, 0.0, 0.0]
    hist = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    signal: List[float] = []
    for ch in range(s.channels):
        signal = ar1_series(rng, s.signal_length, 0.85 + 0.01 * (ch % 5))
        filtered = fir_filter(signal, taps)
        energy += sum(v * v for v in filtered)
        peak = max(peak, max(convolve(signal[:600], taps)))
        for alpha in (0.05, 0.1, 0.2, 0.4):
            tail += exp_smooth(moving_average(signal, 16), alpha)[-1]
        autocorr += autocorrelation(signal, 5)
        rolling = max(rolling, max(rolling_std(signal[:1500], 40)))
        for ramp in (0.0, 0.5, 1.5):
            weights = [1.0 + ramp * i / len(signal) for i in range(len(signal))]
            m = weighted_moments(signal, weights)
            moments = [x + y for x, y in zip(moments, m)]
        clipped += clip_fraction(signal, -0.8, 0.8)
        hist = [x + y for x, y in zip(hist, histogram(signal, 10, -2.0, 2.0))]
        segment = signal[:512]
        dominant += dominant_bin(dft_power(segment))
        smooth_peak = max(smooth_peak, max(median_filter(signal[:2000], 9)))
    rep.record(sec, "dominant bins", dominant)
    rep.record(sec, "median filter peak", smooth_peak)
    rep.record(sec, "fir energy", energy)
    rep.record(sec, "convolution peak", peak)
    rep.record(sec, "smoothed tail sum", tail)
    rep.record(sec, "autocorrelation(5)", autocorr / s.channels)
    rep.record(sec, "rolling std max", rolling)
    rep.record(sec, "weighted moments", "%.5f %.5f %.5f" % tuple(moments))
    rep.record(sec, "clipped", clipped / s.channels)
    rep.record(sec, "histogram", " ".join("%s %d" % (bar(c, max(hist), 12), c) for c in hist[:3]))

    alarms = 0
    first_alarm = -1
    for ch in range(s.drift_channels):
        series = ar1_series(rng, s.series_length, 0.5, shift_at=s.series_length * 2 // 3, shift=1.5)
        grown: List[float] = []
        baseline = None
        for t, value in enumerate(series):
            grown.append(value)
            if t >= 64:
                recent = tail_variance(grown, 300)
                if baseline is None:
                    baseline = recent
                elif recent > 3.0 * baseline:
                    alarms += 1
                    if first_alarm < 0:
                        first_alarm = t
    rep.record(sec, "drift alarms", alarms)
    rep.record(sec, "first alarm", first_alarm)

    xs = signal[:s.rank_samples]
    ys = [x + 0.5 * rng.gauss() for x in xs]
    rep.record(sec, "kendall tau", kendall_tau(xs, ys))
    rep.record(sec, "spearman rho", spearman_rho(xs, ys))

    lo, hi = confidence_interval(rng, signal[:400], s.bootstrap_rounds)
    rep.record(sec, "bootstrap CI", "[%.4f, %.4f]" % (lo, hi))

    table = make_sales_table(rng, s.csv_rows)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "sales.csv")
        write_table(path, table)
        loaded = read_table(path)
    kinds = describe_columns(loaded)
    means = column_means(loaded, ["quantity", "price", "revenue"])
    rep.record(sec, "csv rows", len(loaded))
    rep.record(sec, "csv types", " ".join("%s=%s" % kv for kv in kinds.items()))
    rep.record(sec, "mean revenue", means["revenue"])
    by_region = revenue_by_region(loaded)
    rep.record(sec, "top region", max(by_region, key=by_region.get))
    z = normalise_column(loaded.float_column("revenue"))
    rep.record(sec, "z-score range", "%.3f %.3f" % (min(z), max(z)))


JOBS: Dict[str, Job] = {
    "sim": job_sim,
    "puzzles": job_puzzles,
    "text": job_text,
    "graph": job_graph,
    "linalg": job_linalg,
    "optimise": job_optimise,
    "signals": job_signals,
}


def run_jobs(cfg: Settings, names: List[str]) -> Report:
    """Run the named jobs in order and return the combined report."""
    rep = Report("Quanta suite (%s scale, seed %d)" % (cfg.scale.name, cfg.seed))
    for name in names:
        log.info("running job %s", name)
        JOBS[name](cfg, rep)
    return rep


def summary_table(rep: Report) -> str:
    """One row per report section: how many figures it contains."""
    rows: List[List[object]] = [[title, len(values)] for title, values in rep.data.items()]
    return format_table(["section", "figures"], rows)
