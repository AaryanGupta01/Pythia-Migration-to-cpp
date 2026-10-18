# edge cases: shadowed loop variables vs. the overflow-guard optimizer, comprehensions in functions and
# methods, int64 range ends; ends with an uncaught ValueError from max() of an empty generator
def big(n: int) -> int:
    i: int = 3
    total: int = [i * i for i in [n, n]][0]    # the comprehension's i is n here, not the outer 3
    return total + i


class Bag:
    items: list[int]

    def __init__(self, items: list[int]) -> None:
        self.items = items

    def evens(self) -> list[int]:
        return [x for x in self.items if x % 2 == 0]

    def heaviest(self) -> int:
        return max(self.items, key=lambda x: x % 5)


print(big(5), big(-7))
b: Bag = Bag([4, 9, 2, 7, 14])
print(b.evens(), b.heaviest(), sum(x for x in b.items), [[y for y in range(x)] for x in range(3)])
m: int = 9223372036854775807
print(sum(v for v in [m, -1]), max(i for i in range(m - 2, m)), [i for i in range(m - 1, m)])
print([j for j in reversed(range(m - 3, m, 2))], [j for j in range(-m - 1, -m + 2)])
print([j for j in range(m - 1, -m, -m)], len([0 for _ in range(-m, m, m)]))
print(max(c for c in "" if c), "unreachable")
