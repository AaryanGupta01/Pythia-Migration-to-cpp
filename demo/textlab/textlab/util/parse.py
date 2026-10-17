"""Loose input parsing helpers (dynamic typing on purpose)."""


def parse_number(token):
    # Not eligible: `value` is a str, then an int, then a float.
    value = token.strip()
    if value.isdigit():
        value = int(value)
    elif value.replace(".", "", 1).isdigit():
        value = float(value)
    return value


def summarize(*values):
    # Not eligible: *args is outside the PySub subset.
    total = 0.0
    for v in values:
        total += v
    return total / len(values) if values else 0.0
