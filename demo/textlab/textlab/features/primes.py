"""Prime-based features: a sieve helper plus a checksum built on it."""


def sieve_flags(n: int) -> list[bool]:
    flags: list[bool] = []
    for i in range(n + 1):
        flags.append(True)
    for p in range(2, n + 1):
        if flags[p]:
            m: int = p * p
            while m <= n:
                flags[m] = False
                m += p
    return flags


def prime_square_sum(n: int, mod: int) -> int:
    flags: list[bool] = sieve_flags(n)
    total: int = 0
    for p in range(2, n + 1):
        if flags[p]:
            total = (total + p * p) % mod
    return total
