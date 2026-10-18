# expect: unexpected keyword argument
def f(a: int, b: int = 2) -> int:
    return a + b
print(f(1, c=3))
