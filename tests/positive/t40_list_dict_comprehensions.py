# list / dict comprehensions: filters, several clauses, nesting, scoping
def squares(n: int) -> list[int]:
    return [i * i for i in range(n)]


def pairs(xs: list[int], ys: list[int]) -> list[int]:
    return [x * 10 + y for x in xs if x % 2 == 1 for y in ys if y != x]


def transpose(m: list[list[int]]) -> list[list[int]]:
    return [[row[j] for row in m] for j in range(len(m[0]))]


def counts(words: list[str]) -> dict[str, int]:
    return {w: len(w) for w in words if w}


print(squares(6), squares(0))
print(pairs([1, 2, 3], [1, 2, 3]))
print(transpose([[1, 2, 3], [4, 5, 6]]))
print(counts(["apple", "", "kiwi", "apple"]))

x: int = 99
ys: list[int] = [x + 1 for x in [1, 2, 3]]
print(ys, x)                      # the comprehension's x neither leaks nor clobbers the outer x
zs: list[int] = [x for x in [x, x + 1]]   # the first iterable is evaluated in the enclosing scope
print(zs)
words: list[str] = ["b", "a", "c"]
print([w.upper() for w in words], [c for c in "hello" if c != "l"])
print({k: v for k in [1, 2] for v in [10, 20]})
d: dict[str, int] = {"a": 1, "b": 2}
print([k + str(d[k]) for k in d], {k: d[k] * 2 for k in d})
print([[r * c for c in range(1, 4)] for r in range(1, 3)])
print([a if a > 2 else -a for a in range(5)])
print([i for i in range(10, 0, -3)], [i for i in range(0)], [f / 2 for f in [1, 2, 3]])
grid: list[list[int]] = [[] for _ in range(3)]
grid[1].append(5)
print(grid)
nums: list[int] = [3, 1, 2]
print([n for n in nums if n > 1 if n < 3], len([0 for _ in nums]))
print([s for s in sorted(["pear", "fig", "apple"])])
try:
    print([10 // v for v in [5, 2, 0, 1]])
except ZeroDivisionError as e:
    print("caught", e)
try:
    print([i for i in range(1, 5, 0)])
except ValueError as e:
    print("caught", e)
print([nums[i] for i in range(-1, -4, -1)])
