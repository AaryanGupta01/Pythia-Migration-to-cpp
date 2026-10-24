def steps(n: int) -> int:
    c: int = 0
    while n != 1:
        if n % 2 == 0:
            n = n // 2
        else:
            n = 3 * n + 1
        c += 1
    return c

best: int = 0
arg: int = 0
for i in range(1, 300000):
    s: int = steps(i)
    if s > best:
        best = s
        arg = i
print(arg, best)
