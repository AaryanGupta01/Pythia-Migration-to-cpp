"""Permutation statistics: pancake flipping (Fannkuch) over every ordering of n items."""


def fannkuch(n: int) -> int:
    """Largest number of prefix reversals ("pancake flips") needed to bring a 0 to the front,
    over all n! permutations of 0..n-1.  Permutations are enumerated by factorial counting."""
    perm1: list[int] = []
    perm: list[int] = []
    count: list[int] = []
    for i in range(n):
        perm1.append(i)
        perm.append(0)
        count.append(0)
    max_flips: int = 0
    r: int = n
    while True:
        while r != 1:
            count[r - 1] = r
            r -= 1
        for i in range(n):
            perm[i] = perm1[i]
        flips: int = 0
        k: int = perm[0]
        while k != 0:
            i: int = 0
            j: int = k
            while i < j:
                tmp: int = perm[i]
                perm[i] = perm[j]
                perm[j] = tmp
                i += 1
                j -= 1
            flips += 1
            k = perm[0]
        if flips > max_flips:
            max_flips = flips
        while True:
            if r == n:
                return max_flips
            first: int = perm1[0]
            for i in range(r):
                perm1[i] = perm1[i + 1]
            perm1[r] = first
            count[r] -= 1
            if count[r] > 0:
                break
            r += 1


def next_permutation(items: list[int]) -> bool:
    """Rearrange `items` into the next lexicographic permutation in place; False when it was the last."""
    i: int = len(items) - 2
    while i >= 0 and items[i] >= items[i + 1]:
        i -= 1
    if i < 0:
        return False
    j: int = len(items) - 1
    while items[j] <= items[i]:
        j -= 1
    tmp: int = items[i]
    items[i] = items[j]
    items[j] = tmp
    lo: int = i + 1
    hi: int = len(items) - 1
    while lo < hi:
        tmp = items[lo]
        items[lo] = items[hi]
        items[hi] = tmp
        lo += 1
        hi -= 1
    return True


def count_derangements(n: int) -> int:
    """Permutations of n items with no fixed point, by brute-force enumeration (small n only)."""
    items: list[int] = []
    for i in range(n):
        items.append(i)
    total: int = 0
    while True:
        fixed: bool = False
        for i in range(n):
            if items[i] == i:
                fixed = True
                break
        if not fixed:
            total += 1
        if not next_permutation(items):
            break
    return total
