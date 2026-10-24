"""Subprocess worker for oracle replay and per-function benchmarking.

    python _replay_worker.py <job.json>

job: {mode: replay|bench, original: <dir>, file: <rel path>, name, so: <path>, modname,
      calls: <jsonl of {"args": enc, ...}>, n_max}
Protocol on the real stdout: lines "@<call index>" then one "RESULT <json>".
Everything else printed by the code under test goes to /dev/null.
"""
import gc
import importlib
import importlib.util
import json
import os
import signal
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if sys.path and os.path.abspath(sys.path[0] or ".") == HERE:
    sys.path.pop(0)                 # don't shadow user modules (trace.py, models.py, ...)

spec = importlib.util.spec_from_file_location("_pythia_codec", os.path.join(HERE, "codec.py"))
codec = importlib.util.module_from_spec(spec)
sys.modules["_pythia_codec"] = codec
spec.loader.exec_module(codec)

PROTO = os.fdopen(os.dup(1), "w", buffering=1)
_null = os.open(os.devnull, os.O_WRONLY)
os.dup2(_null, 1)
sys.stdout = open(os.devnull, "w")


class CallTimeout(BaseException):
    pass


def _alarm(_s, _f):
    raise CallTimeout()


# Per-call watchdog: SIGALRM where it exists, else (Windows) a timer thread that interrupts the main thread.
TIMEOUT_EXC = (CallTimeout, KeyboardInterrupt)
if hasattr(signal, "setitimer"):
    def arm(seconds):
        signal.signal(signal.SIGALRM, _alarm)
        signal.setitimer(signal.ITIMER_REAL, seconds)

    def disarm():
        signal.setitimer(signal.ITIMER_REAL, 0)
else:
    import _thread
    import threading
    _timer = [None]

    def arm(seconds):
        t = threading.Timer(seconds, _thread.interrupt_main)
        t.daemon = True
        _timer[0] = t
        t.start()

    def disarm():
        t = _timer[0]
        if t is not None:
            t.cancel()


def load_original(root, rel, name):
    sys.path.insert(0, root)
    here = os.path.dirname(os.path.join(root, rel))
    if os.path.abspath(here) != os.path.abspath(root):
        sys.path.insert(1, here)                    # a script imports its siblings by bare name (`from utils import f`)
    mod = rel[:-3].replace("/", ".")
    if mod.endswith(".__init__"):
        mod = mod[:-9]
    try:
        m = importlib.import_module(mod)
        return getattr(m, name)
    except Exception:
        pass
    # A script that reads input() or runs its work at import time: execute the top-level statements one by one and
    # skip the ones that fail, so the definitions (and constants that don't need input) still load.
    import ast
    path = os.path.join(root, rel)
    tree = ast.parse(open(path, encoding="utf-8").read(), path)
    ns = {"__name__": "_pythia_orig_" + name, "__file__": path}
    for st in tree.body:
        try:
            exec(compile(ast.Module([st], []), path, "exec"), ns)
        except Exception:
            pass
    return ns[name]


def load_so(path, modname):
    s = importlib.util.spec_from_file_location(modname, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


def outcome(fn, args):
    try:
        return ("ret", fn(*args))
    except TIMEOUT_EXC:
        raise
    except Exception as e:
        return ("exc", type(e).__name__)


def show(o):
    return ("raises " + o[1]) if o[0] == "exc" else codec.display(o[1])


def replay(job, fn_py, mod):
    fn_c = getattr(mod, job["name"])
    fb = getattr(mod, "FallbackError", None)
    calls = [json.loads(l) for l in open(job["calls"], encoding="utf-8") if l.strip()][: job["n_max"]]
    res = {"total": 0, "matched": 0, "exc_matches": 0, "skipped": 0, "mismatches": 0,
           "first_mismatch": None, "timeouts": 0}
    t_start = time.monotonic()
    for i, c in enumerate(calls):
        if time.monotonic() - t_start > job.get("budget_s", 30):
            res["budget_exhausted"] = True      # partial replay beats a killed worker
            break
        PROTO.write(f"@{i}\n")
        pa, ca = codec.decode(c["args"]), codec.decode(c["args"])
        arm(job.get("call_timeout", 1))
        try:
            po = outcome(fn_py, pa)
        except TIMEOUT_EXC:
            res["timeouts"] += 1
            res["skipped"] += 1
            continue
        finally:
            disarm()
        if po[0] == "exc" and po[1] in ("RecursionError", "MemoryError"):
            res["skipped"] += 1
            continue
        co = outcome(fn_c, ca)
        if co[0] == "exc" and (co[1] == "FallbackError" or (fb and fb.__name__ == co[1])):
            res["skipped"] += 1
            continue
        res["total"] += 1
        kind = None
        if po[0] != co[0] or (po[0] == "exc" and po[1] != co[1]):
            kind = "exception"
        elif po[0] == "ret" and not codec.same(po[1], co[1]):
            kind = "value"
        elif po[0] == "ret" and not codec.same(pa, ca):
            kind = "mutation"
        if kind is None:
            res["matched"] += 1
            res["exc_matches"] += po[0] == "exc"
            continue
        res["mismatches"] += 1
        if res["first_mismatch"] is None:
            res["first_mismatch"] = {
                "args": codec.display_args(codec.decode(c["args"])), "kind": kind,
                "python": show(po) if kind != "mutation" else codec.display_args(pa),
                "cpp": show(co) if kind != "mutation" else codec.display_args(ca)}
    return res


def bench(job, fn_py, mod):
    fn_c = getattr(mod, job["name"])
    fb = getattr(mod, "FallbackError", ())
    raw = [json.loads(l) for l in open(job["calls"], encoding="utf-8") if l.strip()]
    cap = job.get("calls_cap", 200)
    if len(raw) > cap:
        step = len(raw) / cap
        raw = [raw[int(k * step)] for k in range(cap)]
    keep = []
    spent = 0.0
    for c in raw:                                  # drop calls the .so can't take or that are pathologically slow in Python
        if spent > job.get("py_budget_s", 1.5) and keep:
            break                                  # enough samples: a 90 s benchmark of one function helps nobody
        a = codec.decode(c["args"])
        t0 = time.perf_counter()
        try:
            arm(5)
            outcome(fn_py, a)
        except TIMEOUT_EXC:
            continue
        finally:
            disarm()
            spent += time.perf_counter() - t0     # timeouts count too, or a run of 5 s timeouts never trips the budget
        try:
            fn_c(*codec.decode(c["args"]))
        except fb:
            continue
        except Exception:
            pass
        keep.append((c, len(json.dumps(c["args"]))))
    if not keep:
        return {"error": "no callable samples"}
    weight = sum(w for _, w in keep) + 1

    def fresh(loops):
        return [[codec.decode(c["args"]) for c, _ in keep] for _ in range(loops)]

    def run(fn, sets):
        gc.disable()
        t0 = time.perf_counter()
        for L in sets:
            for a in L:
                try:
                    fn(*a)
                except Exception:
                    pass
        dt = time.perf_counter() - t0
        gc.enable()
        return dt / len(sets)

    one = run(fn_py, fresh(1))
    loops = int(max(1, min(500, 0.05 / max(one, 1e-7), 6_000_000 // weight)))
    repeats = 5 if one < 0.3 else 3 if one < 1 else 1
    py, cp = [], []
    for _ in range(repeats):
        PROTO.write("@b\n")
        s = fresh(loops)
        py.append(run(fn_py, s))
        s = fresh(loops)
        cp.append(run(fn_c, s))
    pm, cm = statistics.median(py) * 1000, statistics.median(cp) * 1000
    return {"py_ms": pm, "cpp_ms": cm, "speedup": pm / max(cm, 1e-6), "calls_timed": len(keep),
            "repeats": repeats, "loops": loops}


def main():
    job = json.load(open(sys.argv[1], encoding="utf-8"))
    out = {}
    try:
        fn_py = load_original(job["original"], job["file"], job["name"])
    except BaseException as e:
        out = {"error": f"could not import original {job['file']}::{job['name']}: {type(e).__name__}: {e}"}
    else:
        try:
            mod = load_so(job["so"], job["modname"])
        except BaseException as e:
            out = {"error": f"could not load compiled module: {type(e).__name__}: {e}"}
        else:
            try:
                out = (replay if job["mode"] == "replay" else bench)(job, fn_py, mod)
            except BaseException as e:
                out = {"error": f"{type(e).__name__}: {e}"}
    PROTO.write("RESULT " + json.dumps(out) + "\n")
    PROTO.flush()
    os._exit(0)


main()
