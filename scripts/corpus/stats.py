scores = [88, 92, 79, 65, 95, 70, 84, 91, 58, 77, 83, 99, 62]

mean = sum(scores) / len(scores)
ordered = sorted(scores)
mid = len(ordered) // 2
median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
variance = sum((s - mean) ** 2 for s in scores) / (len(scores) - 1)
stdev = variance ** 0.5

print(f"mean={mean:.2f} median={median} stdev={stdev:.3f}")
print("max:", max(scores), "min:", min(scores))
grades = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
for s in scores:
    if s >= 90:
        grades["A"] += 1
    elif s >= 80:
        grades["B"] += 1
    elif s >= 70:
        grades["C"] += 1
    elif s >= 60:
        grades["D"] += 1
    else:
        grades["F"] += 1
for g, n in grades.items():
    print(g, "*" * n)
above = [s for s in scores if s > mean]
print("above mean:", above)
