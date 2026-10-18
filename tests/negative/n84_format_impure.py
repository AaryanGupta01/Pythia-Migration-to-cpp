# expect: must be used exactly once
def f() -> int:
    return 1
print("{0} {0}".format(f()))
