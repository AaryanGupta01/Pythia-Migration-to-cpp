"""Pair counting step of byte-pair-encoding training: counts[a * vocab + b] = occurrences of (a, b)."""


def count_pairs(ids: list[int], vocab: int) -> list[int]:
    counts: list[int] = []
    for i in range(vocab * vocab):
        counts.append(0)
    for i in range(len(ids) - 1):
        counts[ids[i] * vocab + ids[i + 1]] += 1
    return counts
