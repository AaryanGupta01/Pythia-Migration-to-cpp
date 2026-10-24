"""Levenshtein distance for fuzzy de-duplication of tokens."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_fbfd1f38", "edit_distance")
def edit_distance(a: str, b: str) -> int:
    n: int = len(a)
    m: int = len(b)
    bc: list[str] = []
    prev: list[int] = []
    cur: list[int] = []
    for j in range(m):
        bc.append(b[j])
    for j in range(m + 1):
        prev.append(j)
        cur.append(0)
    for i in range(1, n + 1):
        ca: str = a[i - 1]
        cur[0] = i
        for j in range(1, m + 1):
            cost: int = 1
            if ca == bc[j - 1]:
                cost = 0
            best: int = prev[j] + 1
            if cur[j - 1] + 1 < best:
                best = cur[j - 1] + 1
            if prev[j - 1] + cost < best:
                best = prev[j - 1] + cost
            cur[j] = best
        for j in range(m + 1):
            prev[j] = cur[j]
    return prev[m]
