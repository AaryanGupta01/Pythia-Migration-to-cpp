def knapsack(w: list[int], v: list[int], cap: int) -> int:
    dp: list[int] = [0] * (cap + 1)
    for i in range(len(w)):
        for c in range(cap, w[i] - 1, -1):
            cand: int = dp[c - w[i]] + v[i]
            if cand > dp[c]:
                dp[c] = cand
    return dp[cap]

W: list[int] = []
V: list[int] = []
x: int = 3
for i in range(200):
    x = (x * 1103515245 + 12345) % 2147483648
    W.append(5 + x % 40)
    V.append(1 + (x // 64) % 100)
print(knapsack(W, V, 20000))
