# expect: default values must be constants
N = 3
def f(a: int = N) -> int:
    return a
print(f())
