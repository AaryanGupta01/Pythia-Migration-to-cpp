"""Monte-Carlo estimate of pi with an inline LCG (no calls, tiny inputs, long loop)."""
try:  # pythia-accel
    from _pythia_accel import accelerated as _pythia_accelerated
except ImportError:
    def _pythia_accelerated(*_a, **_k):
        return lambda f: f

MODULUS = 2147483648


@_pythia_accelerated("pythia_f5499568", "monte_carlo_pi")
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
