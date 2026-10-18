# PySub 1.3: dict values of any supported type -- adjacency lists, nested dicts, sets, objects
from typing import Dict, List


class Account:
    owner: str
    balance: int

    def __init__(self, owner: str, balance: int = 0) -> None:
        self.owner = owner
        self.balance = balance


def build_graph(edges: list[list[int]]) -> Dict[int, List[int]]:
    g: dict[int, list[int]] = {}
    for e in edges:
        if e[0] not in g:
            g[e[0]] = []
        if e[1] not in g:
            g[e[1]] = []
        g[e[0]].append(e[1])
        g[e[1]].append(e[0])
    return g


def degree(g: dict[int, list[int]]) -> dict[int, int]:
    out: dict[int, int] = {}
    for k in g:
        out[k] = len(g[k])
    return out


def dfs(g: dict[int, list[int]], node: int, seen: set[int], order: list[int]) -> None:
    seen.add(node)
    order.append(node)
    for nxt in g[node]:
        if nxt not in seen:
            dfs(g, nxt, seen, order)


g = build_graph([[1, 2], [1, 3], [2, 4], [3, 4], [4, 5]])
print(g)
print(degree(g), g[4], len(g), 5 in g, 9 in g)
order: list[int] = []
dfs(g, 1, set(), order)
print(order)
grades: dict[str, dict[str, float]] = {"ada": {"math": 91.5, "art": 78.0}, "bob": {}}
grades["bob"]["math"] = 66.25
grades["cy"] = {"art": 88.0}
print(grades, grades["ada"]["art"], grades.get("zed", {"none": 0.0}))
tags: dict[str, set[str]] = {"a": {"x"}}
tags["a"].add("y")
tags["b"] = set()
print(sorted(tags["a"]), len(tags["b"]), "a" in tags)
bank: dict[int, Account] = {}
bank[1] = Account("ada", 50)
bank[2] = Account("bob")
bank[1].balance += 25
for k in bank:
    print(k, bank[k].owner, bank[k].balance)
nested: dict[str, list[list[int]]] = {"m": [[1, 2], [3, 4]]}
nested["m"][1][0] = 30
print(nested["m"][1], len(nested["m"]))
print(g[99])
