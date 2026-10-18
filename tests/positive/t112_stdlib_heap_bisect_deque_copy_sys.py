# t112: Standard library algorithms and collections: deque, heapq, bisect, copy, sys.maxsize, doctest, typing

from collections import deque
from collections.abc import Iterable, Sequence
from sys import maxsize
import copy
import heapq
import bisect
import doctest
from typing import cast

# 1. collections.deque
d: list[int] = deque([10, 20])
d.append(30)
d.appendleft(5)
print("deque popleft:", d.popleft())
print("deque pop:", d.pop())
print("deque state:", list(d))

# 2. Sequence and Iterable annotations
def sum_seq(seq: Sequence[int]) -> int:
    s: int = 0
    for x in seq:
        s += x
    return s

print("sum_seq:", sum_seq(d))

# 3. sys.maxsize
print("maxsize > 0:", maxsize > 0)
print("maxsize == 9223372036854775807:", maxsize == 9223372036854775807)

# 4. copy
orig: list[int] = [1, 2, 3]
c: list[int] = copy.copy(orig)
c.append(4)
print("orig:", orig)
print("copy:", c)

# 5. heapq
h: list[int] = [5, 3, 8, 1, 2]
heapq.heapify(h)
print("heap after heapify:", h)
heapq.heappush(h, 0)
print("heappop 1:", heapq.heappop(h))
print("heappop 2:", heapq.heappop(h))
print("heappop 3:", heapq.heappop(h))
print("heappushpop:", heapq.heappushpop(h, 4))
print("heap state:", h)

# 6. bisect
sorted_list: list[int] = [10, 20, 20, 30, 40]
print("bisect_left 20:", bisect.bisect_left(sorted_list, 20))
print("bisect_right 20:", bisect.bisect_right(sorted_list, 20))
bisect.insort_left(sorted_list, 25)
print("after insort_left 25:", sorted_list)

# 7. cast
val: int = cast(int, 42)
print("cast result:", val)

# 8. doctest.testmod()
doctest.testmod()
print("doctest testmod called")
