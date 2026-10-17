"""A tiny inverted index with TF-IDF ranking."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List

WORD = re.compile(r"[a-z]+")
STOPWORDS = frozenset(["the", "a", "an", "of", "and", "to", "in"])


def tokenize(text: str) -> List[str]:
    """Lower-case word tokens without stop words."""
    return [w for w in WORD.findall(text.lower()) if w not in STOPWORDS]


def term_frequencies(tokens: List[str]) -> Dict[str, int]:
    """Occurrences of each token."""
    return dict(Counter(tokens))


class InvertedIndex:
    """Maps terms to the documents containing them and ranks documents for a query by TF-IDF."""

    def __init__(self) -> None:
        self.postings: Dict[str, Dict[int, int]] = defaultdict(dict)
        self.lengths: List[int] = []

    def add(self, text: str) -> int:
        """Index a document and return its id."""
        doc_id = len(self.lengths)
        tokens = tokenize(text)
        self.lengths.append(len(tokens))
        for term, count in term_frequencies(tokens).items():
            self.postings[term][doc_id] = count
        return doc_id

    def idf(self, term: str) -> float:
        docs = len(self.postings.get(term, ()))
        return 0.0 if docs == 0 else (len(self.lengths) / docs) ** 0.5

    def search(self, query: str, limit: int = 5) -> List[int]:
        """Ids of the best-matching documents, best first (ties broken by id)."""
        scores: Dict[int, float] = defaultdict(float)
        for term in set(tokenize(query)):
            weight = self.idf(term)
            for doc_id, count in self.postings.get(term, {}).items():
                scores[doc_id] += weight * count / (1 + self.lengths[doc_id]) ** 0.5
        ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        return [doc_id for doc_id, _ in ranked[:limit]]


def top_terms(index: InvertedIndex, limit: int) -> List[str]:
    """Terms appearing in the most documents (document frequency, then alphabetical)."""
    ranked = sorted(index.postings, key=lambda t: (-len(index.postings[t]), t))
    return ranked[:limit]
