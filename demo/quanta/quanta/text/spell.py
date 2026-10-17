"""Nearest-word spelling suggestions built on the edit-distance kernels."""
from __future__ import annotations

from typing import List

from quanta.text.distance import levenshtein


class SpellChecker:
    """Suggest dictionary words for a possibly misspelled query."""

    def __init__(self, dictionary: List[str], max_distance: int = 3) -> None:
        self.dictionary = dictionary
        self.max_distance = max_distance

    def suggest(self, word: str) -> str:
        """Closest dictionary word by Levenshtein distance; the first in dictionary order wins ties."""
        best, best_d = word, self.max_distance + 1
        for candidate in self.dictionary:
            if abs(len(candidate) - len(word)) >= best_d:
                continue
            d = levenshtein(word, candidate)
            if d < best_d:
                best, best_d = candidate, d
        return best

    def correct_all(self, words: List[str]) -> int:
        """Number of words whose suggestion differs from the input."""
        return sum(1 for w in words if self.suggest(w) != w)
