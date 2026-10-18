# enumerate / zip / reversed / range in for headers and comprehensions, with tuple-style targets
def total_weighted(xs: list[int]) -> int:
    t: int = 0
    for i, x in enumerate(xs):
        t += i * x
    return t


names: list[str] = ["ann", "bob", "cy"]
ages: list[int] = [31, 22, 45, 99]
for i, n in enumerate(names):
    print(i, n)
for i, n in enumerate(names, 1):
    print(i, n, end="; ")
print()
for i, n in enumerate(names, start=10):
    print(i, n, end="; ")
print()
for n, a in zip(names, ages):          # zip stops at the shortest
    print(n, a)
for s, b, c in zip("xyz", ages, [1.5, 2.5]):
    print(s, b, c)
for (k, (n, a)) in enumerate(zip(names, ages)):
    print(k, n, a)
for x in reversed(ages):
    print(x, end=" ")
print()
for ch in reversed("abc"):
    print(ch, end="")
print()
for i in reversed(range(1, 10, 3)):
    print(i, end=" ")
print()
for i, ch in enumerate("hi"):
    print(i, ch)
d: dict[str, int] = {"p": 1, "q": 2}
for i, key in enumerate(d):
    print(i, key, d[key])
print(total_weighted([5, 6, 7]))
print([i * x for i, x in enumerate([4, 5, 6])], [a + b for a, b in zip([1, 2, 3], [10, 20])])
print({n: a for n, a in zip(names, ages)}, [n for i, n in enumerate(names) if i != 1])
print([i for i in range(3)], [j for j in reversed(range(-2, 3))], [c for c in reversed("ab")])


i: int = 100
for i, v in enumerate([7, 8]):
    pass
print(i, v)
xs: list[int] = [1, 2, 3]
for i, v in enumerate(xs):              # the list grows while it is iterated, like CPython's list iterator
    if v < 3:
        xs.append(v * 10)
print(xs)
for v in reversed(xs):
    if v == 20:
        break
    print(v, end=" ")
print()
for i, v in enumerate(xs):
    if i % 2 == 0:
        continue
    print(i, v, end=" | ")
print()
