# expect: generator expressions are supported only as the sole argument
xs: list[int] = [1, 2]
print(len(x for x in xs))
