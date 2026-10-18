def rev(s: str) -> str:
    return s[::-1]


def is_pal(s: str) -> bool:
    return s == s[::-1]


def tail(xs: list[int]) -> list[int]:
    return xs[1:]


def halves(xs: list[int]) -> int:
    mid = len(xs) // 2
    return sum(xs[:mid]) - sum(xs[mid:])


s = "abcdefgh"
print(s[2:5], s[:3], s[5:], s[:], s[-3:], s[:-3], s[-5:-2], s[::2], s[1::2], s[::-1], s[::-2], s[6:1:-2])
print(s[10:], s[:100], s[-100:2], s[3:3], s[5:2], s[2:-100], s[100:200], s[-1:-5:-1], s[:0:-1], s[7:-9:-3])
print(rev("hello"), is_pal("racecar"), is_pal("ab"), rev(""), rev("x"))
xs = [10, 20, 30, 40, 50, 60]
print(xs[1:3], xs[:2], xs[4:], xs[:], xs[-2:], xs[::2], xs[::-1], xs[5:0:-2], xs[10:], xs[-100:2], xs[2:2])
print(tail(xs), halves(xs), tail([1]), tail([1, 2]))
ys = xs[:]
ys[0] = 99
print(xs[0], ys[0], xs == xs[:], len(xs[1:-1]))
fs = [1.5, 2.5, 3.5]
print(fs[1:], fs[::-1], fs[:-1])
ss = ["a", "bb", "ccc", "dddd"]
print(ss[1:3], ss[::-1], ss[-1:])
bs = [True, False, True]
print(bs[::2], bs[1:])
grid = [[1, 2], [3, 4], [5, 6]]
print(grid[1:], grid[::-1], grid[0][1:], grid[:2][0][::-1])
k = 2
print(s[k:], s[:k], s[-k:], s[k:k + 3], xs[k::k], s[True:], s[:True])
print("hello world"[6:], "x"[1:], "x"[:-1], "".join(ss[1:3]), "-".join(ss[::-1]))
words = "the quick brown fox".split()
print(words[1:], words[-2:], " ".join(words[::-1]))
for step in [1, 2, 3, -1, -2, -3]:
    print(step, s[::step], xs[::step])
try:
    z = 0
    print(s[::z])
except ValueError as e:
    print("str", e)
try:
    z = 0
    print(xs[1:4:z])
except ValueError as e:
    print("list", e)
