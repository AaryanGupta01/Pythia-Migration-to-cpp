# PySub 1.3: list repetition [x] * n, n * [x]; shallow like Python ([[0]] * 3 shares the inner list)
n: int = 4
row: list[int] = [0] * n
print(row, [1, 2] * 3, 2 * ["ab"], [7] * 0, [7] * -2, [True] * 2, [0.5] * 2)
grid: list[list[int]] = [[0] * 3 for _ in range(2)]
grid[0][1] = 5
print(grid)
shared: list[list[int]] = [[0] * 2] * 3
shared[0][0] = 9
print(shared)


def cut_rod(price: list[int], n: int) -> int:
    dp: list[int] = [0] * (n + 1)
    for i in range(1, n + 1):
        for j in range(1, i + 1):
            dp[i] = max(dp[i], price[j - 1] + dp[i - j])
    return dp[n]


print(cut_rod([1, 5, 8, 9, 10, 17, 17, 20], 8))
