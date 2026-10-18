s = "hello world"
print("-42".zfill(6), "+4".zfill(5), "".zfill(3), "abc".zfill(2), "7".zfill(3), "-".zfill(3))
print("abc".center(6, "*"), "abc".center(7, "*"), "ab".center(5, "*"), "abc".center(2), "abc".center(8), "x".center(4, "-"))
print("abc".ljust(6, "."), "abc".rjust(6, "."), "abc".ljust(2), "abc".rjust(2), "abc".ljust(5) + "|", "abc".rjust(5))
print("123".isnumeric(), "".isnumeric(), "12a".isnumeric(), "123".isdecimal(), "a".isdecimal())
print("Hello World".istitle(), "Hello world".istitle(), "HELLO".istitle(), "Hello 1A".istitle(), "".istitle(), "hello".istitle())
print("AbC".casefold(), "ABC def".casefold())
print("abcabc".removeprefix("abc"), "abcabc".removesuffix("abc"), "abc".removeprefix(""), "abc".removesuffix(""), "abc".removeprefix("x"), "abc".removesuffix("abcd"))
print(repr("a\tbc\td".expandtabs()), repr("a\tbc\td\n\te".expandtabs(4)), repr("a\tb".expandtabs(0)), repr("a\tb".expandtabs(1)))
print("a,b,c,d".split(",", 1), "a,b,c,d".split(",", 2), "a,b,c,d".split(",", 0), "a,b".split(",", -1), "a,b,c".split(",", 10))
print("  a b  c ".split(None, 1), "  a b  c ".split(None, 0), "  a b  c ".split(None), "   ".split(None, 2), "a b c".split(None, 5))
print("a,b,c,d".rsplit(",", 1), "a,b,c,d".rsplit(",", 2), "a,b,c,d".rsplit(","), "a,b".rsplit(",", 0), ",a,".rsplit(","))
print("  a b  c ".rsplit(None, 1), "  a b  c ".rsplit(), "  a b  c ".rsplit(None, 0), "".rsplit(None, 1), "abc".rsplit(None, 1))
print("a--b--c".rsplit("--", 1), "a--b--c".split("--", 1), "aaa".rsplit("aa", 1), "aaa".split("aa", 1))
print("a\nb\r\nc\n\nd".splitlines(), "a\nb\r\nc\n".splitlines(True), "a\x0bb\x0cc\x1cd\x1de\x1ef".splitlines(), "".splitlines(), "\n".splitlines(), "x".splitlines(True))
print("aaaa".count("a", 1, 3), "aaaa".count("", 1, 3), "aaaa".count("", 5), "aaaa".count("", 4), "abcabc".count("c", -3), "abab".count("ab", 1), "abab".count("ab"))
print("abcabc".find("b", 2), "abcabc".find("b", 2, 4), "abc".find("", 3), "abc".find("", 4), "abc".find("", -10), "abcabc".rfind("b", 0, 4), "abcabc".rfind("b", 2), "abcabc".find("c", -2))
print("abcabc".index("b", 2), "abcabc".rindex("b"), "abcabc".rindex("b", 0, 4), "abc".index("c", -1))
print("abcabc".startswith("ca", 2), "abcabc".startswith("", 7), "abcabc".startswith("", 6), "abcabc".startswith("abc", 0, 2), "abcabc".startswith("abc", 3))
print("abcabc".endswith("ab", 0, 5), "abcabc".endswith("", 0, -10), "abcabc".endswith("abc", 3), "abcabc".endswith("bca", 1, 5), "abcabc".endswith("c", 0, 3))
print("abc".isascii(), "".isascii())
n = 7
w = 5
print(str(n).zfill(w), str(n).rjust(w, "0"), "x".center(w), "ab".ljust(w, "-") + "|")
print(len(s.center(21)), s.title().istitle(), s.split(" ", 1)[1], s.rsplit(" ", 1)[0])
text = "one two  three"
print(text.split(None, 1), text.splitlines(), text.count("o", 3), text.find("t", 5))
d = {"b": 2, "a": 1}
print(",".join(d.keys()), "-".join(sorted(d.keys())), "x".join(d.keys()))
for bad in ["", "ab"]:
    try:
        print("abc".center(6, bad))
    except TypeError as e:
        print("center", e)
    try:
        print("abc".ljust(6, bad))
    except TypeError as e:
        print("ljust", e)
try:
    print("abc".index("z", 1))
except ValueError as e:
    print("index", e)
try:
    print("abc".rindex("z"))
except ValueError as e:
    print("rindex", e)
try:
    sep = ""
    print("abc".rsplit(sep, 1))
except ValueError as e:
    print("rsplit", e)
try:
    sep = ""
    print("abc".split(sep, 1))
except ValueError as e:
    print("split", e)
