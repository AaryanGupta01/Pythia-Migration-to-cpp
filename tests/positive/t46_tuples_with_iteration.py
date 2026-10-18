# enumerate/zip items are tuples: list(enumerate(..)), list(zip(..)), tuple keys, d.items() in comprehensions
def rank(scores: dict[str, int]) -> list[str]:
    return [f"{i}. {name} ({s})" for i, (name, s) in
            enumerate(sorted(scores.items(), key=lambda kv: (-kv[1], kv[0])), 1)]


names: list[str] = ["ann", "bob", "cy"]
ages: list[int] = [31, 22, 45]
print(list(enumerate(names)), list(zip(names, ages)), sorted(zip(ages, names)))
print(list(enumerate("ab", 5)), list(zip(range(3), reversed(names))))
for p in enumerate(names):
    print(p, p[0], p[1])
for i, (n, a) in enumerate(zip(names, ages)):
    print(i, n, a)
pairs: list[tuple[str, int]] = [("x", 3), ("y", 1), ("z", 2)]
print([n * k for n, k in pairs], {n: k for n, k in pairs}, sorted(pairs, key=lambda t: t[1]))
print(max(pairs, key=lambda t: t[1]), min(pairs, key=lambda t: (t[1] % 2, t[0])))
d: dict[str, int] = {"b": 2, "a": 2, "c": 5}
print(rank(d), [k for k, v in d.items() if v == 2], sum(v for k, v in d.items()))
people: list[tuple[str, int]] = [("di", 30), ("al", 25), ("bo", 30)]
people.sort(key=lambda t: (-t[1], t[0]))
print(people, sorted(people, key=lambda t: t[0], reverse=True))
print([t for t in zip([1, 2], [3, 4], [5, 6])], any(a > b for a, b in zip([1, 5], [2, 4])))
print([v * 2 for v in d.values()], sorted(d.keys(), key=lambda k: -d[k]), "".join(c for c in "abcdef"[::2]))
print(max(d.values()), sum(d.values()), [w[1:] for w in names if w[:1] != "b"], any(k in "abc" for k in d.keys()))
