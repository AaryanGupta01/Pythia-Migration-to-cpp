"""Edit distances between sequences of symbol codes (characters or tokens mapped to integers).

Callers encode text once (for example with `[ord(c) for c in word]`) and reuse the codes for many comparisons,
which keeps these loops free of string handling.
"""


def levenshtein(a: list[int], b: list[int]) -> int:
    """Minimum number of single-symbol insertions, deletions and substitutions turning `a` into `b`.

    Two-row dynamic programme: O(len(a) * len(b)) time, O(len(b)) space."""
    n: int = len(a)
    m: int = len(b)
    prev: list[int] = []
    cur: list[int] = []
    for j in range(m + 1):
        prev.append(j)
        cur.append(0)
    for i in range(1, n + 1):
        cur[0] = i
        for j in range(1, m + 1):
            cost: int = 1
            if a[i - 1] == b[j - 1]:
                cost = 0
            cur[j] = min(min(prev[j] + 1, cur[j - 1] + 1), prev[j - 1] + cost)
        for j in range(m + 1):
            prev[j] = cur[j]
    return prev[m]


def lcs_length(a: list[int], b: list[int]) -> int:
    """Length of the longest common subsequence of two sequences (full table, O(len(a) * len(b)) memory)."""
    n: int = len(a)
    m: int = len(b)
    table: list[list[int]] = []
    for i in range(n + 1):
        line: list[int] = []
        for j in range(m + 1):
            line.append(0)
        table.append(line)
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    return table[n][m]


def hamming(a: str, b: str) -> int:
    """Number of positions at which two strings differ; the shorter one is padded, so extra length counts."""
    shorter: int = min(len(a), len(b))
    diff: int = max(len(a), len(b)) - shorter
    for i in range(shorter):
        if a[i] != b[i]:
            diff += 1
    return diff
