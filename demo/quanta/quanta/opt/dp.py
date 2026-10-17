"""Dynamic-programming optimisers: knapsack, change counting, subsequence and path problems."""

MODULUS = 1000000007
UNREACHABLE = 1000000000


def knapsack_01(weights: list[int], values: list[int], capacity: int) -> int:
    """Best total value of items (each usable once) whose weights fit in `capacity`."""
    best: list[int] = []
    for c in range(capacity + 1):
        best.append(0)
    for i in range(len(weights)):
        w: int = weights[i]
        v: int = values[i]
        for c in range(capacity, w - 1, -1):
            cand: int = best[c - w] + v
            if cand > best[c]:
                best[c] = cand
    return best[capacity]


def coin_ways(coins: list[int], amount: int) -> int:
    """Number of multisets of `coins` summing to `amount`, modulo 1_000_000_007."""
    ways: list[int] = []
    for a in range(amount + 1):
        ways.append(0)
    ways[0] = 1
    for coin in coins:
        for a in range(coin, amount + 1):
            ways[a] = (ways[a] + ways[a - coin]) % MODULUS
    return ways[amount]


def longest_increasing_subsequence(seq: list[int]) -> int:
    """Length of the longest strictly increasing subsequence, O(n^2)."""
    n = len(seq)
    if n == 0:
        return 0
    best = [1] * n
    for i in range(1, n):
        for j in range(i):
            if seq[j] < seq[i] and best[j] + 1 > best[i]:
                best[i] = best[j] + 1
    return max(best)


def grid_min_path(cost: list[list[int]]) -> int:
    """Cheapest top-left to bottom-right path moving right, down or diagonally down-right."""
    rows = len(cost)
    cols = len(cost[0])
    acc = [row[:] for row in cost]
    for r in range(rows):
        for c in range(cols):
            if r == 0 and c == 0:
                continue
            up = acc[r - 1][c] if r > 0 else UNREACHABLE
            left = acc[r][c - 1] if c > 0 else UNREACHABLE
            diag = acc[r - 1][c - 1] if r > 0 and c > 0 else UNREACHABLE
            acc[r][c] += min(up, left, diag)
    return acc[rows - 1][cols - 1]
