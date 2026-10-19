"""Pair counting step of byte-pair-encoding training: counts[a * vocab + b] = occurrences of (a, b)."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_f1a89857", "count_pairs")
def count_pairs(ids: list[int], vocab: int) -> list[int]:
    counts: list[int] = []
    for i in range(vocab * vocab):
        counts.append(0)
    for i in range(len(ids) - 1):
        counts[ids[i] * vocab + ids[i + 1]] += 1
    return counts
