# Graph / tree classes with list / dict fields of objects, forward references, recursive __str__, objects in
# dicts / tuples / comprehensions, key= sorting of objects, Optional results
from typing import Optional


class Graph:
    def __init__(self, n: int) -> None:
        self.n = n
        self.adj: dict[int, list[int]] = {}
        for i in range(n):
            self.adj[i] = []
        self.names: list["Vertex"] = []

    def add_edge(self, a: int, b: int) -> None:
        self.adj[a].append(b)
        self.adj[b].append(a)

    def bfs(self, start: int) -> list[int]:
        seen = [False] * self.n
        order: list[int] = []
        queue = [start]
        seen[start] = True
        while queue:
            v = queue.pop(0)
            order.append(v)
            for w in self.adj[v]:
                if not seen[w]:
                    seen[w] = True
                    queue.append(w)
        return order

    def vertex(self, i: int) -> Optional["Vertex"]:
        for v in self.names:
            if v.idx == i:
                return v
        return None


class Vertex:
    def __init__(self, idx: int, label: str, parent: Optional["Vertex"] = None) -> None:
        self.idx = idx
        self.label = label
        self.parent = parent
        self.children: list[Vertex] = []
        if parent is not None:
            parent.children.append(self)

    def path(self) -> str:
        if self.parent is None:
            return self.label
        return self.parent.path() + "/" + self.label

    def __str__(self) -> str:
        inner = ", ".join(str(c) for c in self.children)
        return f"{self.label}[{inner}]" if self.children else self.label

    def depth(self) -> int:
        d = 0
        p = self.parent
        while p is not None:
            d += 1
            p = p.parent
        return d


class Person:
    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age

    def __repr__(self) -> str:
        return f"Person({self.name!r}, {self.age})"


g = Graph(6)
for a, b in [(0, 1), (0, 2), (1, 3), (2, 4), (4, 5)]:
    g.add_edge(a, b)
print(g.bfs(0), g.bfs(5), g.adj)
root = Vertex(0, "root")
usr = Vertex(1, "usr", root)
lib = Vertex(2, "lib", usr)
Vertex(3, "bin", root)
g.names = [root, usr, lib]
print(lib.path(), lib.depth(), root, usr)
found = g.vertex(2)
print(found.label if found else "none", g.vertex(9) is None)
people = [Person("ann", 31), Person("bob", 25), Person("cy", 31), Person("di", 19)]
print(sorted(people, key=lambda p: p.age))
print(sorted(people, key=lambda p: (-p.age, p.name)))
print(max(people, key=lambda p: p.age), min(people, key=lambda p: p.name))
ages = {p.name: p.age for p in people}
mx = max(ages.values())
oldest = [p.name for p in people if p.age == mx]
print(ages, oldest)
by_age: dict[int, list[Person]] = {}
for p in people:
    if p.age not in by_age:
        by_age[p.age] = []
    by_age[p.age].append(p)
for age in sorted(by_age):
    print(age, [p.name for p in by_age[age]])
for i, p in enumerate(people):
    if i % 2 == 0:
        print(i, p)
pairs = list(zip(people, [1, 2, 3, 4]))
print(pairs[0][0].name, len(pairs))
print(g.vertex(7).label)
