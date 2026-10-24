"""k-means clustering: the assignment step is the hot loop."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_2396e349", "assign_clusters")
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


class KMeans:
    """Driver loop (a class, so not analysed): calls the compiled-able assign_clusters."""

    def __init__(self, centroids):
        self.centroids = centroids

    def update(self, points, labels):
        dim = len(self.centroids[0])
        sums = [[0.0] * dim for _ in self.centroids]
        counts = [0] * len(self.centroids)
        for point, label in zip(points, labels):
            counts[label] += 1
            for k, value in enumerate(point):
                sums[label][k] += value
        self.centroids = [[s / counts[c] if counts[c] else self.centroids[c][k] for k, s in enumerate(row)]
                          for c, row in enumerate(sums)]

    def fit(self, points, iterations):
        labels = []
        for _ in range(iterations):
            labels = assign_clusters(points, self.centroids)
            self.update(points, labels)
        return labels
