"""Longest common substring and longest palindromic substring."""


def longest_common_substring(a: str, b: str) -> int:
    """Length of the longest run of characters that appears contiguously in both strings."""
    m: int = len(b)
    prev: list[int] = []
    cur: list[int] = []
    for j in range(m + 1):
        prev.append(0)
        cur.append(0)
    best: int = 0
    for i in range(1, len(a) + 1):
        for j in range(1, m + 1):
            if a[i - 1] == b[j - 1]:
                cur[j] = prev[j - 1] + 1
                if cur[j] > best:
                    best = cur[j]
            else:
                cur[j] = 0
        for j in range(m + 1):
            prev[j] = cur[j]
    return best


def longest_palindrome(s: str) -> int:
    """Length of the longest palindromic substring, expanding around every centre."""
    n: int = len(s)
    best: int = 0
    for centre in range(2 * n - 1):
        lo: int = centre // 2
        hi: int = lo + centre % 2
        while lo >= 0 and hi < n and s[lo] == s[hi]:
            lo -= 1
            hi += 1
        if hi - lo - 1 > best:
            best = hi - lo - 1
    return best


def run_length_encode(s: str) -> str:
    """Compress runs of a repeated character, e.g. 'aaabcc' -> 'a3b1c2'."""
    out: str = ""
    i: int = 0
    while i < len(s):
        j: int = i
        while j < len(s) and s[j] == s[i]:
            j += 1
        out = out + s[i] + str(j - i)
        i = j
    return out
