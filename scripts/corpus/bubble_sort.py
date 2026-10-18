def bubble_sort(arr):
    arr = arr[:]
    n = len(arr)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
                swapped = True
        if not swapped:
            break
    return arr


def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


data = [(i * 7919) % 3001 for i in range(3000)]
s = bubble_sort(data)
print("first ten:", s[:10])
print("sorted correctly:", s == sorted(data))
for t in [0, 1500, 2999, 5000]:
    print(f"search {t}: index {binary_search(s, t)}")
