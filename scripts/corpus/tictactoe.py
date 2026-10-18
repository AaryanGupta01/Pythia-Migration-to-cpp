def winner(board):
    lines = [
        [(0, 0), (0, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)], [(2, 0), (2, 1), (2, 2)],
        [(0, 0), (1, 0), (2, 0)], [(0, 1), (1, 1), (2, 1)], [(0, 2), (1, 2), (2, 2)],
        [(0, 0), (1, 1), (2, 2)], [(0, 2), (1, 1), (2, 0)],
    ]
    for line in lines:
        vals = [board[r][c] for r, c in line]
        if vals[0] != " " and vals.count(vals[0]) == 3:
            return vals[0]
    return None


def show(board):
    for i, row in enumerate(board):
        print(" | ".join(row))
        if i < 2:
            print("--+---+--")


board = [[" "] * 3 for _ in range(3)]
moves = [(1, 1), (0, 0), (2, 2), (0, 2), (0, 1), (2, 1), (1, 0), (1, 2)]
player = "X"
for r, c in moves:
    board[r][c] = player
    w = winner(board)
    if w:
        show(board)
        print(f"{w} wins!")
        break
    player = "O" if player == "X" else "X"
else:
    show(board)
    print("draw")
