from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.models import EvidenceType

class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

class SaveDocumentRequest(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=150000)
    department_id: str = Field(default='customer-service', pattern='^[a-zA-Z0-9_-]{1,64}$')
    visibility: Literal['company', 'department'] = 'company'
    evidence_type: EvidenceType = 'general'
    additional_evidence_types: list[EvidenceType] = Field(default_factory=list, max_length=8)
    effective_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    expected_version: int | None = Field(default=None, ge=0)

    @field_validator('effective_at', 'expires_at')
    @classmethod
    def require_timezone(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError('Timestamp must contain a timezone')
        return value

    @model_validator(mode='after')
    def check_dates(self):
        self.additional_evidence_types = sorted(set(self.additional_evidence_types) - {self.evidence_type})
        if self.expires_at and self.expires_at <= self.effective_at:
            raise ValueError('expires_at must be later than effective_at')
        return self

class ChatRequest(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=8)

class EvaluateRequest(StrictModel):
    k: int = Field(default=5, ge=1, le=8)
