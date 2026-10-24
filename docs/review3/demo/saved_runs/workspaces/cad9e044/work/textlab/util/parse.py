"""Loose input parsing helpers (dynamic typing on purpose)."""


def parse_number(token: str) -> int:
    # Not eligible: `value` starts as a str, then becomes an int (and may stay a str).
    value = token
    if len(token) > 0:
        value = int(token)
    return value


def summarize(*values):
    # Not eligible: *args is outside the PySub subset.
    total = 0.0
    for v in values:
        total += v
    return total / len(values) if values else 0.0
