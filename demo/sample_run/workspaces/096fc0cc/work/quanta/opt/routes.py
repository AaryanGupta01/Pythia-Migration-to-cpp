"""Route-length objective for the travelling-salesman annealer in quanta.opt.anneal."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_0853c756", "tour_length")
def tour_length(xs: list[float], ys: list[float], order: list[int]) -> float:
    """Length of the closed tour visiting the cities in `order` and returning to the first."""
    total: float = 0.0
    n: int = len(order)
    for i in range(n):
        a: int = order[i]
        b: int = order[(i + 1) % n]
        dx: float = xs[a] - xs[b]
        dy: float = ys[a] - ys[b]
        total += (dx * dx + dy * dy) ** 0.5
    return total
