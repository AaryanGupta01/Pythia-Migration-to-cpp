def modinv(a: int, m: int) -> int:
    return pow(a, -1, m)


def fastpow(a: int, b: int, m: int) -> int:
    return pow(a, b, m)


print(pow(2, 10), pow(2, 0), pow(-3, 3), pow(2.0, 3), pow(2, 0.5), pow(0, 0), pow(2, -1), pow(2, -2), pow(10, -3))
print(pow(3, 4, 5), pow(2, 100, 1000000007), pow(-2, 3, 5), pow(2, 3, -5), pow(2, 3, 1), pow(2, 0, 1), pow(5, 0, 7), pow(0, 5, 7))
print(modinv(3, 7), modinv(2, 5), modinv(10, 17), pow(2, -1, 5), pow(-3, -1, 7), pow(3, -2, 11), fastpow(7, 222, 1000))
print(bin(5), bin(-5), bin(0), hex(255), hex(-255), hex(0), oct(8), oct(-8), bin(True), hex(1 << 40))
print(int("ff", 16), int("FF", 16), int("0x1f", 0), int("0x1f", 16), int("z", 36), int("-101", 2), int(" 12 "), int("+7"), int("0b101", 0))
print(int("0o17", 0), int("0b11", 2), int("1_000", 10), int("1_0", 0), int("0", 0), int("00", 0), int(" -0x10 ", 0), int("7", 8))
print(int(3.9), int(-3.9), int(0.0), int(True), int("12") + 1, int(1e18), int(-1e18))
print(float("inf"), float("-inf"), float("nan"), float(" Infinity "), float("1_0.5"), float("1e500"), float("-1e500"), float(".5"), float("5."))
print(float("1e-400"), float("+3.5e2"), float("1E3"), float("  7  "), float("-0"), float("infinity") > 1e308)
print(round(2.5), round(3.5), round(-2.5), round(0.5), round(1.5), round(-0.5), round(2.4999), round(1e15 + 0.5), round(True))
print(round(2.675, 2), round(0.125, 2), round(1234.5, -2), round(-0.4, 0), round(1.005, 2), round(123.456, -1), round(7, 1), round(2.5, 0))
print(round(15, -1), round(25, -1), round(-15, -1), round(5, -1), round(1234, -2), round(1e300, -299), round(5e-324, 300))
print(abs(-5), abs(-2.5), abs(0), abs(True), abs(-0.0))
print(2 ** 10, 2.0 ** -1, (-8.0) ** 3, 0.0 ** 0, 2 ** 0.5 > 1.41, 10.0 ** 2, (-2.0) ** 3)
bits = 0
for ch in "1011":
    bits = bits * 2 + int(ch)
print(bits, int("1011", 2), bin(bits)[2:], hex(255)[2:].upper(), oct(64)[2:])
for bad in ["12", "", " ", "0x", "1__0", "_1", "1_", "-", "5 5", "1.5"]:
    try:
        print(int(bad, 2))
    except ValueError as e:
        print(e)
for base in [1, 37, -1]:
    try:
        print(int("1", base))
    except ValueError as e:
        print(e)
for bad in ["abc", "", "1e", "--1", "1_", "0x10", "nan(1)", "in f", "1 2"]:
    try:
        print(float(bad))
    except ValueError as e:
        print(e)
for bad in ["010", "0b2", "9x"]:
    try:
        print(int(bad, 0))
    except ValueError as e:
        print(e)
try:
    z = 0
    print(pow(5, 2, z))
except ValueError as e:
    print(e)
try:
    print(pow(2, -1, 4))
except ValueError as e:
    print(e)
try:
    z = 0
    print(pow(z, -1))
except ZeroDivisionError as e:
    print(e)
try:
    zf = 0.0
    print(zf ** -1)
except ZeroDivisionError as e:
    print(e)
try:
    print(int(float("nan")))
except ValueError as e:
    print(e)
try:
    print(int(float("inf")))
except OverflowError as e:
    print(e)
try:
    print(round(float("nan")))
except ValueError as e:
    print(e)
try:
    print(round(float("inf")))
except OverflowError as e:
    print(e)
try:
    print(2.0 ** 2000)
except OverflowError as e:
    print(e)
