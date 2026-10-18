# expect: enumerate() is supported only as the iterable
xs: list[int] = [1, 2]
print(len(enumerate(xs)))
