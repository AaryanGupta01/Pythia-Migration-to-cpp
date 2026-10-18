# expect: may be None here
from typing import Optional
class N:
    v: int
    def __init__(self, v: int) -> None:
        self.v = v
def f(xs: Optional[list[int]]) -> int:
    return len(xs)
print(f(None))
