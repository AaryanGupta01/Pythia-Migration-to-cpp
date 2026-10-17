"""Online drift detection: compare the recent variance of a growing series with its long-run level."""


def tail_variance(series: list[float], window: int) -> float:
    """Population variance of the last `window` samples of `series` (all of them if fewer exist)."""
    n: int = len(series)
    start: int = max(0, n - window)
    count: int = n - start
    mean: float = 0.0
    for i in range(start, n):
        mean += series[i]
    mean = mean / count
    var: float = 0.0
    for i in range(start, n):
        d: float = series[i] - mean
        var += d * d
    return var / count
