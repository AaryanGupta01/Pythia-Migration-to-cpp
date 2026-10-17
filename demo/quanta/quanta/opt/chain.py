"""More dynamic programmes: matrix-chain ordering, integer partitions, rod cutting, maximum subarray."""

PARTITION_MODULUS = 998244353


def matrix_chain_cost(dims: list[int]) -> int:
    """Fewest scalar multiplications to multiply a chain of matrices; matrix i is dims[i] x dims[i + 1]."""
    n: int = len(dims) - 1
    cost: list[list[int]] = []
    for i in range(n):
        row: list[int] = []
        for j in range(n):
            row.append(0)
        cost.append(row)
    for length in range(2, n + 1):
        for i in range(n - length + 1):
            j: int = i + length - 1
            best: int = -1
            for k in range(i, j):
                c: int = cost[i][k] + cost[k + 1][j] + dims[i] * dims[k + 1] * dims[j + 1]
                if best < 0 or c < best:
                    best = c
            cost[i][j] = best
    return cost[0][n - 1]


def partition_count(n: int) -> int:
    """Number of ways to write n as an unordered sum of positive integers, modulo 998244353."""
    ways: list[int] = []
    for i in range(n + 1):
        ways.append(0)
    ways[0] = 1
    for part in range(1, n + 1):
        for total in range(part, n + 1):
            ways[total] = (ways[total] + ways[total - part]) % PARTITION_MODULUS
    return ways[n]


def rod_cutting(prices: list[int], length: int) -> int:
    """Best revenue from cutting a rod of `length` units; prices[k] is the price of a piece of k + 1 units."""
    best: list[int] = []
    for i in range(length + 1):
        best.append(0)
    for total in range(1, length + 1):
        for cut in range(1, min(total, len(prices)) + 1):
            cand: int = best[total - cut] + prices[cut - 1]
            if cand > best[total]:
                best[total] = cand
    return best[length]


def max_subarray(values: list[int]) -> int:
    """Largest sum of a non-empty contiguous run (Kadane's algorithm)."""
    best: int = values[0]
    run: int = values[0]
    for i in range(1, len(values)):
        if run < 0:
            run = values[i]
        else:
            run += values[i]
        if run > best:
            best = run
    return best
