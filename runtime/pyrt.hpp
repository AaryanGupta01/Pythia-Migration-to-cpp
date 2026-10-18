#ifndef PYRT_HPP
#define PYRT_HPP

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <exception>
#include <limits>
#include <functional>
#include <memory>
#include <optional>
#include <unordered_set>
#include <string>
#include <utility>
#include <vector>

namespace pyrt {

class PythonException : public std::exception {
public:
    PythonException(const char *name, std::string message)
        : name_(name), message_(std::move(message)), what_(name_ + ": " + message_) {}
    const char *what() const noexcept override { return what_.c_str(); }
    const std::string &name() const noexcept { return name_; }
    const std::string &message() const noexcept { return message_; }
private:
    std::string name_;
    std::string message_;
    std::string what_;
};

class IndexError : public PythonException { public: explicit IndexError(const char *m) : PythonException("IndexError", m) {} };
class ZeroDivisionError : public PythonException { public: explicit ZeroDivisionError(const char *m) : PythonException("ZeroDivisionError", m) {} };
class OverflowError : public PythonException { public: explicit OverflowError(const char *m) : PythonException("OverflowError", m) {} };
class ValueError : public PythonException { public: explicit ValueError(const char *m) : PythonException("ValueError", m) {} };
class KeyError : public PythonException { public: explicit KeyError(const char *m) : PythonException("KeyError", m) {} };
class PythiaSemanticError : public PythonException { public: explicit PythiaSemanticError(const char *m) : PythonException("PythiaSemanticError", m) {} };

// Optional per-call arena (used only by library/extension-module wrappers).
// Inactive by default: allocation then behaves exactly as plain `new` and
// nothing is ever freed (divergence D7).  While active, every PyStr / list /
// dict created through arena_new is freed by the matching arena_end().
extern bool arena_active;
void arena_push(void *p, void (*del)(void *));
void arena_begin();
void arena_end();
template <class T, class... A> T *arena_new(A &&...a) {
    T *p = new T(std::forward<A>(a)...);
    if (arena_active) arena_push(p, [](void *q) { delete static_cast<T *>(q); });
    return p;
}

[[noreturn]] void py_raise(const char *exc, const char *msg);

// CPython minor version whose error texts to reproduce (3.11-3.14 word ZeroDivisionError differently).
extern int py_minor;
void pyrt_set_py_minor(int minor);
std::string py_repr_str(const std::string &s);
std::string py_float_repr(double v);
[[noreturn]] void py_raise_pystr(const char *exc, const struct PyStr *msg);

struct PyStr { std::string data; };
PyStr *pystr_new(const char *s, int64_t len);
PyStr *pystr_lit(const char *s);
PyStr *pystr_concat(PyStr *, PyStr *);
PyStr *pystr_repeat(PyStr *, int64_t);
PyStr *pystr_index(PyStr *, int64_t);
PyStr *pystr_upper(PyStr *);
PyStr *pystr_lower(PyStr *);
int64_t pystr_len(PyStr *);
int pystr_cmp(PyStr *, PyStr *);
bool pystr_truthy(PyStr *);
bool pystr_contains(PyStr *, PyStr *);
PyStr *pystr_from_i64(int64_t);
PyStr *pystr_from_f64(double);
PyStr *pystr_from_bool(bool);
int64_t py_i64_from_str(PyStr *);
double py_f64_from_str(PyStr *);

template <typename T> struct PyList {
    std::vector<T> data;
    int64_t size() const { return static_cast<int64_t>(data.size()); }
    int64_t index(int64_t i) const {
        int64_t j = i < 0 ? size() + i : i;
        if (j < 0 || j >= size()) throw IndexError("list index out of range");
        return j;
    }
};
using PyListI64 = PyList<int64_t>;
using PyListF64 = PyList<double>;
using PyListBool = PyList<bool>;
using PyListStr = PyList<PyStr *>;
using PyListList = PyList<void *>;

#define PYRT_DECL_LIST(NAME, T) \
    NAME *NAME##_new(void); void NAME##_append(NAME *, T); T NAME##_get(NAME *, int64_t); \
    void NAME##_set(NAME *, int64_t, T); T NAME##_pop(NAME *); NAME *NAME##_concat(NAME *, NAME *); \
    bool NAME##_eq(NAME *, NAME *); bool NAME##_contains(NAME *, T);
PYRT_DECL_LIST(PyListI64, int64_t)
PYRT_DECL_LIST(PyListF64, double)
PYRT_DECL_LIST(PyListBool, bool)
PYRT_DECL_LIST(PyListStr, PyStr *)
PyListList *PyListList_new(void); void PyListList_append(PyListList *, void *); void *PyListList_get(PyListList *, int64_t);
void PyListList_set(PyListList *, int64_t, void *); void *PyListList_pop(PyListList *); PyListList *PyListList_concat(PyListList *, PyListList *);

#define PYRT_DECL_DICT(NAME, KT, VT) \
    struct NAME { std::vector<KT> keys; std::vector<VT> vals; int64_t size() const { return static_cast<int64_t>(keys.size()); } }; \
    NAME *NAME##_new(void); void NAME##_set(NAME *, KT, VT); VT NAME##_get(NAME *, KT); VT NAME##_get_default(NAME *, KT, VT); bool NAME##_contains(NAME *, KT);
PYRT_DECL_DICT(PyDictIntInt, int64_t, int64_t)
PYRT_DECL_DICT(PyDictIntFloat, int64_t, double)
PYRT_DECL_DICT(PyDictIntBool, int64_t, bool)
PYRT_DECL_DICT(PyDictIntStr, int64_t, PyStr *)
PYRT_DECL_DICT(PyDictStrInt, PyStr *, int64_t)
PYRT_DECL_DICT(PyDictStrFloat, PyStr *, double)
PYRT_DECL_DICT(PyDictStrBool, PyStr *, bool)
PYRT_DECL_DICT(PyDictStrStr, PyStr *, PyStr *)

int64_t py_floordiv_i64(int64_t, int64_t); int64_t py_mod_i64(int64_t, int64_t);
int64_t py_add_i64(int64_t, int64_t); int64_t py_sub_i64(int64_t, int64_t); int64_t py_mul_i64(int64_t, int64_t);
int64_t py_pow_i64(int64_t, int64_t); int64_t py_neg_i64(int64_t); int64_t py_abs_i64(int64_t);
double py_truediv(double, double); double py_truediv_ii(double, double); double py_floordiv_f64(double, double); double py_mod_f64(double, double); double py_pow_f64(double, double);

void py_print_begin(); void py_print_sep(); void py_print_end(); void py_print_i64(int64_t); void py_print_f64(double); void py_print_bool(bool); void py_print_str(PyStr *);
void py_print_list_i64(PyListI64 *); void py_print_list_f64(PyListF64 *); void py_print_list_bool(PyListBool *); void py_print_list_str(PyListStr *);
void py_print_list_generic(PyListList *, void (*)(void *));
void py_print_exception(const PythonException &);
void py_print_dict_intint(PyDictIntInt *); void py_print_dict_intfloat(PyDictIntFloat *); void py_print_dict_intbool(PyDictIntBool *); void py_print_dict_intstr(PyDictIntStr *);
void py_print_dict_strint(PyDictStrInt *); void py_print_dict_strfloat(PyDictStrFloat *); void py_print_dict_strbool(PyDictStrBool *); void py_print_dict_strstr(PyDictStrStr *);

// ---- PySub 1.1: input(), str methods, format(), round(), sum(), list methods, lists of class instances ----
class EOFError : public PythonException { public: explicit EOFError(const char *m) : PythonException("EOFError", m) {} };
PyStr *py_input(PyStr *prompt);
void py_print_sep_s(PyStr *sep); void py_print_end_s(PyStr *end);
PyStr *pystr_strip(PyStr *); PyStr *pystr_lstrip(PyStr *); PyStr *pystr_rstrip(PyStr *);
PyStr *pystr_strip_chars(PyStr *, PyStr *); PyStr *pystr_lstrip_chars(PyStr *, PyStr *); PyStr *pystr_rstrip_chars(PyStr *, PyStr *);
PyStr *pystr_title(PyStr *); PyStr *pystr_capitalize(PyStr *); PyStr *pystr_swapcase(PyStr *);
bool pystr_isdigit(PyStr *); bool pystr_isalpha(PyStr *); bool pystr_isalnum(PyStr *); bool pystr_isspace(PyStr *);
bool pystr_isupper(PyStr *); bool pystr_islower(PyStr *);
bool pystr_startswith(PyStr *, PyStr *); bool pystr_endswith(PyStr *, PyStr *);
int64_t pystr_find(PyStr *, PyStr *); int64_t pystr_rfind(PyStr *, PyStr *); int64_t pystr_index_of(PyStr *, PyStr *);
int64_t pystr_count(PyStr *, PyStr *);
PyStr *pystr_replace(PyStr *, PyStr *, PyStr *);
PyListStr *pystr_split_ws(PyStr *); PyListStr *pystr_split(PyStr *, PyStr *);
PyStr *pystr_join(PyStr *, PyListStr *);
PyStr *py_format_i64(int64_t, PyStr *); PyStr *py_format_f64(double, PyStr *); PyStr *py_format_str(PyStr *, PyStr *);
PyStr *py_format_bool(bool, PyStr *);
int64_t py_round_i64(double); double py_round_f64(double, int64_t); int64_t py_round_int_n(int64_t, int64_t);
int64_t py_sum_i64(PyListI64 *); int64_t py_sum_bool(PyListBool *); double py_sum_f64(PyListF64 *);

// Generic list helpers for any PyList<T>: the list methods, and every operation on lists of class instances
// (PyList<std::shared_ptr<C>>).  Equality is value equality for str/numbers and identity for objects, as in
// CPython for classes without __eq__.
inline std::string py_value_repr(int64_t v) { return std::to_string(v); }
inline std::string py_value_repr(double v) { return py_float_repr(v); }
inline std::string py_value_repr(bool v) { return v ? "True" : "False"; }
inline std::string py_value_repr(PyStr *const &v) { return py_repr_str(v->data); }
template <class T> std::string py_value_repr(const T &) { return "<object>"; }
inline bool pyl_eqv(PyStr *const &a, PyStr *const &b) { return pystr_cmp(a, b) == 0; }
template <class T> bool pyl_eqv(const T &a, const T &b) { return a == b; }
inline bool pyl_lt(PyStr *const &a, PyStr *const &b) { return pystr_cmp(a, b) < 0; }
template <class T> bool pyl_lt(const T &a, const T &b) { return a < b; }
template <class T> PyList<T> *pyl_new() { return arena_new<PyList<T>>(); }
template <class T, class U> void pyl_append(PyList<T> *l, const U &v) { l->data.push_back(static_cast<T>(v)); }
template <class T> T pyl_get(PyList<T> *l, int64_t i) { return l->data[static_cast<size_t>(l->index(i))]; }
template <class T, class U> void pyl_set(PyList<T> *l, int64_t i, const U &v) { l->data[static_cast<size_t>(l->index(i))] = static_cast<T>(v); }
template <class T> T pyl_pop(PyList<T> *l) {
    if (l->data.empty()) throw IndexError("pop from empty list");
    T v = l->data.back(); l->data.pop_back(); return v;
}
template <class T> T pyl_pop_at(PyList<T> *l, int64_t i) {
    if (l->data.empty()) throw IndexError("pop from empty list");
    int64_t j = i < 0 ? l->size() + i : i;
    if (j < 0 || j >= l->size()) throw IndexError("pop index out of range");
    T v = l->data[static_cast<size_t>(j)]; l->data.erase(l->data.begin() + j); return v;
}
template <class T, class U> void pyl_insert(PyList<T> *l, int64_t i, const U &u) {
    T v = static_cast<T>(u);
    int64_t n = l->size();
    if (i < 0) { i += n; if (i < 0) i = 0; }
    if (i > n) i = n;
    l->data.insert(l->data.begin() + i, v);
}
template <class T> void pyl_clear(PyList<T> *l) { l->data.clear(); }
template <class T> void pyl_extend(PyList<T> *l, PyList<T> *o) {
    std::vector<T> tmp = o->data;                       // xs.extend(xs) must see the old contents
    l->data.insert(l->data.end(), tmp.begin(), tmp.end());
}
template <class T> void pyl_reverse(PyList<T> *l) { std::reverse(l->data.begin(), l->data.end()); }
template <class T> PyList<T> *pyl_copy(PyList<T> *l) { auto *r = pyl_new<T>(); r->data = l->data; return r; }
template <class T> PyList<T> *pyl_concat(PyList<T> *a, PyList<T> *b) {
    auto *r = pyl_new<T>(); r->data = a->data; r->data.insert(r->data.end(), b->data.begin(), b->data.end()); return r;
}
template <class T, class U> int64_t pyl_index(PyList<T> *l, const U &u) {
    T v = static_cast<T>(u);
    for (size_t i = 0; i < l->data.size(); ++i) if (pyl_eqv(l->data[i], v)) return static_cast<int64_t>(i);
    throw ValueError((py_minor >= 14 ? std::string("list.index(x): x not in list") : py_value_repr(v) + " is not in list").c_str());
}
template <class T, class U> int64_t pyl_count(PyList<T> *l, const U &u) {
    T v = static_cast<T>(u);
    int64_t n = 0; for (const T &x : l->data) if (pyl_eqv(x, v)) ++n; return n;
}
template <class T, class U> void pyl_remove(PyList<T> *l, const U &u) {
    T v = static_cast<T>(u);
    for (size_t i = 0; i < l->data.size(); ++i)
        if (pyl_eqv(l->data[i], v)) { l->data.erase(l->data.begin() + static_cast<std::ptrdiff_t>(i)); return; }
    throw ValueError("list.remove(x): x not in list");
}
template <class T, class U> bool pyl_contains(PyList<T> *l, const U &u) {
    T v = static_cast<T>(u);
    for (const T &x : l->data) if (pyl_eqv(x, v)) return true; return false;
}
template <class T> bool pyl_eq(PyList<T> *a, PyList<T> *b) {
    if (a->data.size() != b->data.size()) return false;
    for (size_t i = 0; i < a->data.size(); ++i) if (!pyl_eqv(a->data[i], b->data[i])) return false;
    return true;
}
template <class T> void pyl_sort(PyList<T> *l, bool rev) {   // CPython: stable; reverse=True = reverse, sort, reverse
    if (rev) std::reverse(l->data.begin(), l->data.end());
    std::stable_sort(l->data.begin(), l->data.end(), [](const T &a, const T &b) { return pyl_lt(a, b); });
    if (rev) std::reverse(l->data.begin(), l->data.end());
}
template <class T> PyList<T> *pyl_sorted(PyList<T> *l, bool rev) { auto *r = pyl_copy(l); pyl_sort(r, rev); return r; }
// list(s) / sorted(s): one-character strings; list(d) / sorted(d): the keys in insertion order
inline PyListStr *pyl_chars(PyStr *s) {
    auto *r = pyl_new<PyStr *>();
    for (size_t i = 0; i < s->data.size(); ++i) r->data.push_back(pystr_new(s->data.data() + i, 1));
    return r;
}
// ord()/chr() on ASCII; other code points raise PythiaSemanticError (compiled strings are bytes, D13)
inline int64_t py_ord(PyStr *s) {
    if (!s->data.empty() && static_cast<unsigned char>(s->data[0]) >= 0x80)
        throw PythiaSemanticError("ord() of a non-ASCII character is outside PySub (compiled strings are ASCII)");
    if (s->data.size() != 1)
        throw PythonException("TypeError", "ord() expected a character, but string of length " + std::to_string(s->data.size()) + " found");
    return static_cast<unsigned char>(s->data[0]);
}
inline PyStr *py_chr(int64_t i) {
    if (i < 0 || i >= 0x110000) throw ValueError("chr() arg not in range(0x110000)");
    if (i >= 0x80) throw PythiaSemanticError("chr() of a non-ASCII code point is outside PySub (compiled strings are ASCII)");
    char c = static_cast<char>(i);
    return pystr_new(&c, 1);
}
template <class D> auto *pyl_keys(D *d) {
    auto *r = pyl_new<typename decltype(d->keys)::value_type>(); r->data = d->keys; return r;
}
template <class T> T pyl_min(PyList<T> *l) {
    if (l->data.empty()) throw ValueError("min() iterable argument is empty");
    T r = l->data[0]; for (size_t i = 1; i < l->data.size(); ++i) if (pyl_lt(l->data[i], r)) r = l->data[i]; return r;
}
template <class T> T pyl_max(PyList<T> *l) {
    if (l->data.empty()) throw ValueError("max() iterable argument is empty");
    T r = l->data[0]; for (size_t i = 1; i < l->data.size(); ++i) if (pyl_lt(r, l->data[i])) r = l->data[i]; return r;
}


// ---- PySub 1.3: None, nullable objects, module-level names, mutable defaults ---------------------------------
inline void py_print_none() { py_print_str(pystr_lit("None")); }
[[noreturn]] inline void py_none_attr(const char *attr, bool set) {
    std::string m = std::string("'NoneType' object has no attribute '") + attr + "'";
    if (set && py_minor >= 13) m += " and no __dict__ for setting new attributes";
    throw PythonException("AttributeError", m);
}
// obj.attr / obj.method(...) on a class reference: None raises AttributeError exactly like CPython
template <class P> inline const P &py_nn(const P &p, const char *attr) { if (!p) py_none_attr(attr, false); return p; }
template <class P> inline const P &py_nn_set(const P &p, const char *attr) { if (!p) py_none_attr(attr, true); return p; }
inline void py_global_ok(bool ok, const char *name) {
    if (!ok) throw PythonException("NameError", std::string("name '") + name + "' is not defined");
}
// a mutable default value lives for the whole program, even when first built inside a library-call arena
struct ArenaPause {
    bool saved;
    ArenaPause() : saved(arena_active) { arena_active = false; }
    ~ArenaPause() { arena_active = saved; }
};

// ---- set[T] (T = int64_t / double / bool / PyStr *).  No operation exposes iteration order. ---------------
struct PyStrHash { size_t operator()(PyStr *s) const { return std::hash<std::string>()(s->data); } };
struct PyStrEq { bool operator()(PyStr *a, PyStr *b) const { return a->data == b->data; } };
template <class T> struct py_hash { using H = std::hash<T>; using E = std::equal_to<T>; };
template <> struct py_hash<PyStr *> { using H = PyStrHash; using E = PyStrEq; };
template <class T> struct PySet {
    std::unordered_set<T, typename py_hash<T>::H, typename py_hash<T>::E> s;
    int64_t size() const { return static_cast<int64_t>(s.size()); }
};
template <class T> PySet<T> *pyset_new() { return arena_new<PySet<T>>(); }
template <class T, class U> void pyset_add(PySet<T> *s, const U &v) { s->s.insert(static_cast<T>(v)); }
template <class T, class U> bool pyset_contains(PySet<T> *s, const U &v) { return s->s.count(static_cast<T>(v)) != 0; }
template <class T, class U> void pyset_discard(PySet<T> *s, const U &v) { s->s.erase(static_cast<T>(v)); }
template <class T, class U> void pyset_remove(PySet<T> *s, const U &u) {
    T v = static_cast<T>(u);
    if (!s->s.erase(v)) throw KeyError(py_value_repr(v).c_str());
}
template <class T> void pyset_clear(PySet<T> *s) { s->s.clear(); }
template <class T> PySet<T> *pyset_copy(PySet<T> *a) { auto *r = pyset_new<T>(); r->s = a->s; return r; }
// set(x) / s.update(x) / s.union(x) ...: x is a set or a list
template <class T, class U> PySet<T> *pyset_of(PySet<U> *o) { auto *r = pyset_new<T>(); for (const U &x : o->s) r->s.insert(static_cast<T>(x)); return r; }
template <class T, class U> PySet<T> *pyset_of(PyList<U> *o) { auto *r = pyset_new<T>(); for (const U &x : o->data) r->s.insert(static_cast<T>(x)); return r; }
template <class T> PySet<T> *pyset_of_chars(PyStr *s) {
    auto *r = pyset_new<T>();
    for (size_t i = 0; i < s->data.size(); ++i) r->s.insert(pystr_new(s->data.data() + i, 1));
    return r;
}
template <class T, class D> PySet<T> *pyset_of_keys(D *d) { auto *r = pyset_new<T>(); for (const auto &k : d->keys) r->s.insert(k); return r; }
template <class T> PySet<T> *pyset_ior(PySet<T> *a, PySet<T> *b) { if (a != b) for (const T &x : b->s) a->s.insert(x); return a; }
template <class T> PySet<T> *pyset_iand(PySet<T> *a, PySet<T> *b) {
    for (auto it = a->s.begin(); it != a->s.end();) it = b->s.count(*it) ? std::next(it) : a->s.erase(it);
    return a;
}
template <class T> PySet<T> *pyset_isub(PySet<T> *a, PySet<T> *b) {
    if (a == b) { a->s.clear(); return a; }
    for (const T &x : b->s) a->s.erase(x);
    return a;
}
template <class T> PySet<T> *pyset_ixor(PySet<T> *a, PySet<T> *b) {
    if (a == b) { a->s.clear(); return a; }
    for (const T &x : b->s) if (!a->s.erase(x)) a->s.insert(x);
    return a;
}
template <class T> PySet<T> *pyset_or(PySet<T> *a, PySet<T> *b) { return pyset_ior(pyset_copy(a), b); }
template <class T> PySet<T> *pyset_and(PySet<T> *a, PySet<T> *b) { return pyset_iand(pyset_copy(a), b); }
template <class T> PySet<T> *pyset_sub(PySet<T> *a, PySet<T> *b) { return pyset_isub(pyset_copy(a), b); }
template <class T> PySet<T> *pyset_xor(PySet<T> *a, PySet<T> *b) { return pyset_ixor(pyset_copy(a), b); }
template <class T> bool pyset_le(PySet<T> *a, PySet<T> *b) {
    if (a->s.size() > b->s.size()) return false;
    for (const T &x : a->s) if (!b->s.count(x)) return false;
    return true;
}
template <class T> bool pyset_eq(PySet<T> *a, PySet<T> *b) { return a->s.size() == b->s.size() && pyset_le(a, b); }
template <class T> bool pyset_lt(PySet<T> *a, PySet<T> *b) { return a->s.size() < b->s.size() && pyset_le(a, b); }
template <class T> bool pyset_disjoint(PySet<T> *a, PySet<T> *b) {
    for (const T &x : a->s) if (b->s.count(x)) return false;
    return true;
}
template <class T> PyList<T> *pyset_sorted(PySet<T> *s, bool rev) {
    auto *r = pyl_new<T>();
    r->data.assign(s->s.begin(), s->s.end());
    pyl_sort(r, rev);
    return r;
}

// ---- dict[K, V] for any V (lists, dicts, sets, objects): one alias + functions per type, like PYRT_DECL_DICT --
template <class K, class V> struct PyDictG {
    std::vector<K> keys;
    std::vector<V> vals;
    int64_t size() const { return static_cast<int64_t>(keys.size()); }
};
template <class D, class K> int64_t pyd_find(D *d, const K &k) {
    for (size_t i = 0; i < d->keys.size(); ++i) if (pyl_eqv(d->keys[i], k)) return static_cast<int64_t>(i);
    return -1;
}
#define PYRT_DICTG(NAME, KT, VT) \
    using NAME = PyDictG<KT, VT>; \
    inline NAME *NAME##_new() { return arena_new<NAME>(); } \
    inline void NAME##_set(NAME *d, KT k, VT v) { \
        int64_t i = pyd_find(d, k); \
        if (i < 0) { d->keys.push_back(k); d->vals.push_back(v); } else d->vals[static_cast<size_t>(i)] = v; } \
    inline VT NAME##_get(NAME *d, KT k) { \
        int64_t i = pyd_find(d, k); \
        if (i < 0) throw KeyError(py_value_repr(k).c_str()); \
        return d->vals[static_cast<size_t>(i)]; } \
    inline VT NAME##_get_default(NAME *d, KT k, VT v) { int64_t i = pyd_find(d, k); return i < 0 ? v : d->vals[static_cast<size_t>(i)]; } \
    inline bool NAME##_contains(NAME *d, KT k) { return pyd_find(d, k) >= 0; }

// repr() of numbers, str, lists of those and dicts of any of these (print(d) for dict[K, list[int]] etc.)
inline void py_repr_into(std::string &o, int64_t v) { o += std::to_string(v); }
inline void py_repr_into(std::string &o, double v) { o += py_float_repr(v); }
inline void py_repr_into(std::string &o, bool v) { o += v ? "True" : "False"; }
inline void py_repr_into(std::string &o, PyStr *v) { o += py_repr_str(v->data); }
template <class T> void py_repr_into(std::string &o, const std::optional<T> &v) { if (v) py_repr_into(o, *v); else o += "None"; }
template <class T> void py_repr_into(std::string &o, PyList<T> *l) {
    o += '[';
    for (size_t i = 0; i < l->data.size(); ++i) { if (i) o += ", "; py_repr_into(o, l->data[i]); }
    o += ']';
}
template <class D> auto py_repr_into(std::string &o, D *d) -> decltype((void)d->keys, void()) {
    o += '{';
    for (size_t i = 0; i < d->keys.size(); ++i) {
        if (i) o += ", ";
        py_repr_into(o, d->keys[i]); o += ": "; py_repr_into(o, d->vals[i]);
    }
    o += '}';
}
template <class T> void py_print_repr(const T &v) { std::string s; py_repr_into(s, v); py_print_str(pystr_new(s.data(), static_cast<int64_t>(s.size()))); }

} // namespace pyrt
using namespace pyrt;
#endif