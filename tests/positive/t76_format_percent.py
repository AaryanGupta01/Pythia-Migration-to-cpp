import string
from string import ascii_lowercase as lower, digits

n = 5
name = "pythia"
x = 3.14159
print("{} {}".format(1, "a"), "{1}{0}{1}".format(1, "a"), "{x}-{y:.2f}".format(x=1, y=2), "{:>5}|{:<4}|{:^6}|{:05d}".format("a", "b", "c", 42))
print("{{}} {}".format(3), "{}".format(3, 4), "{0} {0} {1}".format(n, name), "{!r} {!s}".format("q", 5), "{:,}".format(1234567), "{:+d}".format(5))
print("{:x} {:X} {:o} {:b} {:08b} {:#>6x}".format(255, 255, 8, 5, 5, 255), "{:>10.3f}|".format(x), "{:e}".format(12345.678), "{:%}".format(0.25))
print("{} items, total {:.1f}".format(n, x * n), "{name}!".format(name=name))
print("{:5}|{:<5}|{:>5}".format(1, 2, 3), "{:5}|".format("ab"), "{:.2}".format("abcdef"), "{}".format(True), "{:d}".format(True))
print(f"{n:x} {n:b} {n:03d} {255:X} {x:.2f}")
print("%d items" % n, "%s=%.2f" % (name, x), "%5d|%-5d|%05d" % (1, 2, 3), "%x %X %o %e %g %%" % (255, 255, 8, 1.5, 0.5))
print("%d" % 3.7, "%d" % -3.7, "%s" % 3, "%s" % 3.5, "%s" % True, "%r" % "a", "%c" % 65, "%c" % "z", "%+d % d" % (5, 5), "%f" % 1)
print("%i" % 3, "%.3s" % "abcdef", "%s" % (1,), "%5s|%-5s|" % ("a", "b"), "%10.4f|" % x, "%-10.2f|" % x, "%+.1f" % 2.55, "%03d:%02d" % (7, 5))
print("%s and %s" % ("a", "b"), "%d%%" % 50, "100%%", "%5.1f%%" % 12.345, "%s" % name, "[%s]" % ("x" * 3), "%x" % -255, "%o" % 64)
print("%d, %d" % (n, n * 2), "%s-%s-%s" % (1, 2.5, "z"), "%s" % ("a" + "b"), "%%d" % (), "%e" % 0.000123, "%G" % 1e-10, "%E" % 12345.6789)
print(lower, digits, string.ascii_uppercase, string.ascii_letters, string.punctuation, string.hexdigits, string.octdigits, repr(string.whitespace))
print(len(string.printable), string.digits[3], string.ascii_lowercase[::-1], string.ascii_lowercase.find("k"), "c" in lower)
shift = 3
msg = "hello"
enc = ""
for ch in msg:
    enc += lower[(lower.index(ch) + shift) % 26]
print(enc)
def label(i: int) -> str:
    return "item-{:03d}".format(i)
print(label(7), label(123), "{}:{}".format(label(1), label(2)))
