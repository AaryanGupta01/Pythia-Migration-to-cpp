inventory = {"apple": 3, "banana": 12, "cherry": 0}
prices = {"apple": 0.5, "banana": 0.25, "cherry": 3.0}

while True:
    cmd = input("> ").strip().split()
    if not cmd:
        continue
    if cmd[0] == "quit":
        break
    elif cmd[0] == "add" and len(cmd) == 3:
        item, qty = cmd[1], int(cmd[2])
        inventory[item] = inventory.get(item, 0) + qty
        print(f"added {qty} {item}")
    elif cmd[0] == "show":
        for item in sorted(inventory):
            value = inventory[item] * prices.get(item, 1.0)
            print(f"{item:<8} {inventory[item]:>4}  ${value:,.2f}")
    elif cmd[0] == "out":
        empty = [k for k, v in inventory.items() if v == 0]
        print("out of stock:", ", ".join(empty) if empty else "nothing")
    else:
        print("unknown command")
