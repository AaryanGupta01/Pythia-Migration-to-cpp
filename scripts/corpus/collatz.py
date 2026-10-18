def collatz_len(n):
    steps = 1
    while n != 1:
        n = n // 2 if n % 2 == 0 else 3 * n + 1
        steps += 1
    return steps


best_n, best_len = 1, 1
for n in range(1, 300000):
    length = collatz_len(n)
    if length > best_len:
        best_n, best_len = n, length
print(f"longest chain under 300000 starts at {best_n} ({best_len} steps)")
