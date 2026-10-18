# PySub 1.3: Optional tuples (tuple[int, int] | None), the LeetCode two_sum shape
from typing import Optional


def two_sum(array: list[int], target: int) -> Optional[tuple[int, int]]:
    seen: dict[int, int] = {}
    for index, num in enumerate(array):
        if num in seen:
            return seen[num], index
        seen[target - num] = index
    return None


r = two_sum([2, 7, 11, 15], 9)
print(r)
print(two_sum([1, 2], 99))
if r is not None:
    a, b = r
    print(a + b)
