#@@ list_basics
nums = [5, 3, 8, 1, 9, 2]
nums.append(7)
nums.insert(0, 4)
nums.remove(8)
print(nums, len(nums), nums.index(9), nums.count(3), 9 in nums, 100 in nums)
print(nums.pop(), nums.pop(0), nums)
nums.sort()
print(nums, max(nums), min(nums), sum(nums))
nums.reverse()
print(nums)
#@@ list_slicing
a = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
print(a[2:5], a[:3], a[7:], a[-3:], a[::2], a[::-1], a[1:8:3], a[-1:-5:-1], a[5:2])
b = a[:]
b[0] = 99
print(a[0], b[0])
a[2:4] = [20, 30, 40]
print(a)
#@@ list_2d_matrix
n = 3
grid = [[0] * n for _ in range(n)]
for i in range(n):
    for j in range(n):
        grid[i][j] = i * n + j
print(grid)
t = [[grid[j][i] for j in range(n)] for i in range(n)]
print(t)
print(sum(sum(row) for row in grid), [row[1] for row in grid])
#@@ list_comprehensions
sq = [x * x for x in range(10)]
ev = [x for x in sq if x % 2 == 0]
pairs = [(i, j) for i in range(3) for j in range(3) if i != j]
print(sq, ev, pairs)
print([c.upper() for c in "hello"], [len(w) for w in ["a", "bb", "ccc"]])
#@@ sorted_key_reverse
words = ["banana", "kiwi", "apple", "fig", "cherry"]
print(sorted(words), sorted(words, key=len), sorted(words, key=lambda w: (len(w), w), reverse=True))
print(sorted([3, 1, 2], reverse=True), sorted("hello"), max(words, key=len), min(words))
#@@ enumerate_zip_map
names = ["ann", "bob", "cy"]
ages = [30, 25, 41]
for i, n in enumerate(names, 1):
    print(i, n)
for n, a in zip(names, ages):
    print(n, a)
print(list(map(lambda x: x * 2, ages)), list(filter(lambda x: x > 28, ages)))
print(list(map(str, ages)), any(a > 40 for a in ages), all(a > 20 for a in ages))
#@@ string_basics
s = "Hello, World"
print(len(s), s[0], s[-1], s[1:5], s[::-1], s.upper(), s.lower(), s.swapcase())
print(s.find("World"), s.find("xyz"), s.replace("l", "L"), s.count("l"), s.startswith("Hell"), s.endswith("d"))
print("a,b,c".split(","), " x y  z ".split(), "-".join(["1", "2", "3"]), "  pad ".strip(), "abc".center(9, "*"))
#@@ string_checks
for t in ["abc", "123", "a1b2", "ABC", "", "hello world"]:
    print(repr(t), t.isalpha(), t.isdigit(), t.isalnum(), t.isupper(), t.islower(), t.isspace())
#@@ palindrome_check
def is_pal(s):
    s = "".join(ch.lower() for ch in s if ch.isalnum())
    return s == s[::-1]

for t in ["A man, a plan, a canal: Panama", "hello", "Was it a car or a cat I saw?"]:
    print(is_pal(t))
#@@ vowel_count
text = "The quick brown fox jumps over the lazy dog"
vowels = 0
for ch in text.lower():
    if ch in "aeiou":
        vowels += 1
print(vowels, len(text.split()), text.title())
#@@ char_frequency
s = "mississippi"
freq = {}
for ch in s:
    freq[ch] = freq.get(ch, 0) + 1
print(freq)
for k in sorted(freq):
    print(k, freq[k])
print(max(freq, key=freq.get))
#@@ caesar_cipher
def shift(s, k):
    out = ""
    for ch in s:
        if ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out += chr((ord(ch) - base + k) % 26 + base)
        else:
            out += ch
    return out

e = shift("Hello, World!", 3)
print(e, shift(e, -3))
#@@ anagram_check
def anagrams(a, b):
    return sorted(a.replace(" ", "").lower()) == sorted(b.replace(" ", "").lower())

print(anagrams("Listen", "Silent"), anagrams("abc", "abd"))
#@@ reverse_words
sentence = "the sky is blue"
print(" ".join(sentence.split()[::-1]), " ".join(w[::-1] for w in sentence.split()))
#@@ int_string_conversion
print(int("42") + 1, int("-17"), float("3.5") * 2, str(99) + "!", int("1010", 2), int("ff", 16), str(3.0), str(True))
print(ord("a"), chr(100), bin(10)[2:], format(10, "b"), "5".zfill(3), str(12).rjust(5, "0"))
#@@ binary_search_function
def bsearch(a, target):
    lo, hi = 0, len(a) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if a[mid] == target:
            return mid
        if a[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1

data = [1, 3, 5, 7, 9, 11, 13]
print(bsearch(data, 7), bsearch(data, 4), bsearch(data, 1), bsearch(data, 13))
#@@ bubble_sort_swap
def bubble(a):
    n = len(a)
    for i in range(n):
        swapped = False
        for j in range(n - 1 - i):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
        if not swapped:
            break
    return a

print(bubble([5, 2, 9, 1, 5, 6]), bubble([]), bubble([1]))
#@@ insertion_selection_sort
def insertion(a):
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    return a

def selection(a):
    for i in range(len(a)):
        m = i
        for j in range(i + 1, len(a)):
            if a[j] < a[m]:
                m = j
        a[i], a[m] = a[m], a[i]
    return a

print(insertion([4, 3, 2, 10, 12, 1, 5, 6]), selection([64, 25, 12, 22, 11]))
#@@ merge_sort_recursive
def merge_sort(a):
    if len(a) <= 1:
        return a
    mid = len(a) // 2
    left, right = merge_sort(a[:mid]), merge_sort(a[mid:])
    out = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            out.append(left[i])
            i += 1
        else:
            out.append(right[j])
            j += 1
    out.extend(left[i:])
    out.extend(right[j:])
    return out

print(merge_sort([38, 27, 43, 3, 9, 82, 10]))
#@@ max_subarray_kadane
def max_subarray(nums):
    best = cur = nums[0]
    for x in nums[1:]:
        cur = max(x, cur + x)
        best = max(best, cur)
    return best

print(max_subarray([-2, 1, -3, 4, -1, 2, 1, -5, 4]), max_subarray([-3, -1, -2]))
#@@ matrix_multiply
def matmul(a, b):
    n, m, p = len(a), len(b), len(b[0])
    c = [[0] * p for _ in range(n)]
    for i in range(n):
        for j in range(p):
            for k in range(m):
                c[i][j] += a[i][k] * b[k][j]
    return c

print(matmul([[1, 2], [3, 4]], [[5, 6], [7, 8]]))
#@@ list_remove_duplicates
a = [3, 1, 3, 2, 1, 5, 2]
seen = []
for x in a:
    if x not in seen:
        seen.append(x)
print(seen, sorted(set(a)), len(set(a)))
#@@ two_sum_dict
def two_sum(nums, target):
    seen = {}
    for i, x in enumerate(nums):
        if target - x in seen:
            return [seen[target - x], i]
        seen[x] = i
    return []

print(two_sum([2, 7, 11, 15], 9), two_sum([3, 2, 4], 6), two_sum([1, 2], 9))
