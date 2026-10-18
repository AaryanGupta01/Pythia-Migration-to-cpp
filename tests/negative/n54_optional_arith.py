# expect: may be None here
from typing import Optional
def f(x: Optional[int]) -> int:
    return x + 1
print(f(2))
