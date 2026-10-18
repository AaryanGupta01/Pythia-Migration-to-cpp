# PySub 1.3: fixed-size heterogeneous tuples, unpacking, tuple-keyed dicts, d.items()
def minmax(xs: list[int]) -> tuple[int, int]:
    lo: int = xs[0]
    hi: int = xs[0]
    for x in xs:
        if x < lo:
            lo = x
        if x > hi:
            hi = x
    return (lo, hi)


def swap(p: tuple[int, str]) -> tuple[str, int]:
    a, b = p
    return b, a


lo, hi = minmax([4, -2, 9, 0])
print(lo, hi, minmax([7]))
t: tuple[int, str] = (1, "a")
print(t, swap(t), t[0], t[-1], len(t), str(t) + "!")
one: tuple[float] = (2.5,)
print(one, (), ((1, 2), "x", True, 1.0))
print((1, 2) < (1, 3), (1, "b") > (1, "a"), (2, 0) <= (1, 9), (1, 2) == (1, 2), (1, 2) != (1, 2))
print(3 in (1, 2, 3), "z" not in ("a", "b"), (1, 2) + ("c",))
for v in (10, 20, 30):
    print(v)
if (0,):
    print("non-empty tuple is truthy")

pts: list[tuple[int, int]] = [(3, 1), (1, 2), (3, 0), (1, 1)]
pts.append((0, 5))
pts.sort()
print(pts, max(pts), pts.index((3, 0)), (1, 2) in pts)
for x, y in pts:
    print(x + y, end=" ")
print()

grid: dict[tuple[int, int], str] = {(0, 0): "origin", (1, 2): "p"}
grid[(2, 2)] = "q"
grid[(0, 0)] = "O"
print(grid, grid[(1, 2)], (2, 2) in grid, grid.get((5, 5), "none"), len(grid))
for k, w in grid.items():
    print(k, w)
ages: dict[str, int] = {"bob": 30, "al": 25}
print(sorted(ages.items()), list(ages.items()))
for name, age in ages.items():
    print(name, age)

a, b, c = "xyz"
print(c, b, a)
q, r = [1, 2]
q, r = r, q
print(q, r)
try:
    m, n = [1, 2, 3]
except ValueError as e:
    print("ValueError:", e)
try:
    print(grid[(9, 9)])
except KeyError as e:
    print("KeyError:", e)
