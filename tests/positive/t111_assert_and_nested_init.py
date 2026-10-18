# t111: assert statement, AssertionError catching, and nested empty container inference

# 1. Assertions that pass
assert 1 < 2
assert 1 + 1 == 2, "math works"
assert 10 != 5, 42

print("asserts passed")

# 2. Assertions caught via try-except
try:
    assert 2 < 1, "custom fail message"
except AssertionError as e:
    print("caught with msg:", str(e))

try:
    assert False
except AssertionError as e:
    print("caught without msg:", repr(str(e)))

# 3. Nested empty container inference
empty_nested: list[list[int]] = [[]]
print("empty_nested:", empty_nested)

nested_mix: list[list[int]] = [[1, 2], [], [3]]
print("nested_mix:", nested_mix)

dict_empty_list: dict[str, list[int]] = {"first": [], "second": [10, 20]}
print("dict_empty_list len:", len(dict_empty_list), len(dict_empty_list["first"]))

