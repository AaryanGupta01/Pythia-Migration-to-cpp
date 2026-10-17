"""k-means clustering: data generation and the Lloyd iteration loop around the compiled-friendly kernels."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from quanta.cluster.kernels import assign_points, inertia, update_centroids
from quanta.util.rng import Lcg


@dataclass
class ClusterFit:
    centroids: List[List[float]]
    labels: List[int]
    inertia: float
    iterations: int


def make_blobs(rng: Lcg, points: int, centres: int, dims: int, spread: float = 0.6) -> List[List[float]]:
    """Gaussian blobs around random centres in [0, 10]^dims."""
    anchors = [[rng.uniform(0.0, 10.0) for _ in range(dims)] for _ in range(centres)]
    data = []
    for _ in range(points):
        anchor = anchors[rng.next_int(centres)]
        data.append([a + spread * rng.gauss() for a in anchor])
    return data


class KMeans:
    """Lloyd's algorithm with deterministic, restart-indexed initialisation."""

    def __init__(self, k: int, max_iter: int = 20) -> None:
        self.k = k
        self.max_iter = max_iter

    def fit(self, points: List[List[float]], restart: int = 0) -> ClusterFit:
        """Cluster `points`; each `restart` number starts from a different, evenly spread set of seed points."""
        stride = len(points) // self.k
        centroids = [list(points[(restart * 131 + i * stride) % len(points)]) for i in range(self.k)]
        labels: List[int] = []
        iterations = 0
        for iterations in range(1, self.max_iter + 1):
            new_labels = assign_points(points, centroids)
            if new_labels == labels:
                break
            labels = new_labels
            centroids = update_centroids(points, labels, centroids)
        return ClusterFit(centroids, labels, inertia(points, labels, centroids), iterations)
