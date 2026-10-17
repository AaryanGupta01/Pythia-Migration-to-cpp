#include "pyrt.hpp"
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <iomanip>
#include <iostream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <utility>

namespace pyrt {

[[noreturn]] void py_raise(const char *exc, const char *msg) {
    std::string m = msg ? msg : "";
    if (std::string(exc) == "IndexError") throw IndexError(m.c_str());
    if (std::string(exc) == "ZeroDivisionError") throw ZeroDivisionError(m.c_str());
    if (std::string(exc) == "OverflowError") throw OverflowError(m.c_str());
    if (std::string(exc) == "ValueError") throw ValueError(m.c_str());
    if (std::string(exc) == "KeyError") throw KeyError(m.c_str());
    if (std::string(exc) == "PythiaSemanticError") throw PythiaSemanticError(m.c_str());
    throw PythonException(exc, m);
}
[[noreturn]] void py_raise_pystr(const char *exc, const PyStr *msg) { py_raise(exc, msg ? msg->data.c_str() : ""); }

bool arena_active = false;
static std::vector<std::pair<void *, void (*)(void *)>> g_arena;
static std::vector<size_t> g_arena_marks;
void arena_push(void *p, void (*del)(void *)) { g_arena.emplace_back(p, del); }
void arena_begin() { g_arena_marks.push_back(g_arena.size()); arena_active = true; }
void arena_end() {
    if (g_arena_marks.empty()) return;
    size_t mark = g_arena_marks.back(); g_arena_marks.pop_back();
    while (g_arena.size() > mark) { auto e = g_arena.back(); g_arena.pop_back(); e.second(e.first); }
    if (g_arena_marks.empty()) { arena_active = false; g_arena.shrink_to_fit(); }
}

static PyStr *make_str(std::string value) { return arena_new<PyStr>(PyStr{std::move(value)}); }
PyStr *pystr_new(const char *s, int64_t len) { return make_str(std::string(s, static_cast<size_t>(len))); }
PyStr *pystr_lit(const char *s) { return make_str(s ? s : ""); }
PyStr *pystr_concat(PyStr *a, PyStr *b) { return make_str(a->data + b->data); }
PyStr *pystr_repeat(PyStr *a, int64_t n) { return n <= 0 ? make_str("") : [&] { std::string r; r.reserve(a->data.size() * static_cast<size_t>(n)); for (int64_t i = 0; i < n; ++i) r += a->data; return make_str(std::move(r)); }(); }
PyStr *pystr_index(PyStr *a, int64_t i) { int64_t j = i < 0 ? static_cast<int64_t>(a->data.size()) + i : i; if (j < 0 || j >= static_cast<int64_t>(a->data.size())) throw IndexError("string index out of range"); return make_str(a->data.substr(static_cast<size_t>(j), 1)); }
PyStr *pystr_upper(PyStr *a) { std::string s = a->data; for (char &c : s) if (c >= 'a' && c <= 'z') c -= 'a' - 'A'; return make_str(std::move(s)); }
PyStr *pystr_lower(PyStr *a) { std::string s = a->data; for (char &c : s) if (c >= 'A' && c <= 'Z') c += 'a' - 'A'; return make_str(std::move(s)); }
int64_t pystr_len(PyStr *a) { return static_cast<int64_t>(a->data.size()); }
int pystr_cmp(PyStr *a, PyStr *b) { return a->data == b->data ? 0 : a->data < b->data ? -1 : 1; }
bool pystr_truthy(PyStr *a) { return !a->data.empty(); }
bool pystr_contains(PyStr *hay, PyStr *needle) { return hay->data.find(needle->data) != std::string::npos; }

PyStr *pystr_from_i64(int64_t v) { return make_str(std::to_string(v)); }
static std::string format_f64(double d) {
    if (std::isnan(d)) return "nan";
    if (std::isinf(d)) return d > 0 ? "inf" : "-inf";
    char sci[64]; int sig = 17;
    for (int s = 1; s <= 17; ++s) { std::snprintf(sci, sizeof sci, "%.*e", s - 1, d); char *end = nullptr; if (std::strtod(sci, &end) == d) { sig = s; break; } }
    const char *epos = std::strchr(sci, 'e'); int expo = epos ? std::atoi(epos + 1) : 0;
    char out[128];
    if (expo < -4 || expo >= 16) {
        std::string mantissa(sci, static_cast<size_t>(epos - sci));
        while (mantissa.size() > 1 && mantissa.back() == '0') mantissa.pop_back();
        if (!mantissa.empty() && mantissa.back() == '.') mantissa.pop_back();
        std::string exponent = expo >= 0 ? std::string("e+") + std::to_string(expo)
                         : std::string("e-") + (std::abs(expo) < 10 ? "0" : "") + std::to_string(std::abs(expo));
        std::snprintf(out, sizeof out, "%s%s", mantissa.c_str(), exponent.c_str());
    }
    else { int dec = std::max(0, sig - 1 - expo); std::snprintf(out, sizeof out, "%.*f", dec, d); if (!std::strchr(out, '.')) std::strcat(out, ".0"); }
    return out;
}
PyStr *pystr_from_f64(double v) { return make_str(format_f64(v)); }
PyStr *pystr_from_bool(bool v) { return pystr_lit(v ? "True" : "False"); }
int64_t py_i64_from_str(PyStr *s) { try { size_t n; long long v = std::stoll(s->data, &n); if (n != s->data.size()) throw std::invalid_argument(""); return v; } catch (...) { throw ValueError("invalid literal for int() with base 10"); } }
double py_f64_from_str(PyStr *s) { try { size_t n; double v = std::stod(s->data, &n); if (n != s->data.size()) throw std::invalid_argument(""); return v; } catch (...) { throw ValueError("could not convert string to float"); } }

int64_t py_add_i64(int64_t a, int64_t b) { if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) throw OverflowError("int64 overflow"); return a + b; }
int64_t py_sub_i64(int64_t a, int64_t b) { if ((b < 0 && a > INT64_MAX + b) || (b > 0 && a < INT64_MIN + b)) throw OverflowError("int64 overflow"); return a - b; }
int64_t py_mul_i64(int64_t a, int64_t b) { if (a && ((b > 0 && (a > INT64_MAX / b || a < INT64_MIN / b)) || (b < 0 && (a == INT64_MIN || -a > INT64_MAX / -b)))) throw OverflowError("int64 overflow"); return a * b; }
int64_t py_neg_i64(int64_t a) { if (a == INT64_MIN) throw OverflowError("int64 overflow"); return -a; }
int64_t py_abs_i64(int64_t a) { return a < 0 ? py_neg_i64(a) : a; }
int64_t py_floordiv_i64(int64_t a, int64_t b) { if (!b) throw ZeroDivisionError("integer division or modulo by zero"); if (a == INT64_MIN && b == -1) throw OverflowError("int64 overflow"); int64_t q = a / b; if (a % b && ((a < 0) != (b < 0))) --q; return q; }
int64_t py_mod_i64(int64_t a, int64_t b) { if (!b) throw ZeroDivisionError("integer division or modulo by zero"); if (a == INT64_MIN && b == -1) return 0; int64_t r = a % b; if (r && ((r < 0) != (b < 0))) r += b; return r; }
int64_t py_pow_i64(int64_t a, int64_t b) { if (b < 0) throw PythiaSemanticError("int ** negative-int yields float in CPython; annotate the base as float to keep the translation sound"); int64_t r = 1; while (b) { if (b & 1) r = py_mul_i64(r, a); b >>= 1; if (b) a = py_mul_i64(a, a); } return r; }
double py_truediv(double a, double b) { if (!b) throw ZeroDivisionError("division by zero"); return a / b; }
double py_floordiv_f64(double a, double b) { if (!b) throw ZeroDivisionError("float floor division by zero"); return std::floor(a / b); }
double py_mod_f64(double a, double b) { if (!b) throw ZeroDivisionError("float modulo"); double r = std::fmod(a, b); if (r && ((r < 0) != (b < 0))) r += b; return r ? r : std::copysign(0.0, b); }
double py_pow_f64(double a, double b) { return std::pow(a, b); }

#define LIST_IMPL(NAME, T, EQ) \
NAME *NAME##_new() { return arena_new<NAME>(); } void NAME##_append(NAME *l,T v){l->data.push_back(v);} \
T NAME##_get(NAME *l,int64_t i){return l->data[static_cast<size_t>(l->index(i))];} void NAME##_set(NAME *l,int64_t i,T v){l->data[static_cast<size_t>(l->index(i))]=v;} \
T NAME##_pop(NAME *l){if(l->data.empty()) throw IndexError("pop from empty list"); T v=l->data.back(); l->data.pop_back(); return v;} \
NAME *NAME##_concat(NAME *a,NAME *b){auto *r=arena_new<NAME>(); r->data=a->data; r->data.insert(r->data.end(),b->data.begin(),b->data.end()); return r;} \
bool NAME##_eq(NAME *a,NAME *b){return a->data.size()==b->data.size() && std::equal(a->data.begin(),a->data.end(),b->data.begin(),EQ);} bool NAME##_contains(NAME *l,T v){return std::find_if(l->data.begin(),l->data.end(),[&](T x){return EQ(x,v);})!=l->data.end();}
LIST_IMPL(PyListI64,int64_t,[](auto a,auto b){return a==b;})
LIST_IMPL(PyListF64,double,[](auto a,auto b){return a==b;})
LIST_IMPL(PyListBool,bool,[](auto a,auto b){return a==b;})
LIST_IMPL(PyListStr,PyStr*,[](auto a,auto b){return pystr_cmp(a,b)==0;})
PyListList *PyListList_new(){return arena_new<PyListList>();} void PyListList_append(PyListList*l,void*v){l->data.push_back(v);} void *PyListList_get(PyListList*l,int64_t i){return l->data[static_cast<size_t>(l->index(i))];} void PyListList_set(PyListList*l,int64_t i,void*v){l->data[static_cast<size_t>(l->index(i))]=v;} void *PyListList_pop(PyListList*l){if(l->data.empty())throw IndexError("pop from empty list");void*v=l->data.back();l->data.pop_back();return v;} PyListList *PyListList_concat(PyListList*a,PyListList*b){auto*r=arena_new<PyListList>();r->data=a->data;r->data.insert(r->data.end(),b->data.begin(),b->data.end());return r;}

#define DICT_IMPL(NAME,KT,VT,EQ) NAME *NAME##_new(){return arena_new<NAME>();} static int64_t NAME##_find(NAME*d,KT k){for(int64_t i=0;i<d->size();++i)if(EQ(d->keys[i],k))return i;return -1;} void NAME##_set(NAME*d,KT k,VT v){auto i=NAME##_find(d,k);if(i<0){d->keys.push_back(k);d->vals.push_back(v);}else d->vals[i]=v;} VT NAME##_get(NAME*d,KT k){auto i=NAME##_find(d,k);if(i<0)throw KeyError("key not found");return d->vals[i];} VT NAME##_get_default(NAME*d,KT k,VT v){auto i=NAME##_find(d,k);return i<0?v:d->vals[i];} bool NAME##_contains(NAME*d,KT k){return NAME##_find(d,k)>=0;}
DICT_IMPL(PyDictIntInt,int64_t,int64_t,[](auto a,auto b){return a==b;})
DICT_IMPL(PyDictIntFloat,int64_t,double,[](auto a,auto b){return a==b;})
DICT_IMPL(PyDictIntBool,int64_t,bool,[](auto a,auto b){return a==b;})
DICT_IMPL(PyDictIntStr,int64_t,PyStr*,[](auto a,auto b){return a==b;})
DICT_IMPL(PyDictStrInt,PyStr*,int64_t,[](auto a,auto b){return pystr_cmp(a,b)==0;})
DICT_IMPL(PyDictStrFloat,PyStr*,double,[](auto a,auto b){return pystr_cmp(a,b)==0;})
DICT_IMPL(PyDictStrBool,PyStr*,bool,[](auto a,auto b){return pystr_cmp(a,b)==0;})
DICT_IMPL(PyDictStrStr,PyStr*,PyStr*,[](auto a,auto b){return pystr_cmp(a,b)==0;})

static bool first=true; void py_print_begin(){first=true;} void py_print_sep(){if(!first)std::cout<<' ';first=false;} void py_print_end(){std::cout<<'\n';} void py_print_i64(int64_t v){std::cout<<v;} void py_print_f64(double v){std::cout<<format_f64(v);} void py_print_bool(bool v){std::cout<<(v?"True":"False");} void py_print_str(PyStr*v){std::cout<<v->data;}
#define PRINT_LIST(FN,LT,ITEM) void FN(LT*l){std::cout<<'[';for(size_t i=0;i<l->data.size();++i){if(i)std::cout<<", ";ITEM(l->data[i]);}std::cout<<']';}
PRINT_LIST(py_print_list_i64,PyListI64,py_print_i64) PRINT_LIST(py_print_list_f64,PyListF64,py_print_f64) PRINT_LIST(py_print_list_bool,PyListBool,py_print_bool)
static void print_repr(PyStr*s){std::cout<<'\'';for(char c:s->data){if(c=='\\'||c=='\'')std::cout<<'\\';if(c=='\n')std::cout<<"\\n";else if(c=='\t')std::cout<<"\\t";else std::cout<<c;}std::cout<<'\'';} PRINT_LIST(py_print_list_str,PyListStr,print_repr)
void py_print_list_generic(PyListList*l,void(*f)(void*)){std::cout<<'[';for(size_t i=0;i<l->data.size();++i){if(i)std::cout<<", ";f(l->data[i]);}std::cout<<']';}
#define PRINT_DICT(FN,DT,K,V) void FN(DT*d){std::cout<<'{';for(size_t i=0;i<d->keys.size();++i){if(i)std::cout<<", ";K(d->keys[i]);std::cout<<": ";V(d->vals[i]);}std::cout<<'}';}
PRINT_DICT(py_print_dict_intint,PyDictIntInt,py_print_i64,py_print_i64) PRINT_DICT(py_print_dict_intfloat,PyDictIntFloat,py_print_i64,py_print_f64) PRINT_DICT(py_print_dict_intbool,PyDictIntBool,py_print_i64,py_print_bool) PRINT_DICT(py_print_dict_intstr,PyDictIntStr,py_print_i64,print_repr)
PRINT_DICT(py_print_dict_strint,PyDictStrInt,print_repr,py_print_i64) PRINT_DICT(py_print_dict_strfloat,PyDictStrFloat,print_repr,py_print_f64) PRINT_DICT(py_print_dict_strbool,PyDictStrBool,print_repr,py_print_bool) PRINT_DICT(py_print_dict_strstr,PyDictStrStr,print_repr,print_repr)
void py_print_exception(const PythonException &e) { std::cerr << e.what() << '\n'; }
}
