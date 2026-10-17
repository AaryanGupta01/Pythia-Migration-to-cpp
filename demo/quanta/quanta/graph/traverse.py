"""Breadth-first traversal helpers for graphs stored as adjacency lists."""


def bfs_levels(adjacency: list[list[int]], source: int) -> list[int]:
    """Hop distance from `source` to every node (-1 when unreachable), using a list as the queue."""
    dist = [-1] * len(adjacency)
    dist[source] = 0
    queue = [source]
    while queue:
        node = queue.pop(0)
        for nxt in adjacency[node]:
            if dist[nxt] < 0:
                dist[nxt] = dist[node] + 1
                queue.append(nxt)
    return dist


def reachable_count(adjacency: list[list[int]], source: int) -> int:
    """Number of nodes reachable from `source`, itself included."""
    return sum(1 for d in bfs_levels(adjacency, source) if d >= 0)
