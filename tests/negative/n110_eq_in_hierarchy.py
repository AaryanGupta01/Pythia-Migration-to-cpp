# expect: cannot define __eq__
class Base:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, other: "Base") -> bool:
        return self.v == other.v


class Sub(Base):
    pass
