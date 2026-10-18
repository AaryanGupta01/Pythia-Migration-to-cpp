# expect: is a tuple, which PySub does not have
xs: list[int] = [3, 1]
for p in enumerate(xs):
    print(p)
