# expect: Generator expression must be parenthesized
xs: list[int] = [3, 1]
print(max(x for x in xs, key=abs))
