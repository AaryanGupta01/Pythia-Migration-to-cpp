"""BPE vocabulary trainer. Hot, but a class: its methods are not eligible."""
from .bpe import count_pairs

CAP = 1024


class Vocab:
    def __init__(self, base: int):
        self.size = base
        self.merges = []

    def merge(self, ids, left, right, new_id):
        out = []
        i = 0
        n = len(ids)
        while i < n:
            if i < n - 1 and ids[i] == left and ids[i + 1] == right:
                out.append(new_id)
                i += 2
            else:
                out.append(ids[i])
                i += 1
        return out

    def train(self, ids, n_merges):
        for _ in range(n_merges):
            counts = count_pairs(ids, CAP)
            if not counts:
                break
            best = max(counts, key=counts.get)
            ids = self.merge(ids, best // CAP, best % CAP, self.size)
            self.merges.append((best // CAP, best % CAP))
            self.size += 1
        return ids
