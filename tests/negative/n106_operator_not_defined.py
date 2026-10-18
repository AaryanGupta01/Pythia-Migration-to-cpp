# expect: unsupported operand type(s) for +
class Money:
    def __init__(self, cents: int) -> None:
        self.cents = cents


total = Money(1) + Money(2)
