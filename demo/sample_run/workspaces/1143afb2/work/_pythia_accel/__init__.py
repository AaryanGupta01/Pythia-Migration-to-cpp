"""PYTHIA accel shim: installed in accelerated projects as `_pythia_accel/`.

    @_pythia_accelerated("pythia_ab12cd34", "edit_distance")
    def edit_distance(a, b): ...        # original body untouched

Loads lib/<modname>*.so by path.  Any import problem -> the original function is
returned unchanged; `FallbackError` from the compiled code -> original runs.
Set PYTHIA_ACCEL=0 to disable acceleration entirely (baseline timing).
"""
import functools
import glob
import importlib.util
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_mods = {}


def _load(modname):
    if modname not in _mods:
        mod = None
        for p in sorted(glob.glob(os.path.join(_HERE, "lib", modname + ".*")) +
                        (glob.glob(os.path.join(_HERE, "lib", modname + "*.so")) + glob.glob(os.path.join(_HERE, "lib", modname + "*.pyd")))):
            try:
                spec = importlib.util.spec_from_file_location(modname, p)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                break
            except Exception:
                mod = None
        _mods[modname] = mod
    return _mods[modname]


def accelerated(modname, name):
    def deco(fn):
        if os.environ.get("PYTHIA_ACCEL") == "0":
            return fn
        try:
            mod = _load(modname)
            native = getattr(mod, name)
            fallback = (getattr(mod, "FallbackError", ()), TypeError)   # TypeError: arg not marshallable (tuple, ...)
        except Exception:
            return fn

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if kwargs:
                return fn(*args, **kwargs)
            try:
                return native(*args)
            except fallback:
                return fn(*args)

        wrapper._pythia_native = native
        wrapper._pythia_original = fn
        return wrapper
    return deco
