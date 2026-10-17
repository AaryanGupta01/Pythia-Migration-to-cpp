"""Prime sieves and simple prime statistics."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_a4d551ee", "sieve_primes")
def sieve_primes(limit: int) -> list[int]:
    """All primes <= limit by the sieve of Eratosthenes."""
    flags: list[bool] = []
    for i in range(limit + 1):
        flags.append(True)
    primes: list[int] = []
    for p in range(2, limit + 1):
        if flags[p]:
            primes.append(p)
            for q in range(p * p, limit + 1, p):
                flags[q] = False
    return primes


@_pythia_accelerated("pythia_ff1099e9", "twin_prime_count")
def twin_prime_count(limit: int) -> int:
    """Number of twin prime pairs (p, p + 2) with p + 2 <= limit."""
    primes: list[int] = sieve_primes(limit)
    twins: int = 0
    for i in range(1, len(primes)):
        if primes[i] - primes[i - 1] == 2:
            twins += 1
    return twins


@_pythia_accelerated("pythia_da27fd77", "prime_gap_record")
def prime_gap_record(limit: int) -> int:
    """Largest gap between consecutive primes up to `limit`."""
    primes: list[int] = sieve_primes(limit)
    best: int = 0
    for i in range(1, len(primes)):
        gap: int = primes[i] - primes[i - 1]
        if gap > best:
            best = gap
    return best


def is_probable_prime(n: int) -> bool:
    """Trial division by 6k +/- 1; exact for 64-bit inputs but slow beyond ~10**12."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    d: int = 5
    while d * d <= n:
        if n % d == 0 or n % (d + 2) == 0:
            return False
        d += 6
    return True


@_pythia_accelerated("pythia_db95abb0", "prime_square_sum")
def prime_square_sum(count: int, modulus: int) -> int:
    """Sum of squares of the first `count` primes, reduced modulo `modulus`."""
    total: int = 0
    found: int = 0
    n: int = 2
    while found < count:
        if is_probable_prime(n):
            total = (total + n * n) % modulus
            found += 1
        n += 1
    return total
