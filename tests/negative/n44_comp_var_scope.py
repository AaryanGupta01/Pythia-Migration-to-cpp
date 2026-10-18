# expect: name 'x' is not defined
xs: list[int] = [1, 2]
ys: list[int] = [x * 2 for x in xs]
print(x)
