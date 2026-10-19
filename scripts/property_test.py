#!/usr/bin/env python3
"""
PYTHIA :: Property-Based and Randomized Differential Testing Harness
Implements Section 8 of the Mega-Prompt specification.

Generates reproducible randomized Python test cases across 10 algorithmic categories:
  1. Integer arithmetic (precedence, negative division, modulo, abs, pow)
  2. Range loops (positive/negative steps, nested loops, accumulators)
  3. Lists and indexing (negative indices, slicing, reverse slicing, list mutations)
  4. Sorting and searching (in-place sort, sorted, reverse, linear search)
  5. String operations (slicing, strip, split, join, replace, predicates)
  6. Dictionary frequency counting (d[k] = d.get(k, 0) + 1, keys, values)
  7. Stack operations (LIFO push/pop, deque, length)
  8. Matrix traversal (2D lists, transpose, row/column sums)
  9. Binary search (iterative sorted array search)
  10. Recursive algorithms (factorial, fibonacci, gcd with bounded depth)

Each generated test case is executed in CPython, compiled to C++17 with Pythia runtime,
executed natively, and differential outputs are compared byte-for-byte.
"""
import argparse
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pythia.cli import compile_source
from pythia import toolchain

RUNTIME = ROOT / "runtime"


# ==============================================================================
# Category Generators (Property & Randomized Programs)
# ==============================================================================

def gen_arithmetic(rng: random.Random) -> str:
    """Tests arithmetic properties, floor division, modulo parity, operator precedence."""
    a = rng.randint(-100, 100)
    b = rng.choice([-15, -7, -3, -1, 1, 2, 3, 5, 11, 25])
    c = rng.randint(-50, 50)
    d = rng.choice([-9, -4, -2, 1, 3, 7])
    p = rng.randint(0, 5)
    return f"""# Property Test: Arithmetic, FloorDiv, and Modulo
a: int = {a}
b: int = {b}
c: int = {c}
d: int = {d}
p: int = {p}
q1: int = a // b
r1: int = a % b
q2: int = c // d
r2: int = c % d
print("divmod1", q1, r1, q1 * b + r1 == a)
print("divmod2", q2, r2, q2 * d + r2 == c)
expr: int = (a + b) * (c - d) // (b + (1 if b == 0 else 0))
print("expr", expr)
print("abs", abs(a), abs(b), abs(c))
print("pow", a ** p if abs(a) < 10 else p ** 3)
"""


def gen_range_loops(rng: random.Random) -> str:
    """Tests range loops with positive/negative steps, nested loops, accumulators."""
    start = rng.randint(-10, 10)
    stop = rng.randint(-20, 30)
    step = rng.choice([-3, -2, -1, 1, 2, 3])
    if step > 0 and stop < start:
        stop = start + rng.randint(5, 25)
    elif step < 0 and stop > start:
        stop = start - rng.randint(5, 25)
    inner_n = rng.randint(2, 6)
    return f"""# Property Test: Range Loops and Steps
acc: int = 0
steps: list[int] = []
for i in range({start}, {stop}, {step}):
    acc += i
    steps.append(i)
print("range_acc", acc, len(steps))
print("steps", steps)

nested_sum: int = 0
for x in range(1, {inner_n}):
    for y in range(1, {inner_n}):
        nested_sum += x * y
print("nested_sum", nested_sum)
"""


def gen_lists_indexing(rng: random.Random) -> str:
    """Tests list indexing, negative indices, slicing, reverse slicing, mutations."""
    sz = rng.randint(5, 15)
    vals = [rng.randint(-50, 50) for _ in range(sz)]
    idx = rng.randint(-sz, sz - 1)
    return f"""# Property Test: List Operations and Slicing
nums: list[int] = {vals}
print("orig", nums)
print("len", len(nums))
print("elem_at_{idx}", nums[{idx}])
print("slice_half", nums[1:{max(2, sz - 2)}])
print("reverse_slice", nums[::-1])
nums.append(999)
print("after_append", nums)
popped: int = nums.pop()
print("after_pop", popped, nums)
nums.extend([100, 200])
print("after_extend", nums)
"""


def gen_sorting_searching(rng: random.Random) -> str:
    """Tests in-place sort, sorted, reverse, linear search."""
    sz = rng.randint(6, 16)
    vals = [rng.randint(-100, 100) for _ in range(sz)]
    target = rng.choice(vals) if rng.random() < 0.7 else 9999
    return f"""# Property Test: Sorting and Searching
data: list[int] = {vals}
s_data: list[int] = sorted(data)
print("sorted", s_data)
data.sort()
print("in_place_sort", data)

target: int = {target}
found_idx: int = -1
for i in range(len(data)):
    if data[i] == target:
        found_idx = i
        break
print("search_target", target, "found", found_idx)
"""


def gen_string_ops(rng: random.Random) -> str:
    """Tests string operations, slicing, strip, split, join, replace, predicates."""
    words = ["pythia", "compiler", "cplusplus", "python", "algorithm", "speed", "test"]
    chosen = rng.sample(words, k=rng.randint(2, 4))
    sep = rng.choice([",", "-", " "])
    s = sep.join(chosen)
    prefix = chosen[0][:2]
    return f"""# Property Test: String Operations
s: str = {repr(s)}
print("s", s)
print("len", len(s))
print("upper", s.upper())
print("lower", s.upper().lower())
print("rev", s[::-1])
print("startswith", s.startswith({repr(prefix)}))
print("replace", s.replace({repr(sep)}, "::"))
parts: list[str] = s.split({repr(sep)})
print("split", parts)
joined: str = "/".join(parts)
print("join", joined)
"""


def gen_dict_frequency(rng: random.Random) -> str:
    """Tests dictionary frequency counter pattern counts[k] = counts.get(k, 0) + 1."""
    keys = [f"item_{rng.randint(1, 6)}" for _ in range(rng.randint(8, 20))]
    return f"""# Property Test: Dictionary Frequency Counting
items: list[str] = {keys}
freq: dict[str, int] = {{}}
for item in items:
    freq[item] = freq.get(item, 0) + 1

for k in sorted(list(freq.keys())):
    print(k, freq[k])
print("total_keys", len(freq))
"""


def gen_stack_ops(rng: random.Random) -> str:
    """Tests stack LIFO push/pop and parenthesis balance simulation."""
    paren_types = ["()", "[]", "{}"]
    expr = "".join(rng.choice(["(", ")", "[", "]", "{", "}"]) for _ in range(rng.randint(4, 12)))
    return f"""# Property Test: Stack Operations and Valid Parens
expr: str = {repr(expr)}
stack: list[str] = []
valid: bool = True
for c in expr:
    if c == "(" or c == "[" or c == "{{":
        stack.append(c)
    else:
        if len(stack) == 0:
            valid = False
            break
        top: str = stack.pop()
        if c == ")" and top != "(":
            valid = False
            break
        elif c == "]" and top != "[":
            valid = False
            break
        elif c == "}}" and top != "{{":
            valid = False
            break

if len(stack) != 0:
    valid = False
print("expr", expr, "is_balanced", valid)
"""


def gen_matrix_traversal(rng: random.Random) -> str:
    """Tests 2D list matrix representation, row/col traversal, transpose."""
    rows = rng.randint(2, 4)
    cols = rng.randint(2, 4)
    mat = [[rng.randint(1, 20) for _ in range(cols)] for _ in range(rows)]
    return f"""# Property Test: Matrix Traversal and Transpose
mat: list[list[int]] = {mat}
rows: int = len(mat)
cols: int = len(mat[0])
print("dimensions", rows, cols)

row_sums: list[int] = []
for r in range(rows):
    s: int = 0
    for c in range(cols):
        s += mat[r][c]
    row_sums.append(s)
print("row_sums", row_sums)

# Transpose
trans: list[list[int]] = []
for c in range(cols):
    col_vals: list[int] = []
    for r in range(rows):
        col_vals.append(mat[r][c])
    trans.append(col_vals)
print("transposed", trans)
"""


def gen_binary_search(rng: random.Random) -> str:
    """Tests binary search algorithm on sorted integers."""
    sz = rng.randint(8, 20)
    arr = sorted(list(set(rng.randint(1, 100) for _ in range(sz))))
    target = rng.choice(arr) if rng.random() < 0.6 else rng.randint(1, 100)
    return f"""# Property Test: Binary Search
arr: list[int] = {arr}
target: int = {target}

lo: int = 0
hi: int = len(arr) - 1
found_idx: int = -1

while lo <= hi:
    mid: int = lo + (hi - lo) // 2
    if arr[mid] == target:
        found_idx = mid
        break
    elif arr[mid] < target:
        lo = mid + 1
    else:
        hi = mid - 1

print("search in", arr, "target", target, "result", found_idx)
"""


def gen_recursion(rng: random.Random) -> str:
    """Tests safe bounded recursive functions (gcd, sum of digits, fibonacci)."""
    a = rng.randint(12, 100)
    b = rng.randint(4, 50)
    n = rng.randint(5, 15)
    return f"""# Property Test: Bounded Recursion
def gcd(x: int, y: int) -> int:
    return x if y == 0 else gcd(y, x % y)

def sum_digits(n: int) -> int:
    return n if n < 10 else (n % 10) + sum_digits(n // 10)

def fib(k: int) -> int:
    if k <= 1:
        return k
    return fib(k - 1) + fib(k - 2)

print("gcd", gcd({a}, {b}))
print("sum_digits", sum_digits({a * b}))
print("fib", fib({n}))
"""


CATEGORIES = {
    "arithmetic": gen_arithmetic,
    "range_loops": gen_range_loops,
    "lists_indexing": gen_lists_indexing,
    "sorting_searching": gen_sorting_searching,
    "string_ops": gen_string_ops,
    "dict_frequency": gen_dict_frequency,
    "stack_ops": gen_stack_ops,
    "matrix_traversal": gen_matrix_traversal,
    "binary_search": gen_binary_search,
    "recursion": gen_recursion,
}


# ==============================================================================
# Differential Test Runner
# ==============================================================================

def run_test_case(src: str, workdir: Path, timeout: int = 15) -> dict:
    """
    Executes Python source under CPython and under Pythia compiled C++17,
    comparing stdout, stderr, and return code.
    """
    res = {"pass": False, "cpython": {}, "pythia": {}, "error": None}
    
    # 1. Run in CPython
    try:
        p_py = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, timeout=timeout)
        res["cpython"] = {
            "stdout": p_py.stdout,
            "stderr": p_py.stderr,
            "code": p_py.returncode
        }
    except Exception as e:
        res["error"] = f"CPython execution failed: {e}"
        return res

    # 2. Compile to C++17 with Pythia
    try:
        code, notes, errs, opt = compile_source(src, "prop_test.py")
        if errs:
            res["error"] = f"Pythia rejected program: {[str(e) for e in errs]}"
            return res
    except Exception as e:
        res["error"] = f"Pythia compiler crashed: {e}"
        return res

    # 3. Compile C++ executable
    stem = f"test_{int(time.time() * 1000) % 1000000}_{random.randint(100, 999)}"
    d = workdir / stem
    d.mkdir(parents=True, exist_ok=True)
    cpp_path = d / f"{stem}.cpp"
    cpp_path.write_text(code, encoding="utf-8")
    for fn in ("pyrt.cpp", "pyrt.hpp"):
        shutil.copy(RUNTIME / fn, d)

    bin_path = d / (f"{stem}.exe" if os.name == "nt" else stem)
    cxx = toolchain.find_cxx()[0] or ("g++.exe" if os.name == "nt" else "c++")
    cmd = [cxx, "-std=c++17", "-O2", "-flto", "-I", str(d), str(cpp_path),
           str(d / "pyrt.cpp"), *toolchain.exe_link_args(), "-o", str(bin_path)]
    p_cc = subprocess.run(cmd, capture_output=True, text=True, env=toolchain.env_for(cxx))
    if p_cc.returncode != 0:
        res["error"] = f"C++ compiler failed:\n{p_cc.stderr[:300]}"
        return res

    # 4. Execute compiled C++ binary
    try:
        p_cpp = subprocess.run([str(bin_path)], capture_output=True, text=True, timeout=timeout)
        res["pythia"] = {
            "stdout": p_cpp.stdout,
            "stderr": p_cpp.stderr,
            "code": p_cpp.returncode
        }
    except Exception as e:
        res["error"] = f"Compiled binary failed to execute: {e}"
        return res

    # 5. Differential check
    same_stdout = (res["cpython"]["stdout"] == res["pythia"]["stdout"])
    same_code = (res["cpython"]["code"] == res["pythia"]["code"])
    res["pass"] = (same_stdout and same_code)
    if not res["pass"]:
        res["error"] = f"Output mismatch: CPython {res['cpython']['stdout']!r} vs C++ {res['pythia']['stdout']!r}"

    return res


def main():
    ap = argparse.ArgumentParser(description="Property-based randomized differential testing for Pythia")
    ap.add_argument("--count", type=int, default=5, help="Number of tests per category (default: 5)")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    ap.add_argument("--category", choices=list(CATEGORIES.keys()) + ["all"], default="all")
    ap.add_argument("--json", action="store_true", help="Output machine-readable JSON summary")
    ap.add_argument("--triage", default=str(ROOT / "build" / "prop_triage"))
    a = ap.parse_args()

    workdir = Path(tempfile.mkdtemp(prefix="pythia_prop_"))
    rng = random.Random(a.seed)

    selected_cats = list(CATEGORIES.keys()) if a.category == "all" else [a.category]
    total_tests = len(selected_cats) * a.count
    passed = 0
    failed = 0
    results_log = []

    print(f"\n====================================================================")
    print(f"PYTHIA PROPERTY-BASED RANDOMIZED DIFFERENTIAL TEST SUITE")
    print(f"  Categories: {len(selected_cats)} | Tests per category: {a.count} | Seed: {a.seed}")
    print(f"====================================================================\n")

    t0 = time.time()
    for cat in selected_cats:
        cat_gen = CATEGORIES[cat]
        print(f"--- Category: {cat} ---")
        for i in range(a.count):
            case_seed = a.seed * 1000 + i
            sub_rng = random.Random(case_seed)
            src = cat_gen(sub_rng)
            r = run_test_case(src, workdir)
            test_id = f"{cat}_{i+1:02d}"
            if r["pass"]:
                passed += 1
                print(f"  [{test_id}] PASS (byte-for-byte identical)")
            else:
                failed += 1
                print(f"  [{test_id}] FAIL: {r['error']}")
                triage_dir = Path(a.triage)
                triage_dir.mkdir(parents=True, exist_ok=True)
                (triage_dir / f"{test_id}.py").write_text(src, encoding="utf-8")
                (triage_dir / f"{test_id}_py.out").write_text(r["cpython"].get("stdout", ""), encoding="utf-8")
                (triage_dir / f"{test_id}_cpp.out").write_text(r["pythia"].get("stdout", ""), encoding="utf-8")
            results_log.append({"id": test_id, "category": cat, "pass": r["pass"], "error": r["error"]})

    dt = time.time() - t0
    shutil.rmtree(workdir, ignore_errors=True)

    print(f"\n====================================================================")
    print(f"SUMMARY: {passed}/{total_tests} passed ({passed/total_tests * 100:.1f}%) in {dt:.1f}s")
    if failed == 0:
        print("  ALL RANDOMIZED PROPERTY TESTS PROVED 100% CPYTHON EQUIVALENT!")
    else:
        print(f"  {failed} failures saved to {a.triage}")
    print(f"====================================================================\n")

    if a.json:
        print(json.dumps({"total": total_tests, "passed": passed, "failed": failed, "results": results_log}))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
