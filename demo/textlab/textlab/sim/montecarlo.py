"""Monte-Carlo estimate of pi with an inline LCG (no calls, tiny inputs, long loop)."""

MODULUS = 2147483648


def monte_carlo_pi(samples: int, seed: int) -> float:
    state: int = seed % MODULUS
    inside: int = 0
    for i in range(samples):
        state = (state * 1103515245 + 12345) % MODULUS
        x: float = float(state) / 2147483648.0
        state = (state * 1103515245 + 12345) % MODULUS
        y: float = float(state) / 2147483648.0
        if x * x + y * y < 1.0:
            inside += 1
    return 4.0 * float(inside) / float(samples)
