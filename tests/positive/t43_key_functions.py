# key= lambdas and function references in sorted / min / max / list.sort; stability, ties, reverse
class Person:
    name: str
    age: int

    def __init__(self, name: str, age: int) -> None:
        self.name = name
        self.age = age


def score(w: str) -> int:
    return len(w) % 3


def grow(v: int, xs: list[int]) -> int:
    xs.append(v)
    return -v


def by_distance(xs: list[int], target: int) -> list[int]:
    return sorted(xs, key=lambda v: abs(v - target))     # the lambda reads the enclosing function's target


def oldest(people: list[Person]) -> str:
    return max(people, key=lambda p: p.age).name


def youngest_names(people: list[Person]) -> list[str]:
    people.sort(key=lambda p: p.age)
    return [p.name for p in people]


words: list[str] = ["pear", "Fig", "apple", "kiwi", "Banana", "date", "fig"]
print(sorted(words, key=len))
print(sorted(words, key=len, reverse=True))              # ties keep their original order under reverse too
print(sorted(words, key=str.lower), sorted(words, key=lambda w: w[-1]))
print(sorted(words, key=score), min(words, key=len), max(words, key=len), max(words, key=score))
print(min(words, key=lambda w: w.lower()), max(words, key=lambda w: (len(w) * 10) % 7))
print(by_distance([1, 9, 4, 6, 5, 3], 5))
nums: list[int] = [5, -3, 2, -5, 3, -2]
print(sorted(nums, key=abs), min(nums, key=abs), max(nums, key=abs), sorted(nums, key=lambda n: -n))
nums.sort(key=abs, reverse=True)
print(nums)
nums.sort(key=lambda n: n % 2 == 0)
print(nums)
grid: list[list[int]] = [[3, 1], [2], [9, 9, 9], [0, 0]]
print(sorted(grid, key=len), max(grid, key=sum), min(grid, key=lambda r: r[0]))
grid.sort(key=lambda r: r[-1])
print(grid)
ps: list[Person] = [Person("ann", 30), Person("bob", 25), Person("cy", 30), Person("di", 19)]
print(oldest(ps), youngest_names(ps), [p.name for p in sorted(ps, key=lambda p: p.age, reverse=True)])
print(sorted("hello", key=lambda c: -ord(c)), sorted({"b": 1, "a": 2}, key=lambda k: k))
print(max((w for w in words if "a" in w), key=len), sorted((n * n for n in range(-3, 3)), key=lambda n: -n))
print(min(range(10), key=lambda i: (i - 4) * (i - 4)), sorted([2.5, -1.0, 0.5], key=lambda f: f * f))
fs: list[float] = [1.0, 2.0]
print(sorted(fs, key=float), max(["a", "b"], key=str.upper))
try:
    print(min([w for w in words if len(w) > 9], key=len))
except ValueError as e:
    print("caught", e)
xs: list[int] = [3, 1, 2]
try:
    xs.sort(key=lambda v: 10 // (v - 1))
except ZeroDivisionError as e:
    print("caught", e, xs)                 # a failing key leaves the list as it was
xs.sort(key=lambda v: len(xs) * 100 - v)  # CPython hides the list while sorting: len(xs) is 0 inside the key
print(xs)
try:
    xs.sort(key=lambda v: grow(v, xs))
except ValueError as e:
    print("caught", e, xs)                 # the sorted items survive, the appends are dropped
