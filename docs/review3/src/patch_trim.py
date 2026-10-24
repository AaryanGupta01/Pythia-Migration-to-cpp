import re
from pathlib import Path
H = Path(__file__).resolve().parent

b = (H / "build_report.py").read_text(encoding="utf-8")
b = b.replace("import rc1, rc2, rc3, rc4", "import rc1, rc1b, rc2b, rc3, rc3b, rc4")
for n in (2, 3, 4, 5):
    b = b.replace(f"rc1.sec{n}(d, F)", f"rc1b.sec{n}(d, F)")
for n in (6, 7, 8, 9):
    b = b.replace(f"rc2.sec{n}(d, F)", f"rc2b.sec{n}(d, F)")
for n in (10, 11, 12, 13):
    b = b.replace(f"rc3.sec{n}(d, F)", f"rc3b.sec{n}(d, F)")
(H / "build_report.py").write_text(b, encoding="utf-8")

t = (H / "tables.py").read_text(encoding="utf-8")
a = t.index("R2R3_ROWS = [")
e = t.index("WHY_ROWS")
rows = '''R2R3_ROWS = [
    ["Input", "Hand-annotated PySub", "Ordinary Python: snippet, file, folder or GitHub URL; types inferred"],
    ["Unit", "One whole program", "One function at a time inside a project, spliced back behind a decorator"],
    ["Types", "Written by the author", "In-house inference (observe, fixpoint, search); no LLM needed"],
    ["Evidence", "Oracle: 17 positive, 20 negative programs", "Oracle 78 and 88, plus replay of the program's own calls for every converted function"],
    ["Language", "Scalars, lists, PyDict, PySet", "Plus classes, tuples, comprehensions, try/except, f-strings, a standard-library subset"],
    ["Interface", "Command line", "Studio: pipeline stepper, diff with fidelity gutter, function journey, playground, report"],
    ["Delivery", "Clone and run", "Windows installer, portable zip, wheel, Docker image"],
    ["Back ends", "C++17 (WebAssembly promised)", "C++17 only; **WebAssembly dropped**"],
]

'''
t = t[:a] + rows + t[e:]
# shorter known issues
a = t.index("KNOWN_ISSUES = [")
e = t.index("REFS_BOOKS")
ki = '''KNOWN_ISSUES = [
    "**Snippet `coin_change`** is refused (int and float on different paths): 21 of 22 snippets pass, not the 22 of 22 in `STATUS.md` (Section 9.2).",
    "**`docs/grammar.ebnf` is the v0.1 core** (33 named rules; Review 1 reported 41). The language has grown past it; later constructs are described by prose rules generated from the compiler source.",
    "**Stale text:** the D8 note still describes `setjmp`/`longjmp`, and the D7 note calls reclamation \\"the Review 3 target\\".",
    "**Dictionaries use a linear scan** (`runtime/pyrt.cpp:131`), about 29 times slower than CPython on our dictionary kernel.",
    "**Stress harness not re-run;** `STATUS.md` lists three older stress-harness bugs that we did not re-investigate.",
    "**A stale server is the usual cause of impossible-looking errors;** the launcher checks a build fingerprint, but a forgotten WSL server on the same port can still answer first.",
]

'''
t = t[:a] + ki + t[e:]
(H / "tables.py").write_text(t, encoding="utf-8")

for f in ("report_texts.py", "tables.py", "report_tables.py", "rc2b.py"):
    p = H / f
    s = p.read_text(encoding="utf-8")
    s = s.replace("Section 9.4", "Section 9.2").replace("Section 9.3)", "Section 9.2)")
    p.write_text(s, encoding="utf-8")

# trim interp / texts that sec10b no longer uses is harmless; shorten studio text
r = (H / "report_texts.py").read_text(encoding="utf-8")
r = r.replace('''    F["studio_text"] = ("Each project was run through the real application path (the HTTP API that the UI uses) on a clean server with no LLM key, with its trace command "
                        "and the build cache cold unless marked warm. A function is counted *accelerated* only if its replay matched on every call and its measured "
                        "speedup was at least 1.1x. " + " ".join(parts))''', '''    F["studio_text"] = ("Each project ran through the real application path (the HTTP API the UI uses) on a clean server with no LLM key and a cold build cache. "
                        "A function counts as *accelerated* only if every replayed call matched and its measured speedup was at least 1.1x. The row marked \\"before print fix\\" is the "
                        "first TextLab run, whose output hash differed until commit `bd7e8ca`. " + " ".join(parts))''')
(H / "report_texts.py").write_text(r, encoding="utf-8")
print("patched")
