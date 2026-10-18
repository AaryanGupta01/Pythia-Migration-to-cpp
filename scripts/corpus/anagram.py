from collections import defaultdict

words = ["listen", "silent", "enlist", "google", "gooegl", "cat", "act", "tac", "dog"]
groups = defaultdict(list)
for w in words:
    groups["".join(sorted(w))].append(w)

for key, group in groups.items():
    if len(group) > 1:
        print(key, "->", group)
print(len(groups), "groups")
