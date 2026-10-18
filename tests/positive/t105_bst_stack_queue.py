# BST insert / search / inorder / delete as methods with recursion through self; Stack and Queue classes over
# lists (field type inferred from .append evidence); a custom exception path; generic-looking containers


class BSTNode:
    def __init__(self, key: int) -> None:
        self.key = key
        self.left: "BSTNode | None" = None
        self.right: "BSTNode | None" = None


class BST:
    def __init__(self) -> None:
        self.root = None
        self.count = 0

    def insert(self, key: int) -> bool:
        if self.root is None:
            self.root = BSTNode(key)
            self.count += 1
            return True
        return self._insert(self.root, key)

    def _insert(self, node: BSTNode, key: int) -> bool:
        if key == node.key:
            return False
        if key < node.key:
            if node.left is None:
                node.left = BSTNode(key)
                self.count += 1
                return True
            return self._insert(node.left, key)
        if node.right is None:
            node.right = BSTNode(key)
            self.count += 1
            return True
        return self._insert(node.right, key)

    def contains(self, key: int) -> bool:
        node = self.root
        while node is not None:
            if key == node.key:
                return True
            node = node.left if key < node.key else node.right
        return False

    def inorder(self) -> list[int]:
        out: list[int] = []
        self._inorder(self.root, out)
        return out

    def _inorder(self, node: "BSTNode | None", out: list[int]) -> None:
        if node is None:
            return
        self._inorder(node.left, out)
        out.append(node.key)
        self._inorder(node.right, out)

    def min_key(self) -> int:
        if self.root is None:
            raise ValueError("empty tree")
        node = self.root
        while node.left is not None:
            node = node.left
        return node.key

    def delete(self, key: int) -> None:
        self.root = self._delete(self.root, key)

    def _delete(self, node: "BSTNode | None", key: int) -> "BSTNode | None":
        if node is None:
            return None
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            self.count -= 1
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            succ = node.right
            while succ.left is not None:
                succ = succ.left
            node.key = succ.key
            self.count += 1
            node.right = self._delete(node.right, succ.key)
        return node

    def height(self, node: "BSTNode | None" = None, top: bool = True) -> int:
        if top:
            node = self.root
        if node is None:
            return 0
        return 1 + max(self.height(node.left, False), self.height(node.right, False))


class Stack:
    def __init__(self) -> None:
        self.items = []

    def push(self, x: str) -> None:
        self.items.append(x)

    def pop(self) -> str:
        if self.is_empty():
            raise IndexError("pop from empty stack")
        return self.items.pop()

    def peek(self) -> str:
        return self.items[-1]

    def is_empty(self) -> bool:
        return len(self.items) == 0

    def __len__(self) -> int:
        return len(self.items)

    def __repr__(self) -> str:
        return f"Stack({self.items})"


class Queue:
    def __init__(self, capacity: int) -> None:
        self.data: list[int] = []
        self.capacity = capacity
        self.dropped = 0

    def enqueue(self, x: int) -> None:
        if len(self.data) >= self.capacity:
            self.data.pop(0)
            self.dropped += 1
        self.data.append(x)

    def dequeue(self) -> int:
        return self.data.pop(0)


def balanced(s: str) -> bool:
    st = Stack()
    pairs = {")": "(", "]": "[", "}": "{"}
    for ch in s:
        if ch in "([{":
            st.push(ch)
        elif ch in pairs:
            if st.is_empty() or st.pop() != pairs[ch]:
                return False
    return st.is_empty()


t = BST()
for k in [50, 30, 70, 20, 40, 60, 80, 30, 65]:
    t.insert(k)
print(t.inorder(), t.count, t.contains(65), t.contains(66), t.min_key(), t.height())
t.delete(50)
t.delete(20)
t.delete(999)
print(t.inorder(), t.count, t.root.key if t.root else -1, t.height())
st = Stack()
for w in "abc":
    st.push(w)
print(st, len(st), st.peek(), st.pop(), st)
print([balanced(x) for x in ["([]{})", "([)]", "((", ""]])
q = Queue(3)
for i in range(5):
    q.enqueue(i * i)
print(q.data, q.dropped, q.dequeue(), q.data)
e = BST()
try:
    e.min_key()
except ValueError as err:
    print("ValueError:", err)
while not st.is_empty():
    print(st.pop(), end=" ")
print()
st.pop()
