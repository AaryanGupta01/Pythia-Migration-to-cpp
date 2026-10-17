"""Synthetic corpus: noisy copies of a small set of base words, stored in a text file."""
import os
import tempfile

LETTERS = "abcdefghijklmnopqrstuvwxyz"


def make_words(rng, n_base, n_variants):
    base = []
    for _ in range(n_base):
        base.append("".join(LETTERS[rng.next_int(26)] for _ in range(12 + rng.next_int(9))))
    words = []
    for _ in range(n_variants):
        w = base[rng.next_int(n_base)]
        for _ in range(rng.next_int(3)):
            pos = rng.next_int(len(w))
            w = w[:pos] + LETTERS[rng.next_int(26)] + w[pos + 1:]
        words.append(w)
    return words


def write_corpus(words, per_line=8):
    path = os.path.join(tempfile.gettempdir(), "textlab_corpus_%d.txt" % os.getpid())
    with open(path, "w") as fh:
        for i in range(0, len(words), per_line):
            fh.write(" ".join(words[i:i + per_line]) + "\n")
    return path


def load_corpus(path):
    # Not eligible: file I/O.
    words = []
    with open(path) as fh:
        for line in fh:
            words.extend(line.split())
    os.remove(path)
    return words
