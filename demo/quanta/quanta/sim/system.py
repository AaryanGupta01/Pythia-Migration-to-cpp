"""Initial conditions and bookkeeping for the n-body simulation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from quanta.sim.nbody import SOLAR_MASS, advance, total_energy

DAYS_PER_YEAR = 365.24

# name, position (AU), velocity (AU/day), mass (solar masses)
_BODIES = [
    ("sun", (0.0, 0.0, 0.0), (0.0, 0.0, 0.0), 1.0),
    ("jupiter", (4.84143144246472090, -1.16032004402742839, -0.103622044471123109),
     (1.66007664274403694e-03, 7.69901118419740425e-03, -6.90460016972063023e-05), 9.54791938424326609e-04),
    ("saturn", (8.34336671824457987, 4.12479856412430479, -0.403523417114321381),
     (-2.76742510726862411e-03, 4.99852801234917238e-03, 2.30417297573763929e-05), 2.85885980666130812e-04),
    ("uranus", (12.8943695621391310, -15.1111514016986312, -0.223307578892655734),
     (2.96460137564761618e-03, 2.37847173959480950e-03, -2.96589568540237556e-05), 4.36624404335156298e-05),
    ("neptune", (15.3796971148509165, -25.9193146099879641, 0.179258772950371181),
     (2.68067772490389322e-03, 1.62824170038242295e-03, -9.51592254519715870e-05), 5.15138902046611451e-05),
]


@dataclass
class System:
    """Parallel coordinate lists for a set of gravitating bodies."""

    names: List[str]
    x: List[float]
    y: List[float]
    z: List[float]
    vx: List[float]
    vy: List[float]
    vz: List[float]
    mass: List[float]

    @classmethod
    def outer_planets(cls) -> "System":
        """The sun and the four giant planets, with the sun's velocity set so total momentum is zero."""
        s = cls([], [], [], [], [], [], [], [])
        for name, pos, vel, m in _BODIES:
            s.names.append(name)
            s.x.append(pos[0])
            s.y.append(pos[1])
            s.z.append(pos[2])
            s.vx.append(vel[0] * DAYS_PER_YEAR)
            s.vy.append(vel[1] * DAYS_PER_YEAR)
            s.vz.append(vel[2] * DAYS_PER_YEAR)
            s.mass.append(m * SOLAR_MASS)
        px = sum(v * m for v, m in zip(s.vx, s.mass))
        py = sum(v * m for v, m in zip(s.vy, s.mass))
        pz = sum(v * m for v, m in zip(s.vz, s.mass))
        s.vx[0], s.vy[0], s.vz[0] = -px / SOLAR_MASS, -py / SOLAR_MASS, -pz / SOLAR_MASS
        return s

    def energy(self) -> float:
        return total_energy(self.x, self.y, self.z, self.vx, self.vy, self.vz, self.mass)

    def advance(self, dt: float, steps: int) -> None:
        advance(self.x, self.y, self.z, self.vx, self.vy, self.vz, self.mass, dt, steps)

    def distance_from_sun(self, i: int) -> float:
        return ((self.x[i] - self.x[0]) ** 2 + (self.y[i] - self.y[0]) ** 2 + (self.z[i] - self.z[0]) ** 2) ** 0.5
