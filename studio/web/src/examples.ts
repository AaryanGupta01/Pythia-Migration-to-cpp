// Playground examples: two are already PySub (compile at once), two are ordinary Python that the
// AI converter turns into PySub (the type checker then proves every answer, and Run compares the
// original program under CPython with the compiled conversion on the same input).

export interface Example {
  id: string
  title: string
  note: string
  code: string
  stdin?: string
}

const STUDENTS = `students = []


def add_student():
    name = input("Enter student name: ")

    try:
        marks = float(input("Enter marks out of 100: "))

        if marks < 0 or marks > 100:
            print("Invalid marks!")
            return

        student = {
            "name": name,
            "marks": marks
        }

        students.append(student)
        print(f"{name} added successfully!")

    except ValueError:
        print("Please enter a valid number.")


def display_students():
    if not students:
        print("No students found.")
        return

    print("\\n--- Student Records ---")

    for index, student in enumerate(students, start=1):
        print(
            f"{index}. {student['name']} - "
            f"{student['marks']} marks"
        )


def calculate_average():
    if len(students) == 0:
        print("No records available.")
        return

    total = 0

    for student in students:
        total += student["marks"]

    average = total / len(students)
    print(f"Class average: {average:.2f}")


def search_student():
    name = input("Enter name to search: ").strip().lower()

    for student in students:
        if student["name"].lower() == name:
            print(f"Name: {student['name']}")
            print(f"Marks: {student['marks']}")

            if student["marks"] >= 50:
                print("Result: Pass")
            else:
                print("Result: Fail")

            return

    print("Student not found.")


def display_topper():
    if not students:
        print("No records available.")
        return

    topper = max(students, key=lambda student: student["marks"])

    print("\\n--- Topper ---")
    print(f"Name: {topper['name']}")
    print(f"Marks: {topper['marks']}")


def sort_students():
    if not students:
        print("No records available.")
        return

    students.sort(
        key=lambda student: student["marks"],
        reverse=True
    )

    print("Students sorted by marks in descending order.")
    display_students()


def main():
    while True:
        print("\\n===== Student Grade Manager =====")
        print("1. Add Student")
        print("2. Display Students")
        print("3. Calculate Average")
        print("4. Search Student")
        print("5. Display Topper")
        print("6. Sort Students")
        print("7. Exit")

        choice = input("Enter your choice: ")

        if choice == "1":
            add_student()
        elif choice == "2":
            display_students()
        elif choice == "3":
            calculate_average()
        elif choice == "4":
            search_student()
        elif choice == "5":
            display_topper()
        elif choice == "6":
            sort_students()
        elif choice == "7":
            print("Exiting program...")
            break
        else:
            print("Invalid choice. Try again.")


if __name__ == "__main__":
    main()
`

const STUDENTS_STDIN = `1
Ada Lovelace
91.5
1
Linus
48
1
Grace
not-a-number
1
Grace
77.25
2
3
4
grace
5
6
7
`

const EDIT = `def edit_distance(a: str, b: str) -> int:
    """Levenshtein distance with a rolling row."""
    m: int = len(b)
    prev: list[int] = []
    for j in range(m + 1):
        prev.append(j)
    for i in range(1, len(a) + 1):
        cur: list[int] = [i]
        for j in range(1, m + 1):
            cost: int = 1
            if a[i - 1] == b[j - 1]:
                cost = 0
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[m]


pairs: list[str] = ["kitten:sitting", "intention:execution", "flaw:lawn"]
for p in pairs:
    words: list[str] = p.split(":")
    print(f"{words[0]:>10} -> {words[1]:<10} {edit_distance(words[0], words[1])}")
`

const PRIMES = `def sieve(n: int) -> list[int]:
    flags: list[bool] = []
    for i in range(n + 1):
        flags.append(i >= 2)
    p: int = 2
    while p * p <= n:
        if flags[p]:
            for m in range(p * p, n + 1, p):
                flags[m] = False
        p += 1
    out: list[int] = []
    for i in range(n + 1):
        if flags[i]:
            out.append(i)
    return out


primes: list[int] = sieve(200000)
gaps: list[int] = []
for i in range(1, len(primes)):
    gaps.append(primes[i] - primes[i - 1])
print(f"{len(primes):,} primes below 200,000; largest {primes[-1]}")
print(f"sum = {sum(primes):,}   mean gap = {sum(gaps) / len(gaps):.3f}   widest gap = {max(gaps)}")
`

const TEMPS = `def to_celsius(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


readings: list[float] = []
while True:
    line: str = input("Fahrenheit (blank to stop): ").strip()
    if line == "":
        break
    try:
        readings.append(float(line))
    except ValueError:
        print(f"  '{line}' is not a number, skipped")

if len(readings) > 0:
    for f in readings:
        print(f"{f:8.1f} F = {to_celsius(f):7.2f} C")
    print(f"average {to_celsius(sum(readings) / len(readings)):.2f} C, max {to_celsius(max(readings)):.2f} C")
`

export const EXAMPLES: Example[] = [
  { id: 'edit', title: 'Edit distance', note: 'PySub: compiles as written', code: EDIT },
  { id: 'primes', title: 'Prime sieve and stats', note: 'PySub: sum, max, f-string formatting', code: PRIMES },
  { id: 'temps', title: 'Temperature converter (interactive)', note: 'PySub with input(): type the input below', code: TEMPS, stdin: '98.6\n212\nabc\n-40\n\n' },
  { id: 'students', title: 'Student grade manager', note: 'Plain Python: convert it with AI first', code: STUDENTS, stdin: STUDENTS_STDIN },
]
