from __future__ import annotations
import math
import re
from collections import Counter
TOKEN_RE = re.compile('[A-Za-z0-9_\\-]+|[\\u4e00-\\u9fff]')
SENTENCE_RE = re.compile('(?<=[.!?。！？])\\s+|\\n+')

def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]

def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]

def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum((x * y for x, y in zip(a, b, strict=False)))
    na = math.sqrt(sum((x * x for x in a)))
    nb = math.sqrt(sum((y * y for y in b)))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)

def overlap_score(query: str, text: str) -> float:
    q = Counter(tokenize(query))
    t = Counter(tokenize(text))
    if not q:
        return 0.0
    overlap = sum((min(count, t[token]) for token, count in q.items()))
    return overlap / sum(q.values())
