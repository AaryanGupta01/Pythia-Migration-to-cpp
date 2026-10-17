"""k-means clustering: the assignment step is the hot loop."""


def assign_clusters(points: list[list[float]], centroids: list[list[float]]) -> list[int]:
    out: list[int] = []
    dim: int = len(centroids[0])
    for p in range(len(points)):
        best: int = 0
        best_d: float = 1e18
        for c in range(len(centroids)):
            d: float = 0.0
            for k in range(dim):
                diff: float = points[p][k] - centroids[c][k]
                d += diff * diff
            if d < best_d:
                best_d = d
                best = c
        out.append(best)
    return out


def update_centroids(points, labels, centroids):
    sums = [[0.0] * len(centroids[0]) for _ in centroids]
    counts = [0] * len(centroids)
    for point, label in zip(points, labels):
        counts[label] += 1
        for k, value in enumerate(point):
            sums[label][k] += value
    return [[s / counts[c] if counts[c] else centroids[c][k] for k, s in enumerate(row)]
            for c, row in enumerate(sums)]


def kmeans(points, centroids, iterations):
    labels = []
    for _ in range(iterations):
        labels = assign_clusters(points, centroids)
        centroids = update_centroids(points, labels, centroids)
    return labels, centroids
