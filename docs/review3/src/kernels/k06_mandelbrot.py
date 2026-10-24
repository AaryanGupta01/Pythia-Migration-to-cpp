def mandel(w: int, h: int, limit: int) -> int:
    inside: int = 0
    for py in range(h):
        for px in range(w):
            cr: float = -2.0 + 3.0 * px / w
            ci: float = -1.5 + 3.0 * py / h
            zr: float = 0.0
            zi: float = 0.0
            k: int = 0
            while k < limit and zr * zr + zi * zi <= 4.0:
                t: float = zr * zr - zi * zi + cr
                zi = 2.0 * zr * zi + ci
                zr = t
                k += 1
            if k == limit:
                inside += 1
    return inside

print(mandel(300, 300, 300))
