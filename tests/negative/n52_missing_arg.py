# expect: missing
def f(a: int, b: int, c: int = 0) -> int:
    return a + b + c
print(f(1, c=3))
