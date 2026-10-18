"""PYTHIA's in-house, deterministic Python -> PySub converter (no LLM).

    to_pysub(source, stdin="") -> ConvertResult(source, changes, problems)

It only adds what the compiler can't work out by itself: type annotations (parameters, returns, empty containers,
variables whose first value has a narrower type, class fields) and one structural rewrite, dicts used as records ->
small classes. Everything else (comprehensions, lambdas, tuples, f-strings, ...) is left exactly as written; the
compiler supports those natively. Edits are made on the original text, so comments and strings never change.
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from . import observe as _observe
from .infer import MODULE, Engine, infer, is_rec, parents, sinks
from .types import complete, contains, is_bad, render, show

OPTIONAL = "Optional[{}]"


@dataclass
class ConvertResult:
    source: str
    changes: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    behaviour_checked: bool = False

    @property
    def ok(self) -> bool:
        return not self.problems


class _Src:
    def __init__(self, text: str):
        self.text = text
        self.lines = text.splitlines(keepends=True)
        self.starts = [0]
        for ln in self.lines:
            self.starts.append(self.starts[-1] + len(ln))

    def off(self, lineno: int, col: int) -> int:
        """(1-based line, UTF-8 byte column) -> character offset."""
        if lineno > len(self.lines):
            return len(self.text)
        line = self.lines[lineno - 1]
        return self.starts[lineno - 1] + len(line.encode("utf-8")[:col].decode("utf-8", "replace"))

    def start(self, n) -> int:
        return self.off(n.lineno, n.col_offset)

    def end(self, n) -> int:
        return self.off(n.end_lineno, n.end_col_offset)

    def line_start(self, lineno: int) -> int:
        return self.starts[min(lineno - 1, len(self.lines))]

    def indent_of(self, lineno: int) -> str:
        ln = self.lines[lineno - 1]
        return ln[:len(ln) - len(ln.lstrip(" \t"))]


def _camel(name: str) -> str:
    name = name.strip("_")
    irregular = {"people": "person", "children": "child", "men": "man", "women": "woman", "data": "item"}
    name = irregular.get(name.lower(), name)
    if name.endswith("ies") and len(name) > 4:
        name = name[:-3] + "y"
    elif name.endswith("s") and not name.endswith("ss") and len(name) > 3:
        name = name[:-1]
    return "".join(p[:1].upper() + p[1:] for p in name.split("_") if p)


def _bindings(stmts_owner, own_nodes):
    """name -> [(pos, kind, node)] for every binding site among own_nodes."""
    out: Dict[str, list] = {}

    def add(name, node, kind, site):
        out.setdefault(name, []).append(((site.lineno, site.col_offset), kind, node))

    for n in own_nodes:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                simple = len(n.targets) == 1 and isinstance(t, ast.Name)
                for x in ast.walk(t):
                    if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store):
                        add(x.id, n, "assign" if simple else "other", x)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            add(n.target.id, n, "ann", n.target)
        elif isinstance(n, (ast.AugAssign,)) and isinstance(n.target, ast.Name):
            add(n.target.id, n, "other", n.target)
        elif isinstance(n, (ast.For, ast.AsyncFor, ast.withitem, ast.NamedExpr)):
            tgt = n.target if not isinstance(n, ast.withitem) else n.optional_vars
            if tgt is not None:
                for x in ast.walk(tgt):
                    if isinstance(x, ast.Name):
                        add(x.id, n, "other", x)
    for v in out.values():
        v.sort(key=lambda e: e[0])
    return out


def _module_own(tree):
    stack = list(tree.body)
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                                  ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                stack.append(c)


def _func_own(fn):
    stack = list(fn.body)
    while stack:
        n = stack.pop()
        yield n
        for c in ast.iter_child_nodes(n):
            if not isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda,
                                  ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                stack.append(c)


def _close_paren(src: _Src, fn) -> Optional[int]:
    """Offset just after the ')' that closes a def's parameter list (None if it already has '->')."""
    start = src.start(fn)
    text = src.text[start:]
    depth, seen_open, close = 0, False, None
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.OP:
                continue
            if tok.string == "(":
                depth += 1
                seen_open = True
            elif tok.string == ")":
                depth -= 1
                if depth == 0 and seen_open and close is None:
                    close = tok.end
            elif tok.string == "->" and close is not None:
                return None
            elif tok.string == ":" and close is not None and depth == 0:
                break
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return None
    if close is None:
        return None
    line, col = close
    # tokenize columns here are character columns of the substring, which starts at fn's column on its first line
    if line == 1:
        return start + col
    return src.line_start(fn.lineno + line - 1) + col


def to_pysub(source: str, stdin: str = "", run: bool = True, check: bool = True) -> ConvertResult:
    """Convert untyped Python to PySub by adding types (and turning record dicts into classes).
    run=True: if static inference leaves gaps, execute the original once on `stdin` and use the types observed at
    run time to fill them. check=True: run original and conversion under CPython and require identical output."""
    stripped = strip_doctest(source)
    doctest_removed = stripped != source
    source = stripped
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return ConvertResult(source, [], [f"line {e.lineno}: not valid Python: {e.msg}"])
    base = Engine(tree).run()
    holes = any(not complete(t) and not is_bad(t) for k, t in base.slots.items()) or any(
        ("var", f.qual, p.arg) not in base.slots for f in base.funcs.values() for p in f.params)
    obs = _observe.observe(source, stdin) if run and holes else None
    seeds = None
    if obs and obs["types"]:
        seeds = {k: t for k, t in obs["types"].items()
                 if not complete(base.slots.get(k)) and not is_bad(base.slots.get(k)) and complete(t)}
    def build_with(sd):
        eng_, records_, rejected_ = infer(tree, seeds=sd)
        plan_ = _Plan(source, tree, eng_, records_)
        for rid, why in rejected_.items():
            plan_.problems.append(f"the dicts with keys {', '.join(rid)} look like records but can't become a class: "
                                  f"{why}")
        plan_.build()
        return eng_, plan_

    eng, plan = build_with(seeds)
    out = plan.apply()
    guessed = _guess_uncalled(tree, eng, seeds, build_with, plan, out)
    if guessed is not None:
        plan, out, note = guessed
        plan.changes.append(note)
    res = ConvertResult(out, plan.changes, plan.problems)
    try:
        ast.parse(out)
    except SyntaxError as e:                     # never hand back broken Python
        return ConvertResult(source, [], [f"internal: the converted program did not parse ({e.msg}, line {e.lineno})"])
    if check and out != source:
        orig = obs if obs and not obs["timed_out"] and obs["stdout"] is not None else _observe.run_plain(source, stdin)
        mine = _observe.run_plain(out, stdin) if orig is not None else None
        if mine is not None:
            same = mine["stdout"] == orig["stdout"] and mine["exception"] == orig["exception"]
            res.behaviour_checked = same
            if not same:
                res.problems.append("internal: the converted program prints something different under CPython; "
                                    "please report this program")
    if doctest_removed:
        res.changes.append("removed doctest.testmod() (it prints nothing when the examples pass)")
    return res


def strip_doctest(source: str) -> str:
    """`import doctest` and `doctest.testmod()` / `run_docstring_examples(...)` calls: they print nothing when the
    examples pass, and PySub has no doctest. Statements become `pass` (an `if __name__` body must not go empty)."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source
    lines = source.split("\n")
    cuts = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and all(a.name == "doctest" for a in n.names):
            cuts.append(n)
        elif isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Attribute) \
                and isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == "doctest" \
                and not n.value.args and all(k.arg not in ("verbose", "optionflags") for k in n.value.keywords):
            cuts.append(n)                         # testmod(verbose=True) prints a transcript: left alone
    uses = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == "doctest")
    cut_uses = sum(1 for c in cuts if isinstance(c, ast.Expr))
    if uses > cut_uses:                            # something else still needs the module (verbose=True, ...)
        cuts = []
    for n in sorted(cuts, key=lambda n: -n.lineno):
        indent = lines[n.lineno - 1][:len(lines[n.lineno - 1]) - len(lines[n.lineno - 1].lstrip())]
        lines[n.lineno - 1:n.end_lineno] = [indent + "pass"]
    return "\n".join(lines)


def _error_count(src: str) -> int:
    try:
        from ..cli import compile_source
        return len(compile_source(src, "convert.py")[2])
    except Exception:
        return 10 ** 6


def _compiles(src: str) -> bool:
    return _error_count(src) == 0


def _guess_uncalled(tree, eng, seeds, build_with, plan, out):
    """Parameters that no call site types (a `class Solution` of LeetCode methods, a library function nobody calls
    here): pick types by trying candidates, best hint first, and keeping the first that makes the whole program
    type-check. Returns (plan, out, note) or None when nothing is unresolved / nothing fits."""
    if not any("couldn't work out the type of parameter" in p and "never called" in p for p in plan.problems):
        return None
    if _compiles(out):
        return None
    from . import search
    unresolved = []
    for f in eng.funcs.values():
        pos = f.node.args.posonlyargs + f.node.args.args
        skip = 1 if f.kind in ("method", "classmethod") and pos else 0
        for p in (pos + f.node.args.kwonlyargs)[skip:]:
            if p.annotation is None and not complete(eng.slots.get(("var", f.qual, p.arg))):
                unresolved.append((f.qual, f.node, p.arg))
    if not unresolved or len(unresolved) > 6:
        return None
    cache = {}

    def build(sd):
        merged = dict(seeds or {})
        merged.update(sd)
        e2, p2 = build_with(merged)
        o2 = p2.apply()
        cache[o2] = p2
        return o2
    hit = search.best_assignment(unresolved, build, _error_count)
    if hit is None:
        return None
    sd, o = hit
    shown = ", ".join(f"{k[2]}: {render(t, lambda r: 'Record')}" for k, t in sd.items())
    return cache[o], o, (f"parameter types guessed from how the body uses them ({shown}); nothing in this file calls "
                         f"the function, so check they match your intent")


class _Plan:
    def __init__(self, source, tree, eng: Engine, records):
        self.src = _Src(source)
        self.tree = tree
        self.eng = eng
        self.records = records                    # rid -> [Dict nodes]
        self.edits: List[tuple] = []              # (start, end, text, seq)
        self.changes: List[str] = []
        self.problems: List[str] = []
        self.need_optional = False
        self.rec_names: Dict[tuple, str] = {}
        self.top_names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | set(eng.classes) | \
            set(eng.top_funcs)
        self.late_class_ref = False

    # -------------------------------------------------------------- helpers
    def edit(self, a, b, text):
        self.edits.append((a, b, text, len(self.edits)))

    def r(self, t, where_line: int = 0) -> Optional[str]:
        s = render(t, lambda rid: self.rec_names.get(rid, "Record"), OPTIONAL)
        if s is None:
            return None
        if "Optional[" in s:
            self.need_optional = True
        for name, line in ((k.name, k.node.lineno) for k in self.eng.classes.values()):
            if where_line and line > where_line and re.search(rf"\b{re.escape(name)}\b", s):
                self.late_class_ref = True
        return s

    def problem(self, line, msg):
        self.problems.append(f"line {line}: {msg}" if line else msg)

    # -------------------------------------------------------------- the plan
    def build(self):
        self._records()
        self._functions()
        self._variables(MODULE, None, _module_own(self.tree))
        for f in self.eng.funcs.values():
            self._variables(f.qual, f, _func_own(f.node))
        self._class_fields()
        self._loop_else()
        self._ifexp_mixed()
        self._num_sinks()
        self._header()

    def _records(self):
        if not self.records:
            return
        par = parents(self.tree)
        for rid, lits in self.records.items():
            hints = []
            for key, t in self.eng.slots.items():
                if key[0] == "var" and t == ("list", ("rec", rid)):
                    hints.insert(0, key[2])
                elif key[0] == "var" and t == ("rec", rid) and len(key[2]) > 2:
                    hints.append(key[2])
            for n in lits:
                p = par.get(n)
                if isinstance(p, ast.Call) and isinstance(p.func, ast.Attribute) and isinstance(p.func.value, ast.Name):
                    hints.insert(0, p.func.value.id)
            name = "Record"
            for h in hints:
                c = _camel(h)
                if c and c.isidentifier() and len(c) > 2:
                    name = c
                    break
            base, i = name, 2
            while name in self.top_names or name in self.rec_names.values():
                name, i = f"{base}{i}", i + 1
            self.rec_names[rid] = name
        self.rec_classes = []
        for rid, lits in self.records.items():
            first = min(lits, key=lambda n: (n.lineno, n.col_offset))
            order = [k.value for k in first.keys]
            name = self.rec_names[rid]
            fields = []
            for k in order:
                t = self.eng.slots.get(("field", rid, k))
                s = self.r(t)
                if s is None:
                    self.problem(first.lineno, f"couldn't work out the type of field '{k}' of {name} ({show(t)})")
                    s = "int"
                fields.append((k, s))
            code = [f"class {name}:"] + [f"    {k}: {s}" for k, s in fields] + [""]
            code.append(f"    def __init__(self, {', '.join(f'{k}: {s}' for k, s in fields)}) -> None:")
            code += [f"        self.{k} = {k}" for k, _ in fields] + ["", "", ""]
            self.rec_classes.append("\n".join(code))
            self.changes.append(f"dicts with keys {', '.join(order)} became class {name}")
            for n in lits:
                keys = [k.value for k in n.keys]
                kw = keys != order
                a, b = self.src.start(n), self.src.end(n)
                self.edit(a, a + 1, name + "(")
                self.edit(b - 1, b, ")")
                for k, v in zip(n.keys, n.values):
                    self.edit(self.src.start(k), self.src.start(v), f"{k.value}=" if kw else "")
        for node, t in self.eng.types.items():
            if is_rec(t):
                p = par.get(node)
                if isinstance(p, ast.Subscript) and p.value is node and t[1] in self.records:
                    self.edit(self.src.end(node), self.src.end(p), "." + p.slice.value)

    def _functions(self):
        for f in self.eng.funcs.values():
            fn = f.node
            pos = fn.args.posonlyargs + fn.args.args
            skip = 1 if f.kind in ("method", "classmethod") and pos else 0
            defaults = dict(zip([p.arg for p in pos[len(pos) - len(fn.args.defaults):]], fn.args.defaults))
            defaults.update({p.arg: d for p, d in zip(fn.args.kwonlyargs, fn.args.kw_defaults) if d is not None})
            pretty = f.qual.replace(".<locals>.", ".") + "()"
            for p in (pos + fn.args.kwonlyargs)[skip:]:
                if p.annotation is not None:
                    continue
                t = self.eng.slots.get(("var", f.qual, p.arg))
                s = self.r(t, fn.lineno)
                if s is None or not complete(t) and s is None:
                    why = "it is never called" if t is None else f"it receives {show(t)}"
                    self.problem(p.lineno, f"couldn't work out the type of parameter '{p.arg}' of {pretty}: {why}")
                    continue
                if p.arg in defaults:
                    d = defaults[p.arg]
                    self.edit(self.src.end(p), self.src.start(d), f": {s} = ")
                else:
                    self.edit(self.src.end(p), self.src.end(p), f": {s}")
                self.changes.append(f"parameter {p.arg}: {s} in {pretty}")
            for extra in (fn.args.vararg, fn.args.kwarg):
                if extra is not None and extra.annotation is None:
                    self.problem(fn.lineno, f"*{extra.arg} parameters of {pretty} are not converted")
            if fn.returns is not None:
                continue
            if f.generator:
                self.problem(fn.lineno, f"{pretty} is a generator function (yield); it is left as it is")
                continue
            rt = self.eng.slots.get(("ret", f.qual))
            if rt in (None, "None"):
                s = "None" if fn.name == "__init__" else None
            else:
                s = self.r(rt, fn.lineno)
                if s is None:
                    self.problem(fn.lineno, f"couldn't work out what {pretty} returns ({show(rt)})")
                    continue
            if s is None:
                continue
            at = _close_paren(self.src, fn)
            if at is not None:
                self.edit(at, at, f" -> {s}")
                if s != "None":
                    self.changes.append(f"{pretty} returns {s}")

    def _variables(self, scope, f, own):
        own = list(own)
        sites = _bindings(None, own)
        params = {p.arg for p in f.params} if f else set()
        for name, lst in sites.items():
            if name in params or (f is not None and name in f.globals):
                continue
            key = ("var", scope, name)
            t = self.eng.slots.get(key)
            if any(kind == "ann" for _, kind, _ in lst):
                continue
            pos, kind, node = lst[0]
            line = pos[0]
            if is_bad(t):
                self.problem(line, f"'{name}' holds values of different types ({t[1]}); PySub variables keep one type")
                continue
            if t is None:
                continue
            want = self.r(t, line if scope == MODULE else 0)
            if kind == "assign":
                have = render(self.eng.types.get(node.value), lambda rid: self.rec_names.get(rid, "Record"), OPTIONAL)
                if want == have:
                    continue
                if want is None:
                    if not complete(t) and isinstance(t, tuple) and t[0] in ("list", "dict", "set"):
                        self.problem(line, f"couldn't work out what '{name}' holds ({show(t)}): nothing is ever put in it")
                    continue
                tgt = node.targets[0]
                self.edit(self.src.end(tgt), self.src.end(tgt), f": {want}")
                self.changes.append(f"{name}: {want}" + ("" if scope == MODULE else f" in {scope.replace('.<locals>.', '.')}()"))
            elif want is not None:
                site_t = None
                for x in ast.walk(node.target if hasattr(node, "target") else node):
                    if isinstance(x, ast.Name) and x.id == name:
                        site_t = self.eng.types.get(x)
                        break
                if site_t is not None and render(site_t, lambda rid: self.rec_names.get(rid, "Record"), OPTIONAL) != want \
                        and not isinstance(node, (ast.For, ast.AsyncFor)):
                    self.problem(line, f"'{name}' needs the type {want} but its first assignment can't carry an "
                                       f"annotation; assign it on its own line first")
        # globals assigned only inside functions are checked at module level by their module bindings

    def _class_fields(self):
        for k in self.eng.classes.values():
            body = k.node.body
            if not body or body[0].lineno == k.node.lineno:
                if k.attrs - k.declared:
                    self.problem(k.node.lineno, f"class {k.name} is on one line; its fields can't be declared")
                continue
            first = body[0]
            at_line = first.lineno
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                if len(body) < 2:
                    continue
                at_line = first.end_lineno + 1
            indent = self.src.indent_of(first.lineno)
            class_level = set()
            for c in body:
                if isinstance(c, ast.Assign):
                    class_level |= {t.id for t in c.targets if isinstance(t, ast.Name)}
            order = []
            for m in k.methods.values():
                if m.kind != "method" or not m.params:
                    continue
                me = m.params[0].arg
                for n in sorted((x for x in _func_own(m.node) if isinstance(x, ast.Attribute)),
                                key=lambda x: (0 if m.node.name == "__init__" else 1, x.lineno, x.col_offset)):
                    if isinstance(n.ctx, ast.Store) and isinstance(n.value, ast.Name) and n.value.id == me:
                        if n.attr not in order:
                            order.append(n.attr)
            order.sort(key=lambda a: 0 if a in self._init_attrs(k) else 1)
            lines = []
            for a in order:
                if a in k.declared or a in class_level:
                    continue
                t = self.eng.slots.get(("attr", k.name, a))
                s = self.r(t, k.node.lineno)
                if s is None:
                    self.problem(k.node.lineno, f"couldn't work out the type of {k.name}.{a} ({show(t)})")
                    continue
                lines.append(f"{indent}{a}: {s}\n")
                self.changes.append(f"field {k.name}.{a}: {s}")
            if lines:
                pos = self.src.line_start(at_line)
                blank_next = at_line <= len(self.src.lines) and not self.src.lines[at_line - 1].strip()
                self.edit(pos, pos, "".join(lines) + ("" if blank_next else "\n"))

    def _loop_else(self):
        """for/while ... else -> a flag set before the loop, cleared at each break, tested by `if flag:`."""
        from .infer import _walk_loop
        used = {n.id for n in ast.walk(self.tree) if isinstance(n, ast.Name)}
        k = 1
        for loop in ast.walk(self.tree):
            if not isinstance(loop, (ast.For, ast.While)) or not loop.orelse:
                continue
            indent = self.src.indent_of(loop.lineno)
            breaks = [n for s in loop.body for n in _walk_loop(s) if isinstance(n, ast.Break)]
            lone = all(self.src.lines[b.lineno - 1].strip() == "break" for b in breaks)
            else_line = next((ln for ln in range(loop.orelse[0].lineno, loop.lineno, -1)
                              if self.src.lines[ln - 1].startswith(indent + "else")
                              and self.src.lines[ln - 1][len(indent) + 4:].lstrip().startswith(":")), None)
            if not lone or else_line is None or self.src.lines[loop.lineno - 1][:len(indent)] != indent:
                self.problem(loop.lineno, "a loop with an else: block whose break shares a line with other code; "
                                          "put each break on its own line")
                continue
            flag = "no_break"
            while flag in used:
                k += 1
                flag = f"no_break{k}"
            used.add(flag)
            at = self.src.line_start(loop.lineno)
            self.edit(at, at, f"{indent}{flag} = True\n")
            for b in breaks:
                bl = self.src.line_start(b.lineno)
                self.edit(bl, bl, f"{self.src.indent_of(b.lineno)}{flag} = False\n")
            e = self.src.line_start(else_line) + len(indent)
            self.edit(e, e + 4, f"if {flag}")
            self.changes.append(f"line {loop.lineno}: the loop's else: block became `if {flag}:`")

    def _ifexp_mixed(self):
        """When an IfExp has one branch float and the other int (or int literal), harmonize to float."""
        for n in ast.walk(self.tree):
            if not isinstance(n, ast.IfExp):
                continue
            bt = self.eng.types.get(n.body)
            ot = self.eng.types.get(n.orelse)
            if (bt in ("float", "num") and ot == "int") or (bt == "int" and ot in ("float", "num")):
                target = n.orelse if ot == "int" else n.body
                if isinstance(target, ast.Constant) and isinstance(target.value, int) and not isinstance(target.value, bool):
                    pos = self.src.start(target)
                    end = self.src.end(target)
                    self.edit(pos, end, f"{float(target.value)}")
                    self.changes.append(f"line {target.lineno}: widened integer literal {target.value} in conditional expression to float")
                elif isinstance(target, ast.UnaryOp) and isinstance(target.op, ast.USub) and isinstance(target.operand, ast.Constant) and isinstance(target.operand.value, int):
                    pos = self.src.start(target)
                    end = self.src.end(target)
                    self.edit(pos, end, f"-{float(target.operand.value)}")
                    self.changes.append(f"line {target.lineno}: widened integer literal -{target.operand.value} in conditional expression to float")
                else:
                    pos = self.src.start(target)
                    end = self.src.end(target)
                    self.edit(pos, pos, "float(")
                    self.edit(end, end, ")")
                    self.changes.append(f"line {target.lineno}: wrapped int branch of conditional expression with float()")

    def _init_attrs(self, k):
        init = k.methods.get("__init__")
        if init is None or not init.params:
            return set()
        me = init.params[0].arg
        return {n.attr for n in _func_own(init.node) if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Store)
                and isinstance(n.value, ast.Name) and n.value.id == me}

    def _num_sinks(self):
        par = parents(self.tree)
        seen = set()
        for n, why in sinks(self.eng, par):
            if why != "printed":
                continue
            t = self.eng.types.get(n)
            if contains(t, lambda x: x == "num") and n.lineno not in seen:
                seen.add(n.lineno)
                self.problem(n.lineno, f"`{ast.unparse(n)}` is an int on some runs and a float on others; PySub must "
                                       f"pick one type, and an int prints as 83 where a float prints 83.0")

    def _header(self):
        head = []
        names = {a.asname or a.name for s in self.tree.body if isinstance(s, ast.ImportFrom) for a in s.names}
        if self.need_optional and "Optional" not in names:
            head.append("from typing import Optional\n\n\n")
        for c in getattr(self, "rec_classes", []):
            head.append(c)
        body = self.tree.body
        i = 0
        while i < len(body) and (isinstance(body[i], (ast.Import, ast.ImportFrom)) or
                                 i == 0 and isinstance(body[i], ast.Expr) and isinstance(body[i].value, ast.Constant)):
            i += 1
        if self.late_class_ref and not any(isinstance(s, ast.ImportFrom) and s.module == "__future__" for s in body):
            j = 1 if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) else 0
            at = self.src.line_start(body[j].lineno) if j < len(body) else len(self.src.text)
            self.edit(at, at, "from __future__ import annotations\n")
        if not head:
            return
        if i < len(body):
            at = self.src.line_start(body[i].lineno)
            text = "".join(head)
        else:
            at = len(self.src.text)
            text = ("\n" if self.src.text and not self.src.text.endswith("\n") else "") + "".join(head)
        self.edit(at, at, text)
        if self.need_optional and "Optional" not in names:
            self.changes.append("from typing import Optional")

    def apply(self) -> str:
        text = self.src.text
        last = None
        for a, b, s, _ in sorted(self.edits, key=lambda e: (e[0], e[1], e[3]), reverse=True):
            if last is not None and b > last:
                continue                                   # overlapping edit (should not happen): keep the first
            text = text[:a] + s + text[b:]
            last = a
        return text


__all__ = ["to_pysub", "ConvertResult"]
