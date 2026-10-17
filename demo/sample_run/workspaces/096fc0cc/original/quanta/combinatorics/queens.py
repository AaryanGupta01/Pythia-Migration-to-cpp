"""The n-queens puzzle: count the placements of n non-attacking queens on an n x n board."""


def count_queens(n: int) -> int:
    """Number of distinct solutions of the n-queens puzzle (92 for n = 8).

    Iterative backtracking: `pos[row]` is the column currently holding the queen of `row` (-1 when the
    row is empty) and three occupancy tables mark attacked columns and diagonals."""
    pos: list[int] = []
    cols: list[bool] = []
    diag_down: list[bool] = []
    diag_up: list[bool] = []
    for i in range(n):
        pos.append(-1)
        cols.append(False)
    for i in range(2 * n):
        diag_down.append(False)
        diag_up.append(False)
    solutions: int = 0
    row: int = 0
    while row >= 0:
        c: int = pos[row] + 1
        if pos[row] >= 0:
            cols[pos[row]] = False
            diag_down[row + pos[row]] = False
            diag_up[row - pos[row] + n - 1] = False
        placed: bool = False
        while c < n:
            if not cols[c] and not diag_down[row + c] and not diag_up[row - c + n - 1]:
                cols[c] = True
                diag_down[row + c] = True
                diag_up[row - c + n - 1] = True
                pos[row] = c
                placed = True
                break
            c += 1
        if placed:
            if row == n - 1:
                solutions += 1
            else:
                row += 1
                pos[row] = -1
        else:
            pos[row] = -1
            row -= 1
    return solutions
