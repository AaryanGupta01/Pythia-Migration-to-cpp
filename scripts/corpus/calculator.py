def calculate(a, op, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise ZeroDivisionError("cannot divide by zero")
        return a / b
    raise ValueError(f"unknown operator {op}")


while True:
    line = input("calc> ")
    if line == "q":
        print("bye")
        break
    parts = line.split()
    if len(parts) != 3:
        print("usage: <number> <op> <number>")
        continue
    try:
        x, op, y = float(parts[0]), parts[1], float(parts[2])
        print("=", calculate(x, op, y))
    except ValueError as e:
        print("error:", e)
    except ZeroDivisionError as e:
        print("error:", e)
