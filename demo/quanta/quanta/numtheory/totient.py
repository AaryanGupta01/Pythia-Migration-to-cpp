"""Euler's totient function and coprimality counting."""


def totient_sieve(limit: int) -> list[int]:
    """phi(n) for every n in 0..limit, computed with a sieve over the prime factors."""
    phi: list[int] = []
    for n in range(limit + 1):
        phi.append(n)
    for p in range(2, limit + 1):
        if phi[p] == p:
            for m in range(p, limit + 1, p):
                phi[m] = phi[m] // p * (p - 1)
    return phi


def totient_sum(limit: int) -> int:
    """Sum of phi(n) for 1 <= n <= limit (the number of reduced fractions with denominator <= limit)."""
    phi: list[int] = totient_sieve(limit)
    total: int = 0
    for n in range(1, limit + 1):
        total += phi[n]
    return total


def count_coprime_pairs(limit: int) -> int:
    """Pairs (a, b) with 1 <= a < b <= limit and gcd(a, b) = 1, by running Euclid's algorithm on each pair."""
    pairs: int = 0
    for b in range(2, limit + 1):
        for a in range(1, b):
            x: int = a
            y: int = b
            while y != 0:
                t: int = x % y
                x = y
                y = t
            if x == 1:
                pairs += 1
    return pairs


def perfect_numbers(limit: int) -> list[int]:
    """Perfect numbers (equal to the sum of their proper divisors) up to `limit`, by a divisor-sum sieve."""
    sums: list[int] = []
    for n in range(limit + 1):
        sums.append(0)
    for d in range(1, limit // 2 + 1):
        for m in range(2 * d, limit + 1, d):
            sums[m] += d
    found: list[int] = []
    for n in range(2, limit + 1):
        if sums[n] == n:
            found.append(n)
    return found
