# @dataclass records: generated __init__ (defaults), __repr__, __eq__, order=True comparisons and sorting;
# frozen dataclasses; __post_init__; nested records; class attributes next to fields
from dataclasses import dataclass
from typing import Optional


@dataclass
class Point:
    x: int
    y: int = 0

    def dist2(self) -> int:
        return self.x * self.x + self.y * self.y


@dataclass(order=True)
class Employee:
    dept: str
    salary: float
    name: str = "?"
    manager: Optional["Employee"] = None
    tags: Optional[list[str]] = None


@dataclass(frozen=True)
class Money:
    amount: int
    currency: str = "EUR"

    def add(self, other: "Money") -> "Money":
        if other.currency != self.currency:
            raise ValueError(f"currency mismatch: {self.currency} vs {other.currency}")
        return Money(self.amount + other.amount, self.currency)


@dataclass
class Box:
    label: str
    items: list[int]
    kind = "box"

    def __post_init__(self) -> None:
        self.items.sort()


p, q = Point(3, 4), Point(3)
print(p, q, p == Point(3, 4), p != q, p.dist2(), repr(q), [p, q])
boss = Employee("eng", 200.5, "Ann")
staff = [Employee("eng", 120.0, "Bob", boss, ["new"]), Employee("art", 99.5, "Cy"), boss,
         Employee("eng", 120.0, "Al")]
for e in sorted(staff):
    print(e.name, e.dept, e.salary, e.manager.name if e.manager else None)
print(staff[0])
print(max(staff).name, min(staff).name, staff[1] < staff[0], staff[0] >= staff[3], boss == Employee("eng", 200.5, "Ann"))
m = Money(5).add(Money(7))
print(m, m == Money(12), m.amount)
b = Box("b1", [3, 1, 2])
print(b, b.kind, Box.kind)
print(Money(1).add(Money(2, "USD")))
