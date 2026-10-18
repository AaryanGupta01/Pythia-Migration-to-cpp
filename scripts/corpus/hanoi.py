moves = 0


def hanoi(n, src, dst, via):
    global moves
    if n == 0:
        return
    hanoi(n - 1, src, via, dst)
    moves += 1
    if n >= 18:
        print(f"move disk {n} from {src} to {dst}")
    hanoi(n - 1, via, dst, src)


hanoi(20, "A", "C", "B")
print("total moves:", moves)
