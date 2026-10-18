# Private-name mangling (self.__x is _C__x), in-place dunders (__iadd__), x[i] += v through __getitem__ /
# __setitem__, dict values that are objects updated with +=, membership / index / count / remove of objects
# through __eq__, inherited properties, class attributes redefined in a subclass read through self
from dataclasses import dataclass


class Matrix:
    def __init__(self, rows: int, cols: int) -> None:
        self.__rows = rows
        self.__cols = cols
        self.__data = [0] * (rows * cols)

    def __getitem__(self, i: int) -> int:
        return self.__data[i]

    def __setitem__(self, i: int, v: int) -> None:
        self.__data[i] = v

    def __iadd__(self, k: int) -> "Matrix":
        for i in range(len(self.__data)):
            self.__data[i] += k
        return self

    def __str__(self) -> str:
        lines: list[str] = []
        for r in range(self.__rows):
            lines.append(" ".join(str(self.__data[r * self.__cols + c]) for c in range(self.__cols)))
        return "\n".join(lines)


@dataclass
class Money:
    cents: int

    def __add__(self, other: "Money") -> "Money":
        return Money(self.cents + other.cents)


class Sensor:
    unit = "?"

    def __init__(self, raw: float) -> None:
        self.raw = raw

    @property
    def reading(self) -> str:
        return f"{self.raw:.1f}{self.unit}"


class Thermo(Sensor):
    unit = "C"


class Hygro(Sensor):
    unit = "%"


m = Matrix(2, 3)
m[4] = 7
m[4] += 1
m[0] -= 2
alias = m
m += 10
print(m)
print(alias is m, m[4], m[0])
wallet: dict[str, Money] = {"ann": Money(100), "bob": Money(5)}
wallet["ann"] += Money(250)
for k in wallet:
    wallet[k] += Money(1)
print(wallet["ann"], wallet["bob"], Money(3) in [Money(1), Money(3)], [Money(2), Money(3)].index(Money(3)))
coins = [Money(1), Money(2), Money(1)]
coins.remove(Money(1))
print(coins, coins.count(Money(1)), coins == [Money(2), Money(1)], Money(9) not in coins)
sensors: list[Sensor] = [Thermo(21.456), Hygro(55.0), Sensor(1.0)]
print([s.reading for s in sensors], [s.unit for s in sensors])
print(m._Matrix__rows)
