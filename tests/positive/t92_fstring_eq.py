# PySub 1.3: self-documenting f-string fields {x=}
x: int = 5
name: str = "ab"
f1: float = 2.5
xs: list[int] = [1, 2]
print(f"{x=}")
print(f"{x = }, {name=}, {f1=:.3f}, {xs=}, {x * 2=}")
print(f"{name=!s} {x=:>4} {x+1 = }")
