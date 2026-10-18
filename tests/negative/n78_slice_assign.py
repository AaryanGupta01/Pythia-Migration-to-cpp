# expect: invalid assignment target
xs = [1, 2, 3]
xs[0:2] = [9]
print(xs)
