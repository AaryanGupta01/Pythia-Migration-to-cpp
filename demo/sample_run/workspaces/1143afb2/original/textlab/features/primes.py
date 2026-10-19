"""Prime-based features: a trial-division helper plus a checksum built on it."""


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    d: int = 2
    while d * d <= n:
        if n % d == 0:
            return False
        d += 1
    return True


def prime_square_sum(limit: int, mod: int) -> int:
    total: int = 0
    for p in range(2, limit):
        if is_prime(p):
            total = (total + p * p) % mod
    return total
