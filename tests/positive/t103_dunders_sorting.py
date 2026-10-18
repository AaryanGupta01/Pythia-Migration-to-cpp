# Dunder methods: __eq__/__ne__/__lt__/__le__ (and the reflected __gt__ / __ge__), sorted/min/max/sort of user
# objects, operator overloading with reflected operands, __neg__/__abs__, __getitem__/__setitem__, in-place ops
from typing import Optional


class Version:
    def __init__(self, major: int, minor: int) -> None:
        self.major = major
        self.minor = minor

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self.major == other.major and self.minor == other.minor

    def __lt__(self, other: "Version") -> bool:
        return (self.major, self.minor) < (other.major, other.minor)

    def __le__(self, other: "Version") -> bool:
        return self == other or self < other

    def __repr__(self) -> str:
        return f"v{self.major}.{self.minor}"


class Vec:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def __add__(self, other: "Vec") -> "Vec":
        return Vec(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec") -> "Vec":
        return Vec(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> "Vec":
        return Vec(self.x * k, self.y * k)

    def __rmul__(self, k: float) -> "Vec":
        return self * k

    def __neg__(self) -> "Vec":
        return Vec(-self.x, -self.y)

    def __abs__(self) -> float:
        return (self.x ** 2 + self.y ** 2) ** 0.5

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vec) and self.x == other.x and self.y == other.y

    def __str__(self) -> str:
        return f"({self.x}, {self.y})"


class Grid:
    def __init__(self, n: int) -> None:
        self.cells = [0] * n

    def __getitem__(self, i: int) -> int:
        return self.cells[i]

    def __setitem__(self, i: int, v: int) -> None:
        self.cells[i] = v

    def __len__(self) -> int:
        return len(self.cells)

    def __bool__(self) -> bool:
        return sum(self.cells) > 0


vs = [Version(1, 2), Version(0, 9), Version(1, 0), Version(0, 9)]
print(sorted(vs), min(vs), max(vs), sorted(vs, reverse=True))
vs.sort()
print(vs, vs[0] == vs[1], vs[0] != vs[2], vs[0] is vs[1], Version(1, 0) in vs, vs.index(Version(1, 0)))
print(vs[1] < vs[2], vs[2] > vs[1], vs[0] <= vs[1], vs[3] >= vs[2], vs.count(Version(0, 9)))
print(max(Version(2, 0), Version(2, 0)) is not None, min(Version(3, 1), Version(3, 0)))
none_v: Optional[Version] = None
print(vs[0] == none_v, vs[0] != none_v, none_v == vs[0], none_v != None)
a, b = Vec(1.0, 2.0), Vec(3.0, -1.0)
c = a + b * 2.0 - Vec(0.5, 0.5)
print(c, -c, abs(Vec(3.0, 4.0)), 3.0 * a, a == Vec(1.0, 2.0), a != b)
acc = Vec(0.0, 0.0)
for v in [a, b, c]:
    acc += v
print(acc)
g = Grid(4)
print(bool(g), len(g), g[0])
g[2] = 7
g[3] += 1
print(g[2], g[-1], g.cells, bool(g))
if g:
    print("grid has content")
print(sorted([Version(5, 1), Version(5, 0)])[0], vs[1] < Version(0, 10))
print(Version(1, 0) < None)
