from collections import deque, Counter


def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def binary_search(nums, target):
    left, right = 0, len(nums) - 1

    while left <= right:
        mid = (left + right) // 2

        if nums[mid] == target:
            return mid
        elif nums[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1


def two_sum(nums, target):
    seen = {}

    for i, num in enumerate(nums):
        complement = target - num

        if complement in seen:
            return [seen[complement], i]

        seen[num] = i

    return []


def bfs(graph, start):
    queue = deque([start])
    visited = {start}
    order = []

    while queue:
        node = queue.popleft()
        order.append(node)

        for neighbor in graph.get(node, []):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return order


def fibonacci(n):
    a, b = 0, 1

    for _ in range(n):
        yield a
        a, b = b, a + b


def analyze(nums):
    squares = [x * x for x in nums]
    evens = list(filter(lambda x: x % 2 == 0, nums))
    frequencies = Counter(nums)

    return squares, evens, frequencies


nums = [4, 2, 7, 2, 9, 4, 1]

print("Factorial:", factorial(6))
print("Binary search:", binary_search(sorted(nums), 7))
print("Two sum:", two_sum(nums, 11))

graph = {
    0: [1, 2],
    1: [0, 3],
    2: [0, 3],
    3: [1, 2]
}

print("BFS:", bfs(graph, 0))
print("Fibonacci:", list(fibonacci(8)))

squares, evens, frequencies = analyze(nums)
print("Squares:", squares)
print("Evens:", evens)
print("Frequencies:", dict(frequencies))
print("Unique sorted:", sorted(set(nums)))

stack = []
stack.append(10)
stack.append(20)
print("Popped:", stack.pop())
print("Stack:", stack)

matrix = [[1, 2], [3, 4]]
print("Matrix total:", sum(sum(row) for row in matrix))
print("Transpose:", [list(row) for row in zip(*matrix)])

try:
    print(nums[100])
except IndexError:
    print("Index error handled")

