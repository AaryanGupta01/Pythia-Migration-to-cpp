# Changelog

## 0.4.1
- `queens`: iterative backtracking replaces the recursive search (no stack growth for n > 14).
- `spectral`: matrix entries are computed inline instead of through a helper call.
- `cli`: `--tiny` workload for tests; scale flags are accepted before or after the command.

## 0.4.0
- New `quanta.opt.anneal` (travelling-salesman annealer) and `quanta.stats.drift`.
- Report schema bumped to 2 (`quanta.io.jsonio`); `quanta compare` diffs two reports.
- k-means gained deterministic, restart-indexed initialisation.

## 0.3.0
- Discrete-event queue simulation, sparse graph helpers, TF-IDF index.
- Optional NumPy fast paths in `quanta.linalg.accel`.

## 0.2.0
- Benchmark suite split into per-domain jobs; INI configuration of workload sizes.

## 0.1.0
- First public cut: kernels for sieving, Collatz, edit distance, matrix products and n-body.
