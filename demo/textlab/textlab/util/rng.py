"""Deterministic pseudo-random numbers (hand-written LCG, glibc constants)."""


class Rng:
    """Methods of a class are never analysed: PYTHIA v1 handles module-level functions only."""

    def __init__(self, seed: int):
        self.state = seed % 2147483648

    def next_int(self, bound: int) -> int:
        self.state = (self.state * 1103515245 + 12345) % 2147483648
        return (self.state // 65536) % bound

    def next_float(self) -> float:
        self.state = (self.state * 1103515245 + 12345) % 2147483648
        return self.state / 2147483648.0
