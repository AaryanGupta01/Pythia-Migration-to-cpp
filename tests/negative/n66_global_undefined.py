# expect: must be assigned at module level
def f() -> None:
    global total
    total = 1
f()
