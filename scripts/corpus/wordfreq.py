text = """It was the best of times, it was the worst of times, it was the age of wisdom,
it was the age of foolishness, it was the epoch of belief, it was the epoch of incredulity"""

counts = {}
for word in text.lower().replace(",", "").split():
    counts[word] = counts.get(word, 0) + 1

top = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
for word, n in top:
    print(f"{word:>12} {'#' * n} {n}")
print("distinct words:", len(counts))
