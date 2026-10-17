"""Matrix decompositions on row-major lists of floats."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_70925aee", "determinant")
def determinant(a: list[list[float]]) -> float:
    """Determinant by LU elimination with partial pivoting (the input is not modified)."""
    n: int = len(a)
    m: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            row.append(a[i][j])
        m.append(row)
    det: float = 1.0
    for col in range(n):
        pivot: int = col
        for r in range(col + 1, n):
            if abs(m[r][col]) > abs(m[pivot][col]):
                pivot = r
        if m[pivot][col] == 0.0:
            return 0.0
        if pivot != col:
            for j in range(n):
                tmp: float = m[col][j]
                m[col][j] = m[pivot][j]
                m[pivot][j] = tmp
            det = -det
        det *= m[col][col]
        for r in range(col + 1, n):
            factor: float = m[r][col] / m[col][col]
            for j in range(col, n):
                m[r][j] -= factor * m[col][j]
    return det


def trace(a: list[list[float]]) -> float:
    """Sum of the diagonal."""
    total: float = 0.0
    for i in range(len(a)):
        total += a[i][i]
    return total


def power_iteration(a: list[list[float]], steps: int) -> float:
    """Dominant eigenvalue estimate (Rayleigh quotient) after `steps` multiplications."""
    n: int = len(a)
    v: list[float] = []
    for i in range(n):
        v.append(1.0)
    eig: float = 0.0
    for step in range(steps):
        w: list[float] = []
        for i in range(n):
            acc: float = 0.0
            for j in range(n):
                acc += a[i][j] * v[j]
            w.append(acc)
        norm: float = 0.0
        for i in range(n):
            norm += w[i] * w[i]
        norm = norm ** 0.5
        num: float = 0.0
        den: float = 0.0
        for i in range(n):
            num += w[i] * v[i]
            den += v[i] * v[i]
        eig = num / den
        for i in range(n):
            v[i] = w[i] / norm
    return eig
