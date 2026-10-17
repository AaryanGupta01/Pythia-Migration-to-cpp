"""Collatz (3n + 1) trajectories."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_cb082849", "collatz_steps")
def collatz_steps(n: int) -> int:
    """Number of halving/tripling steps needed to reach 1 from n."""
    steps: int = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        steps += 1
    return steps


@_pythia_accelerated("pythia_d4f149ab", "longest_collatz")
def longest_collatz(limit: int) -> int:
    """Starting value below `limit` with the longest trajectory (smallest one on ties)."""
    best_start: int = 1
    best_len: int = 0
    for start in range(1, limit):
        length: int = collatz_steps(start)
        if length > best_len:
            best_len = length
            best_start = start
    return best_start


def peak_value(start: int) -> int:
    """Highest value visited on the trajectory from `start`."""
    peak: int = start
    n: int = start
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        if n > peak:
            peak = n
    return peak
