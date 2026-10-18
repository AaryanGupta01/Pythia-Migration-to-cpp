"""PySub 1.1: f-strings, format specs, str methods, list methods, lists of objects, print(sep=, end=)."""


class Student:
    name: str
    marks: float

    def __init__(self, name: str, marks: float) -> None:
        self.name = name
        self.marks = marks


def grade(marks: float) -> str:
    if marks >= 50:
        return "Pass"
    return "Fail"


def topper(students: list[Student]) -> Student:
    best: Student = students[0]
    for s in students:
        if s.marks > best.marks:
            best = s
    return best


def sort_by_marks(students: list[Student]) -> None:
    for i in range(1, len(students)):
        cur: Student = students[i]
        j: int = i - 1
        while j >= 0 and students[j].marks < cur.marks:
            students[j + 1] = students[j]
            j -= 1
        students[j + 1] = cur


def average(students: list[Student]) -> float:
    total: float = 0.0
    for s in students:
        total += s.marks
    return total / len(students)


roster: list[Student] = []
for line in ["  ada , 91.5", "Linus,48", " grace ,77.25 ", "ken, 50"]:
    parts: list[str] = line.split(",")
    roster.append(Student(parts[0].strip().title(), float(parts[1])))

for i in range(len(roster)):
    s: Student = roster[i]
    print(f"{i + 1}. {s.name:<8}|{s.marks:>7.2f} {grade(s.marks)}")

print(f"Class average: {average(roster):.2f}")
t: Student = topper(roster)
print(f"Topper: {t.name} ({t.marks})")
sort_by_marks(roster)
names: list[str] = []
for s in roster:
    names.append(s.name)
print(", ".join(names))
print(len(roster), roster[0] in roster, Student("x", 1.0) in roster)

xs: list[int] = [5, 3, 9, 1, 3]
xs.sort()
print(xs, sorted([2.5, -1.0, 2.0], reverse=True), sum(xs), min(xs), max(xs), max(4, 11, 7))
xs.insert(0, 42)
xs.insert(-1, 7)
xs.remove(3)
print(xs, xs.index(9), xs.count(3), xs.pop(0), xs.pop(-1), xs)
ys: list[int] = xs.copy()
ys.extend([100, 200])
ys.reverse()
print(ys, xs, ys == xs)

w: str = "  Hello, World  "
print(w.strip(), w.lstrip(), w.rstrip() + "|", w.upper(), w.lower().strip())
print("x".join(["a", "b", "c"]), "a-b--c".split("-"), "  one two   three ".split())
print("banana".count("an"), "banana".find("na"), "banana".rfind("na"), "banana".replace("an", "AN"))
print("hello world's end".title(), "pYTHON".capitalize(), "Ab1".swapcase())
print("123".isdigit(), "12a".isdigit(), "abc".isalpha(), "abc1".isalnum(), " ".isspace(), "ABC".isupper())
print("data.csv".endswith(".csv"), "data.csv".startswith("dat"), "xyxzy".strip("xy"))
print(round(2.5), round(3.5), round(-2.5), round(2.675, 2), round(1234, -2), round(1250, -2))
print(format(1234567.891, ",.2f"), format(42, "08d"), format(-3.14159, "+.3f"), format(0.25, ".1%"))
print(format(7, "^9"), "|" + format("ab", ">5") + "|", format(12.0, "e"), format(True, ""), format(5, "x^7"))
print(f"{3 + 4} {'nested'} {{braces}} {12345678:,} {-0.0} {1e22} {1.5}")
print("a", "b", "c", sep="-", end="!\n")
print("no newline", end="")
print(" ... joined")
total_len: int = 0
for word in "the quick brown fox".split(" "):
    total_len += len(word)
print(f"total_len: {total_len}")
