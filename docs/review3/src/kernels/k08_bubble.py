def lcg(x: int) -> int:
    return (x * 1103515245 + 12345) % 2147483648

def bubble(a: list[int]) -> int:
    n: int = len(a)
    swaps: int = 0
    for i in range(n):
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                t: int = a[j]
                a[j] = a[j + 1]
                a[j + 1] = t
                swaps += 1
    return swaps

data: list[int] = []
x: int = 7
for i in range(3000):
    x = lcg(x)
    data.append(x % 100000)
print(bubble(data), data[0], data[2999])
