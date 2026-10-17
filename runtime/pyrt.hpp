#ifndef PYRT_HPP
#define PYRT_HPP

#include <cmath>
#include <cstdint>
#include <exception>
#include <limits>
#include <memory>
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
double py_truediv(double, double); double py_floordiv_f64(double, double); double py_mod_f64(double, double); double py_pow_f64(double, double);

void py_print_begin(); void py_print_sep(); void py_print_end(); void py_print_i64(int64_t); void py_print_f64(double); void py_print_bool(bool); void py_print_str(PyStr *);
void py_print_list_i64(PyListI64 *); void py_print_list_f64(PyListF64 *); void py_print_list_bool(PyListBool *); void py_print_list_str(PyListStr *);
void py_print_list_generic(PyListList *, void (*)(void *));
void py_print_exception(const PythonException &);
void py_print_dict_intint(PyDictIntInt *); void py_print_dict_intfloat(PyDictIntFloat *); void py_print_dict_intbool(PyDictIntBool *); void py_print_dict_intstr(PyDictIntStr *);
void py_print_dict_strint(PyDictStrInt *); void py_print_dict_strfloat(PyDictStrFloat *); void py_print_dict_strbool(PyDictStrBool *); void py_print_dict_strstr(PyDictStrStr *);

} // namespace pyrt
using namespace pyrt;
#endif