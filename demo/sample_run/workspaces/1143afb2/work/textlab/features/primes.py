"""Prime-based features: a trial-division helper plus a checksum built on it."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_e23224d4", "is_prime")
def is_prime(n: int) -> bool:
    if n < 2:
        return False
    d: int = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


@_pythia_accelerated("pythia_820e97a5", "prime_square_sum")
def prime_square_sum(limit: int, mod: int) -> int:
    total: int = 0
    for p in range(2, limit):
        if is_prime(p):
            total = (total + p * p) % mod
    return total
