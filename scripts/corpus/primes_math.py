import math


def is_prime(n):
    if n < 2:
        return False
    for d in range(2, int(math.sqrt(n)) + 1):
        if n % d == 0:
            return False
    return True


def factorize(n):
    factors = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            factors.append(d)
            n //= d
        d += 1
    if n > 1:
        factors.append(n)
    return factors


primes = [n for n in range(2, 200000) if is_prime(n)]
print(len(primes), "primes below 200000")
for n in [360, 97, 1001, 65536, 999983]:
    print(n, "=", " x ".join(str(f) for f in factorize(n)))
print("gcd(84, 36) =", math.gcd(84, 36))
