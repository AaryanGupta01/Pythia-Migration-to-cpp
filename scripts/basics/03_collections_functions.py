#@@ dict_basics
d = {"a": 1, "b": 2}
d["c"] = 3
d["a"] += 10
print(d, len(d), d.get("z"), d.get("z", 0), "b" in d, "z" in d)
print(list(d.keys()), list(d.values()), list(d.items()))
print(d.pop("b"), d, d.setdefault("q", 9), d)
d.update({"x": 1, "a": 0})
print(d)
for k, v in d.items():
    print(k, v)
#@@ dict_word_count
text = "the cat and the hat and the bat"
counts = {}
for w in text.split():
    counts[w] = counts.get(w, 0) + 1
for w, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
    print(w, c)
#@@ dict_comprehension_invert
sq = {x: x * x for x in range(6)}
inv = {v: k for k, v in sq.items()}
print(sq, inv, {k: v for k, v in sq.items() if v % 2 == 0})
#@@ nested_dict_records
students = {"ann": {"math": 90, "art": 70}, "bob": {"math": 60, "art": 85}}
for name, marks in students.items():
    print(name, sum(marks.values()) / len(marks), max(marks, key=marks.get))
students["cy"] = {"math": 77}
print(len(students), sorted(students))
#@@ set_operations
a = {1, 2, 3, 4}
b = {3, 4, 5}
print(sorted(a | b), sorted(a & b), sorted(a - b), sorted(a ^ b), a <= b, {3} <= a, 2 in a, len(a))
a.add(10)
a.discard(1)
a.remove(2)
print(sorted(a), sorted(set("hello")), sorted(set([3, 1, 3])))
#@@ tuple_basics
t = (1, "two", 3.0)
print(t, t[0], t[-1], len(t), t + (4,), t[1:], "two" in t)
a, b, c = t
print(a, b, c)
x, y = 1, 2
x, y = y, x
print(x, y)
def minmax(v):
    return min(v), max(v)
lo, hi = minmax([4, 9, 1])
print(lo, hi, minmax([5]))
#@@ sort_list_of_tuples
people = [("ann", 30), ("bob", 25), ("cy", 30), ("di", 22)]
print(sorted(people, key=lambda p: p[1]), sorted(people, key=lambda p: (-p[1], p[0])))
people.sort()
print(people, max(people, key=lambda p: p[1]))
#@@ counter_defaultdict_deque
from collections import Counter, defaultdict, deque
c = Counter("abracadabra")
print(c.most_common(2), c["a"], c["z"])
g = defaultdict(list)
for w in ["apple", "avocado", "banana", "blueberry", "cherry"]:
    g[w[0]].append(w)
print(dict(g))
dq = deque([1, 2, 3])
dq.append(4)
dq.appendleft(0)
print(dq.popleft(), dq.pop(), list(dq), len(dq))
#@@ heapq_bisect
import heapq
import bisect
h = []
for x in [5, 1, 8, 3, 2]:
    heapq.heappush(h, x)
print([heapq.heappop(h) for _ in range(3)], h[0])
a = [1, 3, 5, 7]
print(bisect.bisect_left(a, 5), bisect.bisect_right(a, 5), bisect.bisect_left(a, 4))
bisect.insort(a, 4)
print(a, heapq.nlargest(2, a), heapq.nsmallest(2, a))
#@@ function_defaults_kwargs
def greet(name, greeting="Hello", punct="!"):
    return greeting + ", " + name + punct

print(greet("Ann"), greet("Bob", "Hi"), greet("Cy", punct="?"), greet(punct=".", name="Di"))
#@@ function_multiple_returns
def stats(nums):
    n = len(nums)
    mean = sum(nums) / n
    var = sum((x - mean) ** 2 for x in nums) / n
    return n, mean, var ** 0.5

n, m, s = stats([2, 4, 4, 4, 5, 5, 7, 9])
print(n, m, s)
print(divmod(17, 5), divmod(-17, 5))
#@@ recursion_factorial_fib
def fact(n):
    return 1 if n <= 1 else n * fact(n - 1)

def fib(n):
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fact(10), [fib(i) for i in range(15)])
#@@ memoized_fib_dict
memo = {}
def fib(n):
    if n in memo:
        return memo[n]
    memo[n] = n if n < 2 else fib(n - 1) + fib(n - 2)
    return memo[n]

print(fib(50), fib(80), len(memo))
#@@ lru_cache_decorator
from functools import lru_cache

@lru_cache(maxsize=None)
def paths(r, c):
    if r == 0 or c == 0:
        return 1
    return paths(r - 1, c) + paths(r, c - 1)

print(paths(10, 10), paths(16, 16))
#@@ nested_function_closure
def count_calls(n):
    count = 0
    def inc():
        nonlocal count
        count += 1
        return count
    for _ in range(n):
        inc()
    return inc()

print(count_calls(3))
def outer(n):
    def helper(x):
        return x * n
    return [helper(i) for i in range(4)]
print(outer(3))
#@@ global_variable
total = 0
def add(x):
    global total
    total += x

for i in range(5):
    add(i)
print(total)
#@@ lambda_basics
sq = lambda x: x * x
add = lambda a, b: a + b
print(sq(7), add(2, 3), (lambda x: x + 1)(9))
#@@ hanoi_recursion
moves = []
def hanoi(n, src, dst, via):
    if n == 0:
        return
    hanoi(n - 1, src, via, dst)
    moves.append((src, dst))
    hanoi(n - 1, via, dst, src)

hanoi(4, "A", "C", "B")
print(len(moves), moves[:5])
#@@ permutations_subsets
def perms(a):
    if len(a) <= 1:
        return [a]
    out = []
    for i in range(len(a)):
        for p in perms(a[:i] + a[i + 1:]):
            out.append([a[i]] + p)
    return out

def subsets(a):
    res = [[]]
    for x in a:
        res += [s + [x] for s in res]
    return res

print(perms([1, 2, 3]), subsets([1, 2, 3]))
#@@ dp_knapsack_lcs
def knapsack(W, wt, val):
    dp = [0] * (W + 1)
    for i in range(len(wt)):
        for w in range(W, wt[i] - 1, -1):
            dp[w] = max(dp[w], dp[w - wt[i]] + val[i])
    return dp[W]

def lcs(a, b):
    dp = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            dp[i][j] = dp[i - 1][j - 1] + 1 if a[i - 1] == b[j - 1] else max(dp[i - 1][j], dp[i][j - 1])
    return dp[-1][-1]

print(knapsack(50, [10, 20, 30], [60, 100, 120]), lcs("AGGTAB", "GXTXAYB"))
#@@ graph_bfs_dfs
graph = {"A": ["B", "C"], "B": ["D"], "C": ["D", "E"], "D": ["F"], "E": ["F"], "F": []}
from collections import deque
def bfs(start):
    seen, order, q = {start}, [], deque([start])
    while q:
        n = q.popleft()
        order.append(n)
        for m in graph[n]:
            if m not in seen:
                seen.add(m)
                q.append(m)
    return order

def dfs(n, seen=None):
    if seen is None:
        seen = []
    seen.append(n)
    for m in graph[n]:
        if m not in seen:
            dfs(m, seen)
    return seen

print(bfs("A"), dfs("A"))
