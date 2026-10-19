# PySub 1.4: deep recursion parity, sys.setrecursionlimit, sys.stdin, sys.exit
import sys
depth: int = 0
def f(n: int) -> int:
    global depth
    depth = n
    return f(n + 1)
try:
    f(0)
except RecursionError as e:
    print("limit", sys.getrecursionlimit(), "reached", depth, e)
sys.setrecursionlimit(5000)
try:
    f(0)
except RecursionError as e:
    print("limit", sys.getrecursionlimit(), "reached", depth)
def g(n: int) -> int:
    return 0 if n == 0 else 1 + g(n - 1)
print(g(4000))
sys.setrecursionlimit(200000)
print(g(100000))
line = sys.stdin.readline()
print(repr(line), repr(sys.stdin.readline().strip()))
rest = sys.stdin.readlines()
print(rest, len(rest))
print(repr(sys.stdin.readline()))
sys.exit(0)
print("not reached")
