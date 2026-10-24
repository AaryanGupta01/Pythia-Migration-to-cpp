"""2-D softened gravity: leapfrog-style integration of a small particle cloud."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f

SOFTENING = 0.01


@_pythia_accelerated("pythia_81e16165", "simulate_energy")
def simulate_energy(px: list[float], py: list[float], vx: list[float],
                    vy: list[float], mass: list[float], steps: int, dt: float) -> float:
    n: int = len(px)
    x: list[float] = []
    y: list[float] = []
    u: list[float] = []
    v: list[float] = []
    for i in range(n):
        x.append(px[i])
        y.append(py[i])
        u.append(vx[i])
        v.append(vy[i])
    for s in range(steps):
        for i in range(n):
            ax: float = 0.0
            ay: float = 0.0
            for j in range(n):
                if i != j:
                    dx: float = x[j] - x[i]
                    dy: float = y[j] - y[i]
                    d2: float = dx * dx + dy * dy + SOFTENING
                    inv: float = 1.0 / (d2 * (d2 ** 0.5))
                    ax += mass[j] * dx * inv
                    ay += mass[j] * dy * inv
            u[i] += ax * dt
            v[i] += ay * dt
        for i in range(n):
            x[i] += u[i] * dt
            y[i] += v[i] * dt
    kinetic: float = 0.0
    for i in range(n):
        kinetic += 0.5 * mass[i] * (u[i] * u[i] + v[i] * v[i])
    return kinetic
