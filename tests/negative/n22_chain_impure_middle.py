# expect: chained comparison with a computed middle operand
def f(x: int) -> int:
    print("called")
    return x


print(0 < f(3) < 5)
