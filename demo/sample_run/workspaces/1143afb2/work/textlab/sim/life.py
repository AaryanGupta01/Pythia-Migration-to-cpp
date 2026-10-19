"""Conway's Game of Life on a torus. Fixable: tuple loops, ternary, enumerate, comprehensions."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_015b9217", "life_generations")
def life_generations(grid: list[list[int]], gens: int) -> int:
    h = len(grid)
    w = len(grid[0])
    cells = [row[:] for row in grid]
    for _ in range(gens):
        nxt = [[0] * w for _ in range(h)]
        for y, row in enumerate(cells):
            for x in range(w):
                total = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dy != 0 or dx != 0:
                            total += cells[(y + dy) % h][(x + dx) % w]
                nxt[y][x] = 1 if total == 3 or (row[x] == 1 and total == 2) else 0
        cells = nxt
    return sum(sum(row) for row in cells)
