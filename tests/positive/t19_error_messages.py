"""Exception texts and reprs must match the CPython running the comparison (3.11-3.14 word some differently)."""


def attempt(kind: int) -> str:
    d: dict[str, int] = {"a": 1}
    e: dict[int, str] = {1: "x"}
    xs: list[int] = [1, 2, 3]
    try:
        if kind == 0:
            print(1 // 0)
        elif kind == 1:
            print(7 % 0)
        elif kind == 2:
            print(1 / 0)
        elif kind == 3:
            print(1.5 / 0.0)
        elif kind == 4:
            print(1.5 // 0.0)
        elif kind == 5:
            print(1.5 % 0.0)
        elif kind == 6:
            print(int(" 12x "))
        elif kind == 7:
            print(float("abc"))
        elif kind == 8:
            print(d["missing"])
        elif kind == 9:
            print(e[42])
        elif kind == 10:
            print(xs.index(99))
        elif kind == 11:
            xs.remove(99)
        elif kind == 12:
            print("abc".index("z"))
        elif kind == 13:
            print("a,b".split(""))
        elif kind == 14:
            print(xs[10])
        else:
            print(round(float("nan")))
    except ZeroDivisionError as err:
        return "ZeroDivisionError: " + str(err)
    except ValueError as err:
        return "ValueError: " + str(err)
    except KeyError as err:
        return "KeyError: " + str(err)
    except IndexError as err:
        return "IndexError: " + str(err)
    return "no error"


for k in range(16):
    print(k, attempt(k))

print(int("  42  "), float(" 2.5\n"), ["it's", 'say "hi"', "tab\there", "both ' and \""])
