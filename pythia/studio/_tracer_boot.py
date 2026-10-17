"""In-process tracer.  Installed as `sitecustomize.py` in a temp dir that is put
first on PYTHONPATH of the user's entry command (alongside `_pythia_codec.py`,
a copy of codec.py).  Config: JSON file named by $PYTHIA_TRACE_CFG.

Records per target function: calls, cumulative/self time, observed arg/return
types, element counts, and <=N sampled (args-at-entry, ret|exc) JSONL records.
Never raises into the user's program.
"""
import json
import os
import sys
import threading
import time


def _chain():
    """Run the next sitecustomize on the path, if any."""
    try:
        import importlib.util
        here = os.path.dirname(os.path.abspath(__file__))
        path = [p for p in sys.path if os.path.abspath(p or ".") != here]
        spec = importlib.util.PathFinder.find_spec("sitecustomize", path)
        if spec and spec.origin and os.path.abspath(spec.origin) != os.path.abspath(__file__):
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
    except Exception:
        pass


def _install():
    cfg_path = os.environ.get("PYTHIA_TRACE_CFG")
    if not cfg_path or os.environ.get("PYTHIA_TRACE_ACTIVE"):
        return
    os.environ["PYTHIA_TRACE_ACTIVE"] = "1"          # children of the traced process stay untraced
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    import _pythia_codec as codec

    out_dir = cfg["out_dir"]
    max_samples = cfg.get("max_samples", 500)
    perf = time.perf_counter_ns
    MISSING = object()

    class Stat:
        __slots__ = ("fid", "name", "calls", "cum", "selft", "depth", "arg_types", "ret_type",
                     "arg_elems", "ret_elems", "nsampled", "samples", "skipped", "fh", "simple",
                     "nparams", "pnames", "nret", "fid_hash")

        def __init__(self, fid, name):
            self.fid, self.name = fid, name
            self.calls = self.cum = self.selft = self.depth = 0
            self.arg_types, self.ret_type = None, None
            self.arg_elems = self.ret_elems = 0.0
            self.nsampled = self.samples = self.skipped = self.nret = 0
            self.fh = None
            self.simple = False
            self.nparams = 0
            self.pnames = ()

    by_key = {}
    for t in cfg["targets"]:
        by_key[(t["file"], t["name"])] = Stat(t["id"], t["name"])
    stats = {s.fid: s for s in by_key.values()}
    codes = {}
    stacks = {}
    realpaths = {}
    mon = None if os.environ.get("PYTHIA_TRACE_NO_MON") else getattr(sys, "monitoring", None)
    lock = threading.Lock()
    os.makedirs(out_dir, exist_ok=True)

    def resolve(code):
        fn = code.co_filename
        rp = realpaths.get(fn)
        if rp is None:
            try:
                rp = os.path.realpath(fn)
            except Exception:
                rp = fn
            realpaths[fn] = rp
        st = by_key.get((rp, getattr(code, "co_qualname", code.co_name)))
        if st is not None and code.co_flags & (0x20 | 0x80 | 0x200):     # generators/coroutines
            st = None
        if st is not None and not st.nparams:
            st.nparams = code.co_argcount
            st.pnames = code.co_varnames[:code.co_argcount]
            st.arg_types = ["?"] * code.co_argcount
            st.simple = not (code.co_flags & 0x0C) and not code.co_kwonlyargcount
        codes[code] = st
        return st

    def elems(v):
        t = type(v)
        return float(len(v)) if t in (list, dict, str, tuple) else 1.0

    def enter(code, frame):
        st = codes.get(code, MISSING)
        if st is MISSING:
            st = resolve(code)
        if st is None:
            return False
        st.calls += 1
        n = st.calls
        sample = None
        flag = False
        if st.samples < max_samples and (n <= 300 or n % 23 == 0):
            try:
                loc = frame.f_locals
                args = [loc[p] for p in st.pnames]
                at = st.arg_types
                for i, v in enumerate(args):
                    at[i] = codec.join_types(at[i], codec.tdesc(v))
                st.arg_elems += sum(elems(v) for v in args)
                st.nsampled += 1
                flag = True
                if st.simple:
                    sample = codec.encode(args)
            except (codec.TooBig, codec.Unencodable, KeyError):
                st.skipped += 1
            except Exception:
                st.skipped += 1
        stk = stacks.setdefault(threading.get_ident(), [])
        stk.append([st, perf(), sample, 0, flag])
        st.depth += 1
        return True

    def leave(code, ret, exc):
        stk = stacks.get(threading.get_ident())
        if not stk:
            return
        st = codes.get(code)
        while stk and stk[-1][0] is not st:        # frames that began before tracing / lost events
            stk.pop()
        if not stk:
            return
        ent = stk.pop()
        dt = perf() - ent[1]
        st.depth -= 1
        if st.depth == 0:
            st.cum += dt
        st.selft += dt - ent[3]
        if stk:
            stk[-1][3] += dt
        if exc is None:
            try:
                st.ret_type = codec.join_types(st.ret_type, codec.tdesc(ret)) if st.ret_type else codec.tdesc(ret)
                if ent[4]:
                    st.ret_elems += elems(ret)
                    st.nret += 1
            except Exception:
                pass
        if ent[2] is not None:
            try:
                rec = {"args": ent[2]}
                if exc is None:
                    rec["ret"] = codec.encode(ret)
                    rec["exc"] = None
                else:
                    rec["ret"] = None
                    rec["exc"] = type(exc).__name__
                with lock:
                    if st.fh is None:
                        st.fh = open(os.path.join(out_dir, st.fid_hash + ".jsonl"), "a", encoding="utf-8")
                    st.fh.write(json.dumps(rec) + "\n")
                    st.samples += 1
            except (codec.TooBig, codec.Unencodable):
                st.skipped += 1
            except Exception:
                st.skipped += 1

    import hashlib
    for t in cfg["targets"]:
        stats[t["id"]].fid_hash = hashlib.sha1(t["id"].encode()).hexdigest()[:12]

    def dump(final=False):
        per = {}
        total_calls = 0
        for s in stats.values():
            if not s.calls:
                continue
            total_calls += s.calls
            ns = max(s.nsampled, 1)
            per[s.fid] = {
                "calls": s.calls, "cum_s": s.cum / 1e9, "self_s": s.selft / 1e9,
                "arg_types": s.arg_types or [], "ret_type": s.ret_type,
                "avg_arg_elems": s.arg_elems / ns, "avg_ret_elems": (s.ret_elems / max(s.nret, 1)) if s.ret_type else 0.0,
                "samples": s.samples, "skipped": s.skipped}
        tmp = os.path.join(out_dir, "progress.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"calls": total_calls, "functions_seen": len(per), "per_fn": per, "final": final}, f)
        os.replace(tmp, os.path.join(out_dir, "progress.json"))

    def flush_all():
        with lock:
            for s in stats.values():
                if s.fh:
                    try:
                        s.fh.flush()
                    except Exception:
                        pass

    def ticker():
        while True:
            time.sleep(0.4)
            try:
                flush_all()
                dump()
            except Exception:
                pass

    def finish(*_a):
        try:
            if mon:
                mon.set_events(TOOL, 0)
            else:
                sys.setprofile(None)
            flush_all()
            dump(True)
        except Exception:
            pass

    if mon:
        TOOL = mon.PROFILER_ID
        ev = mon.events
        try:
            mon.use_tool_id(TOOL, "pythia")
        except ValueError:
            TOOL = mon.OPTIMIZER_ID
            mon.use_tool_id(TOOL, "pythia")
        DISABLE = mon.DISABLE

        def on_start(code, off):
            st = codes.get(code, MISSING)
            if st is MISSING:
                st = resolve(code)
                if st is not None:
                    mon.set_local_events(TOOL, code, ev.PY_RETURN)
            if st is None:
                return DISABLE
            enter(code, sys._getframe(1))

        mon.register_callback(TOOL, ev.PY_START, on_start)
        mon.register_callback(TOOL, ev.PY_RETURN, lambda code, off, ret: leave(code, ret, None))
        # PY_UNWIND cannot be a local event: global, cheap early-out for non-target code
        mon.register_callback(TOOL, ev.PY_UNWIND,
                              lambda code, off, exc: leave(code, None, exc) if code in codes and codes[code] else None)
        mon.set_events(TOOL, ev.PY_START | ev.PY_UNWIND)
    else:                                              # sys.setprofile fallback (<3.12)
        def prof(frame, event, arg):
            if event == "call":
                enter(frame.f_code, frame)
            elif event == "return":
                leave(frame.f_code, arg, None)
        sys.setprofile(prof)
        threading.setprofile(prof)

    import atexit
    atexit.register(finish)
    try:
        import signal
        def on_term(sig, frm):
            finish()
            os._exit(128 + sig)
        signal.signal(signal.SIGTERM, on_term)
    except Exception:
        pass
    th = threading.Thread(target=ticker, daemon=True, name="pythia-trace-ticker")
    th.start()
    dump()


try:
    _install()
except Exception as _e:                                # never break the user's program
    try:
        sys.stderr.write(f"[pythia tracer disabled: {_e!r}]\n")
    except Exception:
        pass
_chain()
