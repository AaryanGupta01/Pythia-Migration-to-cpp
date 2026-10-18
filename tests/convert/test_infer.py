"""In-house Python -> PySub converter: inference and rewrites.
Run: python -m pytest tests/convert  (or python tests/convert/test_infer.py)"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pythia.convert import to_pysub  # noqa: E402
from pythia.convert.infer import infer  # noqa: E402
from pythia.convert.observe import run_plain  # noqa: E402
from pythia.convert.types import render  # noqa: E402
from pythia.studio.pysub_rules import check_source  # noqa: E402


def slots(src):
    eng, _, _ = infer(ast.parse(src))
    return {k: render(t) for k, t in eng.slots.items()}


def conv(src, stdin=""):
    r = to_pysub(src, stdin)
    assert r.behaviour_checked or r.source == src, r.problems
    return r


def test_empty_list_from_appends():
    r = conv("xs = []\nfor i in range(3):\n    xs.append(i * 2)\nprint(xs)\n")
    assert "xs: list[int] = []" in r.source
    assert not r.problems and not check_source(r.source)


def test_call_sites_type_params_and_returns():
    s = slots("def area(w, h):\n    return w * h\n\nprint(area(2, 3.5))\n")
    assert s[("var", "area", "w")] == "int" and s[("var", "area", "h")] == "float"
    assert s[("ret", "area")] == "float"


def test_input_int_float_and_methods():
    s = slots("n = int(input())\nname = input().strip().title()\nparts = name.split()\nx = float(parts[0])\n")
    assert s[("var", "<module>", "n")] == "int" and s[("var", "<module>", "parts")] == "list[str]"
    assert s[("var", "<module>", "x")] == "float"


def test_dict_counter_and_nested_containers():
    src = ("counts = {}\nfor w in 'a b a'.split():\n    counts[w] = counts.get(w, 0) + 1\n"
           "grid = []\nfor r in range(2):\n    grid.append([0] * 3)\nprint(counts, grid)\n")
    r = conv(src)
    assert "counts: dict[str, int] = {}" in r.source and "grid: list[list[int]] = []" in r.source


def test_int_and_float_printed_is_reported_not_guessed():
    src = "xs = [3, 1, 2]\nm = xs[1] if len(xs) % 2 else (xs[0] + xs[1]) / 2\nprint(m)\n"
    r = to_pysub(src)
    assert any("int on some runs and a float" in p for p in r.problems)


def test_int_then_float_accumulator_widens_when_never_printed():
    src = ("def avg(vals):\n    total = 0\n    for v in vals:\n        total += v\n    return total / len(vals)\n\n"
           "print(avg([1.5, 2.0]))\n")
    r = conv(src)
    assert "total: float = 0" in r.source and "vals: list[float]" in r.source and "-> float" in r.source
    assert not r.problems and not check_source(r.source)


def test_record_dicts_become_a_class():
    src = ("people = []\n\ndef add(name, age):\n    people.append({'name': name, 'age': age})\n\n"
           "def show(p):\n    print(p['name'] + ' is ' + str(p['age']))\n\n"
           "def main():\n    add('Ada', 36)\n    add('Linus', 21)\n    for p in people:\n        show(p)\n"
           "    people[0]['age'] += 1\n    print(people[0]['age'])\n\nmain()\n")
    r = conv(src)
    assert "class Person:" in r.source and "    age: int" in r.source
    assert "Person(name, age)" in r.source and "p.name" in r.source and "people[0].age += 1" in r.source
    assert "people: list[Person] = []" in r.source
    assert "def show(p: Person)" in r.source


def test_record_that_is_printed_is_not_rewritten():
    src = "d = {'name': 'x', 'n': 1}\nprint(d)\n"
    r = to_pysub(src)
    assert "class" not in r.source and any("print" in p for p in r.problems)


def test_record_with_unknown_key_is_not_rewritten():
    src = "d = {'name': 'x', 'n': 1}\nk = input()\nprint(d[k])\n"
    r = to_pysub(src, "name\n")
    assert "class" not in r.source


def test_optional_return():
    s = slots("def find(xs, t):\n    for x in xs:\n        if x == t:\n            return x\n    return None\n"
              "print(find(['a'], 'a'))\n")
    assert s[("ret", "find")] == "Optional[str]"


def test_class_fields_and_methods():
    src = ("class Account:\n    def __init__(self, owner, start):\n        self.owner = owner\n"
           "        self.balance = start\n        self.log = []\n\n    def deposit(self, amount):\n"
           "        self.balance += amount\n        self.log.append(amount)\n        return self.balance\n\n"
           "a = Account('Ann', 10)\nprint(a.deposit(5))\nprint(a.log)\n")
    r = conv(src)
    for frag in ("    owner: str\n", "    balance: int\n", "    log: list[int]\n",
                 "def __init__(self, owner: str, start: int) -> None:", "def deposit(self, amount: int) -> int:"):
        assert frag in r.source, frag
    assert not check_source(r.source)


def test_comments_and_strings_untouched():
    src = "# keep me  \nxs = []  # trailing\nxs.append('a # not a comment')\nprint(xs)\n"
    r = conv(src)
    assert r.source == "# keep me  \nxs: list[str] = []  # trailing\nxs.append('a # not a comment')\nprint(xs)\n"


def test_runtime_observation_fills_a_gap():
    src = ("import copy\n\ndef total(grid):\n    s = 0\n    for row in grid:\n        for v in row:\n"
           "            s += v\n    return s\n\ng = copy.deepcopy([[1, 2], [3]])\nprint(total(g))\n")
    r = to_pysub(src)
    assert "def total(grid: list[list[int]]) -> int:" in r.source, r.source


def test_behaviour_identical_on_corpus():
    corpus = ROOT / "scripts" / "corpus"
    for p in sorted(corpus.glob("*.py")):
        sp = p.with_suffix(".stdin")
        stdin = sp.read_text(encoding="utf-8") if sp.exists() else ""
        src = p.read_text(encoding="utf-8")
        r = to_pysub(src, stdin, check=False)
        a, b = run_plain(src, stdin, timeout=30), run_plain(r.source, stdin, timeout=30)
        assert a == b, p.name


def test_compiled_record_program_matches():
    """End to end through the real compiler (needs g++); skipped when no C++ compiler is available."""
    import tempfile
    from pythia.studio.server import playground
    from pythia.toolchain import find_cxx
    if find_cxx()[0] is None:
        return
    src = ("def add(students, name, marks):\n    students.append({'name': name, 'marks': marks})\n\n"
           "def report(students):\n    total = 0\n    best = students[0]\n    for s in students:\n"
           "        total += s['marks']\n        if s['marks'] > best['marks']:\n            best = s\n"
           "    print('average', round(total / len(students), 2))\n    print('best', best['name'], best['marks'])\n\n"
           "def main():\n    students = []\n    n = int(input())\n    for i in range(n):\n        name = input()\n"
           "        add(students, name, float(input()))\n    report(students)\n\nmain()\n")
    stdin = "2\nAda\n91.5\nBob\n77\n"
    r = conv(src, stdin)
    assert not r.problems, r.problems
    run = playground.run_snippet(r.source, Path(tempfile.gettempdir()) / "pythia-pg-cache", stdin, reference=src)
    assert run.get("ok") and run.get("same"), run


def test_converter_answers_in_house_without_llm():
    import tempfile
    from pythia.studio import converter, llm
    from pythia.studio.server import playground
    from pythia.toolchain import find_cxx
    if find_cxx()[0] is None:
        return
    called = []
    orig = llm.make_client
    llm.make_client = lambda *a, **k: called.append(1)       # any LLM use would show up here
    try:
        src = (ROOT / "scripts" / "corpus" / "caesar.py").read_text(encoding="utf-8")
        stdin = (ROOT / "scripts" / "corpus" / "caesar.stdin").read_text(encoding="utf-8")
        cache = Path(tempfile.gettempdir()) / "pythia-pg-cache"
        res = converter.convert(src, {}, playground.compile_snippet, stdin,
                                lambda code, sin, o: playground.run_snippet(code, cache, sin, o))
    finally:
        llm.make_client = orig
    assert res["ok"] and res["provider"] == "pythia" and res["model"] == "in-house", res
    assert res["behaviour_checked"] and not called and len(res["attempts"]) == 1


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as e:
                fails += 1
                print("FAIL", name, e)
    sys.exit(1 if fails else 0)
