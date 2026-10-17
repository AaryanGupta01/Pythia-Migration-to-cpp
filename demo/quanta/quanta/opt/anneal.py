"""Simulated annealing for the travelling-salesman problem (2-opt moves, geometric cooling)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

from quanta.opt.routes import tour_length
from quanta.util.rng import Lcg

log = logging.getLogger(__name__)


@dataclass
class AnnealResult:
    """Outcome of one annealing run."""

    best_length: float
    start_length: float
    accepted: int
    proposed: int
    order: List[int] = field(default_factory=list)

    @property
    def improvement(self) -> float:
        return 1.0 - self.best_length / self.start_length


class TourAnnealer:
    """Anneal a closed tour over fixed city coordinates.

    The objective is recomputed from scratch for every proposal: simple and obviously correct, and
    the dominant cost of a run (see quanta.opt.routes.tour_length)."""

    def __init__(self, xs: List[float], ys: List[float], seed: int = 11) -> None:
        if len(xs) != len(ys) or len(xs) < 4:
            raise ValueError("need at least four cities with matching x/y lists")
        self.xs, self.ys = xs, ys
        self.rng = Lcg(seed)

    def run(self, steps: int, t_start: float = 1.0, t_end: float = 0.01) -> AnnealResult:
        n = len(self.xs)
        order = list(range(n))
        current = tour_length(self.xs, self.ys, order)
        best, best_order = current, order[:]
        start = current
        accepted = 0
        cooling = (t_end / t_start) ** (1.0 / max(1, steps))
        temp = t_start
        for _ in range(steps):
            i = self.rng.next_int(n - 1)
            j = self.rng.next_int(n - 1)
            if i > j:
                i, j = j, i
            if i == j:
                continue
            order[i:j + 1] = reversed(order[i:j + 1])
            candidate = tour_length(self.xs, self.ys, order)
            delta = candidate - current
            if delta < 0 or self.rng.next_float() < acceptance_probability(delta, temp):
                current = candidate
                accepted += 1
                if current < best:
                    best, best_order = current, order[:]
            else:
                order[i:j + 1] = reversed(order[i:j + 1])
            temp *= cooling
        log.debug("anneal: %d/%d accepted, %.3f -> %.3f", accepted, steps, start, best)
        return AnnealResult(best, start, accepted, steps, best_order)


def acceptance_probability(delta: float, temp: float) -> float:
    """Metropolis acceptance probability exp(-delta / temp) from a short Taylor series (x > -8)."""
    x: float = -delta / temp
    if x < -8.0:
        return 0.0
    term: float = 1.0
    total: float = 1.0
    for k in range(1, 18):
        term = term * x / k
        total += term
    return max(0.0, total)
