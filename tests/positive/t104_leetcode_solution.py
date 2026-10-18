# LeetCode style: `class Solution` with no __init__ and no fields, methods calling helpers through self,
# recursion through self, TreeNode / ListNode definitions with Optional children and default arguments
from typing import List, Optional


class TreeNode:
    def __init__(self, val: int = 0, left: Optional["TreeNode"] = None, right: Optional["TreeNode"] = None):
        self.val = val
        self.left = left
        self.right = right


class ListNode:
    def __init__(self, val: int = 0, next: Optional["ListNode"] = None):
        self.val = val
        self.next = next


class Solution:
    def maxDepth(self, root: Optional[TreeNode]) -> int:
        if root is None:
            return 0
        return 1 + max(self.maxDepth(root.left), self.maxDepth(root.right))

    def inorder(self, root: Optional[TreeNode]) -> List[int]:
        out: List[int] = []
        self._walk(root, out)
        return out

    def _walk(self, node: Optional[TreeNode], out: List[int]) -> None:
        if node:
            self._walk(node.left, out)
            out.append(node.val)
            self._walk(node.right, out)

    def isValidBST(self, root: Optional[TreeNode]) -> bool:
        return self._valid(root, None, None)

    def _valid(self, node: Optional[TreeNode], lo: Optional[int], hi: Optional[int]) -> bool:
        if node is None:
            return True
        if lo is not None and node.val <= lo:
            return False
        if hi is not None and node.val >= hi:
            return False
        return self._valid(node.left, lo, node.val) and self._valid(node.right, node.val, hi)

    def reverseList(self, head: Optional[ListNode]) -> Optional[ListNode]:
        prev = None
        while head:
            nxt = head.next
            head.next = prev
            prev = head
            head = nxt
        return prev

    def mergeTwoLists(self, a: Optional[ListNode], b: Optional[ListNode]) -> Optional[ListNode]:
        dummy = ListNode()
        tail = dummy
        while a and b:
            if a.val <= b.val:
                tail.next, a = a, a.next
            else:
                tail.next, b = b, b.next
            tail = tail.next
        tail.next = a if a else b
        return dummy.next

    def twoSum(self, nums: List[int], target: int) -> List[int]:
        seen: dict[int, int] = {}
        for i, n in enumerate(nums):
            if target - n in seen:
                return [seen[target - n], i]
            seen[n] = i
        return []


def build(vals: List[int]) -> Optional[ListNode]:
    head: Optional[ListNode] = None
    for v in reversed(vals):
        head = ListNode(v, head)
    return head


def to_list(node: Optional[ListNode]) -> List[int]:
    out: List[int] = []
    while node is not None:
        out.append(node.val)
        node = node.next
    return out


root = TreeNode(5, TreeNode(3, TreeNode(2), TreeNode(4)), TreeNode(8, None, TreeNode(9)))
s = Solution()
print(s.maxDepth(root), s.inorder(root), s.isValidBST(root))
root.left.right.val = 7
print(s.isValidBST(root), s.inorder(root), s.maxDepth(None))
print(to_list(s.reverseList(build([1, 2, 3, 4]))), to_list(s.reverseList(None)))
print(to_list(s.mergeTwoLists(build([1, 3, 5]), build([2, 3, 6, 7]))))
print(s.twoSum([2, 7, 11, 15], 9), Solution().twoSum([3, 3], 6), s.twoSum([1], 5))
print(root.right.left.val)
