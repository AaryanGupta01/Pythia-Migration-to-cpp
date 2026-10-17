"""k-mer statistics for nucleotide-like sequences."""


def kmer_counts(seq: str, k: int) -> dict[str, int]:
    """Occurrences of every length-k window of `seq`."""
    counts: dict[str, int] = {}
    for i in range(len(seq) - k + 1):
        kmer: str = seq[i:i + k]
        counts[kmer] = counts.get(kmer, 0) + 1
    return counts


def gc_content(seq: str) -> float:
    """Fraction of G and C bases."""
    gc: int = 0
    for ch in seq:
        if ch == "G" or ch == "C":
            gc += 1
    if len(seq) == 0:
        return 0.0
    return gc / len(seq)


def longest_run(seq: str) -> int:
    """Length of the longest stretch of one repeated character."""
    best: int = 0
    run: int = 0
    prev: str = ""
    for ch in seq:
        if ch == prev:
            run += 1
        else:
            run = 1
            prev = ch
        if run > best:
            best = run
    return best
