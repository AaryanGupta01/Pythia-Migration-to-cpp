# PySub 1.2: list() of a list / str / dict, sorted() of a str / dict
word: str = "banana"
chars: list[str] = list(word)
print(chars, len(chars))
print("".join(sorted(word)), sorted(word, reverse=True))

counts: dict[str, int] = {}
for ch in word:
    counts[ch] = counts.get(ch, 0) + 1
print(list(counts), sorted(counts), sorted(counts, reverse=True))
for k in sorted(counts):
    print(k, counts[k])

ages: dict[int, str] = {30: "c", 10: "a", 20: "b"}
print(list(ages), sorted(ages))

xs: list[int] = [3, 1, 2]
ys: list[int] = list(xs)
ys.append(9)
print(xs, ys, sorted(ys))
grid: list[list[int]] = [[1], [2]]
g2: list[list[int]] = list(grid)
g2.append([3])
g2[0].append(7)
print(len(grid), len(g2), grid[0])
print(sorted(""), list(""))
