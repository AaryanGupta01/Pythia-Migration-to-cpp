tasks = []


def add(title, priority):
    tasks.append({"title": title, "priority": priority, "done": False})


def complete(index):
    if 0 <= index < len(tasks):
        tasks[index]["done"] = True
    else:
        print("no such task")


def show():
    for i, t in enumerate(sorted(tasks, key=lambda t: t["priority"])):
        mark = "x" if t["done"] else " "
        print(f"[{mark}] {t['title']} (p{t['priority']})")


add("write report", 2)
add("email Bob", 1)
add("fix bug #42", 1)
add("plan sprint", 3)
complete(2)
complete(9)
show()
left = len([t for t in tasks if not t["done"]])
print(f"{left} tasks left")
