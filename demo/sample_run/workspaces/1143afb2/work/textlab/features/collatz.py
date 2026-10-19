"""Collatz stopping times. Fixable: no annotations (observed types from the trace fill them in)."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_68738d09", "collatz_longest")
def collatz_longest(limit):
    best = 0
    best_start = 1
    for start in range(1, limit):
        n = start
        steps = 0
        while n != 1:
            if n % 2 == 0:
                n = n // 2
            else:
                n = 3 * n + 1
            steps += 1
        if steps > best:
            best = steps
            best_start = start
    return best_start * 1000 + best
