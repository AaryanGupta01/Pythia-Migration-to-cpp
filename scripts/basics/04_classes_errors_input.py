#@@ class_basic
class Dog:
    def __init__(self, name, age):
        self.name = name
        self.age = age

    def bark(self):
        return self.name + " says woof"

    def birthday(self):
        self.age += 1

d = Dog("Rex", 3)
d.birthday()
print(d.bark(), d.age)
#@@ class_str_repr
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __str__(self):
        return f"({self.x}, {self.y})"

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def __add__(self, o):
        return Point(self.x + o.x, self.y + o.y)

    def __eq__(self, o):
        return self.x == o.x and self.y == o.y

p = Point(1, 2) + Point(3, 4)
print(p, repr(p), p == Point(4, 6), p == Point(0, 0))
print(f"{p}", [str(Point(i, i)) for i in range(3)])
#@@ class_bank_account
class Account:
    def __init__(self, owner, balance=0):
        self.owner = owner
        self.balance = balance
        self.history = []

    def deposit(self, amt):
        if amt <= 0:
            raise ValueError("Deposit must be positive")
        self.balance += amt
        self.history.append(("deposit", amt))

    def withdraw(self, amt):
        if amt > self.balance:
            raise ValueError("Insufficient funds")
        self.balance -= amt
        self.history.append(("withdraw", amt))

a = Account("Ann", 100)
a.deposit(50)
try:
    a.withdraw(500)
except ValueError as e:
    print("Error:", e)
a.withdraw(30)
print(a.owner, a.balance, a.history)
#@@ class_inheritance_super
class Animal:
    def __init__(self, name):
        self.name = name

    def speak(self):
        return "..."

    def describe(self):
        return self.name + " says " + self.speak()

class Dog(Animal):
    def speak(self):
        return "Woof"

class Puppy(Dog):
    def __init__(self, name, toy):
        super().__init__(name)
        self.toy = toy

    def speak(self):
        return super().speak() + "!"

for a in [Animal("Generic"), Dog("Rex"), Puppy("Bit", "ball")]:
    print(a.describe())
#@@ class_linked_list
class Node:
    def __init__(self, val):
        self.val = val
        self.next = None

class LinkedList:
    def __init__(self):
        self.head = None
        self.size = 0

    def push_back(self, v):
        n = Node(v)
        self.size += 1
        if not self.head:
            self.head = n
            return
        cur = self.head
        while cur.next:
            cur = cur.next
        cur.next = n

    def to_list(self):
        out, cur = [], self.head
        while cur:
            out.append(cur.val)
            cur = cur.next
        return out

    def reverse(self):
        prev, cur = None, self.head
        while cur:
            cur.next, prev, cur = prev, cur, cur.next
        self.head = prev

ll = LinkedList()
for x in [1, 2, 3, 4]:
    ll.push_back(x)
ll.reverse()
print(ll.to_list(), ll.size)
#@@ class_bst
class TreeNode:
    def __init__(self, key):
        self.key = key
        self.left = None
        self.right = None

def insert(root, key):
    if root is None:
        return TreeNode(key)
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    return root

def inorder(root):
    return inorder(root.left) + [root.key] + inorder(root.right) if root else []

def height(root):
    return 0 if root is None else 1 + max(height(root.left), height(root.right))

root = None
for k in [50, 30, 70, 20, 40, 60, 80, 35]:
    root = insert(root, k)
print(inorder(root), height(root))
#@@ class_stack_queue
class Stack:
    def __init__(self):
        self.items = []

    def push(self, x):
        self.items.append(x)

    def pop(self):
        return self.items.pop()

    def is_empty(self):
        return len(self.items) == 0

    def __len__(self):
        return len(self.items)

def balanced(s):
    st = Stack()
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in s:
        if ch in "([{":
            st.push(ch)
        elif ch in pairs:
            if st.is_empty() or st.pop() != pairs[ch]:
                return False
    return st.is_empty()

print(balanced("{[()]}"), balanced("([)]"), balanced("(("), len(Stack()))
#@@ leetcode_solution_class
class Solution:
    def isValid(self, s):
        stack = []
        m = {")": "(", "]": "[", "}": "{"}
        for c in s:
            if c in m:
                if not stack or stack.pop() != m[c]:
                    return False
            else:
                stack.append(c)
        return not stack

    def maxProfit(self, prices):
        lo, best = float("inf"), 0
        for p in prices:
            lo = min(lo, p)
            best = max(best, p - lo)
        return best

sol = Solution()
print(sol.isValid("()[]{}"), sol.isValid("(]"), sol.maxProfit([7, 1, 5, 3, 6, 4]), sol.maxProfit([7, 6, 4]))
#@@ try_except_basic
def div(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return "cannot divide by zero"

print(div(10, 4), div(1, 0))
for s in ["12", "x", "3.5"]:
    try:
        print(int(s) * 2)
    except ValueError as e:
        print("bad:", e)
#@@ try_except_index_key
data = [1, 2, 3]
d = {"a": 1}
for f in [lambda: data[5], lambda: d["z"], lambda: 1 // 0, lambda: int("q")]:
    try:
        f()
    except IndexError as e:
        print("IndexError:", e)
    except KeyError as e:
        print("KeyError:", e)
    except (ZeroDivisionError, ValueError) as e:
        print(type(e).__name__, e)
#@@ raise_finally_else
def check(n):
    try:
        if n < 0:
            raise ValueError("negative")
        result = n * 2
    except ValueError as e:
        print("caught", e)
        return None
    else:
        print("ok")
        return result
    finally:
        print("cleanup", n)

print(check(4), check(-1))
#@@ assert_statement
def safe_sqrt(x):
    assert x >= 0, "x must be non-negative"
    return x ** 0.5

print(safe_sqrt(16))
try:
    safe_sqrt(-1)
except AssertionError as e:
    print("assertion failed:", e)
#@@ recursion_limit_error
def depth(n):
    return depth(n + 1)

try:
    depth(0)
except RecursionError:
    print("recursion limit hit")
def sum_to(n):
    return 0 if n == 0 else n + sum_to(n - 1)
print(sum_to(900))
#@@ uncaught_error_exit
nums = [1, 2, 3]
print(nums[1])
print(nums[10])
#@@stdin
#@@ input_name_age
name = input("Name: ")
age = int(input("Age: "))
print("Hello,", name + "!", "Next year you'll be", age + 1)
#@@stdin
Ada
36
#@@ input_sum_numbers
n = int(input())
nums = list(map(int, input().split()))
print(sum(nums), max(nums), min(nums), sum(nums) / n)
#@@stdin
5
3 9 -2 7 11
#@@ input_two_ints
a, b = map(int, input().split())
print(a + b, a * b, a // b, a % b)
x, y = input().split()
print(x + y, float(x) * 2)
#@@stdin
17 5
3 4
#@@ input_test_cases
t = int(input())
for case in range(1, t + 1):
    n = int(input())
    arr = [int(x) for x in input().split()]
    print(f"Case #{case}: {sum(arr)} {sorted(arr)}")
#@@stdin
3
3
5 1 4
2
10 -10
1
7
#@@ input_loop_until_blank
total = 0
while True:
    line = input("number> ")
    if line == "":
        break
    try:
        total += float(line)
    except ValueError:
        print("skip", line)
print("total:", total)
#@@stdin
3.5
abc
4

ignored
#@@ input_menu_calculator
while True:
    cmd = input("calc> ").split()
    if not cmd:
        continue
    if cmd[0] == "quit":
        break
    a, op, b = float(cmd[0]), cmd[1], float(cmd[2])
    if op == "+":
        print(a + b)
    elif op == "/":
        print(a / b if b else "div by zero")
    else:
        print("unknown", op)
#@@stdin
1 + 2
5 / 0
2 ^ 3
10 / 4
quit
#@@ sys_stdin_readline
import sys
n = int(sys.stdin.readline())
rows = [sys.stdin.readline().split() for _ in range(n)]
print(n, rows, sum(len(r) for r in rows))
#@@stdin
2
a b c
d e
#@@ print_star_unpack_sep
arr = [3, 1, 2]
print(*arr)
print(*arr, sep=", ")
print("a", "b", sep="")
print("x", end="")
print("y", 1.5, True, None, [1, "a"], (1, 2), {"k": 1})
#@@ student_grade_manager
students = []
while True:
    cmd = input("1.add 2.list 3.avg 4.quit: ")
    if cmd == "1":
        name = input("name: ")
        try:
            marks = float(input("marks: "))
        except ValueError:
            print("bad marks")
            continue
        students.append({"name": name, "marks": marks})
    elif cmd == "2":
        for i, s in enumerate(students, 1):
            print(f"{i}. {s['name']} - {s['marks']}")
    elif cmd == "3":
        print(f"avg {sum(s['marks'] for s in students) / len(students):.2f}" if students else "none")
    elif cmd == "4":
        break
#@@stdin
1
Ada
91.5
1
Bob
x
1
Bob
70
2
3
4
