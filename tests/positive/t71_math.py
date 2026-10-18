import math
from math import floor, ceil, sqrt as root, pi


def circle(r: float) -> float:
    return math.pi * r * r


def dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    for i in range(2, math.isqrt(n) + 1):
        if n % i == 0:
            return False
    return True


print(math.sqrt(16), math.sqrt(2) == root(2), math.isqrt(99), math.isqrt(10 ** 12))
print(math.floor(2.7), math.floor(-2.1), math.ceil(2.1), math.ceil(-2.9), math.trunc(-2.9), floor(5), ceil(True))
print(math.fabs(-3), math.fabs(-0.5), math.pow(2, 10), math.pow(2.5, 2), math.pow(9, 0.5))
print(math.gcd(12, 18), math.gcd(-4, 6), math.gcd(0, 0), math.gcd(12, 18, 30), math.lcm(4, 6), math.lcm(0, 5), math.lcm(2, 3, 4))
print(math.factorial(0), math.factorial(5), math.factorial(20), math.comb(10, 3), math.comb(5, 7), math.comb(60, 30))
print(math.perm(5, 2), math.perm(5), math.perm(3, 5), math.perm(20, 20))
print(math.isfinite(1.5), math.isfinite(math.inf), math.isinf(-math.inf), math.isnan(math.nan), math.isnan(1.0))
print(math.copysign(3, -0.0), math.fmod(-5, 3), math.fmod(5.5, 2), math.copysign(0.0, -1))
print(math.inf, -math.inf, math.nan, math.inf > 1e308)
print(math.isclose(0.1 + 0.2, 0.3), math.isclose(1.0, 1.1), math.isclose(0, 1e-12, abs_tol=1e-9), math.isclose(1, 1.0001, rel_tol=0.001))
print(f"{math.pi:.6f} {math.e:.6f} {math.tau:.6f} {pi:.4f}")
print(f"{math.exp(1):.6f} {math.log(10):.6f} {math.log(8, 2):.6f} {math.log2(1024):.6f} {math.log10(1000):.6f}")
print(f"{math.sin(1):.6f} {math.cos(1):.6f} {math.tan(1):.6f} {math.atan(1):.6f} {math.atan2(1, -1):.6f}")
print(f"{math.asin(0.5):.6f} {math.acos(0.5):.6f} {math.degrees(math.pi):.6f} {math.radians(180):.6f}")
print(f"{math.sinh(1):.6f} {math.cosh(1):.6f} {math.tanh(1):.6f} {math.log1p(1):.6f} {math.expm1(1):.6f}")
print(f"{circle(2.0):.4f} {dist(0.0, 0.0, 3.0, 4.0)}")
print(math.exp(0), math.log(1), math.sin(0), math.cos(0), math.sqrt(0), math.log2(8), math.log10(100))
print(is_prime(97), is_prime(91), is_prime(2), is_prime(1))
total = 0.0
for k in range(1, 6):
    total += 1.0 / math.factorial(k)
print(f"{total:.9f}")
print(math.log(1, 5), math.log(5, 5), math.sqrt(True), math.isqrt(True))
for bad in [0, -1]:
    try:
        print(math.log(bad))
    except ValueError as e:
        print("log", bad, e)
try:
    print(math.sqrt(-4))
except ValueError as e:
    print("sqrt", e)
try:
    print(math.factorial(-1))
except ValueError as e:
    print("fact", e)
try:
    print(math.exp(1000))
except OverflowError as e:
    print("exp", e)
try:
    print(math.log(2, 1))
except ZeroDivisionError as e:
    print("log base 1", e)
try:
    print(math.isqrt(-1))
except ValueError as e:
    print("isqrt", e)
try:
    print(math.comb(5, -1))
except ValueError as e:
    print("comb", e)
try:
    print(math.comb(-5, 1))
except ValueError as e:
    print("comb n", e)
try:
    print(math.asin(2.0))
except ValueError as e:
    print("asin", e)
try:
    print(math.sin(math.inf))
except ValueError as e:
    print("sin", e)
try:
    print(math.floor(math.nan))
except ValueError as e:
    print("floor", e)
try:
    print(math.ceil(math.inf))
except OverflowError as e:
    print("ceil", e)
try:
    print(math.fmod(1, 0))
except ValueError as e:
    print("fmod", e)
try:
    print(math.pow(0, -1))
except ValueError as e:
    print("pow", e)
try:
    print(math.log10(0.0))
except ValueError as e:
    print("log10", e)
try:
    print(math.log2(-0.5))
except ValueError as e:
    print("log2", e)
