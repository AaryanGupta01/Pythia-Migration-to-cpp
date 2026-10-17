"""Escape-time fractals (Mandelbrot set) rendered one scanline at a time."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f

PALETTE = " .:-=+*#%@"


@_pythia_accelerated("pythia_7e2898b9", "mandelbrot_row")
def mandelbrot_row(py: int, width: int, height: int, max_iter: int) -> list[int]:
    """Escape iteration counts for scanline `py` of a width x height view of [-2.2, 0.8] x [-1.2, 1.2]."""
    row: list[int] = []
    ci: float = (py / height) * 2.4 - 1.2
    for px in range(width):
        cr: float = (px / width) * 3.0 - 2.2
        zr: float = 0.0
        zi: float = 0.0
        n: int = 0
        while n < max_iter and zr * zr + zi * zi <= 4.0:
            t: float = zr * zr - zi * zi + cr
            zi = 2.0 * zr * zi + ci
            zr = t
            n += 1
        row.append(n)
    return row


@_pythia_accelerated("pythia_d1362556", "escape_area")
def escape_area(width: int, height: int, max_iter: int) -> int:
    """Number of grid points that never escape: a crude estimate of the set's area."""
    inside: int = 0
    for py in range(height):
        row: list[int] = mandelbrot_row(py, width, height, max_iter)
        for v in row:
            if v >= max_iter:
                inside += 1
    return inside


def shade_row(counts: list[int], max_iter: int) -> str:
    """Map escape counts to PALETTE characters (glue: uses the module-level palette string)."""
    out = []
    for c in counts:
        out.append(PALETTE[min(len(PALETTE) - 1, c * len(PALETTE) // (max_iter + 1))])
    return "".join(out)
