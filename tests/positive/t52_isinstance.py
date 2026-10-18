# PySub 1.3: isinstance() / type() decided from static types; input validation raising TypeError
from typing import Optional, Union


class Point:
    x: int

    def __init__(self, x: int) -> None:
        self.x = x


def factorial(n: int) -> int:
    if not isinstance(n, int):
        raise TypeError("factorial() only accepts integral values")
    if n < 0:
        raise ValueError("factorial() not defined for negative values")
    r = 1
    for i in range(2, n + 1):
        r *= i
    return r


def mean(xs: list[float]) -> float:
    if not isinstance(xs, list):
        raise TypeError("expected a list")
    for x in xs:
        if not isinstance(x, (int, float)):
            raise TypeError("all elements must be numbers")
    return sum(xs) / len(xs)


def check_name(s: str) -> str:
    if type(s) != str:
        raise TypeError("name must be a string")
    if isinstance(s, (int, float, list)):
        return "number?"
    return s.upper()


def area(p: Optional[Point]) -> int:
    if isinstance(p, Point):
        return p.x * p.x
    return -1


def count(calls: list[int]) -> int:
    calls.append(1)
    return len(calls)


calls: list[int] = []
print(factorial(5), isinstance(True, int), isinstance(3, bool), isinstance("a", str), type(True) == bool)
print(mean([1.0, 2.0, 4.5]), check_name("ada"), area(Point(4)), area(None))
print(isinstance(count(calls), int), isinstance(count(calls), str), calls)
v: Union[int, None] = 7
w: Optional[int] = None
print(isinstance(v, int), isinstance(w, int), type(v) is not float, isinstance(1.5, (int, float)))
for n in [3, -2]:
    try:
        print(factorial(n))
    except ValueError as e:
        print("ValueError:", e)
try:
    raise TypeError("custom type error")
except TypeError as e:
    print("caught", e)
print(factorial(-1))
