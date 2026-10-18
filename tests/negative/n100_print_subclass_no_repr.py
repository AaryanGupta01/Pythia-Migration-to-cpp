# expect: defines neither __str__ nor __repr__
class Base:
    def __repr__(self) -> str:
        return "Base()"


class Plain:
    pass


class Sub(Plain):
    pass


b: Plain = Sub()
print(b)
