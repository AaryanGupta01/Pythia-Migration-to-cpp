# Error paths with user classes: exact exception messages for None operands of dunder operators, len() with a
# negative __len__, missing attributes on None, exceptions raised inside __str__ / methods / properties
from typing import Optional


class P:
    def __init__(self, x: int) -> None:
        self.x = x

    def __lt__(self, other: "P") -> bool:
        return self.x < other.x

    def __add__(self, other: "P") -> "P":
        return P(self.x + other.x)

    def __neg__(self) -> "P":
        return P(-self.x)

    def __repr__(self) -> str:
        return f"P({self.x})"


class Weird:
    def __init__(self, n: int) -> None:
        self.n = n

    def __len__(self) -> int:
        return self.n

    def __str__(self) -> str:
        if self.n > 100:
            raise ValueError("too big to show")
        return "W" * self.n


class Box:
    def __init__(self, v: Optional[P]) -> None:
        self.v = v

    @property
    def doubled(self) -> P:
        if self.v is None:
            raise ValueError("empty box")
        return self.v + self.v


def attempt(i: int) -> None:
    none_p: Optional[P] = None
    try:
        if i == 0:
            print(P(1) < none_p)
        elif i == 1:
            print(none_p < P(1))
        elif i == 2:
            print(P(1) + none_p)
        elif i == 3:
            print(none_p + P(1))
        elif i == 4:
            print(-none_p)
        elif i == 5:
            print(len(Weird(-1)))
        elif i == 6:
            print(Weird(200))
        elif i == 7:
            print(Box(None).doubled)
        elif i == 8:
            print(none_p.x)
        elif i == 9:
            print(sorted([P(2), none_p, P(1)]))
        elif i == 10:
            print(min([P(3), P(2)]), max([P(1)]), Box(P(4)).doubled)
            print(min([none_p, P(2)]))
        else:
            ws: list[P] = []
            print(max(ws))
    except TypeError as e:
        print("TypeError:", e)
    except ValueError as e:
        print("ValueError:", e)
    except KeyError as e:
        print("KeyError:", e)
    except AttributeError as e:
        print("AttributeError:", e)


for i in range(12):
    attempt(i)
print(len(Weird(3)), str(Weird(2)), bool(Weird(0)), bool(Weird(1)))
w: Optional[Weird] = None
print(len(w))
