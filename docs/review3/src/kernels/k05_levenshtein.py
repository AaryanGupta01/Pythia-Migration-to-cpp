def levenshtein(a: str, b: str) -> int:
    prev: list[int] = []
    for j in range(len(b) + 1):
        prev.append(j)
    for i in range(1, len(a) + 1):
        cur: list[int] = [i]
        for j in range(1, len(b) + 1):
            cost: int = 0 if a[i - 1] == b[j - 1] else 1
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[len(b)]

def make(n: int, seed: int) -> str:
    s: str = ""
    x: int = seed
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        s += chr(97 + x % 4)
    return s

print(levenshtein(make(1500, 1), make(1500, 2)))
