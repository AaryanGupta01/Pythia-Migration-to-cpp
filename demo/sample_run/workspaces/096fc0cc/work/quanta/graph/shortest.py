"""All-pairs and single-source shortest paths on dense graphs given as weight matrices.

A weight of NO_EDGE means "no direct edge".  Matrices are square lists of lists of ints.
"""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f

NO_EDGE = 1000000000


@_pythia_accelerated("pythia_b024560c", "floyd_warshall")
def floyd_warshall(weights: list[list[int]]) -> list[list[int]]:
    """Shortest distance between every pair of nodes; NO_EDGE where no path exists."""
    n: int = len(weights)
    dist: list[list[int]] = []
    for i in range(n):
        row: list[int] = []
        for j in range(n):
            row.append(weights[i][j])
        dist.append(row)
    for k in range(n):
        for i in range(n):
            dik: int = dist[i][k]
            if dik >= NO_EDGE:
                continue
            for j in range(n):
                alt: int = dik + dist[k][j]
                if alt < dist[i][j]:
                    dist[i][j] = alt
    return dist


@_pythia_accelerated("pythia_c0ba7141", "dijkstra_dense")
def dijkstra_dense(weights: list[list[int]], source: int) -> list[int]:
    """Single-source shortest distances with the O(n^2) array-scan variant of Dijkstra's algorithm."""
    n: int = len(weights)
    dist: list[int] = []
    done: list[bool] = []
    for i in range(n):
        dist.append(NO_EDGE)
        done.append(False)
    dist[source] = 0
    for step in range(n):
        u: int = -1
        for i in range(n):
            if not done[i] and (u == -1 or dist[i] < dist[u]):
                u = i
        if u == -1 or dist[u] >= NO_EDGE:
            break
        done[u] = True
        for v in range(n):
            w: int = weights[u][v]
            if w < NO_EDGE and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    return dist


@_pythia_accelerated("pythia_d031e8c1", "eccentricity_sum")
def eccentricity_sum(weights: list[list[int]]) -> int:
    """Sum over nodes of the distance to their farthest reachable node (graph 'radius' bookkeeping)."""
    dist: list[list[int]] = floyd_warshall(weights)
    total: int = 0
    for i in range(len(dist)):
        far: int = 0
        for j in range(len(dist)):
            if dist[i][j] < NO_EDGE and dist[i][j] > far:
                far = dist[i][j]
        total += far
    return total
