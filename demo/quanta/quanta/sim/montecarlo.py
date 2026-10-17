"""Monte-Carlo estimators driven by an inline linear congruential generator.

The generator is inlined (rather than imported from quanta.util.rng) so that each estimator is a
self-contained function whose result depends only on its arguments.
"""


def estimate_pi(samples: int, seed: int) -> float:
    """Estimate pi from the fraction of random points in the unit square that fall inside the quarter circle."""
    state: int = seed % 2147483648
    hits: int = 0
    for i in range(samples):
        state = (state * 1103515245 + 12345) % 2147483648
        x: float = state / 2147483648.0
        state = (state * 1103515245 + 12345) % 2147483648
        y: float = state / 2147483648.0
        if x * x + y * y <= 1.0:
            hits += 1
    return 4.0 * hits / samples


def integrate_poly(coeffs: list[float], lo: float, hi: float, samples: int, seed: int) -> float:
    """Monte-Carlo integral of the polynomial sum(coeffs[k] * x**k) over [lo, hi]."""
    state: int = seed % 2147483648
    total: float = 0.0
    for i in range(samples):
        state = (state * 1103515245 + 12345) % 2147483648
        x: float = lo + (hi - lo) * (state / 2147483648.0)
        acc: float = 0.0
        for k in range(len(coeffs) - 1, -1, -1):
            acc = acc * x + coeffs[k]
        total += acc
    return total / samples * (hi - lo)


def walk_endpoints(walkers: int, steps: int, seed: int) -> list[int]:
    """Final positions of independent +/-1 random walks, returned as a list for later histogramming."""
    state: int = seed % 2147483648
    ends: list[int] = []
    for w in range(walkers):
        pos: int = 0
        for s in range(steps):
            state = (state * 1103515245 + 12345) % 2147483648
            if (state // 65536) % 2 == 0:
                pos += 1
            else:
                pos -= 1
        ends.append(pos)
    return ends
