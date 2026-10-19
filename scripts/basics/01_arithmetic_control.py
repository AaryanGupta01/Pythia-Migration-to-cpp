#@@ hello_world
print("Hello, World!")
#@@ arithmetic_ops
a = 17
b = 5
print(a + b, a - b, a * b, a / b, a // b, a % b, a ** 2)
print(-a // b, -a % b, a // -b, a % -b, 7.5 // 2, 7.5 % 2)
#@@ augmented_assign
x = 10
x += 5
x -= 3
x *= 2
x //= 5
x **= 2
x %= 7
print(x)
y = 7.5
y /= 2
print(y)
#@@ float_printing
print(0.1 + 0.2, 1 / 3, 2 / 3, 1e10, 1.5e-7, 100.0, 3.14159265358979, 2.5 * 4)
print(round(2.5), round(3.5), round(-2.5), round(2.675, 2), round(1234.5678, -2), round(7))
print(int(3.9), int(-3.9), float(3), abs(-4.5), abs(-7))
#@@ comparisons_logic
a, b, c = 3, 7, 5
print(a < b, a > b, a == 3, a != 3, a <= 3, b >= 8)
print(a < c < b, a < b < c, not a == b, a < b and b < c, a > b or c > a)
print(1 if a > b else 2, "yes" if a < b else "no")
#@@ if_elif_else_grade
score = 83
if score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 70:
    grade = "C"
else:
    grade = "F"
print("Grade:", grade)
#@@ for_range_forms
for i in range(5):
    print(i, end=" ")
print()
for i in range(2, 10, 3):
    print(i, end=" ")
print()
for i in range(10, 0, -4):
    print(i, end=" ")
print()
for i in range(0):
    print("never")
print("done")
#@@ while_countdown
n = 5
while n > 0:
    print(n)
    n -= 1
print("liftoff")
#@@ while_true_break
i = 0
while True:
    i += 1
    if i % 2 == 0:
        continue
    if i > 9:
        break
    print(i)
#@@ for_else_prime
for n in range(2, 20):
    for d in range(2, n):
        if n % d == 0:
            break
    else:
        print(n, "is prime")
#@@ nested_loops_pattern
for i in range(1, 6):
    print("*" * i)
for i in range(1, 5):
    print(" " * (4 - i) + "*" * (2 * i - 1))
#@@ sum_digits
n = 98765
total = 0
while n:
    total += n % 10
    n //= 10
print(total)
#@@ factorial_loop
n = 10
f = 1
for i in range(1, n + 1):
    f *= i
print(f)
#@@ fibonacci_loop
a, b = 0, 1
for _ in range(15):
    print(a, end=" ")
    a, b = b, a + b
print()
#@@ gcd_euclid
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

print(gcd(48, 18), gcd(17, 5), gcd(0, 9))
#@@ is_prime_function
def is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True

print([n for n in range(30) if is_prime(n)])
#@@ collatz
def collatz(n):
    steps = 0
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps

print(collatz(27), collatz(97))
#@@ power_and_mod
def power(base, exp, mod):
    result = 1
    base %= mod
    while exp > 0:
        if exp & 1:
            result = result * base % mod
        base = base * base % mod
        exp >>= 1
    return result

print(power(2, 100, 1000000007), pow(3, 200, 13))
#@@ leap_year
def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)

for y in (1900, 2000, 2023, 2024):
    print(y, is_leap(y))
#@@ temperature_table
for c in range(-10, 41, 10):
    f = c * 9 / 5 + 32
    print(f"{c:4d} C = {f:6.1f} F")
#@@ bitwise_basics
a = 0b1011
b = 0b0110
print(a & b, a | b, a ^ b, ~a, a << 2, a >> 1, bin(a), hex(255), oct(8))
print(bin(a & b).count("1"), 5 & -5)
#@@ number_formatting
n = 1234567.891
print(f"{n:,.2f}", f"{n:>15.1f}", f"{n:e}", f"{42:08d}", f"{42:+d}", f"{255:x}", f"{0.256:.1%}")
print("%d items cost %.2f total (%s)" % (3, 9.5, "ok"), "{} and {}".format(1, "two"), "{1}{0}".format("a", "b"))
#@@ math_module
import math
print(math.sqrt(144), math.floor(2.7), math.ceil(2.1), math.gcd(12, 18), math.factorial(10))
print(math.pi, math.e, math.hypot(3, 4), math.isqrt(99), abs(math.log(math.e) - 1) < 1e-12)
