# PySub 1.3: set[T] -- membership, algebra, sorted(); never iterated or printed directly (hash order)
from typing import Set


def unique_count(xs: list[int]) -> int:
    return len(set(xs))


def has_duplicates(words: list[str]) -> bool:
    seen: set[str] = set()
    for w in words:
        if w in seen:
            return True
        seen.add(w)
    return False


def bfs_order(adj: dict[int, list[int]], start: int) -> list[int]:
    visited: Set[int] = {start}
    order: list[int] = [start]
    i = 0
    while i < len(order):
        for nxt in adj[order[i]]:
            if nxt not in visited:
                visited.add(nxt)
                order.append(nxt)
        i += 1
    return order


a = {5, 1, 3, 9, 1}
b: set[int] = set([3, 4, 5, 6])
print(len(a), sorted(a), sorted(b, reverse=True), 3 in a, 7 not in a)
print(sorted(a | b), sorted(a & b), sorted(a - b), sorted(a ^ b))
print(sorted(a.union(b)), sorted(a.intersection([1, 9, 10])), sorted(a.difference(b)), sorted(a.symmetric_difference(b)))
print(a.issubset(a | b), a.issuperset({1, 3}), a.isdisjoint({100}), a == {1, 3, 5, 9}, a != b, {1} < a, a <= a, a > {9})
alias = a
a |= {42}
a -= {1}
print(sorted(alias), alias is a, len(alias))
a.add(7)
a.discard(1000)
a.remove(42)
c = a.copy()
c.clear()
print(sorted(a), len(c), bool(c), bool(a), not c)
a.update([8, 8, 9])
a.intersection_update({7, 8, 9, 10})
print(sorted(a))
letters = set("mississippi")
print(sorted(letters), len(letters), "s" in letters, unique_count([1, 2, 2, 3, 3, 3]))
print(has_duplicates(["a", "b", "a"]), has_duplicates(["x", "y"]))
fl = {1.5, 2.0, 2}
print(sorted(fl), 2 in fl, 2.0 in fl)
flags = {True, False, True}
print(len(flags), sorted(flags))
d = {"k": 1, "j": 2}
print(sorted(set(d)), bfs_order({1: [2, 3], 2: [4], 3: [4], 4: [1]}, 1))
s2: set[int] = set()
s2.remove(3)
