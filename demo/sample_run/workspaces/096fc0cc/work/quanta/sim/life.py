"""Conway's Game of Life on a bounded (dead border) grid of 0/1 cells."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_ec390a0d", "life_step")
def life_step(grid: list[list[int]]) -> list[list[int]]:
    """One generation; cells outside the grid count as dead."""
    h: int = len(grid)
    w: int = len(grid[0])
    nxt: list[list[int]] = []
    for r in range(h):
        row: list[int] = []
        for c in range(w):
            alive: int = 0
            for dr in range(-1, 2):
                for dc in range(-1, 2):
                    if dr == 0 and dc == 0:
                        continue
                    rr: int = r + dr
                    cc: int = c + dc
                    if rr >= 0 and rr < h and cc >= 0 and cc < w:
                        alive += grid[rr][cc]
            if alive == 3 or (alive == 2 and grid[r][c] == 1):
                row.append(1)
            else:
                row.append(0)
        nxt.append(row)
    return nxt


@_pythia_accelerated("pythia_635510ba", "life_population")
def life_population(grid: list[list[int]], generations: int) -> int:
    """Live cells after the given number of generations (bounded grid, dead border)."""
    h = len(grid)
    w = len(grid[0])
    cur = [row[:] for row in grid]
    for _ in range(generations):
        nxt = [[0] * w for _ in range(h)]
        for r in range(h):
            for c in range(w):
                alive = sum(cur[r + dr][c + dc]
                            for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                            if (dr or dc) and 0 <= r + dr < h and 0 <= c + dc < w)
                nxt[r][c] = 1 if alive == 3 or (alive == 2 and cur[r][c]) else 0
        cur = nxt
    return sum(sum(row) for row in cur)
