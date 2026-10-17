"""Test-matrix constructors."""
from __future__ import annotations

from typing import List

from quanta.util.rng import Lcg


def random_matrix(rng: Lcg, rows: int, cols: int) -> List[List[float]]:
    return [[rng.uniform(-1.0, 1.0) for _ in range(cols)] for _ in range(rows)]


def diagonally_dominant(rng: Lcg, n: int) -> List[List[float]]:
    """Random n x n matrix whose diagonal dominates each row, so elimination is well conditioned."""
    m = random_matrix(rng, n, n)
    for i in range(n):
        m[i][i] += n
    return m


def residual_norm(a: List[List[float]], x: List[float], b: List[float]) -> float:
    """Euclidean norm of a x - b."""
    total = 0.0
    for row, rhs in zip(a, b):
        r = sum(aij * xj for aij, xj in zip(row, x)) - rhs
        total += r * r
    return total ** 0.5
