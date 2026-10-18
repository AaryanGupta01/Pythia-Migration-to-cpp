# PySub 1.3: chained assignment a = b = v (v evaluated once, targets left to right)
def f(n: int) -> int:
    print("eval")
    return n * 2


a = b = f(3)
print(a, b)
xs: list[int] = [0, 0, 0]
i: int = 0
xs[i] = i = 2
print(xs, i)
sieve: list[bool] = [True] * 4
sieve[0] = sieve[1] = False
print(sieve)
p = q = r = "x"
print(p + q + r)
u, w = v, z = [7, 8]
print(u, w, v, z)
