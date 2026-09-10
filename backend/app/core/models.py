from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
EvidenceType = Literal['review_rule', 'material_requirement', 'arrival_rule', 'maintenance_policy', 'finance_policy', 'service_workflow', 'promotion_policy', 'general']
EVIDENCE_TYPES = ('review_rule', 'material_requirement', 'arrival_rule', 'maintenance_policy', 'finance_policy', 'service_workflow', 'promotion_policy', 'general')

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def iso_now() -> str:
    return utcnow().isoformat()

class Principal(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid')
    user_id: str
    name: str
    tenant_id: str
    department_id: str
    role: Literal['admin', 'employee']

class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    route: Literal['direct', 'retrieve', 'clarify']
    required_evidence: list[EvidenceType] = Field(default_factory=list, max_length=8)
    clarification_question: str | None = None
    reason: str = Field(min_length=1, max_length=500)

    @model_validator(mode='after')
    def check_route(self):
        self.required_evidence = list(dict.fromkeys(self.required_evidence))
        if self.route == 'retrieve' and (not self.required_evidence):
            raise ValueError('A retrieval decision must name the required evidence')
        if self.route == 'clarify' and (not (self.clarification_question or '').strip()):
            raise ValueError('A clarification decision must contain a question')
        if self.route != 'retrieve' and self.required_evidence:
            raise ValueError('Only retrieval decisions may request evidence')
        return self

class GroundedAnswer(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['answered', 'insufficient_evidence']
    answer: str = Field(min_length=1, max_length=12000)
    source_ids: list[str] = Field(default_factory=list, max_length=32)

@dataclass(slots=True)
class Document:
    id: str
    revision_id: str
    tenant_id: str
    title: str
    content: str
    version: int
    checksum: str
    department_id: str
    visibility: str
    evidence_type: str
    effective_at: str
    expires_at: str | None
    source_path: str
    active: bool = True
    created_at: str = field(default_factory=iso_now)
    chunk_count: int = 0
    additional_evidence_types: list[str] = field(default_factory=list)

@dataclass(slots=True)
class Chunk:
    id: str
    document_id: str
    revision_id: str
    tenant_id: str
    title: str
    text: str
    version: int
    index: int
    department_id: str
    visibility: str
    evidence_type: str
    effective_at: str
    expires_at: str | None
    source_path: str
    active: bool = True
    vector: list[float] = field(default_factory=list, repr=False)
    additional_evidence_types: list[str] = field(default_factory=list)

    def evidence_types(self) -> set[str]:
        return {self.evidence_type, *self.additional_evidence_types}

@dataclass(slots=True)
class RetrievalHit:
    chunk: Chunk
    score: float
    dense_score: float | None = None
    lexical_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None

@dataclass(slots=True)
class Answer:
    text: str
    citations: list[dict[str, Any]]
    trace_id: str
    outcome: str
    route: str
    search_attempts: int
    required_evidence: list[str]
    missing_evidence: list[str]
    stop_reason: str
    timings_ms: dict[str, float]
    runtime: dict[str, Any]

@dataclass(slots=True)
class BenchmarkCase:
    query: str
    relevant_source_ids: tuple[str, ...]
    expected_keywords: tuple[str, ...] = ()
