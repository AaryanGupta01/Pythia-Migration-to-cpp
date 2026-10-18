# PySub 1.3: default parameter values and keyword arguments
from __future__ import annotations
from typing import List, Optional


def power(base: int, exp: int = 2, mod: int = 0) -> int:
    r = base ** exp
    if mod != 0:
        r = r % mod
    return r


def greet(name: str, greeting: str = "Hello", punct: str = "!") -> str:
    return greeting + ", " + name + punct


def scale(xs: List[float], factor: float = 2.0, offset: float = -0.5) -> List[float]:
    out: List[float] = []
    for x in xs:
        out.append(x * factor + offset)
    return out


def append_to(x: int, acc: list[int] = []) -> list[int]:
    acc.append(x)                     # the default list is shared between calls, as in CPython
    return acc


def find(xs: list[int], target: int, start: int = 0) -> Optional[int]:
    for i in range(start, len(xs)):
        if xs[i] == target:
            return i
    return None


def trace(tag: str) -> int:
    print("eval", tag)
    return len(tag)


def pair(a: int, b: int, c: int = 100) -> int:
    return a * 10000 + b * 100 + c


class Counter:
    count: int
    step: int

    def __init__(self, start: int = 0, step: int = 1) -> None:
        self.count = start
        self.step = step

    def bump(self, times: int = 1) -> int:
        self.count += self.step * times
        return self.count


print(power(3), power(3, 3), power(3, exp=4), power(base=2, mod=5, exp=10), power(exp=3, base=5))
print(greet("Ada"), greet("Bob", "Hi"), greet("Cy", punct="?"), greet(punct=".", name="Di", greeting="Yo"))
print(scale([1.0, 2.5]), scale([1.0], factor=3.0), scale([4.0], offset=1.0))
print(append_to(1), append_to(2), append_to(3, []), append_to(4))
print(find([5, 6, 7, 6], 6), find([5, 6, 7, 6], 6, start=2), find([5, 6], 9))
print(pair(1, 2), pair(c=3, b=2, a=1), pair(1, c=5, b=7))
print(pair(b=trace("bb"), a=trace("a")))          # keyword arguments evaluate left to right
c = Counter()
d = Counter(10, step=5)
e = Counter(step=-1)
print(c.bump(), c.bump(times=3), d.bump(2), e.bump(), e.bump(times=4))
print(power(2, exp=40, mod=1000))
