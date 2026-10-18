# PySub 1.3: and / or / not in conditions need no common operand type (only truthiness is used)
def f(out: list[list[int]], s: int, name: str) -> int:
    n: int = 0
    if out and out[-1][1] >= s:
        n += 1
    if name or out:
        n += 10
    while out and len(out) > 2 and not name:
        out.pop()
        n += 100
    if not (out and name):
        n += 1000
    return n


print(f([[1, 5]], 3, ""), f([], 0, "x"), f([[1, 2], [3, 4], [5, 6]], 0, ""), f([[0, 0]], 1, "q"))
