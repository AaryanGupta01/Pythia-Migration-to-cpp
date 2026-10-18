# expect: different signature
class Shape:
    def area(self) -> float:
        return 0.0


class Square(Shape):
    def __init__(self, s: int) -> None:
        self.s = s

    def area(self) -> int:
        return self.s * self.s
