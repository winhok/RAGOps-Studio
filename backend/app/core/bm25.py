from __future__ import annotations

import math
from collections import Counter

from .text import tokenize


class BM25Index:
    def __init__(self, documents: list[str], *, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs = [tokenize(doc) for doc in documents]
        self.doc_freq: Counter[str] = Counter()
        for tokens in self.docs:
            self.doc_freq.update(set(tokens))
        self.avgdl = sum(len(tokens) for tokens in self.docs) / max(len(self.docs), 1)

    def score(self, query: str, doc_idx: int) -> float:
        tokens = self.docs[doc_idx]
        if not tokens:
            return 0.0
        counts = Counter(tokens)
        total = 0.0
        n_docs = max(len(self.docs), 1)
        for term in tokenize(query):
            df = self.doc_freq.get(term, 0)
            if not df:
                continue
            idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            tf = counts.get(term, 0)
            denom = tf + self.k1 * (1 - self.b + self.b * len(tokens) / max(self.avgdl, 1))
            total += idf * ((tf * (self.k1 + 1)) / denom if denom else 0.0)
        return total

    def rank(self, query: str) -> list[tuple[int, float]]:
        ranked = [(i, self.score(query, i)) for i in range(len(self.docs))]
        return sorted(ranked, key=lambda item: item[1], reverse=True)
