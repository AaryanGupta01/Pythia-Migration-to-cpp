class Student:
    def __init__(self, name, marks):
        self.name = name
        self.marks = marks

    def average(self):
        if not self.marks:
            return 0
        return sum(self.marks) / len(self.marks)

    def grade(self):
        avg = self.average()
        if avg >= 90:
            return "A"
        elif avg >= 75:
            return "B"
        elif avg >= 50:
            return "C"
        return "F"

    def display(self):
        print(f"{self.name}: {self.average():.2f} ({self.grade()})")


def find_student(students, name):
    for student in students:
        if student.name.lower() == name.lower():
            return student
    return None


def main():
    students = [
        Student("Arun", [90, 85, 92]),
        Student("Meera", [78, 88, 80]),
        Student("John", [45, 50, 40]),
        Student("Priya", [95, 98, 96]),
        Student("Sam", [])
    ]

    for student in students:
        student.display()

    print("\nTop students:")
    ranked = sorted(students, key=lambda s: s.average(), reverse=True)

    for student in ranked[:3]:
        print(student.name, student.average())

    passed = [s.name for s in students if s.average() >= 50]
    print("\nPassed:", passed)

    all_marks = [mark for s in students for mark in s.marks]
    print("Total marks:", sum(all_marks))
    print("Highest mark:", max(all_marks))
    print("Unique marks:", sorted(set(all_marks)))

    lookup = {s.name: s.average() for s in students}
    print("Arun's average:", lookup.get("Arun", 0))
    print("Missing student:", lookup.get("Unknown", "Not found"))

    result = find_student(students, "meera")
    if result is not None:
        print("Found:", result.name)

    try:
        print(10 / 0)
    except ZeroDivisionError:
        print("Division error handled")
    finally:
        print("Program finished")


main()

