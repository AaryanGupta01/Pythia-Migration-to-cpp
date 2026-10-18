# PySub 1.3: Optional / None -- linked lists and binary search trees
from typing import Optional


class Node:
    val: int
    next: Optional["Node"]

    def __init__(self, val: int, next: Optional["Node"] = None) -> None:
        self.val = val
        self.next = next


class LinkedList:
    head: Optional[Node]
    size: int

    def __init__(self) -> None:
        self.head = None
        self.size = 0

    def push(self, v: int) -> None:
        self.head = Node(v, self.head)
        self.size += 1

    def append(self, v: int) -> None:
        if self.head is None:
            self.head = Node(v)
        else:
            cur = self.head
            while cur.next is not None:
                cur = cur.next
            cur.next = Node(v)
        self.size += 1

    def to_list(self) -> list[int]:
        out: list[int] = []
        node = self.head
        while node is not None:
            out.append(node.val)
            node = node.next
        return out

    def find(self, v: int) -> Optional[Node]:
        node = self.head
        while node:
            if node.val == v:
                return node
            node = node.next
        return None

    def reverse(self) -> None:
        prev: Optional[Node] = None
        cur = self.head
        while cur is not None:
            nxt = cur.next
            cur.next = prev
            prev = cur
            cur = nxt
        self.head = prev


class TreeNode:
    key: int
    left: "TreeNode | None"
    right: "TreeNode | None"

    def __init__(self, key: int) -> None:
        self.key = key
        self.left = None
        self.right = None


def insert(root: Optional[TreeNode], key: int) -> TreeNode:
    if root is None:
        return TreeNode(key)
    if key < root.key:
        root.left = insert(root.left, key)
    else:
        root.right = insert(root.right, key)
    return root


def inorder(root: TreeNode | None, out: list[int]) -> None:
    if root is None:
        return
    inorder(root.left, out)
    out.append(root.key)
    inorder(root.right, out)


def height(root: Optional[TreeNode]) -> int:
    if not root:
        return 0
    return 1 + max(height(root.left), height(root.right))


def min_key(root: Optional[TreeNode]) -> Optional[int]:
    if root is None:
        return None
    while root.left is not None:
        root = root.left
    return root.key


def first_even(xs: list[int]) -> int | None:
    for x in xs:
        if x % 2 == 0:
            return x
    return None


def describe(x: Optional[int]) -> str:
    if x is None:
        return "nothing"
    return "got " + str(x * 2)


ll = LinkedList()
for v in [3, 1, 4]:
    ll.append(v)
ll.push(9)
print(ll.to_list(), ll.size)
ll.reverse()
print(ll.to_list())
n = ll.find(4)
print(n is None, n is not None, ll.find(42) is None)
if n is not None:
    print("found", n.val)
root: Optional[TreeNode] = None
for k in [50, 30, 70, 20, 40, 60, 80, 35]:
    root = insert(root, k)
keys: list[int] = []
inorder(root, keys)
print(keys, height(root), min_key(root), min_key(None))
e = first_even([1, 3, 6, 8])
f = first_even([1, 3])
print(e, f, e == 6, f == None, f != None, describe(e), describe(f))
best: Optional[int] = None
for x in [7, 2, 9, 4]:
    if best is None or x < best:
        best = x
print("best", best)
g = e if e is not None else -1
h = f if f is not None else -1
print(g + h, str(e) + "/" + str(f), f"{f} and {e}")
t: Optional[str] = None
print(t)
t = "set"
print(t, len(t) if t is not None else 0)
empty = LinkedList()
print(empty.head is None, empty.to_list())
print(empty.head.val)
