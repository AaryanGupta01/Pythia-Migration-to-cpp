"""Rank-based association measures (O(n^2), no sorting required)."""


def kendall_tau(xs: list[float], ys: list[float]) -> float:
    """Kendall's tau-a between two equally long samples: (concordant - discordant) / (n choose 2)."""
    n: int = len(xs)
    concordant: int = 0
    discordant: int = 0
    for i in range(n):
        for j in range(i + 1, n):
            a: float = (xs[i] - xs[j]) * (ys[i] - ys[j])
            if a > 0.0:
                concordant += 1
            elif a < 0.0:
                discordant += 1
    return (concordant - discordant) / (n * (n - 1) / 2)


def rank_transform(values: list[float]) -> list[float]:
    """Average ranks (1-based; ties share the mean of the ranks they occupy)."""
    n: int = len(values)
    ranks: list[float] = []
    for i in range(n):
        below: int = 0
        equal: int = 0
        for j in range(n):
            if values[j] < values[i]:
                below += 1
            elif values[j] == values[i]:
                equal += 1
        ranks.append(below + (equal + 1) / 2.0)
    return ranks


def spearman_rho(xs: list[float], ys: list[float]) -> float:
    """Spearman correlation: the Pearson correlation of the rank-transformed samples."""
    rx: list[float] = rank_transform(xs)
    ry: list[float] = rank_transform(ys)
    n: int = len(rx)
    mx: float = 0.0
    my: float = 0.0
    for i in range(n):
        mx += rx[i]
        my += ry[i]
    mx = mx / n
    my = my / n
    sxy: float = 0.0
    sxx: float = 0.0
    syy: float = 0.0
    for i in range(n):
        sxy += (rx[i] - mx) * (ry[i] - my)
        sxx += (rx[i] - mx) * (rx[i] - mx)
        syy += (ry[i] - my) * (ry[i] - my)
    return sxy / (sxx * syy) ** 0.5
