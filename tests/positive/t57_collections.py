# PySub 1.3: collections.defaultdict and Counter
from collections import defaultdict, Counter
from typing import DefaultDict


def word_freq(text: str) -> dict[str, int]:
    freq: defaultdict[str, int] = defaultdict(int)
    for w in text.split():
        freq[w] += 1
    return freq


def group_by_len(words: list[str]) -> dict[int, list[str]]:
    groups: dict[int, list[str]] = defaultdict(list)
    for w in words:
        groups[len(w)].append(w)
    return groups


def anagram_key(w: str) -> str:
    return "".join(sorted(w))


text = "the cat and the hat and the bat"
f = word_freq(text)
print(f)
print(f["the"], f["dog"], "dog" in f, len(f))
g = group_by_len(["a", "bb", "cc", "ddd", "e"])
print(g, g[7], len(g))
for k in g:
    print(k, g[k])
c = Counter(text.split())
print(c)
print(c["the"], c["zebra"], "zebra" in c, len(c))
print(c.most_common(2), c.most_common(), c.most_common(0))
letters = Counter("mississippi")
print(letters, letters.most_common(1))
nums = Counter([3, 1, 3, 2, 1, 3])
nums[5] += 2
nums[1] -= 1
print(nums, nums.most_common())
empty: Counter[str] = Counter()
print(empty, empty["x"], len(empty))
fl: defaultdict[str, float] = defaultdict(float)
fl["a"] += 1.5
print(fl, fl["b"])
sets: dict[str, set[int]] = defaultdict(set)
sets["x"].add(3)
sets["x"].add(3)
sets["y"].add(1)
print(sorted(sets["x"]), len(sets), sorted(sets["z"]))
names: DefaultDict[str, str] = defaultdict(str)
names["k"] += "v"
print(names, names["missing"] == "")
plain: dict[str, int] = {"a": 1}
print(plain["zz"])
