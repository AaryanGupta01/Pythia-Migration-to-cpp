"""Deterministic pseudo-random numbers.

Every workload in Quanta is generated from a hand-written linear congruential generator so that a
run is reproducible bit for bit on any machine and Python version, independent of `random`.
"""
from __future__ import annotations

from typing import List, Sequence, TypeVar

T = TypeVar("T")

_A = 1103515245
_C = 12345
_M = 2147483648


class Lcg:
    """31-bit LCG (the classic ANSI C constants).  Cheap, deterministic and good enough for workloads."""

    def __init__(self, seed: int = 1) -> None:
        self.state = seed % _M

    def next_int(self, bound: int) -> int:
        """Uniform integer in [0, bound)."""
        self.state = (self.state * _A + _C) % _M
        return (self.state // 65536) % bound

    def next_float(self) -> float:
        """Uniform float in [0, 1)."""
        self.state = (self.state * _A + _C) % _M
        return self.state / _M

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self.next_float()

    def gauss(self) -> float:
        """Approximately standard normal: the sum of twelve uniforms minus six."""
        state = self.state
        total = 0.0
        for _ in range(12):
            state = (state * _A + _C) % _M
            total += state / _M
        self.state = state
        return total - 6.0

    def floats(self, n: int, lo: float = 0.0, hi: float = 1.0) -> List[float]:
        return [self.uniform(lo, hi) for _ in range(n)]

    def ints(self, n: int, bound: int) -> List[int]:
        return [self.next_int(bound) for _ in range(n)]

    def choice(self, items: Sequence[T]) -> T:
        return items[self.next_int(len(items))]

    def shuffle(self, items: List[T]) -> None:
        """Fisher-Yates shuffle in place."""
        for i in range(len(items) - 1, 0, -1):
            j = self.next_int(i + 1)
            items[i], items[j] = items[j], items[i]
