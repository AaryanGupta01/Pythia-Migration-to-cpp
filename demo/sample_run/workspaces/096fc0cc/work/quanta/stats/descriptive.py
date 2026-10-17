"""Descriptive statistics over lists of floats."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


def histogram(values: list[float], bins: int, lo: float, hi: float) -> list[int]:
    """Counts of values per equal-width bin over [lo, hi); values outside the range are ignored."""
    counts: list[int] = []
    for b in range(bins):
        counts.append(0)
    width: float = (hi - lo) / bins
    for v in values:
        if v >= lo and v < hi:
            idx: int = int((v - lo) / width)
            if idx >= bins:
                idx = bins - 1
            counts[idx] += 1
    return counts


def rolling_std(values: list[float], window: int) -> list[float]:
    """Population standard deviation over a trailing window (recomputed from scratch at each position)."""
    out: list[float] = []
    for i in range(len(values)):
        start: int = max(0, i - window + 1)
        span: int = i - start + 1
        mean: float = 0.0
        for k in range(start, i + 1):
            mean += values[k]
        mean = mean / span
        var: float = 0.0
        for k in range(start, i + 1):
            d: float = values[k] - mean
            var += d * d
        out.append((var / span) ** 0.5)
    return out


def autocorrelation(values: list[float], lag: int) -> float:
    """Sample autocorrelation of the series at the given lag."""
    n: int = len(values)
    mean: float = 0.0
    for v in values:
        mean += v
    mean = mean / n
    num: float = 0.0
    den: float = 0.0
    for i in range(n):
        den += (values[i] - mean) * (values[i] - mean)
        if i + lag < n:
            num += (values[i] - mean) * (values[i + lag] - mean)
    return num / den


@_pythia_accelerated("pythia_ce227290", "weighted_moments")
def weighted_moments(values: list[float], weights: list[float]) -> list[float]:
    """[weighted mean, weighted variance, weighted skewness] of the sample."""
    total_w = 0.0
    mean = 0.0
    for v, w in zip(values, weights):
        total_w += w
        mean += v * w
    mean = mean / total_w
    var = 0.0
    skew = 0.0
    for v, w in zip(values, weights):
        d = v - mean
        var += w * d * d
        skew += w * d * d * d
    var = var / total_w
    skew = skew / total_w / (var ** 1.5) if var > 0 else 0.0
    return [mean, var, skew]


def clip_fraction(values: list[float], lo: float, hi: float) -> float:
    """Share of samples that fall outside [lo, hi]."""
    if not values:
        return 0.0
    outside = len([v for v in values if v < lo or v > hi])
    return outside / len(values)
