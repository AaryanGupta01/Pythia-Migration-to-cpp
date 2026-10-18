def popcount(n: int) -> int:
    c = 0
    while n:
        c += n & 1
        n >>= 1
    return c


def is_pow2(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def gray(n: int) -> int:
    return n ^ (n >> 1)


def lowbit(n: int) -> int:
    return n & -n


print(-5 >> 1, -5 & 3, -5 | 3, -5 ^ 3, ~5, ~-1, ~0)
print(5 << 3, 1 << 62, -1 << 63, -8 >> 100, 8 >> 100, 0 << 5)
print(0xFF & 0b1010, 0o17 | 0x10, 1_000 ^ 0xFF)
print(1 | 2 ^ 3 & 4 << 1, 1 + 2 << 3, 16 >> 2 + 1, 6 & 3 == 2, 1 | 2 < 4)
print(-2 ** 2, ~2 ** 2, -3 ** 2 * 2)
print(popcount(255), popcount(1023), is_pow2(64), is_pow2(65), gray(10), lowbit(12), lowbit(-12))
print(True & False, True | False, True ^ True, True & True, False ^ True)
print(~True, ~False, True << 3, True | 2, 5 & True)
x = 12
x &= 10
print(x)
x |= 3
print(x)
x ^= 5
print(x)
x <<= 4
print(x)
x >>= 2
print(x)
flag = True
flag &= False
print(flag)
flag |= True
print(flag)
mask = (1 << 8) - 1
print(mask, 0x1234 & mask, (0x1234 >> 8) & mask)
n = 0
for i in range(10):
    n |= 1 << i
print(n, bin(n), hex(n), oct(n))
a = [5, 3, 9]
print(a[0] ^ a[1] ^ a[2], a[1] << a[0])
try:
    k = -1
    print(1 << k)
except ValueError as e:
    print("shl", e)
try:
    k = -2
    print(1 >> k)
except ValueError as e:
    print("shr", e)
print(1 << 63 - 1 if False else 7)
