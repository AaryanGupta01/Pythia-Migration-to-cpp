#ifndef PYRT_HPP
#define PYRT_HPP

#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <exception>
#include <limits>
#include <memory>
#include <string>
#include <tuple>
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
class ZeroDivisionError : public PythonException { public: explicit ZeroDivisionError(const char *m) : PythonException("ZeroDivisionError", m) {} explicit ZeroDivisionError(const std::string &m) : PythonException("ZeroDivisionError", m) {} };
class OverflowError : public PythonException { public: explicit OverflowError(const char *m) : PythonException("OverflowError", m) {} explicit OverflowError(const std::string &m) : PythonException("OverflowError", m) {} };
class ValueError : public PythonException { public: explicit ValueError(const char *m) : PythonException("ValueError", m) {} explicit ValueError(const std::string &m) : PythonException("ValueError", m) {} };
class KeyError : public PythonException { public: explicit KeyError(const char *m) : PythonException("KeyError", m) {} explicit KeyError(const std::string &m) : PythonException("KeyError", m) {} };
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

// Tuples are std::tuple values.  These overloads must be declared before the generic list helpers below,
// which bind pyl_eqv/pyl_lt/py_value_repr at their point of definition (definitions at the end of the file).
template <class... T> std::string py_value_repr(const std::tuple<T...> &);
template <class T> std::string py_value_repr(PyList<T> *const &);
template <class D> auto py_value_repr(D *const &d) -> decltype(d->vals, std::string());   // any dict
template <class... T> bool pyl_eqv(const std::tuple<T...> &, const std::tuple<T...> &);
template <class... T> bool pyl_lt(const std::tuple<T...> &, const std::tuple<T...> &);

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
// ======================================================================================================
// px_*: builtins / standard-library surface (math, bit operations, slicing, str / list / dict methods, pow,
// int(s, base), bin/hex/oct, format codes x X o b).  Header-only; every error text is CPython's, with the
// texts that changed between CPython versions chosen by py_minor.
// ======================================================================================================
inline PyStr *px_str(std::string s) { return arena_new<PyStr>(PyStr{std::move(s)}); }
[[noreturn]] inline void px_type_error(const std::string &m) { throw PythonException("TypeError", m); }
inline bool px_space(char c) { return c == ' ' || (c >= '\t' && c <= '\r') || (c >= '\x1c' && c <= '\x1f'); }

// ---- int <-> float conversions -----------------------------------------------------------------
inline int64_t px_f2i(double x) {               // int(x) / math.trunc(x): truncate, with CPython's errors
    if (std::isnan(x)) throw ValueError("cannot convert float NaN to integer");
    if (std::isinf(x)) throw OverflowError("cannot convert float infinity to integer");
    if (x >= 9223372036854775808.0 || x <= -9223372036854775809.0) throw OverflowError("int64 overflow");
    return static_cast<int64_t>(x);
}
inline int64_t px_floor_i(double x) { if (std::isfinite(x)) x = std::floor(x); return px_f2i(x); }
inline int64_t px_ceil_i(double x) { if (std::isfinite(x)) x = std::ceil(x); return px_f2i(x); }

// ---- bitwise shifts (Python semantics on int64; results beyond int64 raise OverflowError, D1) ------
inline int64_t px_lshift(int64_t a, int64_t n) {
    if (n < 0) throw ValueError("negative shift count");
    if (a == 0) return 0;
    if (n >= 64) throw OverflowError("int64 overflow");
    int64_t r = static_cast<int64_t>(static_cast<uint64_t>(a) << n);
    if ((r >> n) != a) throw OverflowError("int64 overflow");
    return r;
}
inline int64_t px_rshift(int64_t a, int64_t n) {
    if (n < 0) throw ValueError("negative shift count");
    if (n >= 64) return a < 0 ? -1 : 0;
    return a >> n;
}

// ---- math module -------------------------------------------------------------------------------
[[noreturn]] inline void px_domain() { throw ValueError("math domain error"); }
[[noreturn]] inline void px_range() { throw OverflowError("math range error"); }
[[noreturn]] inline void px_domain_got(const char *msg, double x) {          // 3.14 words domain errors precisely
    if (py_minor >= 14) throw ValueError(std::string(msg) + ", got " + py_float_repr(x));
    px_domain();
}
inline double px_m1(double x, double (*f)(double), bool can_overflow) {     // CPython's math_1 error mapping
    double r = f(x);
    if (std::isnan(r) && !std::isnan(x)) px_domain();
    if (std::isinf(r) && std::isfinite(x)) { if (can_overflow) px_range(); px_domain(); }
    return r;
}
inline double px_sqrt(double x) { if (x < 0) px_domain_got("expected a nonnegative input", x); return std::sqrt(x); }
inline double px_exp(double x) { return px_m1(x, [](double v) { return std::exp(v); }, true); }
inline double px_logchk(double x, bool isint, double (*f)(double)) {        // log/log2/log10 of an int or a float
    if (x <= 0) {
        if (py_minor >= 14) throw ValueError(isint ? std::string("expected a positive input")
                                                    : "expected a positive input, got " + py_float_repr(x));
        px_domain();
    }
    return f(x);
}
inline double px_log(double x, bool xi) { return px_logchk(x, xi, [](double v) { return std::log(v); }); }
inline double px_log_b(double x, bool xi, double b, bool bi) {
    double num = px_log(x, xi), den = px_log(b, bi);
    return py_truediv(num, den);
}
inline double px_log2(double x, bool xi) { return px_logchk(x, xi, [](double v) { return std::log2(v); }); }
inline double px_log10(double x, bool xi) { return px_logchk(x, xi, [](double v) { return std::log10(v); }); }
inline double px_trig(double x, double (*f)(double)) {
    if (std::isinf(x)) px_domain_got("expected a finite input", x);
    return f(x);
}
inline double px_sin(double x) { return px_trig(x, [](double v) { return std::sin(v); }); }
inline double px_cos(double x) { return px_trig(x, [](double v) { return std::cos(v); }); }
inline double px_tan(double x) { return px_trig(x, [](double v) { return std::tan(v); }); }
inline double px_asin(double x) { if (x < -1.0 || x > 1.0 || std::isinf(x)) px_domain_got("expected a number in range from -1 up to 1", x); return std::asin(x); }
inline double px_acos(double x) { if (x < -1.0 || x > 1.0 || std::isinf(x)) px_domain_got("expected a number in range from -1 up to 1", x); return std::acos(x); }
inline double px_atan(double x) { return std::atan(x); }
inline double px_atan2(double y, double x) { return std::atan2(y, x); }
inline double px_sinh(double x) { return px_m1(x, [](double v) { return std::sinh(v); }, true); }
inline double px_cosh(double x) { return px_m1(x, [](double v) { return std::cosh(v); }, true); }
inline double px_tanh(double x) { return std::tanh(x); }
inline double px_asinh(double x) { return std::asinh(x); }
inline double px_acosh(double x) { if (x < 1.0) px_domain_got("expected argument value not less than 1", x); return std::acosh(x); }
inline double px_atanh(double x) { if (!(x > -1.0 && x < 1.0) && !std::isnan(x)) px_domain_got("expected a number between -1 and 1", x); return std::atanh(x); }
inline double px_log1p(double x) { if (x <= -1.0) px_domain_got("expected argument value > -1", x); return std::log1p(x); }
inline double px_expm1(double x) { return px_m1(x, [](double v) { return std::expm1(v); }, true); }
inline double px_degrees(double x) { return x * (180.0 / 3.141592653589793); }
inline double px_radians(double x) { return x * (3.141592653589793 / 180.0); }
inline double px_fabs(double x) { return std::fabs(x); }
inline double px_copysign(double x, double y) { return std::copysign(x, y); }
inline double px_hypot(double x, double y) {
    double r = std::hypot(x, y);
    if (std::isinf(r) && std::isfinite(x) && std::isfinite(y)) px_range();
    return r;
}
inline double px_fmod(double x, double y) {
    if (std::isinf(y) && std::isfinite(x)) return x;
    double r = std::fmod(x, y);
    if (std::isnan(r) && !std::isnan(x) && !std::isnan(y)) px_domain();
    return r;
}
inline double px_math_pow(double x, double y) {                              // math.pow
    if (!std::isfinite(x) || !std::isfinite(y)) return std::pow(x, y);
    double r = std::pow(x, y);
    if (std::isnan(r)) px_domain();
    if (std::isinf(r)) { if (x == 0.0) px_domain(); px_range(); }
    return r;
}
inline bool px_isclose(double a, double b, double rel, double abs_) {
    if (rel < 0.0 || abs_ < 0.0) throw ValueError("tolerances must be non-negative");
    if (a == b) return true;
    if (std::isinf(a) || std::isinf(b)) return false;
    double d = std::fabs(b - a);
    return ((d <= std::fabs(rel * b)) || (d <= std::fabs(rel * a))) || d <= abs_;
}
inline int64_t px_isqrt(int64_t n) {
    if (n < 0) throw ValueError("isqrt() argument must be nonnegative");
    int64_t r = static_cast<int64_t>(std::sqrt(static_cast<double>(n)));
    while (static_cast<__int128>(r) * r > n) --r;
    while (static_cast<__int128>(r + 1) * (r + 1) <= n) ++r;
    return r;
}
inline int64_t px_factorial(int64_t n) {
    if (n < 0) throw ValueError("factorial() not defined for negative values");
    int64_t r = 1;
    for (int64_t i = 2; i <= n; ++i) r = py_mul_i64(r, i);
    return r;
}
inline int64_t px_comb(int64_t n, int64_t k) {
    if (n < 0) throw ValueError("n must be a non-negative integer");
    if (k < 0) throw ValueError("k must be a non-negative integer");
    if (k > n) return 0;
    if (k > n - k) k = n - k;
    __int128 r = 1;
    for (int64_t i = 1; i <= k; ++i) {
        r = r * (n - k + i) / i;
        if (r > INT64_MAX) throw OverflowError("int64 overflow");
    }
    return static_cast<int64_t>(r);
}
inline int64_t px_perm(int64_t n, int64_t k) {
    if (n < 0) throw ValueError("n must be a non-negative integer");
    if (k < 0) throw ValueError("k must be a non-negative integer");
    if (k > n) return 0;
    int64_t r = 1;
    for (int64_t i = 0; i < k; ++i) r = py_mul_i64(r, n - i);
    return r;
}
inline int64_t px_gcd(int64_t a, int64_t b) {
    uint64_t x = a < 0 ? 0 - static_cast<uint64_t>(a) : static_cast<uint64_t>(a);
    uint64_t y = b < 0 ? 0 - static_cast<uint64_t>(b) : static_cast<uint64_t>(b);
    while (y) { uint64_t t = x % y; x = y; y = t; }
    if (x > static_cast<uint64_t>(INT64_MAX)) throw OverflowError("int64 overflow");
    return static_cast<int64_t>(x);
}
inline int64_t px_lcm(int64_t a, int64_t b) {
    if (a == 0 || b == 0) return 0;
    int64_t g = px_gcd(a, b);
    return py_mul_i64(py_abs_i64(a) / g, py_abs_i64(b));
}

// ---- pow ----------------------------------------------------------------------------------------
inline double px_pow_f64(double x, double y) {                               // float ** float, builtin pow
    if (y == 0.0) return 1.0;
    if (std::isnan(x) || std::isnan(y) || std::isinf(x) || std::isinf(y)) return std::pow(x, y);
    if (x == 0.0 && y < 0.0)
        throw ZeroDivisionError(py_minor >= 14 ? "zero to a negative power" : "0.0 cannot be raised to a negative power");
    if (x < 0.0 && std::floor(y) != y)
        throw PythiaSemanticError("negative float ** non-integer yields a complex number in CPython; outside PySub");
    double r = std::pow(x, y);
    if (std::isinf(r)) throw OverflowError("(" + std::to_string(ERANGE) + ", '" + std::strerror(ERANGE) + "')");
    return r;
}
inline int64_t px_pow_mod(int64_t a, int64_t b, int64_t m) {                 // pow(a, b, m), 3.8+ semantics
    if (m == 0) throw ValueError("pow() 3rd argument cannot be 0");
    typedef __int128 I;
    I mm = m < 0 ? -static_cast<I>(m) : static_cast<I>(m);
    auto fmod_ = [&](I v) { I r = v % mm; if (r < 0) r += mm; return r; };   // in [0, |m|)
    I base = fmod_(a);
    if (b < 0) {                                                             // modular inverse of the base
        I old_r = base, r = mm, old_s = 1, s = 0;
        while (r != 0) { I q = old_r / r; I t = old_r - q * r; old_r = r; r = t; t = old_s - q * s; old_s = s; s = t; }
        if (old_r != 1) throw ValueError("base is not invertible for the given modulus");
        base = fmod_(old_s);
        uint64_t e = 0 - static_cast<uint64_t>(b);                           // |b|, exact even for INT64_MIN
        I res = 1 % mm;
        while (e) { if (e & 1) res = res * base % mm; base = base * base % mm; e >>= 1; }
        I out = res;
        if (m < 0 && out != 0) out -= mm;
        return static_cast<int64_t>(out);
    }
    I res = 1 % mm;
    uint64_t e = static_cast<uint64_t>(b);
    while (e) { if (e & 1) res = res * base % mm; base = base * base % mm; e >>= 1; }
    if (m < 0 && res != 0) res -= mm;
    return static_cast<int64_t>(res);
}

// ---- int(s, base), float(s), bin / hex / oct, repr -----------------------------------------------
inline int64_t px_int_from_str(PyStr *s, int64_t base) {
    const std::string &d = s->data;
    if (base != 0 && (base < 2 || base > 36)) throw ValueError("int() base must be >= 2 and <= 36, or 0");
    auto bad = [&]() { throw ValueError("invalid literal for int() with base " + std::to_string(base) + ": " + py_repr_str(d)); };
    size_t b = 0, e = d.size();
    while (b < e && px_space(d[b])) ++b;
    while (e > b && px_space(d[e - 1])) --e;
    bool neg = false;
    if (b < e && (d[b] == '+' || d[b] == '-')) { neg = d[b] == '-'; ++b; }
    int64_t bs = base;
    bool prefixed = false;
    if (b + 1 < e && d[b] == '0') {
        char p = static_cast<char>(d[b + 1] | 0x20);
        int pb = p == 'x' ? 16 : p == 'o' ? 8 : p == 'b' ? 2 : 0;
        if (pb && (base == 0 || base == pb)) { bs = pb; b += 2; prefixed = true; if (b < e && d[b] == '_') ++b; }
    }
    if (bs == 0) bs = 10;
    if (b >= e) bad();
    unsigned __int128 acc = 0;
    bool prev_us = false, any = false, nonzero = false;
    const unsigned __int128 lim = static_cast<unsigned __int128>(1) << 64;
    for (size_t i = b; i < e; ++i) {
        char c = d[i];
        if (c == '_') { if (!any || prev_us) bad(); prev_us = true; continue; }
        int v = c >= '0' && c <= '9' ? c - '0' : (c | 0x20) >= 'a' && (c | 0x20) <= 'z' ? (c | 0x20) - 'a' + 10 : 99;
        if (v >= bs) bad();
        prev_us = false; any = true;
        if (v) nonzero = true;
        if (acc < lim) acc = acc * static_cast<unsigned __int128>(bs) + static_cast<unsigned>(v);
    }
    if (prev_us || !any) bad();
    if (base == 0 && !prefixed && d[b] == '0' && nonzero) bad();             // '010' is not a base-0 literal
    unsigned __int128 maxp = neg ? static_cast<unsigned __int128>(1) << 63 : (static_cast<unsigned __int128>(1) << 63) - 1;
    if (acc > maxp) throw OverflowError("int64 overflow");
    return neg ? static_cast<int64_t>(0 - static_cast<uint64_t>(acc)) : static_cast<int64_t>(acc);
}
inline double px_f64_from_str(PyStr *s) {
    const std::string &d = s->data;
    auto bad = [&]() { throw ValueError("could not convert string to float: " + py_repr_str(d)); };
    size_t b = 0, e = d.size();
    while (b < e && px_space(d[b])) ++b;
    while (e > b && px_space(d[e - 1])) --e;
    std::string t;
    size_t i = b;
    if (i < e && (d[i] == '+' || d[i] == '-')) t += d[i++];
    std::string rest;
    for (size_t k = i; k < e; ++k) rest += static_cast<char>(d[k] >= 'A' && d[k] <= 'Z' ? d[k] | 0x20 : d[k]);
    if (rest == "inf" || rest == "infinity") return t == "-" ? -std::numeric_limits<double>::infinity() : std::numeric_limits<double>::infinity();
    if (rest == "nan") return t == "-" ? -std::numeric_limits<double>::quiet_NaN() : std::numeric_limits<double>::quiet_NaN();
    auto digits = [&](bool &got) {                                           // digits with single underscores between
        bool prev_us = false;
        got = false;
        while (i < e && (std::isdigit(static_cast<unsigned char>(d[i])) || d[i] == '_')) {
            if (d[i] == '_') { if (!got || prev_us) bad(); prev_us = true; ++i; continue; }
            prev_us = false; got = true; t += d[i++];
        }
        if (prev_us) bad();
    };
    bool ip = false, fp = false;
    digits(ip);
    if (i < e && d[i] == '.') { t += d[i++]; digits(fp); }
    if (!ip && !fp) bad();
    if (i < e && (d[i] == 'e' || d[i] == 'E')) {
        t += d[i++];
        if (i < e && (d[i] == '+' || d[i] == '-')) t += d[i++];
        bool ep = false;
        digits(ep);
        if (!ep) bad();
    }
    if (i != e) bad();
    return std::strtod(t.c_str(), nullptr);
}
inline PyStr *px_radix_str(int64_t v, int base) {                            // bin / oct / hex
    uint64_t m = v < 0 ? 0 - static_cast<uint64_t>(v) : static_cast<uint64_t>(v);
    std::string digs;
    do { digs += "0123456789abcdef"[m % static_cast<uint64_t>(base)]; m /= static_cast<uint64_t>(base); } while (m);
    std::reverse(digs.begin(), digs.end());
    return px_str(std::string(v < 0 ? "-" : "") + (base == 2 ? "0b" : base == 8 ? "0o" : "0x") + digs);
}
inline PyStr *px_repr_str_obj(PyStr *s) { return px_str(py_repr_str(s->data)); }
inline std::tuple<double, double> px_divmod_f64(double vx, double wx) {      // divmod(float, float), as float_divmod
    if (wx == 0.0) throw ZeroDivisionError(py_minor >= 14 ? "division by zero" : "float divmod()");
    double mod = std::fmod(vx, wx), div = (vx - mod) / wx, fl;
    if (mod) { if ((wx < 0) != (mod < 0)) { mod += wx; div -= 1.0; } }
    else mod = std::copysign(0.0, wx);
    if (div) { fl = std::floor(div); if (div - fl > 0.5) fl += 1.0; }
    else fl = std::copysign(0.0, vx / wx);
    return std::tuple<double, double>{fl, mod};
}

// format(int, spec) with the radix codes x X o b (all other int specs go to py_format_i64)
PyStr *py_format_i64(int64_t, PyStr *);
inline PyStr *px_format_i64(int64_t v, PyStr *spec) {
    const std::string &sp = spec->data;
    char t = sp.empty() ? 0 : sp.back();
    if (t != 'x' && t != 'X' && t != 'o' && t != 'b') return py_format_i64(v, spec);
    size_t i = 0, n = sp.size() - 1;
    char fill = ' ', align = 0, sign = '-';
    bool zero = false, fill_given = false;
    auto is_al = [](char c) { return c == '<' || c == '>' || c == '^' || c == '='; };
    if (n >= 2 && is_al(sp[1])) { fill = sp[0]; fill_given = true; align = sp[1]; i = 2; }
    else if (n >= 1 && is_al(sp[0])) { align = sp[0]; i = 1; }
    if (i < n && (sp[i] == '+' || sp[i] == '-' || sp[i] == ' ')) sign = sp[i++];
    if (i < n && sp[i] == '0') { zero = true; ++i; }
    int64_t width = 0;
    while (i < n && sp[i] >= '0' && sp[i] <= '9') width = width * 10 + (sp[i++] - '0');
    bool us = false;
    if (i < n && sp[i] == '_') { us = true; ++i; }
    if (i < n && sp[i] == ',') throw ValueError(std::string("Cannot specify ',' with '") + t + "'.");
    if (i < n && sp[i] == '.') throw ValueError("Precision not allowed in integer format specifier");
    if (i != n) throw ValueError("Invalid format specifier");
    uint64_t m = v < 0 ? 0 - static_cast<uint64_t>(v) : static_cast<uint64_t>(v);
    unsigned bs = t == 'b' ? 2 : t == 'o' ? 8 : 16;
    const char *dg = t == 'X' ? "0123456789ABCDEF" : "0123456789abcdef";
    std::string body;
    do { body += dg[m % bs]; m /= bs; } while (m);
    std::reverse(body.begin(), body.end());
    if (us) {
        size_t grp = bs == 8 || bs == 16 || bs == 2 ? 4 : 3, nn = body.size();
        std::string g;
        for (size_t k = 0; k < nn; ++k) { if (k && (nn - k) % grp == 0) g += '_'; g += body[k]; }
        body = g;
    }
    std::string sg = v < 0 ? "-" : sign == '+' ? "+" : sign == ' ' ? " " : "";
    if (zero && !fill_given) { fill = '0'; if (!align) align = '='; }
    if (!align) align = '>';
    std::string s = sg + body;
    if (width <= 0 || static_cast<int64_t>(s.size()) >= width) return px_str(s);
    size_t k = static_cast<size_t>(width) - s.size();
    switch (align) {
        case '<': return px_str(s + std::string(k, fill));
        case '>': return px_str(std::string(k, fill) + s);
        case '^': return px_str(std::string(k / 2, fill) + s + std::string(k - k / 2, fill));
        default:  return px_str(sg + std::string(k, fill) + body);
    }
}
inline PyStr *px_format_bool_spec(bool v, PyStr *spec) {
    if (spec->data.empty()) return pystr_lit(v ? "True" : "False");
    return px_format_i64(v ? 1 : 0, spec);
}
inline PyStr *px_pct_c(int64_t i) { return py_chr(i); }
inline PyStr *px_pct_c_str(PyStr *s) {
    if (s->data.size() != 1) px_type_error("%c requires an int or a unicode character, not a string of length " + std::to_string(s->data.size()));
    return s;
}

// ---- slices -------------------------------------------------------------------------------------
struct PxSlice { int64_t start, step, count; };
inline PxSlice px_slice_calc(int64_t len, bool hl, int64_t lo, bool hh, int64_t hi, bool hs, int64_t st) {
    int64_t step = hs ? st : 1;
    if (step == 0) throw ValueError("slice step cannot be zero");
    if (step < -INT64_MAX) step = -INT64_MAX;
    int64_t lower = step < 0 ? -1 : 0, upper = step < 0 ? len - 1 : len;
    int64_t start, stop;
    if (!hl) start = step < 0 ? upper : lower;
    else { start = lo; if (start < 0) { start += len; if (start < lower) start = lower; } else if (start > upper) start = upper; }
    if (!hh) stop = step < 0 ? lower : upper;
    else { stop = hi; if (stop < 0) { stop += len; if (stop < lower) stop = lower; } else if (stop > upper) stop = upper; }
    int64_t count = 0;
    if (step < 0) { if (stop < start) count = (start - stop - 1) / (-step) + 1; }
    else if (start < stop) count = (stop - start - 1) / step + 1;
    return PxSlice{start, step, count};
}
template <class T> PyList<T> *px_slice(PyList<T> *l, bool hl, int64_t lo, bool hh, int64_t hi, bool hs, int64_t st) {
    PxSlice s = px_slice_calc(l->size(), hl, lo, hh, hi, hs, st);
    auto *r = pyl_new<T>();
    r->data.reserve(static_cast<size_t>(s.count));
    for (int64_t k = 0, i = s.start; k < s.count; ++k, i += s.step) r->data.push_back(l->data[static_cast<size_t>(i)]);
    return r;
}
inline PyStr *px_str_slice(PyStr *a, bool hl, int64_t lo, bool hh, int64_t hi, bool hs, int64_t st) {
    PxSlice s = px_slice_calc(static_cast<int64_t>(a->data.size()), hl, lo, hh, hi, hs, st);
    std::string r;
    r.reserve(static_cast<size_t>(s.count));
    for (int64_t k = 0, i = s.start; k < s.count; ++k, i += s.step) r += a->data[static_cast<size_t>(i)];
    return px_str(std::move(r));
}

// ---- str methods (ASCII) ------------------------------------------------------------------------
inline PyStr *px_pad_fill_check(PyStr *fill) {
    if (fill->data.size() != 1) px_type_error("The fill character must be exactly one character long");
    return fill;
}
inline PyStr *px_zfill(PyStr *s, int64_t w) {
    int64_t n = static_cast<int64_t>(s->data.size());
    if (w <= n) return px_str(s->data);
    std::string z(static_cast<size_t>(w - n), '0');
    if (!s->data.empty() && (s->data[0] == '+' || s->data[0] == '-')) return px_str(s->data.substr(0, 1) + z + s->data.substr(1));
    return px_str(z + s->data);
}
inline PyStr *px_center(PyStr *s, int64_t w, PyStr *fill) {
    px_pad_fill_check(fill);
    int64_t n = static_cast<int64_t>(s->data.size());
    if (w <= n) return px_str(s->data);
    int64_t marg = w - n, left = marg / 2 + (marg & w & 1);
    return px_str(std::string(static_cast<size_t>(left), fill->data[0]) + s->data + std::string(static_cast<size_t>(marg - left), fill->data[0]));
}
inline PyStr *px_ljust(PyStr *s, int64_t w, PyStr *fill) {
    px_pad_fill_check(fill);
    int64_t n = static_cast<int64_t>(s->data.size());
    return px_str(w <= n ? s->data : s->data + std::string(static_cast<size_t>(w - n), fill->data[0]));
}
inline PyStr *px_rjust(PyStr *s, int64_t w, PyStr *fill) {
    px_pad_fill_check(fill);
    int64_t n = static_cast<int64_t>(s->data.size());
    return px_str(w <= n ? s->data : std::string(static_cast<size_t>(w - n), fill->data[0]) + s->data);
}
inline bool px_istitle(PyStr *s) {
    bool cased = false, prev = false;
    for (char c : s->data) {
        if (c >= 'A' && c <= 'Z') { if (prev) return false; prev = true; cased = true; }
        else if (c >= 'a' && c <= 'z') { if (!prev) return false; prev = true; cased = true; }
        else prev = false;
    }
    return cased;
}
inline bool px_isascii(PyStr *s) { for (char c : s->data) if (static_cast<unsigned char>(c) >= 0x80) return false; return true; }
inline PyStr *px_casefold(PyStr *s) { return pystr_lower(s); }
inline PyStr *px_removeprefix(PyStr *s, PyStr *p) {
    if (s->data.compare(0, p->data.size(), p->data) == 0 && s->data.size() >= p->data.size()) return px_str(s->data.substr(p->data.size()));
    return px_str(s->data);
}
inline PyStr *px_removesuffix(PyStr *s, PyStr *p) {
    if (!p->data.empty() && s->data.size() >= p->data.size() && s->data.compare(s->data.size() - p->data.size(), p->data.size(), p->data) == 0)
        return px_str(s->data.substr(0, s->data.size() - p->data.size()));
    return px_str(s->data);
}
inline PyStr *px_expandtabs(PyStr *s, int64_t ts) {
    std::string r;
    int64_t col = 0;
    for (char c : s->data) {
        if (c == '\t') { if (ts > 0) { int64_t k = ts - (col % ts); r.append(static_cast<size_t>(k), ' '); col += k; } }
        else { r += c; if (c == '\n' || c == '\r') col = 0; else ++col; }
    }
    return px_str(std::move(r));
}
inline PyListStr *px_split(PyStr *s, PyStr *sep, int64_t maxsplit) {         // sep == nullptr: split on whitespace runs
    auto *out = pyl_new<PyStr *>();
    const std::string &d = s->data;
    if (maxsplit < 0) maxsplit = INT64_MAX;
    if (!sep) {
        size_t i = 0, n = d.size();
        while (true) {
            while (i < n && px_space(d[i])) ++i;
            if (i >= n) break;
            if (maxsplit == 0) { out->data.push_back(px_str(d.substr(i))); break; }
            size_t j = i; while (j < n && !px_space(d[j])) ++j;
            out->data.push_back(px_str(d.substr(i, j - i))); i = j; --maxsplit;
        }
        return out;
    }
    if (sep->data.empty()) throw ValueError("empty separator");
    size_t i = 0, j;
    while (maxsplit > 0 && (j = d.find(sep->data, i)) != std::string::npos) {
        out->data.push_back(px_str(d.substr(i, j - i))); i = j + sep->data.size(); --maxsplit;
    }
    out->data.push_back(px_str(d.substr(i)));
    return out;
}
inline PyListStr *px_rsplit(PyStr *s, PyStr *sep, int64_t maxsplit) {
    auto *out = pyl_new<PyStr *>();
    const std::string &d = s->data;
    if (maxsplit < 0) maxsplit = INT64_MAX;
    if (!sep) {
        int64_t i = static_cast<int64_t>(d.size());
        while (true) {
            while (i > 0 && px_space(d[static_cast<size_t>(i - 1)])) --i;
            if (i <= 0) break;
            if (maxsplit == 0) { out->data.push_back(px_str(d.substr(0, static_cast<size_t>(i)))); break; }
            int64_t j = i; while (j > 0 && !px_space(d[static_cast<size_t>(j - 1)])) --j;
            out->data.push_back(px_str(d.substr(static_cast<size_t>(j), static_cast<size_t>(i - j)))); i = j; --maxsplit;
        }
    } else {
        if (sep->data.empty()) throw ValueError("empty separator");
        size_t end = d.size();
        while (maxsplit > 0) {
            size_t j = end >= sep->data.size() ? d.rfind(sep->data, end - sep->data.size()) : std::string::npos;
            if (j == std::string::npos) break;
            out->data.push_back(px_str(d.substr(j + sep->data.size(), end - j - sep->data.size()))); end = j; --maxsplit;
        }
        out->data.push_back(px_str(d.substr(0, end)));
    }
    std::reverse(out->data.begin(), out->data.end());
    return out;
}
inline PyListStr *px_splitlines(PyStr *s, bool keep) {
    auto *out = pyl_new<PyStr *>();
    const std::string &d = s->data;
    size_t i = 0, n = d.size();
    while (i < n) {
        size_t j = i;
        while (j < n && !(d[j] == '\n' || d[j] == '\r' || d[j] == '\x0b' || d[j] == '\x0c' || (d[j] >= '\x1c' && d[j] <= '\x1e'))) ++j;
        size_t eol = j;
        if (j < n) { if (d[j] == '\r' && j + 1 < n && d[j + 1] == '\n') j += 2; else j += 1; }
        out->data.push_back(px_str(d.substr(i, (keep ? j : eol) - i)));
        i = j;
    }
    return out;
}
// start/end handling shared by count / find / rfind / index / rindex / startswith / endswith
inline void px_adjust(int64_t len, int64_t &start, int64_t &end) {
    if (end > len) end = len; else if (end < 0) { end += len; if (end < 0) end = 0; }
    if (start < 0) { start += len; if (start < 0) start = 0; }
}
inline int64_t px_find_r(PyStr *s, PyStr *sub, int64_t start, int64_t end, bool last) {
    int64_t len = static_cast<int64_t>(s->data.size()), sl = static_cast<int64_t>(sub->data.size());
    px_adjust(len, start, end);
    if (start > len || end - start < sl) return -1;
    std::string hay = s->data.substr(static_cast<size_t>(start), static_cast<size_t>(end - start));
    size_t k = last ? hay.rfind(sub->data) : hay.find(sub->data);
    return k == std::string::npos ? -1 : static_cast<int64_t>(k) + start;
}
inline int64_t px_str_find(PyStr *s, PyStr *sub, int64_t start, int64_t end) { return px_find_r(s, sub, start, end, false); }
inline int64_t px_str_rfind(PyStr *s, PyStr *sub, int64_t start, int64_t end) { return px_find_r(s, sub, start, end, true); }
inline int64_t px_str_index(PyStr *s, PyStr *sub, int64_t start, int64_t end) {
    int64_t r = px_find_r(s, sub, start, end, false); if (r < 0) throw ValueError("substring not found"); return r;
}
inline int64_t px_str_rindex(PyStr *s, PyStr *sub, int64_t start, int64_t end) {
    int64_t r = px_find_r(s, sub, start, end, true); if (r < 0) throw ValueError("substring not found"); return r;
}
inline int64_t px_str_count(PyStr *s, PyStr *sub, int64_t start, int64_t end) {
    int64_t len = static_cast<int64_t>(s->data.size()), sl = static_cast<int64_t>(sub->data.size());
    px_adjust(len, start, end);
    if (start > len || end - start < sl) return 0;
    if (sl == 0) return end - start + 1;
    std::string hay = s->data.substr(static_cast<size_t>(start), static_cast<size_t>(end - start));
    int64_t c = 0; size_t i = 0;
    while ((i = hay.find(sub->data, i)) != std::string::npos) { ++c; i += sub->data.size(); }
    return c;
}
inline bool px_tail(PyStr *s, PyStr *p, int64_t start, int64_t end, bool at_end) {
    int64_t len = static_cast<int64_t>(s->data.size()), pl = static_cast<int64_t>(p->data.size());
    px_adjust(len, start, end);
    if (start > len || end - start < pl) return false;
    int64_t at = at_end ? end - pl : start;
    return s->data.compare(static_cast<size_t>(at), static_cast<size_t>(pl), p->data) == 0;
}
inline bool px_str_startswith(PyStr *s, PyStr *p, int64_t start, int64_t end) { return px_tail(s, p, start, end, false); }
inline bool px_str_endswith(PyStr *s, PyStr *p, int64_t start, int64_t end) { return px_tail(s, p, start, end, true); }

// ---- list.index(x, start, stop) ---------------------------------------------------------------
template <class T, class U> int64_t px_list_index(PyList<T> *l, const U &u, int64_t start, int64_t stop) {
    T v = static_cast<T>(u);
    int64_t len = l->size();
    if (start < 0) { start += len; if (start < 0) start = 0; }
    if (stop < 0) { stop += len; if (stop < 0) stop = 0; }
    if (stop > len) stop = len;
    for (int64_t i = start; i < stop; ++i) if (pyl_eqv(l->data[static_cast<size_t>(i)], v)) return i;
    throw ValueError((py_minor >= 14 ? std::string("list.index(x): x not in list") : py_value_repr(v) + " is not in list").c_str());
}

// ---- dict methods -----------------------------------------------------------------------------
template <class D, class K> int64_t px_dfind(D *d, const K &k) {
    for (int64_t i = 0; i < d->size(); ++i) if (pyl_eqv(d->keys[static_cast<size_t>(i)], static_cast<typename decltype(D::keys)::value_type>(k))) return i;
    return -1;
}
template <class D> auto *px_dvalues(D *d) { auto *r = pyl_new<typename decltype(d->vals)::value_type>(); r->data = d->vals; return r; }
template <class D, class K> typename decltype(D::vals)::value_type px_dpop(D *d, const K &k) {
    int64_t i = px_dfind(d, k);
    if (i < 0) throw KeyError(py_value_repr(static_cast<typename decltype(D::keys)::value_type>(k)).c_str());
    typename decltype(D::vals)::value_type v = d->vals[static_cast<size_t>(i)];
    d->keys.erase(d->keys.begin() + i); d->vals.erase(d->vals.begin() + i);
    return v;
}
template <class D, class K, class V> typename decltype(D::vals)::value_type px_dpop_default(D *d, const K &k, const V &dflt) {
    int64_t i = px_dfind(d, k);
    typedef typename decltype(D::vals)::value_type VT;
    if (i < 0) return static_cast<VT>(dflt);
    VT v = d->vals[static_cast<size_t>(i)];
    d->keys.erase(d->keys.begin() + i); d->vals.erase(d->vals.begin() + i);
    return v;
}
template <class D, class K, class V> typename decltype(D::vals)::value_type px_dsetdefault(D *d, const K &k, const V &dflt) {
    typedef typename decltype(D::keys)::value_type KT;
    typedef typename decltype(D::vals)::value_type VT;
    int64_t i = px_dfind(d, k);
    if (i >= 0) return static_cast<VT>(d->vals[static_cast<size_t>(i)]);
    d->keys.push_back(static_cast<KT>(k)); d->vals.push_back(static_cast<VT>(dflt));
    return static_cast<VT>(dflt);
}
template <class D> void px_dupdate(D *d, D *o) {
    std::vector<typename decltype(D::keys)::value_type> ks = o->keys;
    auto vs = o->vals;
    for (size_t j = 0; j < ks.size(); ++j) {
        int64_t i = px_dfind(d, ks[j]);
        if (i < 0) { d->keys.push_back(ks[j]); d->vals.push_back(vs[j]); } else d->vals[static_cast<size_t>(i)] = vs[j];
    }
}
template <class D> D *px_dcopy(D *d) { return arena_new<D>(*d); }
template <class D> void px_dclear(D *d) { d->keys.clear(); d->vals.clear(); }
template <class D, class L, class V> D *px_dfromkeys(L *ks, const V &v) {
    D *d = arena_new<D>();
    typedef typename decltype(D::vals)::value_type VT;
    for (auto &k : ks->data) {
        if (px_dfind(d, k) < 0) { d->keys.push_back(k); d->vals.push_back(static_cast<VT>(v)); }
    }
    return d;
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

// ---- tuples ------------------------------------------------------------------------------------------------
template <class Tup, class F, size_t... I> void pyt_each2(const Tup &a, const Tup &b, F f, std::index_sequence<I...>) {
    (f(std::get<I>(a), std::get<I>(b)), ...);
}
// op: 0 <, 1 <=, 2 >, 3 >=.  CPython: the first unequal pair decides, compared with the same operator.
template <class T> bool pyt_rel(int op, const T &a, const T &b) {
    switch (op) {
        case 0: return pyl_lt(a, b);
        case 1: return pyl_lt(a, b) || pyl_eqv(a, b);
        case 2: return pyl_lt(b, a);
        default: return pyl_lt(b, a) || pyl_eqv(a, b);
    }
}
template <class... T> bool pyt_rel(int op, const std::tuple<T...> &a, const std::tuple<T...> &b) {
    bool done = false, r = (op == 1 || op == 3);           // all equal (same length): only <= and >= hold
    pyt_each2(a, b, [&](const auto &x, const auto &y) {
        if (!done && !pyl_eqv(x, y)) { done = true; r = pyt_rel(op, x, y); }
    }, std::index_sequence_for<T...>{});
    return r;
}
template <class... T> bool pyl_eqv(const std::tuple<T...> &a, const std::tuple<T...> &b) {
    bool eq = true;
    pyt_each2(a, b, [&](const auto &x, const auto &y) { eq = eq && pyl_eqv(x, y); }, std::index_sequence_for<T...>{});
    return eq;
}
template <class... T> bool pyl_lt(const std::tuple<T...> &a, const std::tuple<T...> &b) { return pyt_rel(0, a, b); }
template <class T> bool pyt_lt(const T &a, const T &b) { return pyt_rel(0, a, b); }
template <class T> bool pyt_le(const T &a, const T &b) { return pyt_rel(1, a, b); }
template <class T> bool pyt_gt(const T &a, const T &b) { return pyt_rel(2, a, b); }
template <class T> bool pyt_ge(const T &a, const T &b) { return pyt_rel(3, a, b); }
template <class... T> bool pyt_truthy(const std::tuple<T...> &) { return sizeof...(T) > 0; }
template <class... T> int64_t pyt_len(const std::tuple<T...> &) { return static_cast<int64_t>(sizeof...(T)); }
template <class X, class... T> bool pyt_contains(const std::tuple<T...> &t, const X &x) {
    return std::apply([&](const auto &...e) { return (pyl_eqv(e, x) || ...); }, t);
}
template <class E, class... T> PyList<E> *pyt_to_list(const std::tuple<T...> &t) {
    auto *r = pyl_new<E>();
    std::apply([&](const auto &...e) { (r->data.push_back(e), ...); }, t);
    return r;
}

template <class... T> std::string py_value_repr(const std::tuple<T...> &t) {
    std::string s = "(";
    bool first = true;
    std::apply([&](const auto &...e) { ((s += (first ? "" : ", ") + py_value_repr(e), first = false), ...); }, t);
    return s + (sizeof...(T) == 1 ? ",)" : ")");
}
template <class T> std::string py_value_repr(PyList<T> *const &l) {
    std::string s = "[";
    for (size_t i = 0; i < l->data.size(); ++i) s += (i ? ", " : "") + py_value_repr(l->data[i]);
    return s + "]";
}
template <class D> auto py_value_repr(D *const &d) -> decltype(d->vals, std::string()) {
    std::string s = "{";
    for (size_t i = 0; i < d->keys.size(); ++i) s += (i ? ", " : "") + py_value_repr(d->keys[i]) + ": " + py_value_repr(d->vals[i]);
    return s + "}";
}
template <class T> void py_print_repr(const T &v) { std::string s = py_value_repr(v); py_print_str(pystr_new(s.data(), static_cast<int64_t>(s.size()))); }
template <class T> PyStr *py_repr_pystr(const T &v) { std::string s = py_value_repr(v); return pystr_new(s.data(), static_cast<int64_t>(s.size())); }

// a, b = v   (v a list or str; tuples are length-checked statically)
inline void pyt_unpack_check(int64_t have, int64_t n) {
    std::string e = "(expected " + std::to_string(n);
    if (have > n) throw ValueError(("too many values to unpack " + e + (py_minor >= 14 ? ", got " + std::to_string(have) : "") + ")").c_str());
    if (have < n) throw ValueError(("not enough values to unpack " + e + ", got " + std::to_string(have) + ")").c_str());
}
template <class T> PyList<T> *pyl_unpack(PyList<T> *l, int64_t n) { pyt_unpack_check(l->size(), n); return l; }
inline PyStr *pystr_unpack(PyStr *s, int64_t n) { pyt_unpack_check(static_cast<int64_t>(s->data.size()), n); return s; }

// dicts with tuple keys or values (named PyDictT_<hash> aliases are emitted per program)
template <class K, class V> struct PyDictT {
    std::vector<K> keys; std::vector<V> vals;
    int64_t size() const { return static_cast<int64_t>(keys.size()); }
};
template <class K, class V> int64_t pyd_find(PyDictT<K, V> *d, const K &k) {   // ponytail: linear scan, like the monomorphic dicts
    for (size_t i = 0; i < d->keys.size(); ++i) if (pyl_eqv(d->keys[i], k)) return static_cast<int64_t>(i);
    return -1;
}
template <class K, class V> void pyd_set(PyDictT<K, V> *d, const K &k, const V &v) {
    int64_t i = pyd_find(d, k);
    if (i < 0) { d->keys.push_back(k); d->vals.push_back(v); } else d->vals[static_cast<size_t>(i)] = v;
}
template <class K, class V> V pyd_get(PyDictT<K, V> *d, const K &k) {
    int64_t i = pyd_find(d, k);
    if (i < 0) throw KeyError(py_value_repr(k).c_str());
    return d->vals[static_cast<size_t>(i)];
}
template <class K, class V> V pyd_get_default(PyDictT<K, V> *d, const K &k, const V &v) {
    int64_t i = pyd_find(d, k);
    return i < 0 ? v : d->vals[static_cast<size_t>(i)];
}
template <class K, class V> bool pyd_contains(PyDictT<K, V> *d, const K &k) { return pyd_find(d, k) >= 0; }
template <class D> auto *pyd_items(D *d) {                 // any dict -> list[tuple[K, V]]
    using K = typename decltype(d->keys)::value_type;
    using V = typename decltype(d->vals)::value_type;
    auto *r = pyl_new<std::tuple<K, V>>();
    for (size_t i = 0; i < d->keys.size(); ++i) r->data.emplace_back(d->keys[i], d->vals[i]);
    return r;
}


} // namespace pyrt
using namespace pyrt;
#endif