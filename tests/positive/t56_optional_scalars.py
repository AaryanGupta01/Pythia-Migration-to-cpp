# PySub 1.3: Optional scalars, narrowing through if/while/and/or/early return, defaults of None
from typing import Optional


class Cell:
    value: Optional[int]
    label: Optional[str]

    def __init__(self, value: Optional[int] = None, label: str | None = None) -> None:
        self.value = value
        self.label = label


def parse_int(s: str) -> Optional[int]:
    if len(s) == 0 or not s.isdigit():
        return None
    return int(s)


def total(xs: list[str], default: Optional[int] = None) -> int:
    t = 0
    for s in xs:
        v = parse_int(s)
        if v is None:
            if default is None:
                continue
            v = default
        t += v
    return t


def safe_div(a: float, b: float) -> Optional[float]:
    return a / b if b != 0 else None


def countdown(n: Optional[int]) -> int:
    steps = 0
    while n is not None and n > 0:
        n -= 1
        steps += 1
        if n == 2:
            n = None
    return steps


def memo_fib(n: int, cache: dict[int, int] = {}) -> int:
    if n in cache:
        return cache[n]
    r = n if n < 2 else memo_fib(n - 1) + memo_fib(n - 2)
    cache[n] = r
    return r


def first_word(s: str, sep: Optional[str] = None) -> str:
    if sep is None:
        sep = " "
    return s.split(sep)[0]


print(parse_int("42"), parse_int("x"), parse_int(""))
print(total(["1", "x", "3"]), total(["1", "x", "3"], 10), total(["a"], default=-5))
print(safe_div(1.0, 4.0), safe_div(1.0, 0.0))
print(countdown(10), countdown(None), countdown(1))
print(memo_fib(60), memo_fib(10))
print(first_word("hello big world"), first_word("a,b", sep=","))
c = Cell()
d = Cell(5, label="five")
print(c.value, c.label, d.value, d.label, c.value is None, d.value == 5)
v = d.value
if v is not None:
    print(v * 3)
w: Optional[int] = None
w = 4
print(w + 1)
x: Optional[float] = 2.5
y: Optional[bool] = None
print(x, y, bool(y), bool(x), x if x else 0.0)
z = parse_int("7") if True else None
print(z, z == 7, 7 == z, z != 8)
n: Optional[int] = parse_int("12")
if not n:
    print("none or zero")
else:
    print("n is", n + 1)
if n is None:
    raise ValueError("no number")
print(n * n)
m = parse_int("oops")
print(str(m * 2) if m is not None else "no m")
k = c.value
print(k if k is not None else -1, k)
