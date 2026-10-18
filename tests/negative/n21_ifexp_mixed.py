# expect: single static result type
x: int = 1
y: float = 2.5 if x > 0 else 0
print(y)
