"""Reachability and motif counting on 0/1 adjacency matrices."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_c1a434b5", "transitive_closure")
def transitive_closure(adjacency: list[list[int]]) -> list[list[int]]:
    """Warshall's algorithm: entry [i][j] is 1 when j is reachable from i (every node reaches itself)."""
    n: int = len(adjacency)
    reach: list[list[int]] = []
    for i in range(n):
        row: list[int] = []
        for j in range(n):
            if i == j or adjacency[i][j] != 0:
                row.append(1)
            else:
                row.append(0)
        reach.append(row)
    for k in range(n):
        for i in range(n):
            if reach[i][k] == 1:
                for j in range(n):
                    if reach[k][j] == 1:
                        reach[i][j] = 1
    return reach


def count_triangles(adjacency: list[list[int]]) -> int:
    """Number of triangles in an undirected graph given as a symmetric 0/1 matrix."""
    n: int = len(adjacency)
    triangles: int = 0
    for i in range(n):
        for j in range(i + 1, n):
            if adjacency[i][j] != 0:
                for k in range(j + 1, n):
                    if adjacency[i][k] != 0 and adjacency[j][k] != 0:
                        triangles += 1
    return triangles


def degree_histogram(adjacency: list[list[int]]) -> list[int]:
    """hist[d] = number of nodes with exactly d neighbours."""
    n: int = len(adjacency)
    hist: list[int] = []
    for d in range(n + 1):
        hist.append(0)
    for i in range(n):
        deg: int = 0
        for j in range(n):
            if adjacency[i][j] != 0 and i != j:
                deg += 1
        hist[deg] += 1
    return hist
