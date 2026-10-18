# expect: cannot infer the type of field 'items'
class Bag:
    def __init__(self) -> None:
        self.items = []

    def size(self) -> int:
        return len(self.items)


print(Bag().size())
