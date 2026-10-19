d = {"a": 1, "b": 2}
print(d.get("a"), d.get("z"), d.get("z", 0))
x = d.get("b")
if x is not None:
    print(x + 1)
k = "q"
print(d.get(k) is None, max(d, key=d.get), sorted(d, key=d.get, reverse=True))
