# expect: tuple index must be an integer constant
t: tuple[int, str] = (1, "a")
i: int = 0
print(t[i])
