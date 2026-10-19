"""Test drivers for entry-less code: LeetCode / GeeksforGeeks / library-style files that only DEFINE things.

Such code (`class Solution: def twoSum(self, nums, target): ...`) prints nothing, so "run both and compare output" says
nothing. We supply what the judge supplies (typing/collections imports, TreeNode, ListNode), generate a deterministic
driver that calls every public function / Solution method on inputs built from the parameter types, and append the SAME
driver to the original and to the converted program. The call sites also give the type inferencer real evidence.

    plan = build(source)            -> Plan | None  (None: the file already has top-level code, or nothing to call)
    plan.program                     original + prelude + driver (what CPython runs and what gets converted)
    plan.clean(converted_program)    the converted program without the driver

Everything here is plain text generation; inputs come from a seeded generator, so runs are reproducible.
"""
from __future__ import annotations

import ast
import random
import re
import typing
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

MARK = "# ---- pythia generated test driver (not part of your program) ----"
PRELUDE_MARK = "# ---- pythia: what the judge provides ----"
CASES = 12
TYPING = set(typing.__all__) - {"Counter", "Text", "NamedTuple", "TypedDict", "Protocol", "overload", "cast"}
MODULES = {"collections", "heapq", "bisect", "math", "itertools", "functools", "string", "sys"}
COLLECTION_NAMES = {"deque", "defaultdict", "Counter", "OrderedDict"}

TREE_DEF = '''class TreeNode:
    def __init__(self, val=0, left=None, right=None):
        self.val = val
        self.left = left
        self.right = right
'''
LIST_DEF = '''class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next
'''
TREE_STR = '''def _tree_str(root):
    if root is None:
        return "#"
    return str(root.val) + "(" + _tree_str(root.left) + "," + _tree_str(root.right) + ")"
'''
LIST_STR = '''def _list_str(head):
    out = []
    n = 0
    while head is not None and n < 1000:
        out.append(head.val)
        head = head.next
        n += 1
    return str(out)
'''


# ------------------------------------------------------------------------------------------------ normalisation
def normalize(source: str) -> str:
    """Make the text something CPython can parse when the only problem is tabs mixed with spaces (LeetCode's editor
    allows it): tabs expand to 8 columns, the reading the author saw."""
    try:
        ast.parse(source)
        return source
    except SyntaxError:
        pass
    alt = "\n".join(l.expandtabs(8) for l in source.replace("\r\n", "\n").split("\n"))
    try:
        ast.parse(alt)
        return alt
    except SyntaxError:
        return source


# ------------------------------------------------------------------------------------------------ analysis
@dataclass
class Entry:
    name: str
    cls: Optional[str]
    node: ast.FunctionDef
    params: List[Tuple[str, Optional[ast.expr]]]
    ret: Optional[ast.expr]
    specs: List[object] = field(default_factory=list)
    note: str = ""


def _names(tree) -> set:
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}


def _defined(tree) -> set:
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Import):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            out |= {a.asname or a.name for a in n.names}
        elif isinstance(n, (ast.Assign, ast.AnnAssign)):
            tg = n.targets if isinstance(n, ast.Assign) else [n.target]
            out |= {t.id for t in tg if isinstance(t, ast.Name)}
    return out


def is_entryless(tree: ast.Module) -> bool:
    for n in tree.body:
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Pass)):
            continue
        if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str):
            continue
        if isinstance(n, (ast.Assign, ast.AnnAssign)) and isinstance(getattr(n, "value", None),
                                                                      (ast.Constant, ast.List, ast.Dict, ast.Tuple)):
            continue
        return False
    return True


def find_entries(tree: ast.Module) -> List[Entry]:
    out: List[Entry] = []

    def params(fn: ast.FunctionDef, skip_self: bool):
        a = fn.args
        pos = a.posonlyargs + a.args
        if skip_self and pos:
            pos = pos[1:]
        n_def = len(a.defaults)
        req = pos[:len(pos) - n_def] if n_def else pos
        if a.vararg or a.kwarg or a.kwonlyargs:
            return None
        return [(p.arg, p.annotation) for p in req]

    def uses_io(fn) -> bool:
        return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("input", "open", "exit")
                   for n in ast.walk(fn))
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and not n.name.startswith("_") and not uses_io(n) \
                and not n.decorator_list and n.name not in ("main",):
            ps = params(n, False)
            if ps is not None:
                out.append(Entry(n.name, None, n, ps, n.returns))
        elif isinstance(n, ast.ClassDef) and n.name == "Solution":
            has_init = any(isinstance(m, ast.FunctionDef) and m.name == "__init__" for m in n.body)
            if has_init:
                continue
            for m in n.body:
                if isinstance(m, ast.FunctionDef) and not m.name.startswith("_") and not m.decorator_list \
                        and not uses_io(m):
                    ps = params(m, True)
                    if ps is not None:
                        out.append(Entry(m.name, "Solution", m, ps, m.returns))
    return out


# ------------------------------------------------------------------------------------------------ type specs
# spec: "int" "float" "str" "bool" "tree" "llist" | ("list", spec) | ("dict", kspec, vspec) | ("opt", spec)
def parse_spec(a: Optional[ast.expr]):
    if a is None:
        return None
    if isinstance(a, ast.Constant) and isinstance(a.value, str):
        try:
            return parse_spec(ast.parse(a.value, mode="eval").body)
        except SyntaxError:
            return None
    if isinstance(a, ast.Name):
        return {"int": "int", "float": "float", "str": "str", "bool": "bool", "TreeNode": "tree", "ListNode": "llist"}.get(a.id)
    if isinstance(a, ast.Constant) and a.value is None:
        return "none"
    if isinstance(a, ast.Subscript):
        base = a.value.id if isinstance(a.value, ast.Name) else (a.value.attr if isinstance(a.value, ast.Attribute) else "")
        sl = a.slice
        elts = sl.elts if isinstance(sl, ast.Tuple) else [sl]
        if base in ("List", "list", "Sequence", "Iterable", "Deque", "deque") and len(elts) == 1:
            s = parse_spec(elts[0])
            return ("list", s) if s else None
        if base in ("Optional",) and len(elts) == 1:
            s = parse_spec(elts[0])
            return ("opt", s) if s else None
        if base in ("Dict", "dict", "Mapping") and len(elts) == 2:
            k, v = parse_spec(elts[0]), parse_spec(elts[1])
            return ("dict", k, v) if k and v else None
    return None


def _hints(fn: ast.FunctionDef, name: str) -> Dict[str, int]:
    from .convert.search import _hints as h
    return h(fn, name)


def guess_specs(entry: Entry, i: int, file_text: str) -> List[object]:
    """Candidate specs for an unannotated parameter, most plausible first."""
    name, _ = entry.params[i]
    h = _hints(entry.node, name)
    out: List[object] = []
    if "TreeNode" in file_text or ".left" in file_text:
        if name in ("root", "p", "q", "node", "tree", "t", "root1", "root2", "subRoot"):
            out.append("tree")
    if ".next" in file_text and name in ("head", "l1", "l2", "list1", "list2", "node", "headA", "headB", "ll"):
        out.append("llist")
    L = lambda s: ("list", s)  # noqa: E731
    if h.get("nested", 0):
        out += [L(L("int")), L(L("str"))]
    if h.get("str", 0) and not h.get("list", 0):
        out += ["str", L("str")]
    if h.get("list", 0) or h.get("seq", 0):
        out += [L("int"), "str", L(L("int")), L("str")]
    if name in ("n", "k", "m", "x", "target", "num", "size", "i", "j", "amount", "sum", "val", "idx", "capacity", "W"):
        out.append("int")
    out += ["int", L("int"), "str", "float", L(L("int")), "bool"]
    seen, res = set(), []
    for s in out:
        if s not in seen:
            seen.add(s)
            res.append(s)
    return res


# ------------------------------------------------------------------------------------------------ value generation
_INTS = [0, 1, 2, 3, -1, 5, 7, 10, 4, 6, -3, 9]
_STRS = ["", "a", "ab", "abc", "aab", "abca", "bcd", "aaaa", "abba", "xyz", "ba", "racecar"]
_FLOATS = [0.0, 1.5, -2.25, 3.0, 0.5, 10.0]
_LISTS = [[], [1], [2, 1], [3, 1, 2], [1, 2, 3, 4], [5, 5, 5], [0, -1, 2, -3, 4], [9, 7, 5, 3, 1], [1, 1, 2, 2, 3],
          [4, 2, 7, 1, 8, 3], [2, 2], [10, 0, 5]]


def _tree_lit(rng, depth=0, p=0.8) -> str:
    if depth > 3 or (depth > 0 and rng.random() > p):
        return "None"
    v = rng.randint(-3, 9)
    l = _tree_lit(rng, depth + 1, p - 0.2)
    r = _tree_lit(rng, depth + 1, p - 0.2)
    if l == "None" and r == "None":
        return f"TreeNode({v})"
    return f"TreeNode({v}, {l}, {r})"


def _llist_lit(rng) -> str:
    vals = [rng.randint(-2, 9) for _ in range(rng.randint(0, 5))]
    s = "None"
    for v in reversed(vals):
        s = f"ListNode({v}, {s})" if s != "None" else f"ListNode({v})"
    return s


def gen(spec, rng: random.Random, i: int, ctx: List[str]) -> str:
    """A Python literal (or constructor expression) for `spec`; case index i walks the edge-case pools first."""
    if spec == "int":
        return repr(_INTS[i % len(_INTS)] if i < 12 else rng.randint(-5, 20))
    if spec == "float":
        return repr(_FLOATS[i % len(_FLOATS)] if i < 6 else round(rng.uniform(-5, 20), 2))
    if spec == "bool":
        return repr(bool((i + rng.randint(0, 1)) % 2))
    if spec == "str":
        return repr(_STRS[i % len(_STRS)] if i < 12 else "".join(rng.choice("abc") for _ in range(rng.randint(0, 8))))
    if spec == "tree":
        return "None" if i == 0 else _tree_lit(rng)
    if spec == "llist":
        return "None" if i == 0 else _llist_lit(rng)
    if spec == "none":
        return "None"
    if isinstance(spec, tuple):
        if spec[0] == "opt":
            return "None" if i % 5 == 4 else gen(spec[1], rng, i, ctx)
        if spec[0] == "list":
            inner = spec[1]
            if inner == "int":
                return repr(_LISTS[i % len(_LISTS)] if i < 12 else [rng.randint(-3, 9) for _ in range(rng.randint(0, 8))])
            if inner == "float":
                return repr([float(x) for x in _LISTS[i % len(_LISTS)]])
            if inner == "str":
                return repr([_STRS[(i + k) % len(_STRS)] for k in range(i % 4)])
            if inner == "bool":
                return repr([bool((i + k) % 2) for k in range(i % 5)])
            if isinstance(inner, tuple) and inner[0] == "list":
                r, c = 1 + (i % 4), 1 + ((i // 2) % 4)
                cell = lambda: gen(inner[1], rng, rng.randint(0, 11), ctx)  # noqa: E731
                if inner[1] == "int":
                    return "[" + ", ".join("[" + ", ".join(str(rng.randint(0, 9)) for _ in range(c)) + "]" for _ in range(r)) + "]"
                return "[" + ", ".join("[" + ", ".join(cell() for _ in range(c)) + "]" for _ in range(r)) + "]"
            if inner in ("tree", "llist"):
                return "[" + ", ".join(gen(inner, rng, 1 + k, ctx) for k in range(i % 3)) + "]"
            return "[]"
        if spec[0] == "dict":
            n = i % 4
            return "{" + ", ".join(f"{gen(spec[1], rng, i + k, ctx)}: {gen(spec[2], rng, i + k + 1, ctx)}" for k in range(n)) + "}"
    return "None"


def ann_of(spec) -> str:
    """The annotation text for a spec, for inputs that are literally None (a bare `x = None` has no type)."""
    if spec in ("int", "float", "str", "bool"):
        return spec
    if spec == "tree":
        return "TreeNode | None"
    if spec == "llist":
        return "ListNode | None"
    if isinstance(spec, tuple):
        if spec[0] == "list":
            return f"list[{ann_of(spec[1])}]"
        if spec[0] == "dict":
            return f"dict[{ann_of(spec[1])}, {ann_of(spec[2])}]"
        if spec[0] == "opt":
            return f"{ann_of(spec[1])} | None"
    return "int | None"


def _is_mutable(spec) -> bool:
    return isinstance(spec, tuple) and spec[0] in ("list", "dict")


def _ret_printer(entry: Entry) -> str:
    r = entry.ret
    txt = ast.unparse(r) if r is not None else ""
    if "TreeNode" in txt:
        return "_tree_str"
    if "ListNode" in txt:
        return "_list_str"
    return ""


# ------------------------------------------------------------------------------------------------ the plan
@dataclass
class Plan:
    original: str                      # normalised text, as the author wrote it
    prelude: str
    driver: str
    entries: List[Entry]
    n_calls: int
    skipped: Dict[str, str] = field(default_factory=dict)

    @property
    def program(self) -> str:
        return self.prelude + self.original.rstrip("\n") + "\n\n\n" + self.driver

    def clean(self, converted: str) -> str:
        """The converted program without the generated driver (the judge prelude stays: the code needs it)."""
        i = converted.find(MARK)
        return (converted[:i] if i >= 0 else converted).rstrip("\n") + "\n"


def _prelude(tree, text: str, need_tree_str: bool, need_list_str: bool) -> str:
    defined = _defined(tree)
    used = _names(tree)
    lines: List[str] = []
    typing_needed = sorted(n for n in used if n in TYPING and n not in defined and n not in COLLECTION_NAMES)
    if typing_needed:
        lines.append("from typing import " + ", ".join(typing_needed))
    for m in sorted(MODULES & used - defined):
        lines.append("import " + m)
    coll = sorted(n for n in COLLECTION_NAMES if n in used and n not in defined)
    if coll:
        lines.append("from collections import " + ", ".join(coll))
    extra = ""
    if ("TreeNode" in used or need_tree_str) and "TreeNode" not in defined:
        extra += TREE_DEF + "\n\n"
    if ("ListNode" in used or need_list_str) and "ListNode" not in defined:
        extra += LIST_DEF + "\n\n"
    if need_tree_str:
        extra += TREE_STR + "\n\n"
    if need_list_str:
        extra += LIST_STR + "\n\n"
    if not lines and not extra:
        return ""
    return PRELUDE_MARK + "\n" + "\n".join(lines) + ("\n\n" if lines else "") + extra


def _driver_for(entries: List[Entry], seed_key: str) -> Tuple[str, int]:
    out = [MARK]
    out.append("# one block per function: inputs are fixed literals, results are printed, exceptions are printed by class")
    n = 0
    for k, e in enumerate(entries):
        rng = random.Random(zlib.crc32((seed_key + e.name).encode()))
        out.append(f'print("@@ {e.name}")')
        printer = _ret_printer(e)
        for i in range(CASES):
            tag = f"_{k}_{i}"
            ctx: List[str] = []
            lines, args = [], []
            for j, ((pname, _a), spec) in enumerate(zip(e.params, e.specs)):
                if pname in ("n", "N", "size", "length", "m") and j > 0 and e.specs[j - 1] is not None and \
                        (isinstance(e.specs[j - 1], tuple) or e.specs[j - 1] == "str") and rng.random() < 0.8:
                    lit = f"len(_a{tag}_{j - 1})"
                else:
                    lit = gen(spec, rng, i, ctx)
                if lit == "None":
                    lines.append(f"_a{tag}_{j}: {ann_of(spec)} = None")
                else:
                    lines.append(f"_a{tag}_{j} = {lit}")
                args.append(f"_a{tag}_{j}")
            call = f"_s{tag}.{e.name}({', '.join(args)})" if e.cls else f"{e.name}({', '.join(args)})"
            body = list(lines)
            if e.cls:
                body.insert(0, f"_s{tag} = {e.cls}()")
            body.append(f"print({printer}({call}))" if printer else f"print({call})")
            for j, spec in enumerate(e.specs):
                if _is_mutable(spec):
                    body.append(f"print(_a{tag}_{j})")
            out.append("try:")
            out += ["    " + b for b in body]
            out.append("except Exception as _e:")
            out.append('    print("EXC", type(_e).__name__)')
            n += 1
    return "\n".join(out) + "\n", n


_BAD_EXC = ("TypeError", "AttributeError", "NameError", "UnboundLocalError")


def build(source: str, run_python=None) -> Optional[Plan]:
    """A driver plan for entry-less code, or None. `run_python(src, stdin) -> {stdout, exception}` (the Playground's
    CPython runner) lets us VALIDATE guessed parameter types: a guess that makes CPython itself raise TypeError on
    most calls is wrong, so the next candidate is tried."""
    text = normalize(source)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    if not is_entryless(tree):
        return None
    entries = find_entries(tree)
    if not entries:
        return None
    # specs: annotations where given, else candidates validated against CPython
    cands: Dict[Tuple[int, int], List[object]] = {}
    for k, e in enumerate(entries):
        e.specs = []
        for i, (pname, ann) in enumerate(e.params):
            s = parse_spec(ann)
            e.specs.append(s)
            if s is None:
                cands[(k, i)] = guess_specs(e, i, text)
    skipped: Dict[str, str] = {}
    keep: List[Entry] = []
    for k, e in enumerate(entries):
        for i in range(len(e.params)):
            if e.specs[i] is None:
                e.specs[i] = cands[(k, i)][0]
        keep.append(e)

    def prelude_for(es: List[Entry]) -> str:
        pr = [_ret_printer(e) for e in es]
        return _prelude(tree, text, "_tree_str" in pr, "_list_str" in pr)

    if run_python is not None:                                  # coordinate descent over unannotated parameters
        for k, e in enumerate(keep):
            idxs = [i for i in range(len(e.params)) if (entries.index(e), i) in cands]
            if not idxs:
                continue
            seed = text[:40]

            def score(specs):
                saved = e.specs
                e.specs = specs
                drv, n = _driver_for([e], seed)
                e.specs = saved
                r = run_python(prelude_for([e]) + text.rstrip("\n") + "\n\n\n" + drv, "")
                bad = sum(1 for l in (r.get("stdout") or "").splitlines() if l.startswith("EXC ") and l.split()[1] in _BAD_EXC)
                dead = r.get("exception") in ("SyntaxError", "IndentationError", "TabError")
                return (n - bad) - (1000 if dead else 0)
            best = list(e.specs)
            for i in idxs:
                cl = cands[(entries.index(e), i)]
                top, top_s = best[i], score(best)
                for c in cl[1:6]:
                    trial = list(best)
                    trial[i] = c
                    s = score(trial)
                    if s > top_s:
                        top, top_s = c, s
                best[i] = top
            e.specs = best
    drv, n = _driver_for(keep, text[:40])
    return Plan(original=text, prelude=prelude_for(keep), driver=drv, entries=keep, n_calls=n, skipped=skipped)
