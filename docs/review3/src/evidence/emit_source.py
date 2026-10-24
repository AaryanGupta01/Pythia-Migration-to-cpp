def total(xs: list[int], n: int) -> int:
    s: int = 0
    for i in range(n):
        s += xs[i] * 2
    return s
print(total([1, 2, 3], 3))
