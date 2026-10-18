# expect: must be a constant
def f() -> int:
    print("side effect")
    return 1


class C:
    X = f()
