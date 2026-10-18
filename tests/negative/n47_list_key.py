# expect: a key function must return int, float, bool or str
xs: list[int] = [3, 1]
print(sorted(xs, key=lambda a: [a, -a]))
