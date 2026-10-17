"""Spectral norm of the infinite matrix A(i, j) = 1 / ((i + j)(i + j + 1)/2 + i + 1), truncated to n x n.

The matrix is never stored: entries are recomputed on demand, which makes the power iteration
compute-bound rather than memory-bound.
"""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f


@_pythia_accelerated("pythia_af7d4d1a", "mult_av")
def mult_av(v: list[float]) -> list[float]:
    """The product A v."""
    n: int = len(v)
    out: list[float] = []
    for i in range(n):
        acc: float = 0.0
        for j in range(n):
            acc += v[j] / (((i + j) * (i + j + 1)) // 2 + i + 1)
        out.append(acc)
    return out


@_pythia_accelerated("pythia_964c4de6", "mult_atv")
def mult_atv(v: list[float]) -> list[float]:
    """The product A^T v."""
    n: int = len(v)
    out: list[float] = []
    for i in range(n):
        acc: float = 0.0
        for j in range(n):
            acc += v[j] / (((i + j) * (i + j + 1)) // 2 + j + 1)
        out.append(acc)
    return out


@_pythia_accelerated("pythia_fea108f6", "spectral_norm")
def spectral_norm(n: int, iterations: int) -> float:
    """Largest singular value of the n x n truncation, by power iteration on A^T A."""
    u: list[float] = []
    for i in range(n):
        u.append(1.0)
    v: list[float] = []
    for i in range(n):
        v.append(0.0)
    for it in range(iterations):
        v = mult_atv(mult_av(u))
        u = mult_atv(mult_av(v))
    vbv: float = 0.0
    vv: float = 0.0
    for i in range(n):
        vbv += u[i] * v[i]
        vv += v[i] * v[i]
    return (vbv / vv) ** 0.5
