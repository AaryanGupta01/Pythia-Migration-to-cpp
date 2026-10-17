"""Optional NumPy fast paths.  Quanta works without NumPy; these helpers use it when it is importable."""
from __future__ import annotations

from typing import List

from quanta.linalg.dense import matmul

try:  # NumPy is optional and not required by any default code path
    import numpy as np
except ImportError:  # pragma: no cover
    np = None


def have_numpy() -> bool:
    return np is not None


def matmul_fast(a: List[List[float]], b: List[List[float]]) -> List[List[float]]:
    """Matrix product through NumPy when available, otherwise the pure-Python kernel."""
    if np is None:
        return matmul(a, b)
    return (np.array(a) @ np.array(b)).tolist()


def column_norms(a: List[List[float]]) -> List[float]:
    """Euclidean norm of every column."""
    if np is not None:
        return np.linalg.norm(np.array(a), axis=0).tolist()
    return [sum(row[j] ** 2 for row in a) ** 0.5 for j in range(len(a[0]))]
