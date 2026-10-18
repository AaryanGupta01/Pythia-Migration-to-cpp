# PySub 1.2: chained comparisons a < b < c == (a < b and b < c), b evaluated once; (a < b) < c is not a chain
def in_range(i: int, n: int) -> bool:
    return 0 <= i < n


xs: list[int] = [5, 1, 4]
for i in [-1, 0, 2, 3, 9]:
    if 0 <= i < len(xs):
        print(i, "ok", xs[i])
    else:
        print(i, "out of range")
a: int = 3
b: int = 3
c: int = 7
print(1 < a < 5, 1 < a < 2, a == b < c, a == b == c, a < b <= c, c > a >= b > 0)
print(not 0 < a < 2, (1 < a) < 2, (a < c) == True, 1 < a < c < 10)
print(in_range(4, 4), in_range(3, 4), in_range(-1, 4))
s: str = "m"
print("a" <= s <= "z", "a" < s < "c")
k: int = 0
while 0 <= k < len(xs) and xs[k] != 4:
    k += 1
print(k, 1 <= k <= 2, 0 < xs[k] < 5 == 5)
