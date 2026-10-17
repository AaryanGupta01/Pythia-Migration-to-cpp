"""Dense linear algebra on row-major lists of floats."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_cf6326a2", "matmul")
def matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    """Matrix product a @ b (a is n x k, b is k x m)."""
    n: int = len(a)
    k: int = len(b)
    m: int = len(b[0])
    out: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(m):
            acc: float = 0.0
            for t in range(k):
                acc += a[i][t] * b[t][j]
            row.append(acc)
        out.append(row)
    return out


@_pythia_accelerated("pythia_106934f8", "gauss_solve")
def gauss_solve(a: list[list[float]], b: list[float]) -> list[float]:
    """Solve a x = b by Gaussian elimination with partial pivoting.  Inputs are left untouched."""
    n: int = len(b)
    m: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            row.append(a[i][j])
        row.append(b[i])
        m.append(row)
    for col in range(n):
        pivot: int = col
        for r in range(col + 1, n):
            if abs(m[r][col]) > abs(m[pivot][col]):
                pivot = r
        if abs(m[pivot][col]) < 1e-12:
            raise ValueError("matrix is singular")
        if pivot != col:
            for j in range(col, n + 1):
                tmp: float = m[col][j]
                m[col][j] = m[pivot][j]
                m[pivot][j] = tmp
        for r in range(col + 1, n):
            factor: float = m[r][col] / m[col][col]
            for j in range(col, n + 1):
                m[r][j] -= factor * m[col][j]
    x: list[float] = []
    for i in range(n):
        x.append(0.0)
    for i in range(n - 1, -1, -1):
        acc: float = m[i][n]
        for j in range(i + 1, n):
            acc -= m[i][j] * x[j]
        x[i] = acc / m[i][i]
    return x


def transpose(a: list[list[float]]) -> list[list[float]]:
    """Transpose of a rectangular matrix."""
    out: list[list[float]] = []
    for j in range(len(a[0])):
        row: list[float] = []
        for i in range(len(a)):
            row.append(a[i][j])
        out.append(row)
    return out
