# PySub 1.2: conditional expressions (lazy branches, nesting, in f-strings) and `not` precedence
def sign(x: int) -> str:
    return "neg" if x < 0 else "zero" if x == 0 else "pos"


def boom(n: int) -> int:
    print("boom called", n)
    return 10 // n


def pick(a: list[int], b: list[int], first: bool) -> list[int]:
    return a if first else b


xs: list[int] = [-3, 0, 7]
for x in xs:
    print(x, sign(x), "even" if x % 2 == 0 else "odd")
n: int = 0
safe: int = boom(n) if n != 0 else -1
print("safe", safe)
y: float = 2.5 if len(xs) > 2 else 0.5
print(f"y={y:.2f} {'big' if y > 1 else 'small'} {('x' * 3) if y else ''}")
print(pick([1, 2], [3], False), pick([1, 2], [3], True))
s: str = ""
for i in range(5):
    s += str(i) if i % 2 == 0 else "-"
print(s)
total: int = 0
for i in range(10):
    total += i if i > 4 else -i
print(total, not total == 15)

a: int = 3
b: list[int] = [1, 2]
print(not a == 3, not a in b, not a < 2 and a > 1, not not a, not a or True, a > 2 and not a == 4)
