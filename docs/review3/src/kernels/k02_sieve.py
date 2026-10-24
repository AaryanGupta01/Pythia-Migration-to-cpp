def count_primes(n: int) -> int:
    sieve: list[bool] = [True] * (n + 1)
    sieve[0] = False
    sieve[1] = False
    i: int = 2
    while i * i <= n:
        if sieve[i]:
            j: int = i * i
            while j <= n:
                sieve[j] = False
                j += i
        i += 1
    total: int = 0
    for v in sieve:
        if v:
            total += 1
    return total

print(count_primes(4000000))
