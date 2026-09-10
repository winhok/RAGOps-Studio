from __future__ import annotations

from pydantic import BaseModel, Field


class IngestTextRequest(BaseModel):
    source_id: str = Field(min_length=2, max_length=120)
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=20)
    allowed_roles: list[str] = Field(default_factory=lambda: ["public"])
    metadata: dict = Field(default_factory=dict)


class ChatRequest(BaseModel):
    query: str = Field(min_length=2, max_length=2000)
    role: str = "public"
    top_k: int = Field(default=5, ge=1, le=10)


class EvaluateRequest(BaseModel):
    k: int = Field(default=5, ge=1, le=10)
