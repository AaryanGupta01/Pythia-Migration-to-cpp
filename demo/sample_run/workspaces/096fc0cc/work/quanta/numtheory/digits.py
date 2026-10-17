"""Digit-level number puzzles.  Written without type annotations, the way most scripts start out."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


def digit_sum(n):
    total = 0
    while n > 0:
        total += n % 10
        n = n // 10
    return total


@_pythia_accelerated("pythia_afaf9303", "digital_root_total")
def digital_root_total(limit):
    """Sum of the digital roots (repeated digit sums) of 1..limit-1."""
    total = 0
    for n in range(1, limit):
        r = n
        while r >= 10:
            s = 0
            while r > 0:
                s += r % 10
                r = r // 10
            r = s
        total += r
    return total


@_pythia_accelerated("pythia_75036284", "count_palindromes")
def count_palindromes(limit):
    """How many integers in 1..limit-1 read the same in both directions."""
    found = 0
    for n in range(1, limit):
        rev = 0
        m = n
        while m > 0:
            rev = rev * 10 + m % 10
            m = m // 10
        if rev == n:
            found += 1
    return found
