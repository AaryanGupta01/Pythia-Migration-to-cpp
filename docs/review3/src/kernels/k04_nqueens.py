def solve(row: int, n: int, cols: list[bool], d1: list[bool], d2: list[bool]) -> int:
    if row == n:
        return 1
    count: int = 0
    for c in range(n):
        if cols[c] or d1[row + c] or d2[row - c + n - 1]:
            continue
        cols[c] = True
        d1[row + c] = True
        d2[row - c + n - 1] = True
        count += solve(row + 1, n, cols, d1, d2)
        cols[c] = False
        d1[row + c] = False
        d2[row - c + n - 1] = False
    return count

N: int = 9
print(solve(0, N, [False] * N, [False] * (2 * N), [False] * (2 * N)))
