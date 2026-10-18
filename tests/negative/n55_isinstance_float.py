# expect: cannot be decided statically
def f(x: float) -> bool:
    return isinstance(x, float)
print(f(2.0))
