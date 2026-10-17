"""Nearest-word spelling suggestions built on the edit-distance kernel."""
from __future__ import annotations

from typing import List

from quanta.text.distance import levenshtein


class SpellChecker:
    """Suggest dictionary words for a possibly misspelled query."""

    def __init__(self, dictionary: List[str], max_distance: int = 3) -> None:
        self.dictionary = dictionary
        self.codes = [[ord(c) for c in word] for word in dictionary]
        self.max_distance = max_distance

    def suggest(self, word: str) -> str:
        """Closest dictionary word by Levenshtein distance; the first in dictionary order wins ties."""
        query = [ord(c) for c in word]
        best, best_d = word, self.max_distance + 1
        for candidate, codes in zip(self.dictionary, self.codes):
            if abs(len(codes) - len(query)) >= best_d:
                continue
            d = levenshtein(query, codes)
            if d < best_d:
                best, best_d = candidate, d
        return best

    def correct_all(self, words: List[str]) -> int:
        """Number of words whose suggestion differs from the input."""
        return sum(1 for w in words if self.suggest(w) != w)
