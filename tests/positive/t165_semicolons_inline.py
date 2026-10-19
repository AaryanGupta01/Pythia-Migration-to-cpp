# PySub 1.4: semicolons and one-line suites
def f(n: int) -> int:
    a = 1; b = 2
    if n > 3: return a + b
    if n == 0: return 0
    else: a += 5; b += 7
    for i in range(3): a += i; b += 1
    while a < 20: a += 4
    return a * 100 + b;


print(f(0), f(1), f(5))
x = 1; y = 2; print(x + y);
if x < y: print("lt"); print("done")
else: print("ge")
class P: pass
def g() -> None: print("g")
g()
