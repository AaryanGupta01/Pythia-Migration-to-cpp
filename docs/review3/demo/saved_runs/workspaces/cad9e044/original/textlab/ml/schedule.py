"""Learning-rate schedule built as a closure (not eligible: nested function)."""


def make_lr_schedule(base_lr: float, decay: float):
    def lr_at(step: int) -> float:
        return base_lr / (1.0 + decay * step)
    return lr_at
