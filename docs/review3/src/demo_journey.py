"""One real function's journey through every stage (data from evidence/journey.json), as HTML for the viva guide and as excerpts for the figure."""
from __future__ import annotations

import html
import json
import re

from fig_common import FIG
from report_data import EV


def esc(s):
    return html.escape(str(s))


def load():
    p = EV / "journey.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def tree_lines(node, depth=0, out=None, maxd=6, maxn=18, typed=False):
    out = [] if out is None else out
    if len(out) >= maxn or not isinstance(node, dict):
        return out
    if node.get("t") == "TypeExpr" and not typed:
        return out
    if node.get("t") == "TypeExpr":
        return out
    at = node.get("attrs") or {}
    label = node["t"]
    for k in ("name", "op", "id", "value", "method", "var"):
        if k in at and at[k] not in (None, ""):
            label += f" {at[k]!r}" if isinstance(at[k], str) else f" {at[k]}"
            break
    if typed and node.get("ty"):
        label += f"  : {node['ty']}"
    out.append("  " * depth + label)
    if depth >= maxd:
        return out
    for k, v in (node.get("kids") or {}).items():
        if k in ("ann", "returns", "params") and node["t"] in ("FuncDef", "Param"):
            continue
        for ch in (v if isinstance(v, list) else [v]):
            tree_lines(ch, depth + 1, out, maxd, maxn, typed)
    return out


def find_nodes(node, t, out=None, limit=6):
    out = [] if out is None else out
    if isinstance(node, dict):
        if node.get("t") == t and len(out) < limit:
            out.append(node)
        for v in (node.get("kids") or {}).values():
            for ch in (v if isinstance(v, list) else [v]):
                find_nodes(ch, t, out, limit)
    return out


def body_tree(root, fname):
    fd = next(iter(find_nodes(root, "FuncDef", limit=40) and [n for n in find_nodes(root, "FuncDef", limit=40) if (n.get("attrs") or {}).get("name") == fname]), None)
    return fd


def pieces(j):
    rec, st = j["rec"], j["stages"]
    name = rec["name"]
    src = rec["sources"]
    orig = (src.get("original") or "").strip("\n").splitlines()
    pysub = (src.get("pysub") or "").strip("\n").splitlines()
    toks = st.get("tokens") or []
    shown, i0 = [], 0
    for t in toks[i0:i0 + 26]:
        shown.append(t["kind"] if t["kind"] in ("INDENT", "DEDENT", "NEWLINE") else f"{t['kind']}({t['value']})")
    fd = body_tree(st["ast"], name)
    ast = tree_lines(fd, maxd=4, maxn=16) if fd else []
    tfd = body_tree(st["typed_ast"], name)
    tast = tree_lines(tfd, maxd=4, maxn=16, typed=True) if tfd else []
    coerce = find_nodes(st["pir"], "Coerce", limit=3)
    cpp = (src.get("cpp") or "").splitlines()
    k = next((i for i, l in enumerate(cpp) if re.match(rf"static .* f_{name}\(.*\) \{{", l)), 0)
    cpp_fn = cpp[k:k + 22]
    wr = (src.get("wrapper_cpp") or "").splitlines()
    wk = next((i for i, l in enumerate(wr) if l.startswith("static py::object w_")), 0)
    return {"orig": orig, "pysub": pysub, "tokens": shown, "ast": ast, "tast": tast, "coerce": coerce, "cpp": cpp_fn, "wrapper": wr[wk:wk + 20],
            "ge": st.get("guard_elision"), "fid": st.get("fidelity") or [], "name": name}


def box(lines, n=18):
    ls = list(lines)[:n]
    return "<pre>" + esc("\n".join(ls)) + "</pre>"


def journey_html(j):
    rec = j["rec"]
    p = pieces(j)
    tr, bd, rp, bn, sp = rec.get("trace") or {}, rec.get("build") or {}, rec.get("replay") or {}, rec.get("bench") or {}, rec.get("splice") or {}
    fid = p["fid"]
    ge = p["ge"] or {}
    steps = []

    def step(n, title, plain, why, body):
        steps.append(f'<div class="step"><h3><span class="num">{n}</span> {title}</h3><p class="plain">{plain}</p><p class="why"><b>Why:</b> {why}</p>{body}</div>')

    step(1, "Your Python function", f"This is the function exactly as it sits in <code>{esc(rec['file'])}</code>. It has type annotations or not; PYTHIA does not care yet.",
         "Everything starts from your own code. Nothing is rewritten by hand.", box(p["orig"], 14))
    step(2, "The tracer watches the program run",
         f"PYTHIA runs your entry command (<code>{esc(j['cmd'])}</code>) once with a tracer on. For this function it saw <b>{tr.get('calls', '?'):,} calls</b>, "
         f"about <b>{100 * (tr.get('share') or 0):.1f}%</b> of the run time, and argument types <code>{esc(tr.get('arg_types'))}</code> returning <code>{esc(tr.get('ret_type'))}</code>.",
         "Real calls give two things: which functions are worth compiling, and the types they really receive.",
         f"<pre>{esc(json.dumps({k: tr.get(k) for k in ('calls', 'self_s', 'arg_types', 'ret_type', 'samples')}))}</pre>")
    changed = [l for l in p["pysub"] if l not in p["orig"]]
    step(3, "Types are filled in (PySub)",
         "The compiler only accepts PySub, where every variable has a type. If the function was missing annotations, PYTHIA adds them from the observed types and from how the values are used, then asks the real type checker to accept the result. "
         + ("Here the function already type-checked as written, so nothing had to change." if not changed else f"Here {len(changed)} line(s) were added or changed (shown below)."),
         "No guessing without a check: the compiler is the judge.", box(changed[:10] if changed else p["pysub"], 10))
    step(4, "Tokens: the words of the program",
         "The lexer cuts the text into tokens (keywords, names, numbers, operators). Python uses indentation, so the lexer also invents <b>INDENT</b> and <b>DEDENT</b> tokens where the block gets deeper or shallower.",
         "After this, the parser does not need to count spaces: blocks look like braces.", f"<pre>{esc('  '.join(p['tokens']))}</pre>")
    step(5, "AST: the shape of the program",
         "The parser builds a tree: a function contains statements, a loop contains a body, an expression contains operands. Every node remembers its line and column.",
         "Trees are easy to check and rewrite; error messages use the positions.", box(p["ast"], 16))
    step(6, "Type checking: every node gets a type",
         "The type checker walks the tree and writes a type on each node. It pushes expected types inward (bidirectional) and widens bool to int to float where needed. Any mismatch stops here with a line and column.",
         "C++ needs to know the exact type of everything; this is where we find out.", box(p["tast"], 16))
    cz = "; ".join(f"{(c.get('attrs') or {}).get('to', c.get('ty'))}" for c in p["coerce"]) or "none in this function"
    step(7, "Lowering: make hidden things explicit (PIR)",
         f"Python converts silently (an int becomes a float in <code>a / b</code>); C++ must be told. Lowering inserts explicit conversion nodes ({esc(cz)}) and attaches a <b>fidelity note</b> to every place where C++ could behave differently. This function has <b>{len(rec.get('fidelity') or fid)}</b> notes.",
         "This is the Semantic Fidelity Report being born.", box([f"{n.get('line')}:{n.get('col')} {n.get('cls')} ({n.get('severity')})" for n in (rec.get("fidelity") or fid)][:8] or ["(none)"], 8))
    step(8, "Guard elision: remove checks that cannot fire",
         f"Each integer <code>+ - *</code> could overflow 64 bits, so by default it is a checked call. The interval analysis proves some cannot: here <b>{ge.get('elided', '?')}</b> checks were removed and <b>{ge.get('kept', '?')}</b> kept.",
         "Fewer checks, faster code, and never a removed check that was needed.", "")
    step(9, "C++17 code generation",
         "The emitter walks the typed tree and writes readable C++17: typed variables, loops, calls into our runtime for Python behaviour.",
         "Readable output means you can review and export it.", box(p["cpp"], 18))
    step(10, "The pybind11 bridge",
         "A small generated wrapper turns Python arguments into C++ values, calls the function, and turns the result back. Mutated lists are written back. Anything it cannot represent faithfully raises <code>FallbackError</code>, and the original Python runs.",
         "This is the boundary, and it costs time, which is why the ranker predicts it.", box(p["wrapper"], 20))
    step(11, "Build",
         f"g++ compiles the C++ and links a Python extension, <code>{esc(bd.get('module'))}</code>. Builds are cached by content: compile took <b>{bd.get('compile_s', '?')} s</b>{' (cache hit)' if bd.get('cached') else ''}.",
         "A second run of the same project reuses it.", "")
    step(12, "Replay: the oracle on your own calls",
         f"The recorded calls are run through both the original function and the compiled one: <b>{rp.get('matched', '?')} of {rp.get('total', '?')}</b> calls matched (return value, exception, changed arguments; floats bit for bit). Source of inputs: <code>{esc(rp.get('source'))}</code>.",
         "One mismatch and the function is thrown away automatically.", "")
    step(13, "Benchmark",
         f"Python took <b>{bn.get('py_ms', 0):.3f} ms</b> per call and C++ <b>{bn.get('cpp_ms', 0):.3f} ms</b>: <b>{bn.get('speedup', 0):.1f}x</b> faster (median over repeats). Anything under 1.1x is declined.",
         "A function that compiles is not always worth compiling.", "")
    diff = sp.get("diff") or ""
    step(14, "Splice: one line, original kept",
         "PYTHIA adds a decorator above the original function in the working copy. The body is untouched, so the change is tiny and reversible; if the compiled module is missing, Python runs.",
         "The project keeps working whatever happens.", f"<pre>{esc(chr(10).join(diff.splitlines()[:20]))}</pre>")
    return "\n".join(steps)


def make(F, D, pick, jobs):
    j = load()
    out = {}
    if j:
        out["fn_name"] = j["rec"]["name"]
        out["repo_name"] = j["repo"]
        out["journey_html"] = journey_html(j)
        out["journey"] = j
    return out
