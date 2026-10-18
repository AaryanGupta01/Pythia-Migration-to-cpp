# expect: multiple values for argument
def f(a: int, b: int = 2) -> int:
    return a + b
print(f(1, a=3))
