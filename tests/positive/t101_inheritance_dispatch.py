# Single inheritance: overriding, super().__init__ / super().method(), virtual dispatch through base-typed
# references and list[Base], isinstance() on subclasses (decided at run time), narrowing after isinstance
import math


class Shape:
    count = 0

    def __init__(self, name: str) -> None:
        self.name = name
        Shape.count += 1

    def area(self) -> float:
        return 0.0

    def describe(self) -> str:
        return f"{self.name} with area {self.area():.2f}"

    def __repr__(self) -> str:
        return f"Shape({self.name!r})"


class Circle(Shape):
    def __init__(self, r: float) -> None:
        super().__init__("circle")
        self.r = r

    def area(self) -> float:
        return math.pi * self.r * self.r

    def __repr__(self) -> str:
        return f"Circle({self.r})"


class Rect(Shape):
    def __init__(self, w: float, h: float, name: str = "rect") -> None:
        super().__init__(name)
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h

    def describe(self) -> str:
        return "[" + super().describe() + "]"


class Square(Rect):
    def __init__(self, side: float) -> None:
        super().__init__(side, side, "square")

    def __str__(self) -> str:
        return f"Square of side {self.w}"


def total_area(shapes: list[Shape]) -> float:
    t = 0.0
    for s in shapes:
        t += s.area()
    return t


def biggest(shapes: list[Shape]) -> Shape:
    best = shapes[0]
    for s in shapes[1:]:
        if s.area() > best.area():
            best = s
    return best


shapes: list[Shape] = [Circle(1.0), Rect(2.0, 3.0), Square(2.5), Shape("blob")]
for s in shapes:
    print(s.describe())
print(round(total_area(shapes), 4), Shape.count)
print(shapes)
print(biggest(shapes), str(biggest(shapes)), repr(shapes[2]))
for s in shapes:
    kinds = [isinstance(s, Shape), isinstance(s, Rect), isinstance(s, Square), isinstance(s, Circle)]
    print(type(s) == Rect, kinds)
    if isinstance(s, Rect):
        print("  rect sides", s.w, s.h)
    if not isinstance(s, Circle):
        continue
    print("  radius", s.r)
sq = Square(4.0)
r: Rect = sq
sh: Shape = r
print(sh.area(), r.describe(), sh is sq, sh == r)
mixed = [Circle(2.0), Square(1.0)]
print(len(mixed), mixed[1].area(), Shape.count)
