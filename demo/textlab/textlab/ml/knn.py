"""k-nearest-neighbour vote. Fixable: comprehension, generator, zip, sorted, tuple unpacking."""


def knn_vote(train: list[list[float]], labels: list[int], query: list[float], k: int) -> int:
    dists = [sum((a - b) * (a - b) for a, b in zip(row, query)) for row in train]
    ranked = sorted(zip(dists, range(len(dists))))[:k]
    votes = {}
    for _, i in ranked:
        votes[labels[i]] = votes.get(labels[i], 0) + 1
    top = max(votes.values())
    for _, i in ranked:
        if votes[labels[i]] == top:
            return labels[i]
