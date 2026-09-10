from __future__ import annotations

import math
from dataclasses import dataclass, asdict


@dataclass(slots=True)
class EvaluationSummary:
    cases: int
    recall_at_k: float
    mrr: float
    ndcg_at_k: float
    keyword_coverage: float

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 1.0
    found = set(retrieved[:k]) & relevant
    return len(found) / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: set[str]) -> float:
    for idx, item in enumerate(retrieved, start=1):
        if item in relevant:
            return 1.0 / idx
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    dcg = 0.0
    for idx, item in enumerate(retrieved[:k], start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(idx + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(idx + 1) for idx in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 1.0


def keyword_coverage(answer: str, expected_keywords: tuple[str, ...]) -> float:
    if not expected_keywords:
        return 1.0
    lowered = answer.lower()
    matched = sum(1 for kw in expected_keywords if kw.lower() in lowered)
    return matched / len(expected_keywords)
