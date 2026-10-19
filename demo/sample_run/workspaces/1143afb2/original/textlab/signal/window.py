"""Sliding-window energy of a long signal: cheap per call, huge input per call."""


def window_energy(signal: list[float], start: int, width: int) -> float:
    total: float = 0.0
    for i in range(start, start + width):
        total += signal[i] * signal[i]
    return total


def energy_profile(signal, width):
    # Generator: not eligible, and the reason the compiled window_energy gets called ~100k times.
    for s in range(0, len(signal) - width):
        yield window_energy(signal, s, width)
