# Contributing

- Python 3.9 or newer, standard library only.  NumPy imports must be guarded with `try/except ImportError`.
- Keep numerical routines as module-level functions on lists of `int`/`float`/`str` with full type
  annotations; put argument validation and I/O in the callers.
- Workloads must be deterministic: draw random numbers from `quanta.util.rng.Lcg`, never from `random`,
  and never print wall-clock times to stdout (log them to stderr).
- Run `python -m unittest` before sending a change, and `python main.py --small` to check that the
  printed report did not change unless you meant it to.
- Add a CHANGELOG line for anything user-visible.
