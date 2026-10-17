"""Bootstrap resampling and synthetic series generators."""
from __future__ import annotations

from typing import List, Optional

from quanta.util.rng import Lcg


def ar1_series(rng: Lcg, n: int, phi: float = 0.8, shift_at: Optional[int] = None, shift: float = 0.0) -> List[float]:
    """AR(1) process x[t] = phi * x[t-1] + noise, optionally with a level shift (drift) from `shift_at`."""
    out: List[float] = []
    prev = 0.0
    for t in range(n):
        prev = phi * prev + 0.3 * rng.gauss()
        level = shift if shift_at is not None and t >= shift_at else 0.0
        out.append(prev + level)
    return out


def bootstrap_means(rng: Lcg, sample: List[float], rounds: int) -> List[float]:
    """Means of `rounds` resamples (with replacement) of `sample`."""
    n = len(sample)
    means = []
    for _ in range(rounds):
        total = 0.0
        for _ in range(n):
            total += sample[rng.next_int(n)]
        means.append(total / n)
    return means


def percentile(sorted_values: List[float], q: float) -> float:
    """Linear-interpolated percentile (q in [0, 100]) of an already sorted list."""
    if not sorted_values:
        raise ValueError("percentile of an empty sample")
    pos = (len(sorted_values) - 1) * q / 100.0
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def confidence_interval(rng: Lcg, sample: List[float], rounds: int, level: float = 95.0) -> List[float]:
    """Percentile bootstrap confidence interval [low, high] for the mean."""
    means = sorted(bootstrap_means(rng, sample, rounds))
    tail = (100.0 - level) / 2.0
    return [percentile(means, tail), percentile(means, 100.0 - tail)]
