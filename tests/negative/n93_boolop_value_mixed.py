# expect: unrelated types
def g(out: list[int], k: int) -> int:
    return out and k
print(g([1], 2))
