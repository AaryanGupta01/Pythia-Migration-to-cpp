# expect: defines neither __str__ nor __repr__
class Node:
    def __init__(self, v: int) -> None:
        self.v = v


n = Node(1)
print(f"node: {n}")
