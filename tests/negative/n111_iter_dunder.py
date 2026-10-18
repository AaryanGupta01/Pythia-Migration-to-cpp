# expect: __iter__ is outside the PySub subset
class Seq:
    def __init__(self) -> None:
        self.n = 3

    def __iter__(self) -> int:
        return self.n
