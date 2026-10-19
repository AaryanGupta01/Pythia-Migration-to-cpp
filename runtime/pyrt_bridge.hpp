// PYTHIA :: Python <-> runtime marshalling used by generated library-mode
// wrappers (pythia/libmode.py).  Copy semantics: arguments are converted into
// runtime objects, results are converted back; mutated list/dict arguments are
// written back in place by the generated glue (`back`).
//
// Anything that cannot be represented faithfully raises FallbackError (so the
// splice layer can run the original Python); ints outside int64 raise
// OverflowError, like the compiled arithmetic does.
#ifndef PYRT_BRIDGE_HPP
#define PYRT_BRIDGE_HPP

#include <pybind11/pybind11.h>
#include <algorithm>
#include <cstring>
#include <functional>
#include <string>
#include <unordered_map>
#include "pyrt.hpp"

namespace pyb {
namespace py = pybind11;

inline PyObject *FallbackError = nullptr;   // created in the module init
inline PyObject *SemanticError = nullptr;   // PythiaSemanticError(RuntimeError)

// All allocations made while an Arena is alive are freed when it dies.
struct Arena {
    Arena() { pyrt::arena_begin(); }
    ~Arena() { pyrt::arena_end(); }
    Arena(const Arena &) = delete;
    Arena &operator=(const Arena &) = delete;
};

[[noreturn]] inline void fail(PyObject *cls, const char *msg) {
    PyObject *s = PyUnicode_DecodeUTF8(msg, static_cast<Py_ssize_t>(std::strlen(msg)), "replace");
    if (s) { PyErr_SetObject(cls, s); Py_DECREF(s); }
    throw py::error_already_set();
}
[[noreturn]] inline void fallback(const char *why) { fail(FallbackError, why); }

[[noreturn]] inline void raise(const pyrt::PythonException &e) {
    const std::string &n = e.name();
    PyObject *c = PyExc_RuntimeError;
    if (n == "IndexError") c = PyExc_IndexError;
    else if (n == "ZeroDivisionError") c = PyExc_ZeroDivisionError;
    else if (n == "OverflowError") c = PyExc_OverflowError;
    else if (n == "ValueError") c = PyExc_ValueError;
    else if (n == "KeyError") c = PyExc_KeyError;
    else if (n == "EOFError") c = PyExc_EOFError;
    else if (n == "TypeError") c = PyExc_TypeError;
    else if (n == "AttributeError") c = PyExc_AttributeError;
    else if (n == "NameError") c = PyExc_NameError;
    else if (n == "PythiaSemanticError" && SemanticError) c = SemanticError;
    else if (n == "RecursionError" && FallbackError) c = FallbackError;   // let CPython decide where it overflows
    fail(c, e.message().c_str());
}

inline PyObject *ck(PyObject *p) {
    if (!p) throw py::error_already_set();
    return p;
}
inline py::object steal(PyObject *p) { return py::reinterpret_steal<py::object>(ck(p)); }

// ---- scalars -----------------------------------------------------------------
struct I64 {
    using C = int64_t;
    static C in(PyObject *o) {
        if (!PyLong_Check(o)) fallback("expected int");          // bool is an int subclass: accepted
        int ov = 0;
        long long v = PyLong_AsLongLongAndOverflow(o, &ov);
        if (ov) fail(PyExc_OverflowError, "Python int too large to convert to int64");
        if (v == -1 && PyErr_Occurred()) throw py::error_already_set();
        return static_cast<C>(v);
    }
    static PyObject *out(C v) { return ck(PyLong_FromLongLong(v)); }
};
struct F64 {
    using C = double;
    static C in(PyObject *o) {
        if (PyFloat_Check(o)) return PyFloat_AS_DOUBLE(o);
        if (PyLong_Check(o)) {                                    // Python int for a float parameter
            double d = PyLong_AsDouble(o);
            if (d == -1.0 && PyErr_Occurred()) throw py::error_already_set();
            return d;
        }
        fallback("expected float");
    }
    static PyObject *out(C v) { return ck(PyFloat_FromDouble(v)); }
};
struct Bool {
    using C = bool;
    static C in(PyObject *o) {
        if (o == Py_True) return true;
        if (o == Py_False) return false;
        fallback("expected bool");
    }
    static PyObject *out(C v) { PyObject *r = v ? Py_True : Py_False; Py_INCREF(r); return r; }
};
struct Str {
    using C = pyrt::PyStr *;
    static C in(PyObject *o) {
        if (!PyUnicode_Check(o)) fallback("expected str");
        if (!PyUnicode_IS_ASCII(o)) fallback("non-ASCII str is not supported by the compiled code");
        Py_ssize_t n = 0;
        const char *s = PyUnicode_AsUTF8AndSize(o, &n);
        if (!s) throw py::error_already_set();
        return pyrt::pystr_new(s, static_cast<int64_t>(n));
    }
    static PyObject *out(C v) {
        return ck(PyUnicode_DecodeUTF8(v->data.data(), static_cast<Py_ssize_t>(v->data.size()), "strict"));
    }
};

// ---- tuple[scalar or tuple, ...]: immutable, so never written back ------------
template <class... E> struct Tuple {
    using C = std::tuple<typename E::C...>;
    template <size_t... I> static C in_(PyObject *o, std::index_sequence<I...>) {
        return C{E::in(PyTuple_GET_ITEM(o, static_cast<Py_ssize_t>(I)))...};    // braced: left to right
    }
    static C in(PyObject *o) {
        if (!PyTuple_Check(o) || PyTuple_GET_SIZE(o) != static_cast<Py_ssize_t>(sizeof...(E)))
            fallback("expected a tuple of the declared size");
        return in_(o, std::index_sequence_for<E...>{});
    }
    template <size_t... I> static PyObject *out_(const C &v, std::index_sequence<I...>) {
        py::object r = steal(PyTuple_New(static_cast<Py_ssize_t>(sizeof...(E))));
        (PyTuple_SET_ITEM(r.ptr(), static_cast<Py_ssize_t>(I), E::out(std::get<I>(v))), ...);
        return r.release().ptr();
    }
    static PyObject *out(const C &v) { return out_(v, std::index_sequence_for<E...>{}); }
};

// ---- list[scalar] ------------------------------------------------------------
template <class E, class L> struct List {
    using C = L *;
    static C in(PyObject *o) {
        if (!PyList_Check(o)) fallback("expected list");
        Py_ssize_t n = PyList_GET_SIZE(o);
        L *l = pyrt::arena_new<L>();
        l->data.reserve(static_cast<size_t>(n));
        for (Py_ssize_t i = 0; i < n; ++i) l->data.push_back(E::in(PyList_GET_ITEM(o, i)));
        return l;
    }
    static PyObject *out(C l) {
        Py_ssize_t n = static_cast<Py_ssize_t>(l->data.size());
        py::object r = steal(PyList_New(n));
        for (Py_ssize_t i = 0; i < n; ++i) PyList_SET_ITEM(r.ptr(), i, E::out(l->data[static_cast<size_t>(i)]));
        return r.release().ptr();
    }
    // write the final state back into the caller's list, in place
    static void back(PyObject *dst, C l) {
        Py_ssize_t old = PyList_GET_SIZE(dst), n = static_cast<Py_ssize_t>(l->data.size());
        Py_ssize_t m = std::min(old, n);
        for (Py_ssize_t i = 0; i < m; ++i) PyList_SetItem(dst, i, E::out(l->data[static_cast<size_t>(i)]));
        for (Py_ssize_t i = m; i < n; ++i) {
            py::object v = steal(E::out(l->data[static_cast<size_t>(i)]));
            if (PyList_Append(dst, v.ptr()) < 0) throw py::error_already_set();
        }
        if (n < old && PyList_SetSlice(dst, n, old, nullptr) < 0) throw py::error_already_set();
    }
};

// ---- list[list[scalar]] ------------------------------------------------------
template <class Inner> struct List2 {
    using C = pyrt::PyListList *;
    using IC = typename Inner::C;
    static C in(PyObject *o) {
        if (!PyList_Check(o)) fallback("expected list");
        Py_ssize_t n = PyList_GET_SIZE(o);
        C l = pyrt::arena_new<pyrt::PyListList>();
        l->data.reserve(static_cast<size_t>(n));
        for (Py_ssize_t i = 0; i < n; ++i) l->data.push_back(static_cast<void *>(Inner::in(PyList_GET_ITEM(o, i))));
        return l;
    }
    static PyObject *out(C l) {
        Py_ssize_t n = static_cast<Py_ssize_t>(l->data.size());
        py::object r = steal(PyList_New(n));
        for (Py_ssize_t i = 0; i < n; ++i)
            PyList_SET_ITEM(r.ptr(), i, Inner::out(static_cast<IC>(l->data[static_cast<size_t>(i)])));
        return r.release().ptr();
    }
    // inner lists are updated in place where they still exist (identity kept)
    static void back(PyObject *dst, C l) {
        Py_ssize_t old = PyList_GET_SIZE(dst), n = static_cast<Py_ssize_t>(l->data.size());
        Py_ssize_t m = std::min(old, n);
        for (Py_ssize_t i = 0; i < m; ++i) {
            PyObject *row = PyList_GET_ITEM(dst, i);
            if (PyList_Check(row)) Inner::back(row, static_cast<IC>(l->data[static_cast<size_t>(i)]));
            else PyList_SetItem(dst, i, Inner::out(static_cast<IC>(l->data[static_cast<size_t>(i)])));
        }
        for (Py_ssize_t i = m; i < n; ++i) {
            py::object v = steal(Inner::out(static_cast<IC>(l->data[static_cast<size_t>(i)])));
            if (PyList_Append(dst, v.ptr()) < 0) throw py::error_already_set();
        }
        if (n < old && PyList_SetSlice(dst, n, old, nullptr) < 0) throw py::error_already_set();
    }
};

// ---- dict[int|str, scalar] ---------------------------------------------------
template <class K, class V, class D> struct Dict {
    using C = D *;
    static C in(PyObject *o) {
        if (!PyDict_CheckExact(o)) fallback("expected dict (defaultdict/Counter arguments run in Python)");
        C d = pyrt::arena_new<D>();
        Py_ssize_t pos = 0;
        PyObject *k, *v;
        // Python keys are already unique, so append directly (keeps insertion order, O(n)).
        while (PyDict_Next(o, &pos, &k, &v)) {
            d->keys.push_back(K::in(k));
            d->vals.push_back(V::in(v));
        }
        return d;
    }
    static void fill(PyObject *dst, C d) {
        for (size_t i = 0; i < d->keys.size(); ++i) {
            py::object k = steal(K::out(d->keys[i])), v = steal(V::out(d->vals[i]));
            if (PyDict_SetItem(dst, k.ptr(), v.ptr()) < 0) throw py::error_already_set();
        }
    }
    static PyObject *out(C d) {
        if (d->mode) fallback("a defaultdict/Counter result is returned by the original Python");
        py::object r = steal(PyDict_New());
        fill(r.ptr(), d);
        return r.release().ptr();
    }
    static void back(PyObject *dst, C d) {
        PyDict_Clear(dst);
        fill(dst, d);
    }
};

// ---- PySub 1.3: Optional[T] (None <-> empty), set[T] -------------------------------------------
template <class T> struct Opt {                       // Optional[int|float|bool]
    using C = std::optional<typename T::C>;
    static C in(PyObject *o) { if (o == Py_None) return std::nullopt; return T::in(o); }
    static PyObject *out(const C &v) { if (!v) { Py_INCREF(Py_None); return Py_None; } return T::out(*v); }
};
template <class T> struct OptP {                      // Optional[str|list|dict|set]: None <-> nullptr
    using C = typename T::C;
    static C in(PyObject *o) { if (o == Py_None) return nullptr; return T::in(o); }
    static PyObject *out(C v) { if (!v) { Py_INCREF(Py_None); return Py_None; } return T::out(v); }
    static void back(PyObject *dst, C v) { if (v && dst != Py_None) T::back(dst, v); }
};
template <class E, class T> struct Set {
    using C = pyrt::PySet<T> *;
    static C in(PyObject *o) {
        if (!PySet_Check(o) && !PyFrozenSet_Check(o)) fallback("expected set");
        C s = pyrt::pyset_new<T>();
        py::object it = steal(PyObject_GetIter(o));
        while (PyObject *x = PyIter_Next(it.ptr())) {
            py::object hold = steal(x);
            s->s.insert(E::in(x));
        }
        if (PyErr_Occurred()) throw py::error_already_set();
        return s;
    }
    static void fill(PyObject *dst, C s) {
        for (const T &x : s->s) {
            py::object v = steal(E::out(x));
            if (PySet_Add(dst, v.ptr()) < 0) throw py::error_already_set();
        }
    }
    static PyObject *out(C s) { py::object r = steal(PySet_New(nullptr)); fill(r.ptr(), s); return r.release().ptr(); }
    static void back(PyObject *dst, C s) { if (PySet_Clear(dst) < 0) throw py::error_already_set(); fill(dst, s); }
};

// ---- user-class objects (pythia/classes_lib.py generates the per-class traits) ------------------------------
// Attributes are written back after the call, so their Python type must survive the round trip exactly:
// an int stored in a float attribute / a bool in an int attribute runs in Python instead.
struct I64x : I64 {
    static C in(PyObject *o) { if (PyBool_Check(o)) fallback("expected int, found bool"); return I64::in(o); }
};
struct F64x : F64 {
    static C in(PyObject *o) {
        if (!PyFloat_Check(o)) fallback("expected float (an int stored in a float attribute runs in Python)");
        return PyFloat_AS_DOUBLE(o);
    }
};
// One ObjCtx per call: Python object <-> C++ object memo (identity, shared / cyclic graphs), the original Python
// containers of list/dict/set fields (written back in place), write-back actions for every inbound object.
struct ObjCtx {
    std::unordered_map<PyObject *, std::shared_ptr<void>> in;
    std::unordered_map<const void *, PyObject *> out;
    std::unordered_map<const void *, PyObject *> conts;
    std::vector<std::function<void()>> wb;
    std::vector<py::object> keep;
};
inline ObjCtx *&objctx() { static thread_local ObjCtx *c = nullptr; return c; }
struct ObjScope {
    ObjCtx c;
    ObjCtx *prev;
    ObjScope() : prev(objctx()) { objctx() = &c; }
    ~ObjScope() { objctx() = prev; }
    ObjScope(const ObjScope &) = delete;
    ObjScope &operator=(const ObjScope &) = delete;
    void writeback() { for (size_t i = 0; i < c.wb.size(); ++i) c.wb[i](); }
};
inline py::object getattr_fb(PyObject *o, const char *name) {
    PyObject *v = PyObject_GetAttrString(o, name);
    if (!v) {
        PyErr_Clear();
        std::string m = std::string("attribute '") + name + "' is not set on the object";
        fallback(m.c_str());
    }
    return steal(v);
}
inline py::object class_attr(PyObject *cls, const char *name) {      // the class's own attribute (its __dict__)
    py::object d = steal(PyObject_GetAttrString(cls, "__dict__"));
    PyObject *v = PyMapping_GetItemString(d.ptr(), name);
    if (!v) { PyErr_Clear(); std::string m = std::string("class attribute '") + name + "' is missing"; fallback(m.c_str()); }
    return steal(v);
}
inline void setattr_(PyObject *o, const char *name, PyObject *v) {
    if (PyObject_SetAttrString(o, name, v) < 0) throw py::error_already_set();
}
template <class T> void track(const typename T::C &v, PyObject *py) {      // a container that came from Python
    if (v) {
        objctx()->conts[static_cast<const void *>(v)] = py;
        objctx()->keep.push_back(py::reinterpret_borrow<py::object>(py));
    }
}
template <class T> void put_field(PyObject *o, const char *name, const typename T::C &v) {
    py::object x = steal(T::out(v));
    setattr_(o, name, x.ptr());
}
template <class T> void put_cont(PyObject *o, const char *name, const typename T::C &v) {
    ObjCtx *c = objctx();
    if (v) {
        auto it = c->conts.find(static_cast<const void *>(v));
        if (it != c->conts.end()) { T::back(it->second, v); setattr_(o, name, it->second); return; }
    }
    put_field<T>(o, name, v);
}

}  // namespace pyb
#endif
