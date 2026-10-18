name = "o'brien"
q = 'say "hi"'
both = "it's \"x\""
nums = [1, 2, 3]
words = ["a", "b'c"]
d = {"k": 1.5, "j": 2.0}
t = (1, "x", 2.5, True)
i = 3
print(repr("plain"), repr(name), repr(q), repr(both), repr("tab\there\nnl\\bs"), repr(""), repr("\x01\x7f"))
print(repr(5), repr(-5), repr(2.5), repr(1e20), repr(1e-7), repr(True), repr(False), repr(0.1 + 0.2), repr(3.0))
print(repr(nums), repr(words), repr(d), repr(t), repr([(1, "a"), (2, "b")]), repr({1: "x"}), repr(()), repr((1,)))
print(f"{name!r} {q!r} {nums!r} {i!r} {2.5!r} {name!s} {nums!r:>12}|{name!r:<12}|{i!s:>4}|{t!r}")
print("{!r} {!s}".format("a'", "b'"))
print("abc" "def", "a" 'b' "c", "x"
      "y")
print(f"{i}. {name} - " f"{words[0]} marks", "pre-" f"{i}" "-post", "no brace {" f"{i}" "} here")
msg = ("first line, "
       "second line, "
       f"third {i}")
print(msg)
print("%d %s" "!" % (i, name), ("%s" "-%s") % ("a", "b"), "{}" "-{}".format(1, 2))
print(len("ab" "cd"), "ab" "cd" == "abcd", ("a" "b").upper(), "x" "y" * 2)
for k in d:
    print(f"{k!r}: {d[k]!r}")
print(divmod(7, 2), divmod(-7, 2), divmod(7, -2), divmod(-7, -2), divmod(0, 5), divmod(7.5, 2), divmod(-7.5, 2), divmod(7, 2.0), divmod(1e300, 7.0))
q2, r2 = divmod(17, 5)
print(q2, r2, divmod(i, 2)[0], divmod(-0.0, 1.0), divmod(5.0, -2.0), divmod(True, 2))
try:
    z = 0
    print(divmod(5, z))
except ZeroDivisionError as e:
    print(e)
try:
    zf = 0.0
    print(divmod(5.0, zf))
except ZeroDivisionError as e:
    print(e)
