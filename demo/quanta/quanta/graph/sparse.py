"""Sparse weighted graphs: adjacency dictionaries, heap-based Dijkstra and connected components."""
from __future__ import annotations

import heapq
from typing import Dict, List, Optional

from quanta.util.rng import Lcg


class Graph:
    """Undirected weighted graph on nodes 0..n-1."""

    def __init__(self, n: int) -> None:
        self.n = n
        self.adj: Dict[int, Dict[int, int]] = {i: {} for i in range(n)}

    def add_edge(self, u: int, v: int, weight: int) -> None:
        if u == v:
            return
        best = self.adj[u].get(v)
        if best is None or weight < best:
            self.adj[u][v] = weight
            self.adj[v][u] = weight

    @property
    def edge_count(self) -> int:
        return sum(len(nbrs) for nbrs in self.adj.values()) // 2

    def shortest_paths(self, source: int) -> Dict[int, int]:
        """Distances from `source` to every reachable node (binary-heap Dijkstra)."""
        dist: Dict[int, int] = {source: 0}
        heap = [(0, source)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist.get(u, d):
                continue
            for v, w in self.adj[u].items():
                nd = d + w
                if nd < dist.get(v, nd + 1):
                    dist[v] = nd
                    heapq.heappush(heap, (nd, v))
        return dist

    def components(self) -> List[List[int]]:
        """Connected components, each sorted, ordered by smallest member."""
        seen = [False] * self.n
        groups = []
        for start in range(self.n):
            if seen[start]:
                continue
            stack, comp = [start], []
            seen[start] = True
            while stack:
                u = stack.pop()
                comp.append(u)
                for v in self.adj[u]:
                    if not seen[v]:
                        seen[v] = True
                        stack.append(v)
            groups.append(sorted(comp))
        return groups

    def to_matrix(self, no_edge: int) -> List[List[int]]:
        """Dense weight matrix with `no_edge` where nodes are not adjacent and 0 on the diagonal."""
        m = [[no_edge] * self.n for _ in range(self.n)]
        for u, nbrs in self.adj.items():
            m[u][u] = 0
            for v, w in nbrs.items():
                m[u][v] = w
        return m

    def to_adjacency_lists(self) -> List[List[int]]:
        return [sorted(self.adj[u]) for u in range(self.n)]


def random_graph(rng: Lcg, nodes: int, edges_per_node: int, max_weight: int = 20) -> Graph:
    """A connected random graph: a random spanning chain plus `edges_per_node` extra edges per node."""
    g = Graph(nodes)
    order = list(range(nodes))
    rng.shuffle(order)
    for a, b in zip(order, order[1:]):
        g.add_edge(a, b, 1 + rng.next_int(max_weight))
    for u in range(nodes):
        for _ in range(edges_per_node):
            g.add_edge(u, rng.next_int(nodes), 1 + rng.next_int(max_weight))
    return g


def farthest_node(dist: Dict[int, int]) -> Optional[int]:
    """The node with the largest finite distance (lowest id on ties)."""
    if not dist:
        return None
    return min(dist, key=lambda node: (-dist[node], node))
