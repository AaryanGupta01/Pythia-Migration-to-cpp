# expect: called through subclass
class Base:
    def __init__(self, x: int) -> None:
        self.x = x

    @classmethod
    def make(cls, x: int) -> "Base":
        return cls(x)


class Sub(Base):
    pass


s = Sub.make(3)
print(s.x)
