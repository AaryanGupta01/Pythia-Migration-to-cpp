"""Small iteration helpers shared by the command line tools."""
from __future__ import annotations

from typing import Callable, Iterable, Iterator, List, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")


def chunked(items: Sequence[T], size: int) -> Iterator[Sequence[T]]:
    """Yield consecutive slices of at most `size` items."""
    for start in range(0, len(items), size):
        yield items[start:start + size]


def sliding_windows(values: Sequence[float], width: int) -> Iterator[Sequence[float]]:
    """Yield every window of `width` consecutive values."""
    for start in range(len(values) - width + 1):
        yield values[start:start + width]


def make_decay(rate: float) -> Callable[[float], float]:
    """Return a function that decays its argument by `rate` each time it is called."""
    state = {"scale": 1.0}

    def decay(x: float) -> float:
        state["scale"] *= rate
        return x * state["scale"]

    return decay


def combine_counts(*tables: dict) -> dict:
    """Merge any number of count tables by adding the values of equal keys."""
    merged: dict = {}
    for table in tables:
        for key, value in table.items():
            merged[key] = merged.get(key, 0) + value
    return merged


def extrema(values: Sequence[float]) -> Tuple[float, float]:
    """(smallest, largest) value of a non-empty sequence."""
    lo = hi = values[0]
    for v in values:
        if v < lo:
            lo = v
        elif v > hi:
            hi = v
    return lo, hi


def first_peak(values: Sequence[float], threshold: float) -> Optional[int]:
    """Index of the first sample above `threshold` that is not exceeded by its neighbours, if any."""
    for i in range(1, len(values) - 1):
        if values[i] > threshold and values[i] >= values[i - 1] and values[i] >= values[i + 1]:
            return i
    return None


def coerce_cell(value):
    """Interpret a CSV cell as int, float or the original string, in that order of preference."""
    for convert in (int, float):
        try:
            return convert(value)
        except ValueError:
            continue
    return value.strip()


def pairwise_sums(values: List[float], step: int = 1) -> List[float]:
    """Sums of values `step` apart: v[i] + v[i + step]."""
    return [values[i] + values[i + step] for i in range(len(values) - step)]
