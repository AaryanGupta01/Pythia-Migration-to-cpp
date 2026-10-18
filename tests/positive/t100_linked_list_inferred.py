# User classes: fields inferred from `self.x = ...` (no class-level declarations), Optional links, __str__/__len__
from typing import Optional


class Node:
    def __init__(self, data: int, next_node: Optional["Node"] = None) -> None:
        self.data = data
        self.next = next_node


class LinkedList:
    def __init__(self) -> None:
        self.head: Optional[Node] = None
        self.size = 0

    def push_front(self, data: int) -> None:
        self.head = Node(data, self.head)
        self.size += 1

    def append(self, data: int) -> "LinkedList":
        node = Node(data)
        if self.head is None:
            self.head = node
        else:
            cur = self.head
            while cur.next is not None:
                cur = cur.next
            cur.next = node
        self.size += 1
        return self

    def __len__(self) -> int:
        return self.size

    def __str__(self) -> str:
        parts: list[str] = []
        cur = self.head
        while cur is not None:
            parts.append(str(cur.data))
            cur = cur.next
        return " -> ".join(parts) if parts else "<empty>"

    def __contains__(self, item: int) -> bool:
        cur = self.head
        while cur:
            if cur.data == item:
                return True
            cur = cur.next
        return False

    def reverse(self) -> None:
        prev: Optional[Node] = None
        cur = self.head
        while cur is not None:
            nxt = cur.next
            cur.next = prev
            prev = cur
            cur = nxt
        self.head = prev

    def pop_front(self) -> int:
        if self.head is None:
            raise IndexError("pop from empty list")
        node = self.head
        self.head = node.next
        self.size -= 1
        return node.data


ll = LinkedList()
print(ll, len(ll), bool(ll))
ll.append(1).append(2).append(3)
ll.push_front(0)
print(ll, len(ll), 2 in ll, 9 in ll, 9 not in ll)
ll.reverse()
print(f"reversed: {ll} (size {len(ll)})")
if ll:
    print("non-empty")
total = 0
while len(ll) > 0:
    total += ll.pop_front()
print("total", total, str(ll))
ll.pop_front()
