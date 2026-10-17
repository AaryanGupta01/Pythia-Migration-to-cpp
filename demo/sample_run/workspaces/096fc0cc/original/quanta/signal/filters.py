"""Linear filters for evenly sampled signals."""


def fir_filter(signal: list[float], taps: list[float]) -> list[float]:
    """Causal finite-impulse-response filter: out[i] = sum_k taps[k] * signal[i - k] (zero history)."""
    n: int = len(signal)
    m: int = len(taps)
    out: list[float] = []
    for i in range(n):
        acc: float = 0.0
        top: int = min(m, i + 1)
        for k in range(top):
            acc += taps[k] * signal[i - k]
        out.append(acc)
    return out


def convolve(a: list[float], b: list[float]) -> list[float]:
    """Full discrete convolution; the result has len(a) + len(b) - 1 samples."""
    out: list[float] = []
    for i in range(len(a) + len(b) - 1):
        out.append(0.0)
    for i in range(len(a)):
        for j in range(len(b)):
            out[i + j] += a[i] * b[j]
    return out


def hann_taps(count: int) -> list[float]:
    """Smoothing taps shaped like a raised-cosine bump (parabolic approximation), normalised to sum 1."""
    taps: list[float] = []
    total: float = 0.0
    for k in range(count):
        x: float = (k + 0.5) / count
        w: float = 4.0 * x * (1.0 - x)
        taps.append(w)
        total += w
    for k in range(count):
        taps[k] = taps[k] / total
    return taps


def moving_average(signal: list[float], width: int) -> list[float]:
    """Trailing moving average computed with a running sum; early samples average what exists."""
    out: list[float] = []
    running: float = 0.0
    for i in range(len(signal)):
        running += signal[i]
        if i >= width:
            running -= signal[i - width]
        span: int = min(i + 1, width)
        out.append(running / span)
    return out


def exp_smooth(signal: list[float], alpha: float) -> list[float]:
    """Exponentially weighted moving average with smoothing factor `alpha` in (0, 1]."""
    smoothed = [signal[0]] if signal else []
    for i, x in enumerate(signal[1:], start=1):
        prev = smoothed[i - 1]
        smoothed.append(alpha * x + (1.0 - alpha) * prev)
    return smoothed
