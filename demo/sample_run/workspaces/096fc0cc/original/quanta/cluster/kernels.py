"""Inner loops of Lloyd's k-means algorithm on points stored as rows of floats."""


def assign_points(points: list[list[float]], centroids: list[list[float]]) -> list[int]:
    """Index of the nearest centroid (squared Euclidean distance, first one wins ties) for every point."""
    labels: list[int] = []
    dims: int = len(centroids[0])
    for p in points:
        best: int = 0
        best_d: float = -1.0
        for c in range(len(centroids)):
            d: float = 0.0
            for t in range(dims):
                diff: float = p[t] - centroids[c][t]
                d += diff * diff
            if best_d < 0.0 or d < best_d:
                best_d = d
                best = c
        labels.append(best)
    return labels


def update_centroids(points: list[list[float]], labels: list[int],
                     centroids: list[list[float]]) -> list[list[float]]:
    """Mean of the points assigned to each cluster; an empty cluster keeps its previous centre."""
    k: int = len(centroids)
    dims: int = len(centroids[0])
    sums: list[list[float]] = []
    counts: list[int] = []
    for c in range(k):
        zero: list[float] = []
        for t in range(dims):
            zero.append(0.0)
        sums.append(zero)
        counts.append(0)
    for i in range(len(points)):
        c = labels[i]
        counts[c] += 1
        for t in range(dims):
            sums[c][t] += points[i][t]
    out: list[list[float]] = []
    for c in range(k):
        row: list[float] = []
        for t in range(dims):
            if counts[c] > 0:
                row.append(sums[c][t] / counts[c])
            else:
                row.append(centroids[c][t])
        out.append(row)
    return out


def inertia(points: list[list[float]], labels: list[int], centroids: list[list[float]]) -> float:
    """Within-cluster sum of squared distances (the quantity k-means minimises)."""
    total: float = 0.0
    for i in range(len(points)):
        for t in range(len(centroids[0])):
            diff: float = points[i][t] - centroids[labels[i]][t]
            total += diff * diff
    return total
