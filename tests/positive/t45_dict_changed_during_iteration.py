# a comprehension over a dict whose size changes while it runs: uncaught RuntimeError, as in CPython
def add_key(d: dict[int, int], k: int) -> int:
    d[k + 100] = k
    return k


d: dict[int, int] = {1: 1, 2: 2}
print({k: d[k] for k in d}, [k for i, k in enumerate(d)])
print([add_key(d, k) for k in d])
print("unreachable")
