students = []


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

    print("\n--- Student Records ---")

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

    print("\n--- Topper ---")
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
        print("\n===== Student Grade Manager =====")
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
