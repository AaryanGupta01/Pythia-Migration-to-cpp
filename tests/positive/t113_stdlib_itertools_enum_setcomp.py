# t113: Standard library itertools (accumulate, chain), sys.setrecursionlimit, enum class constants

import sys
import itertools
from itertools import accumulate, chain

sys.setrecursionlimit(10000)

# 1. itertools.accumulate on integers
nums: list[int] = [1, 2, 3, 4, 5]
acc_int: list[int] = list(accumulate(nums))
print("accumulate int:", acc_int)

# 2. itertools.accumulate on floats
fnums: list[float] = [1.5, 2.5, 3.0]
acc_float: list[float] = list(itertools.accumulate(fnums))
print("accumulate float:", acc_float)

# 3. itertools.chain
tail: list[int] = [6, 7]
chained: list[int] = list(chain(nums, tail))
print("chained:", chained)

# 4. Class constants (Enum style)
class Direction:
    NORTH = 0
    EAST = 1
    SOUTH = 2
    WEST = 3

print("Direction constants:", Direction.NORTH, Direction.EAST, Direction.SOUTH, Direction.WEST)
d: int = Direction.EAST
if d == Direction.EAST:
    print("Heading east!")

# 5. Empty containers and set operations
empty_acc: list[int] = list(accumulate([10]))
print("single element accumulate:", empty_acc)

