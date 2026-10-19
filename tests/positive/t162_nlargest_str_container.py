import heapq
xs = [5, 1, 8, 3, 2, 9]
print(heapq.nlargest(2, xs), heapq.nsmallest(3, xs))
ws = ["pear", "fig", "banana"]
print(heapq.nlargest(2, ws, key=len), heapq.nsmallest(1, ws, key=len))
print(str(xs), "list: " + str([1.5, 2.0]), f"{xs} and {ws}", str({"a": 1}), f"{ {1: 2.5} }")
print(len(str(xs)), [str(x) for x in [[1], [2, 3]]])
