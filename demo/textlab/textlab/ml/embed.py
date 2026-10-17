"""Row normalisation. Uses numpy when installed, with a pure-Python fallback."""
try:
    import numpy as np
except ImportError:  # numpy is optional for the demo
    np = None


def normalize_rows(rows: list[list[float]]) -> list[list[float]]:
    if np is not None:
        arr = np.array(rows, dtype=float)
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return (arr / norms).tolist()
    out = []
    for row in rows:
        total = 0.0
        for v in row:
            total += v * v
        norm = total ** 0.5 or 1.0
        out.append([v / norm for v in row])
    return out
