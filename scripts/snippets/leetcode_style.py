#@@ two_sum
class Solution:
    def twoSum(self, nums, target):
        seen = {}
        for i, x in enumerate(nums):
            if target - x in seen:
                return [seen[target - x], i]
            seen[x] = i
        return []
#@@ is_palindrome
class Solution:
    def isPalindrome(self, s):
        s = ''.join(c.lower() for c in s if c.isalnum())
        return s == s[::-1]
#@@ max_subarray
class Solution:
    def maxSubArray(self, nums):
        best = cur = nums[0]
        for x in nums[1:]:
            cur = max(x, cur + x)
            best = max(best, cur)
        return best
#@@ fib_dp
class Solution:
    def fib(self, n):
        if n < 2:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b
#@@ lcs
class Solution:
    def longestCommonSubsequence(self, text1, text2):
        m, n = len(text1), len(text2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if text1[i - 1] == text2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
        return dp[m][n]
#@@ knapsack
class Solution:
    def knapSack(self, W, wt, val, n):
        dp = [0] * (W + 1)
        for i in range(n):
            for w in range(W, wt[i] - 1, -1):
                dp[w] = max(dp[w], dp[w - wt[i]] + val[i])
        return dp[W]
#@@ binary_search
class Solution:
    def search(self, nums, target):
        lo, hi = 0, len(nums) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if nums[mid] == target:
                return mid
            elif nums[mid] < target:
                lo = mid + 1
            else:
                hi = mid - 1
        return -1
#@@ merge_intervals
class Solution:
    def merge(self, intervals):
        intervals.sort(key=lambda x: x[0])
        out = []
        for s, e in intervals:
            if out and out[-1][1] >= s:
                out[-1][1] = max(out[-1][1], e)
            else:
                out.append([s, e])
        return out
#@@ valid_parens
class Solution:
    def isValid(self, s):
        stack = []
        pairs = {')': '(', ']': '[', '}': '{'}
        for ch in s:
            if ch in pairs:
                if not stack or stack.pop() != pairs[ch]:
                    return False
            else:
                stack.append(ch)
        return not stack
#@@ coin_change
class Solution:
    def coinChange(self, coins, amount):
        dp = [float('inf')] * (amount + 1)
        dp[0] = 0
        for a in range(1, amount + 1):
            for c in coins:
                if c <= a:
                    dp[a] = min(dp[a], dp[a - c] + 1)
        return dp[amount] if dp[amount] != float('inf') else -1
#@@ count_primes
class Solution:
    def countPrimes(self, n):
        if n < 3:
            return 0
        sieve = [True] * n
        sieve[0] = sieve[1] = False
        for i in range(2, int(n ** 0.5) + 1):
            if sieve[i]:
                for j in range(i * i, n, i):
                    sieve[j] = False
        return sum(sieve)
#@@ group_anagrams
class Solution:
    def groupAnagrams(self, strs):
        groups = {}
        for s in strs:
            key = ''.join(sorted(s))
            groups.setdefault(key, []).append(s)
        return list(groups.values())
#@@ rotate_matrix
class Solution:
    def rotate(self, matrix):
        n = len(matrix)
        for i in range(n):
            for j in range(i + 1, n):
                matrix[i][j], matrix[j][i] = matrix[j][i], matrix[i][j]
        for row in matrix:
            row.reverse()
#@@ gfg_gcd_function
def gcd(a, b):
    while b:
        a, b = b, a % b
    return a

def lcm(a, b):
    return a * b // gcd(a, b)

print(lcm(12, 18))
#@@ gfg_input_program
n = int(input("Enter a number: "))
total = 0
for i in range(1, n + 1):
    if i % 3 == 0 or i % 5 == 0:
        total += i
print("Sum of multiples:", total)
#@@ linked_list
class Node:
    def __init__(self, data):
        self.data = data
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None

    def push(self, data):
        node = Node(data)
        node.next = self.head
        self.head = node

    def length(self):
        n, cur = 0, self.head
        while cur:
            n += 1
            cur = cur.next
        return n

ll = LinkedList()
for x in [3, 1, 4, 1, 5]:
    ll.push(x)
print(ll.length())
#@@ bank_class_driver
class Account:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance

    def deposit(self, amt):
        self.balance += amt
        return self.balance

acc = Account("Ann", 100)
acc.deposit(50)
print(acc.owner, acc.balance)
#@@ bfs_queue
from collections import deque
def bfs_shortest(graph, start, target):
    q = deque([start])
    dist = {start: 0}
    while q:
        u = q.popleft()
        if u == target:
            return dist[u]
        for v in graph.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return -1

adj = {1: [2, 3], 2: [4], 3: [4], 4: [5]}
print(bfs_shortest(adj, 1, 5))
print(bfs_shortest(adj, 1, 99))
#@@ k_largest_heap
import heapq
def k_largest(nums, k):
    h = []
    for x in nums:
        heapq.heappush(h, x)
        if len(h) > k:
            heapq.heappop(h)
    return heapq.heappop(h)

print(k_largest([3, 2, 1, 5, 6, 4], 2))
#@@ bisect_search
import bisect
def count_in_range(nums, low, high):
    i = bisect.bisect_left(nums, low)
    j = bisect.bisect_right(nums, high)
    return j - i

data = [1, 3, 5, 7, 9, 11, 13]
print(count_in_range(data, 4, 10))
#@@ prefix_sum_accumulate
import itertools
def running_sum(nums):
    return list(itertools.accumulate(nums))

print(running_sum([1, 2, 3, 4]))
#@@ climb_stairs_memo
from functools import lru_cache
@lru_cache(None)
def climb_stairs(n):
    if n <= 2:
        return n
    return climb_stairs(n - 1) + climb_stairs(n - 2)

print(climb_stairs(10))

