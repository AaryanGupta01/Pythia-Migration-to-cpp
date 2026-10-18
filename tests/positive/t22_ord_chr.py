# PySub 1.2: ord() / chr() on ASCII text (Caesar cipher), CPython-exact errors
def shift(text: str, k: int) -> str:
    out: str = ""
    for ch in text:
        if ch.isalpha():
            base: int = ord("A") if ch.isupper() else ord("a")
            out += chr((ord(ch) - base + k) % 26 + base)
        else:
            out += ch
    return out


msg: str = "Hello, World! Meet at 10pm."
enc: str = shift(msg, 3)
print(enc)
print(shift(enc, -3))
print(ord("0"), ord(" "), chr(65) + chr(97) + chr(126), ord(chr(127)))
total: int = 0
for c in "PySub":
    total += ord(c)
print(total)
try:
    print(ord("ab"))
except ValueError as e:
    print("unreachable", e)
