# Quanta

A small analytics and simulation toolkit in plain Python 3 (no dependencies; NumPy is used for a
couple of optional fast paths if it happens to be installed).

Quanta bundles the numerical building blocks a data or operations team keeps rewriting:

| package | what is in it |
|---|---|
| `quanta.sim` | n-body gravity, Mandelbrot rendering, Monte-Carlo estimators, a discrete-event queue, Game of Life |
| `quanta.combinatorics`, `quanta.numtheory` | pancake flipping, n-queens, derangements, prime sieves, Collatz trajectories, digit puzzles |
| `quanta.text` | Levenshtein / LCS distances, spell suggestions, k-mer statistics, a TF-IDF inverted index |
| `quanta.graph` | Floyd-Warshall, dense and heap-based Dijkstra, BFS, connected components |
| `quanta.linalg` | matrix products, Gaussian elimination, spectral norm, optional NumPy paths |
| `quanta.cluster`, `quanta.opt` | k-means, simulated annealing for the travelling salesman, knapsack / coin / path DP |
| `quanta.signal`, `quanta.stats` | FIR filtering, smoothing, histograms, rolling statistics, drift detection, bootstrap |
| `quanta.io` | CSV tables, JSON reports, text report rendering |
| `quanta.cli` | the `quanta` command line |

## Running it

```
python main.py --small            # the standard benchmark suite, about half a minute
python main.py --full             # roughly three times the work
python main.py graph --small      # one job: sim puzzles text graph linalg optimise signals
python main.py list               # jobs and scale presets
python main.py --small --json out.json
python main.py compare old.json new.json
python main.py describe data.csv
python -m quanta --tiny           # same entry point as a module; --tiny is the unit-test workload
```

All inputs are generated from a seeded linear congruential generator (`--seed`, default 2024), so
the output is identical on every run and every machine: a change in a printed number is a change in
behaviour.  Scale parameters can be overridden with `--set queens_n=12` or an INI file (`--config`):

```ini
[scale]
queens_n = 12
spectral_n = 400
```

## Tests

```
python -m unittest
```

The suite runs in well under a second (it uses the `--tiny` workload for the end-to-end checks).

## Layout

```
main.py             source-checkout entry point
quanta/             the package (one sub-package per domain, see the table above)
quanta/cli/jobs.py  the benchmark suite: one job function per domain
quanta/config.py    Scale presets and override handling
tests/              unittest modules
```

Performance-sensitive routines live in plain module-level functions with type annotations and no
exotic features (no classes in the hot loops, lists of numbers instead of objects).  That keeps them easy to
profile and easy to hand to a compiler or a faster runtime later.
