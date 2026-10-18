def matmul(a, b):
    n, m, p = len(a), len(b), len(b[0])
    return [[sum(a[i][k] * b[k][j] for k in range(m)) for j in range(p)] for i in range(n)]


def identity(n):
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]


def power(mat, e):
    result = identity(len(mat))
    while e > 0:
        if e % 2 == 1:
            result = matmul(result, mat)
        mat = matmul(mat, mat)
        e //= 2
    return result


fibm = [[1, 1], [1, 0]]
print("fib(80) via matrix power:", power(fibm, 80)[0][1])
big = [[(i * 7 + j * 3) % 10 for j in range(120)] for i in range(120)]
sq = matmul(big, big)
print("trace of big^2:", sum(sq[i][i] for i in range(120)))
