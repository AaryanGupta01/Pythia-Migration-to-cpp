"""Pair counting step of byte-pair-encoding training."""


def count_pairs(ids: list[int], vocab: int) -> dict[int, int]:
    counts: dict[int, int] = {}
    for i in range(len(ids) - 1):
        key: int = ids[i] * vocab + ids[i + 1]
        counts[key] = counts.get(key, 0) + 1
    return counts
