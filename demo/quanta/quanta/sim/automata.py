"""One-dimensional cellular automata on a ring of 0/1 cells (Wolfram rule numbers)."""


def rule_automaton(cells: list[int], rule: int, steps: int) -> list[int]:
    """Apply elementary rule `rule` (0-255) for `steps` generations; the row wraps around at both ends."""
    n: int = len(cells)
    table: list[int] = []
    code: int = rule
    for bit in range(8):
        table.append(code % 2)
        code = code // 2
    cur: list[int] = []
    nxt: list[int] = []
    for i in range(n):
        cur.append(cells[i])
        nxt.append(0)
    for step in range(steps):
        for i in range(n):
            left: int = cur[(i + n - 1) % n]
            right: int = cur[(i + 1) % n]
            nxt[i] = table[left * 4 + cur[i] * 2 + right]
        for i in range(n):
            cur[i] = nxt[i]
    return cur


def density(cells: list[int]) -> float:
    """Fraction of live cells."""
    live: int = 0
    for c in cells:
        live += c
    return live / len(cells)
