# expect: has no setter
class Circle:
    def __init__(self, r: float) -> None:
        self.r = r

    @property
    def area(self) -> float:
        return 3.14 * self.r * self.r


c = Circle(1.0)
c.area = 5.0
