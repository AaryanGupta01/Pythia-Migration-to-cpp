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
    if (std::string(exc) == "EOFError") throw EOFError(m.c_str());
    if (std::string(exc) == "PythiaSemanticError") throw PythiaSemanticError(m.c_str());
    throw PythonException(exc, m);
}
int py_minor = 13;
void pyrt_set_py_minor(int minor) { py_minor = minor; }
std::string py_repr_str(const std::string &s) {             // CPython's str.__repr__ for byte/ASCII strings
    bool sq = s.find('\'') != std::string::npos, dq = s.find('"') != std::string::npos;
    char q = (sq && !dq) ? '"' : '\'';
    std::string r(1, q);
    static const char *hex = "0123456789abcdef";
    for (unsigned char c : s) {
        if (c == static_cast<unsigned char>(q) || c == '\\') { r += '\\'; r += static_cast<char>(c); }
        else if (c == '\n') r += "\\n";
        else if (c == '\t') r += "\\t";
        else if (c == '\r') r += "\\r";
        else if (c < 0x20 || c == 0x7f) { r += "\\x"; r += hex[c >> 4]; r += hex[c & 15]; }
        else r += static_cast<char>(c);
    }
    r += q;
    return r;
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
std::string py_float_repr(double v) { return format_f64(v); }
PyStr *pystr_from_f64(double v) { return make_str(format_f64(v)); }
PyStr *pystr_from_bool(bool v) { return pystr_lit(v ? "True" : "False"); }
static std::string trim_ws(const std::string &d) {     // int()/float() ignore surrounding whitespace, like CPython
    size_t b = 0, e = d.size();
    while (b < e && (d[b] == ' ' || (d[b] >= '\t' && d[b] <= '\r'))) ++b;
    while (e > b && (d[e - 1] == ' ' || (d[e - 1] >= '\t' && d[e - 1] <= '\r'))) --e;
    return d.substr(b, e - b);
}
int64_t py_i64_from_str(PyStr *s) { try { std::string t = trim_ws(s->data); size_t n; if (t.empty() || std::isspace(static_cast<unsigned char>(t[0]))) throw std::invalid_argument(""); long long v = std::stoll(t, &n); if (n != t.size()) throw std::invalid_argument(""); return v; } catch (...) { throw ValueError(("invalid literal for int() with base 10: " + py_repr_str(s->data)).c_str()); } }
double py_f64_from_str(PyStr *s) { try { std::string t = trim_ws(s->data); size_t n; if (t.empty() || (t.size() > 1 && t[0] == '0' && (t[1] == 'x' || t[1] == 'X'))) throw std::invalid_argument(""); double v = std::stod(t, &n); if (n != t.size()) throw std::invalid_argument(""); return v; } catch (...) { throw ValueError(("could not convert string to float: " + py_repr_str(s->data)).c_str()); } }

int64_t py_add_i64(int64_t a, int64_t b) { if ((b > 0 && a > INT64_MAX - b) || (b < 0 && a < INT64_MIN - b)) throw OverflowError("int64 overflow"); return a + b; }
int64_t py_sub_i64(int64_t a, int64_t b) { if ((b < 0 && a > INT64_MAX + b) || (b > 0 && a < INT64_MIN + b)) throw OverflowError("int64 overflow"); return a - b; }
int64_t py_mul_i64(int64_t a, int64_t b) { if (a && ((b > 0 && (a > INT64_MAX / b || a < INT64_MIN / b)) || (b < 0 && (a == INT64_MIN || -a > INT64_MAX / -b)))) throw OverflowError("int64 overflow"); return a * b; }
int64_t py_neg_i64(int64_t a) { if (a == INT64_MIN) throw OverflowError("int64 overflow"); return -a; }
int64_t py_abs_i64(int64_t a) { return a < 0 ? py_neg_i64(a) : a; }
int64_t py_floordiv_i64(int64_t a, int64_t b) { if (!b) throw ZeroDivisionError(py_minor >= 14 ? "division by zero" : "integer division or modulo by zero"); if (a == INT64_MIN && b == -1) throw OverflowError("int64 overflow"); int64_t q = a / b; if (a % b && ((a < 0) != (b < 0))) --q; return q; }
int64_t py_mod_i64(int64_t a, int64_t b) { if (!b) throw ZeroDivisionError(py_minor >= 14 ? "division by zero" : "integer modulo by zero"); if (a == INT64_MIN && b == -1) return 0; int64_t r = a % b; if (r && ((r < 0) != (b < 0))) r += b; return r; }
int64_t py_pow_i64(int64_t a, int64_t b) { if (b < 0) throw PythiaSemanticError("int ** negative-int yields float in CPython; annotate the base as float to keep the translation sound"); int64_t r = 1; while (b) { if (b & 1) r = py_mul_i64(r, a); b >>= 1; if (b) a = py_mul_i64(a, a); } return r; }
double py_truediv(double a, double b) { if (!b) throw ZeroDivisionError(py_minor >= 14 ? "division by zero" : "float division by zero"); return a / b; }
double py_truediv_ii(double a, double b) { if (!b) throw ZeroDivisionError("division by zero"); return a / b; }   // int / int
double py_floordiv_f64(double a, double b) { if (!b) throw ZeroDivisionError(py_minor >= 14 ? "division by zero" : "float floor division by zero"); return std::floor(a / b); }
double py_mod_f64(double a, double b) { if (!b) throw ZeroDivisionError(py_minor >= 14 ? "division by zero" : py_minor == 13 ? "float modulo by zero" : "float modulo"); double r = std::fmod(a, b); if (r && ((r < 0) != (b < 0))) r += b; return r ? r : std::copysign(0.0, b); }
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

static std::string key_repr(int64_t k) { return std::to_string(k); }
static std::string key_repr(PyStr *k) { return py_repr_str(k->data); }
#define DICT_IMPL(NAME,KT,VT,EQ) NAME *NAME##_new(){return arena_new<NAME>();} static int64_t NAME##_find(NAME*d,KT k){for(int64_t i=0;i<d->size();++i)if(EQ(d->keys[i],k))return i;return -1;} void NAME##_set(NAME*d,KT k,VT v){auto i=NAME##_find(d,k);if(i<0){d->keys.push_back(k);d->vals.push_back(v);}else d->vals[i]=v;} VT NAME##_get(NAME*d,KT k){auto i=NAME##_find(d,k);if(i<0){if(d->mode)return pyd_missing(d,k);throw KeyError(key_repr(k).c_str());}return d->vals[i];} VT NAME##_get_default(NAME*d,KT k,VT v){auto i=NAME##_find(d,k);return i<0?v:d->vals[i];} bool NAME##_contains(NAME*d,KT k){return NAME##_find(d,k)>=0;}
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
static void print_repr(PyStr*s){std::cout<<py_repr_str(s->data);} PRINT_LIST(py_print_list_str,PyListStr,print_repr)
void py_print_list_generic(PyListList*l,void(*f)(void*)){std::cout<<'[';for(size_t i=0;i<l->data.size();++i){if(i)std::cout<<", ";f(l->data[i]);}std::cout<<']';}
#define PRINT_DICT(FN,DT,K,V) void FN(DT*d){if(d->mode){py_print_repr(d);return;}std::cout<<'{';for(size_t i=0;i<d->keys.size();++i){if(i)std::cout<<", ";K(d->keys[i]);std::cout<<": ";V(d->vals[i]);}std::cout<<'}';}
PRINT_DICT(py_print_dict_intint,PyDictIntInt,py_print_i64,py_print_i64) PRINT_DICT(py_print_dict_intfloat,PyDictIntFloat,py_print_i64,py_print_f64) PRINT_DICT(py_print_dict_intbool,PyDictIntBool,py_print_i64,py_print_bool) PRINT_DICT(py_print_dict_intstr,PyDictIntStr,py_print_i64,print_repr)
PRINT_DICT(py_print_dict_strint,PyDictStrInt,print_repr,py_print_i64) PRINT_DICT(py_print_dict_strfloat,PyDictStrFloat,print_repr,py_print_f64) PRINT_DICT(py_print_dict_strbool,PyDictStrBool,print_repr,py_print_bool) PRINT_DICT(py_print_dict_strstr,PyDictStrStr,print_repr,print_repr)
void py_print_exception(const PythonException &e) { std::cerr << e.what() << '\n'; }

// ---- PySub 1.1 runtime: input(), print(sep=, end=), str methods, format(), round(), sum() -------------------
PyStr *py_input(PyStr *prompt) {
    std::cout << prompt->data << std::flush;
    std::string line;
    if (!std::getline(std::cin, line)) throw EOFError("EOF when reading a line");
    return make_str(std::move(line));
}
void py_print_sep_s(PyStr *s) { if (!first) std::cout << s->data; first = false; }
void py_print_end_s(PyStr *s) { std::cout << s->data; }

static bool py_space(char c) {          // CPython's ASCII whitespace for str.isspace/strip/split (incl. \x1c-\x1f)
    return c == ' ' || (c >= '\t' && c <= '\r') || (c >= '\x1c' && c <= '\x1f');
}
static bool py_upper_c(char c) { return c >= 'A' && c <= 'Z'; }
static bool py_lower_c(char c) { return c >= 'a' && c <= 'z'; }
static bool py_alpha_c(char c) { return py_upper_c(c) || py_lower_c(c); }
static bool py_digit_c(char c) { return c >= '0' && c <= '9'; }
static char to_up(char c) { return py_lower_c(c) ? static_cast<char>(c - 'a' + 'A') : c; }
static char to_lo(char c) { return py_upper_c(c) ? static_cast<char>(c - 'A' + 'a') : c; }

static PyStr *strip_impl(PyStr *s, bool left, bool right, const std::string *chars) {
    const std::string &d = s->data;
    auto drop = [&](char c) { return chars ? chars->find(c) != std::string::npos : py_space(c); };
    size_t b = 0, e = d.size();
    if (left) while (b < e && drop(d[b])) ++b;
    if (right) while (e > b && drop(d[e - 1])) --e;
    return make_str(d.substr(b, e - b));
}
PyStr *pystr_strip(PyStr *s) { return strip_impl(s, true, true, nullptr); }
PyStr *pystr_lstrip(PyStr *s) { return strip_impl(s, true, false, nullptr); }
PyStr *pystr_rstrip(PyStr *s) { return strip_impl(s, false, true, nullptr); }
PyStr *pystr_strip_chars(PyStr *s, PyStr *c) { return strip_impl(s, true, true, &c->data); }
PyStr *pystr_lstrip_chars(PyStr *s, PyStr *c) { return strip_impl(s, true, false, &c->data); }
PyStr *pystr_rstrip_chars(PyStr *s, PyStr *c) { return strip_impl(s, false, true, &c->data); }
PyStr *pystr_title(PyStr *s) {
    std::string r = s->data; bool prev_cased = false;
    for (char &c : r) {
        if (py_alpha_c(c)) { c = prev_cased ? to_lo(c) : to_up(c); prev_cased = true; }
        else prev_cased = false;
    }
    return make_str(std::move(r));
}
PyStr *pystr_capitalize(PyStr *s) {
    std::string r = s->data;
    for (size_t i = 0; i < r.size(); ++i) r[i] = i == 0 ? to_up(r[i]) : to_lo(r[i]);
    return make_str(std::move(r));
}
PyStr *pystr_swapcase(PyStr *s) {
    std::string r = s->data;
    for (char &c : r) c = py_upper_c(c) ? to_lo(c) : py_lower_c(c) ? to_up(c) : c;
    return make_str(std::move(r));
}
template <class F> static bool all_of_nonempty(PyStr *s, F f) {
    if (s->data.empty()) return false;
    for (char c : s->data) if (!f(c)) return false;
    return true;
}
bool pystr_isdigit(PyStr *s) { return all_of_nonempty(s, py_digit_c); }
bool pystr_isalpha(PyStr *s) { return all_of_nonempty(s, py_alpha_c); }
bool pystr_isalnum(PyStr *s) { return all_of_nonempty(s, [](char c) { return py_alpha_c(c) || py_digit_c(c); }); }
bool pystr_isspace(PyStr *s) { return all_of_nonempty(s, py_space); }
bool pystr_isupper(PyStr *s) {
    bool cased = false; for (char c : s->data) { if (py_lower_c(c)) return false; if (py_upper_c(c)) cased = true; } return cased;
}
bool pystr_islower(PyStr *s) {
    bool cased = false; for (char c : s->data) { if (py_upper_c(c)) return false; if (py_lower_c(c)) cased = true; } return cased;
}
bool pystr_startswith(PyStr *s, PyStr *p) { return s->data.compare(0, p->data.size(), p->data) == 0 && s->data.size() >= p->data.size(); }
bool pystr_endswith(PyStr *s, PyStr *p) {
    return s->data.size() >= p->data.size() && s->data.compare(s->data.size() - p->data.size(), p->data.size(), p->data) == 0;
}
int64_t pystr_find(PyStr *s, PyStr *n) { size_t i = s->data.find(n->data); return i == std::string::npos ? -1 : static_cast<int64_t>(i); }
int64_t pystr_rfind(PyStr *s, PyStr *n) { size_t i = s->data.rfind(n->data); return i == std::string::npos ? -1 : static_cast<int64_t>(i); }
int64_t pystr_index_of(PyStr *s, PyStr *n) { int64_t i = pystr_find(s, n); if (i < 0) throw ValueError("substring not found"); return i; }
int64_t pystr_count(PyStr *s, PyStr *n) {
    if (n->data.empty()) return static_cast<int64_t>(s->data.size()) + 1;
    int64_t c = 0; size_t i = 0;
    while ((i = s->data.find(n->data, i)) != std::string::npos) { ++c; i += n->data.size(); }
    return c;
}
PyStr *pystr_replace(PyStr *s, PyStr *a, PyStr *b) {
    const std::string &d = s->data, &o = a->data, &n = b->data;
    std::string r;
    if (o.empty()) {                                   // CPython inserts `new` around every character
        r = n; for (char c : d) { r += c; r += n; }
        return make_str(std::move(r));
    }
    size_t i = 0, j;
    while ((j = d.find(o, i)) != std::string::npos) { r.append(d, i, j - i); r += n; i = j + o.size(); }
    r.append(d, i, std::string::npos);
    return make_str(std::move(r));
}
PyListStr *pystr_split_ws(PyStr *s) {
    PyListStr *out = PyListStr_new(); const std::string &d = s->data; size_t i = 0, n = d.size();
    while (true) {
        while (i < n && py_space(d[i])) ++i;
        if (i >= n) break;
        size_t j = i; while (j < n && !py_space(d[j])) ++j;
        PyListStr_append(out, make_str(d.substr(i, j - i))); i = j;
    }
    return out;
}
PyListStr *pystr_split(PyStr *s, PyStr *sep) {
    if (sep->data.empty()) throw ValueError("empty separator");
    PyListStr *out = PyListStr_new(); const std::string &d = s->data, &p = sep->data; size_t i = 0, j;
    while ((j = d.find(p, i)) != std::string::npos) { PyListStr_append(out, make_str(d.substr(i, j - i))); i = j + p.size(); }
    PyListStr_append(out, make_str(d.substr(i)));
    return out;
}
PyStr *pystr_join(PyStr *sep, PyListStr *l) {
    std::string r;
    for (size_t i = 0; i < l->data.size(); ++i) { if (i) r += sep->data; r += l->data[i]->data; }
    return make_str(std::move(r));
}

// format(value, spec): the common subset of Python's format-spec mini-language
// [[fill]align][sign][0][width][,|_][.precision][type], type in d s f F e E g G %.
struct FmtSpec { char fill = ' '; bool fill_given = false; char align = 0; char sign = '-'; bool zero = false;
                 int width = -1; char group = 0; int prec = -1; char type = 0; };
static FmtSpec parse_fmt(const std::string &s) {
    FmtSpec f; size_t i = 0, n = s.size();
    auto is_align = [](char c) { return c == '<' || c == '>' || c == '^' || c == '='; };
    if (n >= 2 && is_align(s[1])) { f.fill = s[0]; f.fill_given = true; f.align = s[1]; i = 2; }
    else if (n >= 1 && is_align(s[0])) { f.align = s[0]; i = 1; }
    if (i < n && (s[i] == '+' || s[i] == '-' || s[i] == ' ')) f.sign = s[i++];
    if (i < n && s[i] == '0') { f.zero = true; ++i; }
    bool hw = false; int w = 0;
    while (i < n && py_digit_c(s[i])) { w = w * 10 + (s[i] - '0'); ++i; hw = true; }
    if (hw) f.width = w;
    if (i < n && (s[i] == ',' || s[i] == '_')) f.group = s[i++];
    if (i < n && s[i] == '.') { ++i; int p = 0; while (i < n && py_digit_c(s[i])) { p = p * 10 + (s[i] - '0'); ++i; } f.prec = p; }
    if (i < n) f.type = s[i++];
    if (i != n) throw ValueError("Invalid format specifier");
    return f;
}
static std::string group_digits(const std::string &digits, char sep) {
    std::string out; size_t n = digits.size();
    for (size_t k = 0; k < n; ++k) { if (k && (n - k) % 3 == 0) out += sep; out += digits[k]; }
    return out;
}
static PyStr *pad_fmt(const std::string &sign, const std::string &body, const FmtSpec &f, bool numeric) {
    char align = f.align, fill = f.fill;
    if (f.zero && !f.fill_given) { fill = '0'; if (!align) align = '='; }
    if (!align) align = numeric ? '>' : '<';
    std::string s = sign + body;
    if (f.width < 0 || static_cast<int>(s.size()) >= f.width) return make_str(std::move(s));
    size_t k = static_cast<size_t>(f.width) - s.size();
    switch (align) {
        case '<': return make_str(s + std::string(k, fill));
        case '>': return make_str(std::string(k, fill) + s);
        case '^': return make_str(std::string(k / 2, fill) + s + std::string(k - k / 2, fill));
        default:  return make_str(sign + std::string(k, fill) + body);
    }
}
static std::string sign_of(bool neg, const FmtSpec &f) { return neg ? "-" : f.sign == '+' ? "+" : f.sign == ' ' ? " " : ""; }
static std::string cfmt(const char *pat, int prec, double v) {
    int n = std::snprintf(nullptr, 0, pat, prec, v);
    std::string out(static_cast<size_t>(n) + 1, '\0');
    std::snprintf(&out[0], out.size(), pat, prec, v);
    out.resize(static_cast<size_t>(n));
    return out;
}
static PyStr *fmt_float(double x, const FmtSpec &f) {
    bool neg = std::signbit(x); double a = std::fabs(x); std::string body;
    char t = f.type;
    if (std::isnan(x) || std::isinf(x)) {
        body = std::isnan(x) ? "nan" : "inf";
        if (t == 'F' || t == 'E' || t == 'G') for (char &c : body) c = to_up(c);
        if (t == '%') body += '%';
        FmtSpec g = f; if (g.zero && !g.fill_given) { g.zero = false; }
        return pad_fmt(sign_of(neg && !std::isnan(x), f), body, g, true);
    }
    if (t == 0) body = format_f64(a);                                   // same digits as str()/repr()
    else if (t == 'f' || t == 'F') body = cfmt("%.*f", f.prec < 0 ? 6 : f.prec, a);
    else if (t == '%') body = cfmt("%.*f", f.prec < 0 ? 6 : f.prec, a * 100.0) + "%";
    else if (t == 'e') body = cfmt("%.*e", f.prec < 0 ? 6 : f.prec, a);
    else if (t == 'E') body = cfmt("%.*E", f.prec < 0 ? 6 : f.prec, a);
    else if (t == 'g') body = cfmt("%.*g", f.prec < 0 ? 6 : (f.prec == 0 ? 1 : f.prec), a);
    else if (t == 'G') body = cfmt("%.*G", f.prec < 0 ? 6 : (f.prec == 0 ? 1 : f.prec), a);
    else throw ValueError("Unknown format code for object of type 'float'");
    if (f.group && (t == 'f' || t == 'F' || t == '%' || t == 0)) {
        size_t dot = body.find_first_not_of("0123456789");
        body = group_digits(body.substr(0, dot), f.group) + (dot == std::string::npos ? "" : body.substr(dot));
    }
    return pad_fmt(sign_of(neg, f), body, f, true);
}
PyStr *py_format_f64(double x, PyStr *spec) { return fmt_float(x, parse_fmt(spec->data)); }
PyStr *py_format_i64(int64_t v, PyStr *spec) {
    FmtSpec f = parse_fmt(spec->data);
    if (f.type && f.type != 'd') return fmt_float(static_cast<double>(v), f);
    uint64_t mag = v < 0 ? (0 - static_cast<uint64_t>(v)) : static_cast<uint64_t>(v);
    std::string body = std::to_string(mag);
    if (f.group) body = group_digits(body, f.group);
    return pad_fmt(sign_of(v < 0, f), body, f, true);
}
PyStr *py_format_bool(bool v, PyStr *spec) {
    if (spec->data.empty()) return pystr_lit(v ? "True" : "False");    // bool.__format__('') is str(); else int's
    return py_format_i64(v ? 1 : 0, spec);
}
PyStr *py_format_str(PyStr *s, PyStr *spec) {
    FmtSpec f = parse_fmt(spec->data);
    if (f.type && f.type != 's') throw ValueError("Unknown format code for object of type 'str'");
    std::string body = f.prec >= 0 ? s->data.substr(0, static_cast<size_t>(f.prec)) : s->data;
    return pad_fmt("", body, f, false);
}

int64_t py_round_i64(double x) {
    if (std::isnan(x)) throw ValueError("cannot convert float NaN to integer");
    if (std::isinf(x)) throw OverflowError("cannot convert float infinity to integer");
    double r = std::nearbyint(x);                                    // round half to even, like CPython
    if (r < -9223372036854775808.0 || r >= 9223372036854775808.0) throw OverflowError("int64 overflow");
    return static_cast<int64_t>(r);
}
double py_round_f64(double x, int64_t n) {
    if (!std::isfinite(x) || x == 0.0) return x;
    if (n > 323) return x;
    if (n >= 0) {                                                    // correctly rounded decimal, as CPython's dtoa
        std::string s = cfmt("%.*f", static_cast<int>(n), x);
        double r = std::strtod(s.c_str(), nullptr);
        return r == 0.0 ? std::copysign(0.0, x) : r;
    }
    if (n < -308) return std::copysign(0.0, x);
    double p = std::pow(10.0, static_cast<double>(-n));
    double r = std::nearbyint(x / p) * p;
    return r == 0.0 ? std::copysign(0.0, x) : r;
}
int64_t py_round_int_n(int64_t v, int64_t n) {
    if (n >= 0) return v;
    if (n <= -19) return 0;
    int64_t p = 1; for (int64_t i = 0; i < -n; ++i) p *= 10;
    int64_t q = py_floordiv_i64(v, p), r = py_mod_i64(v, p);
    if (2 * r > p || (2 * r == p && (q & 1))) q = py_add_i64(q, 1);
    return py_mul_i64(q, p);
}
int64_t py_sum_i64(PyListI64 *l) { int64_t s = 0; for (int64_t x : l->data) s = py_add_i64(s, x); return s; }
int64_t py_sum_bool(PyListBool *l) { int64_t s = 0; for (bool x : l->data) s += x ? 1 : 0; return s; }
double py_sum_f64(PyListF64 *l) {                                    // CPython 3.12+: Neumaier compensated sum
    double f = 0.0, c = 0.0;
    for (double x : l->data) {
        double t = f + x;
        if (std::fabs(f) >= std::fabs(x)) c += (f - t) + x; else c += (x - t) + f;
        f = t;
    }
    if (c != 0.0 && std::isfinite(c)) f += c;
    return f;
}
}
