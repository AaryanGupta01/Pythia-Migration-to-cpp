# PySub 1.4: try/except/else/finally, except (A, B), bare raise, builtin exception hierarchy
def f(n: int) -> str:
    try:
        if n == 0:
            raise ValueError("zero")
        if n == 1:
            return "one"
        r = 10 // (n - 2)
    except (ZeroDivisionError, ValueError) as e:
        print("caught", e)
        return "err"
    else:
        print("else", r)
        return "ok"
    finally:
        print("finally", n)


print(f(0), f(1), f(2), f(3))
xs: list[int] = [1, 2]
for k in range(3):
    try:
        print(xs[k])
    except LookupError:
        print("lookup")
    finally:
        print("done", k)
try:
    try:
        print(1 // 0)
    except ArithmeticError as e:
        print("inner", e)
        raise
except Exception as e:
    print("outer", e)
for i in range(3):
    try:
        if i == 1:
            continue
        print("body", i)
    finally:
        print("cleanup", i)
try:
    raise RuntimeError("boom")
except RuntimeError as e:
    print(e)
try:
    print("x")
finally:
    print("y")
