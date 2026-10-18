# expect: cannot unpack a list[int] into 2 names
xs: list[list[int]] = [[1, 2]]
print([a + b for a, b in xs])
