"""k-nearest-neighbour vote. Fixable: comprehension, zip, lambda, sorted, dict.get(max)."""


def knn_vote(train: list[list[float]], labels: list[int], query: list[float], k: int) -> int:
    dists = [sum((a - b) * (a - b) for a, b in zip(row, query)) for row in train]
    order = sorted(range(len(dists)), key=lambda i: dists[i])[:k]
    votes = {}
    for i in order:
        votes[labels[i]] = votes.get(labels[i], 0) + 1
    return max(votes, key=votes.get)
