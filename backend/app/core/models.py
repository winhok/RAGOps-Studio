from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Document:
    id: str
    source_id: str
    title: str
    content: str
    version: int
    checksum: str
    allowed_roles: tuple[str, ...] = ("public",)
    metadata: dict[str, Any] = field(default_factory=dict)
    active: bool = True


@dataclass(slots=True)
class Chunk:
    id: str
    document_id: str
    source_id: str
    title: str
    text: str
    version: int
    allowed_roles: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievalHit:
    chunk: Chunk
    score: float
    dense_score: float = 0.0
    lexical_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0


@dataclass(slots=True)
class Citation:
    source_id: str
    title: str
    chunk_id: str
    quote: str
    score: float


@dataclass(slots=True)
class Answer:
    text: str
    citations: list[Citation]
    trace_id: str
    confidence: float
    timings_ms: dict[str, float]
    route: str = "answer"


@dataclass(slots=True)
class BenchmarkCase:
    query: str
    relevant_source_ids: tuple[str, ...]
    expected_keywords: tuple[str, ...] = ()
    role: str = "public"
