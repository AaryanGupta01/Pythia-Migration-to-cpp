# expect: cannot unpack
xs: list[int] = [1, 2]
for a, b in xs:
    print(a, b)
