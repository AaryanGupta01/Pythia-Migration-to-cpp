xs = [1, 2, 3, 2, 1]
print(xs.index(2), xs.index(2, 2), xs.index(2, -2), xs.index(1, 1), xs.index(2, 0, 2), xs.index(1, -1, 5))
ws = ["a", "b", "a"]
print(ws.index("a", 1), ws.index("b", 0, 3))
fs = [1.5, 2.5]
print(fs.index(2.5, 1))
d = {"x": 1, "y": 2, "z": 3}
print(list(d.keys()), list(d.values()), len(d.keys()), sorted(d.values()), sum(d.values()), max(d.values()))
for k in d.keys():
    print(k, d[k])
for v in d.values():
    print(v)
print("x" in d.keys(), 2 in d.values(), 9 in d.values(), "q" not in d.keys())
print(d.pop("y"), d, d.pop("nope", -1), d.pop("x", 7), d)
print(d.setdefault("z", 99), d.setdefault("w", 5), d)
e = {"a": 10}
e.update(d)
print(e)
e.update({"a": 11, "b": 12})
print(e)
c = e.copy()
c["a"] = 0
print(e["a"], c["a"], len(c))
c.clear()
print(c, len(c))
print(dict.fromkeys(["p", "q", "p"], 0), dict.fromkeys([1, 2, 3], "v"), dict.fromkeys([1, 2], 1.5))
n = {1: 2.5, 2: 3.5}
print(list(n.keys()), list(n.values()), n.setdefault(3, 1.0),n.pop(1), n)
flags = {"on": True}
print(flags.setdefault("off", False), flags)
for key in sorted(e.keys()):
    print(key, e[key])
print(", ".join(e.keys()), list(e.keys())[0])
try:
    print(d.pop("missing"))
except KeyError as err:
    print("KeyError", err)
try:
    print({1: 1}.pop(5))
except KeyError as err:
    print("KeyError", err)
try:
    print(xs.index(9, 1))
except ValueError as err:
    print("ValueError", err)
try:
    print(ws.index("z", 0, 2))
except ValueError as err:
    print("ValueError", err)
