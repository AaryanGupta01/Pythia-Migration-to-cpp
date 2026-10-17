"""Run configuration: workload scale presets plus optional overrides from an INI file or the command line."""
from __future__ import annotations

import configparser
import dataclasses
import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Scale:
    """How much work each job of the benchmark suite does.

    Field names are the keys accepted in the `[scale]` section of a config file."""

    name: str = "small"
    # sim
    nbody_steps: int = 420000
    nbody_chunk: int = 70000
    mandel_width: int = 420
    mandel_height: int = 220
    mandel_iter: int = 1000
    pi_samples: int = 4000000
    walkers: int = 2000
    walk_steps: int = 1000
    queue_customers: int = 40000
    life_size: int = 48
    life_generations: int = 80
    # combinatorics / number theory
    fannkuch_n: int = 9
    queens_n: int = 13
    sieve_limit: int = 6000000
    prime_count: int = 30000
    collatz_limit: int = 250000
    digit_limit: int = 2500000
    totient_limit: int = 900000
    coprime_limit: int = 1300
    perfect_limit: int = 250000
    automaton_cells: int = 1200
    automaton_steps: int = 600
    # text
    dictionary_words: int = 420
    queries: int = 300
    diff_lines: int = 80
    dna_reads: int = 250
    dna_length: int = 15000
    corpus_docs: int = 600
    # graph / linalg / cluster / opt / signal / stats
    graph_nodes: int = 120
    graph_batches: int = 12
    dense_nodes: int = 130
    dense_sources: int = 1500
    sparse_nodes: int = 2000
    bfs_sources: int = 400
    matmul_size: int = 90
    matmul_rounds: int = 20
    solve_size: int = 100
    solve_count: int = 25
    spectral_n: int = 700
    spectral_iters: int = 10
    cluster_points: int = 3500
    cluster_restarts: int = 14
    anneal_cities: int = 60
    anneal_steps: int = 170000
    knapsack_items: int = 120
    knapsack_capacity: int = 6000
    knapsack_runs: int = 20
    dp_rounds: int = 4
    chain_length: int = 130
    partition_n: int = 2500
    path_grids: int = 300
    signal_length: int = 8000
    signal_taps: int = 64
    channels: int = 14
    series_length: int = 12000
    drift_channels: int = 12
    csv_rows: int = 30000
    bootstrap_rounds: int = 60
    rank_samples: int = 800


PRESETS: Dict[str, Scale] = {
    "tiny": Scale(
        name="tiny", nbody_steps=300, nbody_chunk=100, mandel_width=24, mandel_height=12, mandel_iter=40,
        pi_samples=3000, walkers=8, walk_steps=20, queue_customers=100, life_size=8, life_generations=3,
        fannkuch_n=6, queens_n=6, sieve_limit=3000, prime_count=100, collatz_limit=200, digit_limit=300,
        totient_limit=500, coprime_limit=40, perfect_limit=600, automaton_cells=30, automaton_steps=10,
        dictionary_words=20, queries=5, diff_lines=2, dna_reads=2, dna_length=300, corpus_docs=12,
        graph_nodes=12, graph_batches=2, dense_nodes=20, dense_sources=3, sparse_nodes=60, bfs_sources=3,
        matmul_size=6, matmul_rounds=2, solve_size=6, solve_count=2, spectral_n=12, spectral_iters=3,
        cluster_points=60, cluster_restarts=2, anneal_cities=10, anneal_steps=200, knapsack_items=8,
        knapsack_capacity=40, knapsack_runs=2, dp_rounds=1, chain_length=12, partition_n=60, rank_samples=30, path_grids=2, signal_length=80, signal_taps=6,
        channels=2, series_length=120, drift_channels=1, csv_rows=30, bootstrap_rounds=3),
    "small": Scale(),
}


# Scale fields that grow linearly with the amount of work; the rest (grid sizes, depths) stay fixed so
# that kernel arguments keep the shapes the unit tests and traces were built for.
_LINEAR_FIELDS = {"nbody_steps", "pi_samples", "walkers", "queue_customers", "life_generations", "collatz_limit",
                  "digit_limit", "totient_limit", "automaton_steps", "queries", "diff_lines", "dna_reads", "corpus_docs", "graph_batches",
                  "dense_sources", "bfs_sources", "matmul_rounds", "solve_count", "cluster_restarts",
                  "anneal_steps", "knapsack_runs", "dp_rounds", "path_grids", "channels", "csv_rows"}


def full_scale() -> Scale:
    """About three times the work of the small preset in most jobs (and one size step up for the puzzles)."""
    base = Scale()
    changes = {}
    for f in dataclasses.fields(base):
        v = getattr(base, f.name)
        if f.name == "name":
            changes[f.name] = "full"
        elif isinstance(v, int) and f.name in _LINEAR_FIELDS:
            changes[f.name] = v * 3
    changes["fannkuch_n"] = 10
    changes["queens_n"] = 14
    return dataclasses.replace(base, **changes)


PRESETS["full"] = full_scale()


@dataclass
class Settings:
    """Everything a command needs besides its own arguments."""

    scale: Scale
    seed: int = 2024
    verbose: bool = False
    use_numpy: bool = False
    workdir: Optional[str] = None


def load_overrides(path: str) -> Dict[str, int]:
    """Read `[scale]` integer overrides from an INI file.  Unknown keys are reported and skipped."""
    parser = configparser.ConfigParser()
    if not parser.read(path):
        raise FileNotFoundError(f"config file not found: {path}")
    known = {f.name for f in dataclasses.fields(Scale)} - {"name"}
    out: Dict[str, int] = {}
    if parser.has_section("scale"):
        for key, raw in parser.items("scale"):
            if key not in known:
                log.warning("ignoring unknown scale key %r in %s", key, path)
                continue
            try:
                out[key] = int(raw)
            except ValueError:
                raise ValueError(f"[scale] {key} must be an integer, got {raw!r}") from None
    return out


def parse_assignments(items: List[str]) -> Dict[str, int]:
    """Parse `--set key=value` pairs into integer overrides."""
    out: Dict[str, int] = {}
    for item in items:
        key, sep, raw = item.partition("=")
        if not sep:
            raise ValueError(f"expected key=value, got {item!r}")
        out[key.strip()] = int(raw)
    return out


def build_settings(preset: str, config_path: Optional[str] = None, assignments: Optional[List[str]] = None,
                   seed: Optional[int] = None, verbose: bool = False, use_numpy: bool = False) -> Settings:
    """Combine a preset with file and command-line overrides (command line wins)."""
    scale = PRESETS[preset]
    overrides: Dict[str, int] = {}
    if config_path:
        overrides.update(load_overrides(config_path))
    overrides.update(parse_assignments(assignments or []))
    if overrides:
        valid = {f.name for f in dataclasses.fields(Scale)}
        bad = sorted(set(overrides) - valid)
        if bad:
            raise ValueError("unknown scale key(s): " + ", ".join(bad))
        scale = dataclasses.replace(scale, **overrides)
    env_seed = os.environ.get("QUANTA_SEED")
    chosen = seed if seed is not None else int(env_seed) if env_seed else 2024
    return Settings(scale=scale, seed=chosen, verbose=verbose, use_numpy=use_numpy)
