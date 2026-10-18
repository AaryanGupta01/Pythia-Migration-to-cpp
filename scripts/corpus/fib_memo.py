memo = {}


def fib(n):
    if n in memo:
        return memo[n]
    if n < 2:
        result = n
    else:
        result = fib(n - 1) + fib(n - 2)
    memo[n] = result
    return result


for i in [10, 20, 50, 90]:
    print(f"fib({i}) = {fib(i)}")
