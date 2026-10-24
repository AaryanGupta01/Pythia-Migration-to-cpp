def word_counts(n: int) -> int:
    counts: dict[str, int] = {}
    x: int = 11
    for i in range(n):
        x = (x * 1103515245 + 12345) % 2147483648
        w: str = "w" + str(x % 2000)
        if w in counts:
            counts[w] += 1
        else:
            counts[w] = 1
    best: int = 0
    for k in counts:
        if counts[k] > best:
            best = counts[k]
    return best * 100000 + len(counts)

print(word_counts(1500000))
