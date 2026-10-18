# generator expressions consumed by sum/min/max/any/all/sorted/list/str.join, plus any/all of lists
def probe(v: int, calls: list[int]) -> int:
    calls.append(v)
    return v


calls: list[int] = []

xs: list[int] = [3, -1, 4, 1, -5, 9, 2, 6]
print(sum(x * x for x in xs), sum(x for x in xs if x > 100), sum(x > 0 for x in xs))
print(sum(f * 0.1 for f in [1.0, 2.0, 3.0]), sum(0.1 for _ in range(10)))
print(min(x for x in xs), max(abs(x) for x in xs), max(len(w) for w in ["a", "abc", "ab"]))
print(min(w for w in ["pear", "Apple", "fig"]), max(c for c in "hello"))
print(any(x > 5 for x in xs), all(x > -10 for x in xs), any(x > 50 for x in xs), all(x > 0 for x in xs))
empty: list[int] = []
print(any(x > 0 for x in empty), all(x > 0 for x in empty))
g: list[list[int]] = [[1], [1]]
g[0].clear()
print(any([0, 0, 3]), all([1, 2, 0]), any(""), all("abc"), any(g), all(g), all(empty), any(empty))
d: dict[str, int] = {"a": 0, "b": 1}
print(any(d), all(d), any(d[k] for k in d), all(d[k] for k in d))

# short-circuit exactly like CPython: probing stops at the first hit
print(any(probe(v, calls) > 2 for v in [1, 2, 3, 4, 5]), calls)
calls.clear()
print(all(probe(v, calls) < 3 for v in [1, 2, 3, 4, 5]), calls)
calls.clear()
print(sum(probe(v, calls) for v in range(4)), calls)

print(sorted(x % 4 for x in xs), sorted((x for x in xs), reverse=True), list(c for c in "abc"))
print(", ".join(str(x) for x in xs if x > 0), "-".join(w.upper() for w in ["a", "b"]))
print("".join(reversed("stressed")), list(reversed([1, 2, 3])), sorted(reversed([2, 3, 1])))
print(list(range(5)), sum(range(101)), max(range(3, 9, 2)), list(reversed(range(4))))
print(sum(i * j for i in range(1, 4) for j in range(1, 4) if i != j))
print(max(x for row in [[1, 5], [7, 2]] for x in row), any(any(v > 6 for v in r) for r in [[1, 5], [7, 2]]))
try:
    print(min(x for x in xs if x > 100))
except ValueError as e:
    print("caught", e)
try:
    print(max(c for c in ""))
except ValueError as e:
    print("caught", e)
print(max(x for x in [2, 7, 7, 1]), min(f for f in [2.5, -1.0, 3.0]), max(b for b in [False, True]))
