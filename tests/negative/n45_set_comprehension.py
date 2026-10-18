# expect: set comprehensions are outside the PySub subset
xs: list[int] = [1, 2]
print({x for x in xs})
