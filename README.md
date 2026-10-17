# PYTHIA

**A statically typed Python-subset → C transpiler with a differential-testing oracle.**

BCSE307L Compiler Design · Team 2 · Project **A15 — Typed Source-to-Source Transpiler**
VIT Vellore, Fall 2026

**PYTHIA Studio** (the web app that finds Python hotspots and accelerates them with verified C++) lives in [`studio/`](studio/README.md); install it with [`INSTALL.md`](INSTALL.md).

---

## What it does

PYTHIA takes a program written in **PySub** — a statically typed subset of Python 3 —
and emits readable, dependency-free C11 that a stock `cc` compiles to a native binary.
The claim it makes is not "it produces C"; it is **"it produces C that observably
behaves like CPython"**, and the repository ships the falsifier for that claim.

```
source.py ──▶ lexer ──▶ parser ──▶ type checker ──▶ lowering ──▶ C emitter ──▶ target.c
                                        │              │
                                   diagnostics   Semantic Fidelity Report
```

## Quickstart

```bash
git clone <repo> && cd pythia

python3 -m pythia.cli tests/positive/t07_bubble.py --emit-only   # show the C
python3 -m pythia.cli tests/positive/t07_bubble.py --run         # build and run
python3 -m pythia.cli tests/positive/t01_arith.py  --fidelity    # divergence report

python3 tools/oracle.py                                          # full differential suite
```

No third-party dependencies. Requires Python 3.10+, a C11 compiler, and `dot`
+ `matplotlib` only for regenerating `docs/` figures.

## Current results (`tools/oracle.py`)

| Metric | Value |
|---|---|
| Semantic equivalence vs CPython 3.12 | **14 / 14 programs, byte-identical stdout** |
| Exception-class parity | IndexError, ZeroDivisionError, OverflowError reproduced |
| Invalid programs correctly rejected | **12 / 12** |
| Median speedup over CPython | **≈ 9.4×** (min 3.3×, max 13.8×) |
| Divergence classes catalogued | 7 (D1–D7) |
| Implementation size | ≈ 2 800 LOC |

## Layout

```
pythia/
  lexer.py       off-side rule scanner (INDENT/DEDENT)      M1 Vishal
  parser.py      recursive descent + Pratt, panic recovery  M1 Vishal
  ast_nodes.py   AST / TAST node definitions                M1 Vishal
  typecheck.py   symbol table + bidirectional type checker   M2 Rujuta
  lower.py       semantic normalisation, fidelity report    M3 Jahnavi
  emit_c.py      PIR → C11 emitter                          M4 Aaryan
  cli.py         driver, diagnostic rendering               M1 Vishal
runtime/
  pyrt.h/.c      Python-semantics runtime for C             M3 Jahnavi
tools/
  oracle.py      differential testing oracle                M4 Aaryan
tests/
  positive/      14 programs checked against CPython
  negative/      12 programs that must be rejected
docs/
  architecture.png, gantt.png, make_figures.py
```

## The PySub subset

**In:** `int` `float` `bool` `str` `list[T]` `None`; `def` with mandatory parameter
and return annotations; `if/elif/else`, `while`, `for … in range()`, `for … in list/str`,
`break`, `continue`, `return`, `pass`; arithmetic `+ - * / // % **`, comparisons,
`and/or/not`; indexing and index assignment with negative indices; `len` `abs` `min`
`max` `int` `float` `str` `bool` `print`; `list.append` `list.pop` `str.upper`
`str.lower`.

**Deliberately out (Review 2 / 3):** classes, closures, nested lists, `dict`, `set`,
slicing, `try/except`, generators, imports, keyword and default arguments.

## The seven divergence classes

| | Divergence | Status |
|---|---|---|
| D1 | unbounded `int` vs `int64_t` | **guarded** — traps via `__builtin_*_overflow` |
| D2 | `//` floors toward −∞, C truncates toward 0 | **exact** |
| D3 | sign of `%` follows the divisor, not the dividend | **exact** |
| D4 | `/` is always true division | **exact** |
| D5 | negative indexing + `IndexError` bounds checks | **exact** |
| D6 | `int ** negative int` changes the static type | **divergent** — reported, refused |
| D7 | object lifetime (no reclamation yet) | **guarded** — output unaffected |

Every occurrence is logged with source position by `--fidelity`. A transpiler that
silently approximates is a miscompiler; one that reports is a tool.

## License

Coursework submission. Runtime and compiler are original work by Team 2.
