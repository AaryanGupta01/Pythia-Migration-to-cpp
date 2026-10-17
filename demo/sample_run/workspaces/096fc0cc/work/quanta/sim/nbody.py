"""Newtonian n-body integration for the outer solar system.

Bodies are stored as parallel coordinate lists (structure of arrays) so that the integrator touches
plain float lists only.  Units follow the classic benchmark setup: AU, days and solar masses
scaled by 4*pi^2.
"""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f

SOLAR_MASS = 39.47841760435743


@_pythia_accelerated("pythia_fbe123f9", "advance")
def advance(x: list[float], y: list[float], z: list[float],
            vx: list[float], vy: list[float], vz: list[float],
            mass: list[float], dt: float, steps: int) -> None:
    """Advance the system by `steps` fixed time steps of size `dt` (velocity update, then drift)."""
    n: int = len(x)
    for step in range(steps):
        for i in range(n):
            for j in range(i + 1, n):
                dx: float = x[i] - x[j]
                dy: float = y[i] - y[j]
                dz: float = z[i] - z[j]
                dist2: float = dx * dx + dy * dy + dz * dz
                mag: float = dt / (dist2 * (dist2 ** 0.5))
                vx[i] -= dx * mass[j] * mag
                vy[i] -= dy * mass[j] * mag
                vz[i] -= dz * mass[j] * mag
                vx[j] += dx * mass[i] * mag
                vy[j] += dy * mass[i] * mag
                vz[j] += dz * mass[i] * mag
        for i in range(n):
            x[i] += dt * vx[i]
            y[i] += dt * vy[i]
            z[i] += dt * vz[i]


def total_energy(x: list[float], y: list[float], z: list[float],
                 vx: list[float], vy: list[float], vz: list[float],
                 mass: list[float]) -> float:
    """Kinetic plus pairwise gravitational potential energy of the system."""
    n: int = len(x)
    e: float = 0.0
    for i in range(n):
        e += 0.5 * mass[i] * (vx[i] * vx[i] + vy[i] * vy[i] + vz[i] * vz[i])
        for j in range(i + 1, n):
            dx: float = x[i] - x[j]
            dy: float = y[i] - y[j]
            dz: float = z[i] - z[j]
            e -= (mass[i] * mass[j]) / ((dx * dx + dy * dy + dz * dz) ** 0.5)
    return e
