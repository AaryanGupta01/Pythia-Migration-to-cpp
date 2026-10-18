# expect: a key function must return int, float, bool, str or a tuple of those
xs: list[int] = [3, 1]
print(sorted(xs, key=lambda a: [a, -a]))
