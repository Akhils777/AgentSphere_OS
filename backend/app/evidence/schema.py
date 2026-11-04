"""Evidence Envelope and Grounding Schemas.
Formal data models for atomic facts, evidence envelopes, provenance tracking,
and verification outcomes.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class FactCategory(str, Enum):
    FINANCIAL = "financial"
    HEADCOUNT = "headcount"
    LOCATION = "location"
    COMPLIANCE = "compliance"
    LEGAL = "legal"
    INCORPORATION = "incorporation"
    SUBSIDIARY = "subsidiary"
    OPERATIONAL = "operational"
    OTHER = "other"


class VerificationOutcome(str, Enum):
    VERIFIED = "VERIFIED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"
    FORBIDDEN_HALLUCINATION = "FORBIDDEN_HALLUCINATION"


class FactRecord(BaseModel):
    """Represents an atomic, verified fact extracted from source material with provenance."""
    fact_id: str
    subject: str
    category: str
    claim: str
    normalized_value: Any = None
    original_value: str = ""
    unit: str | None = None
    source_doc_id: str = "source_document"
    source_sha256: str = ""
    source_offset: tuple[int, int] | None = None
    source_citation: str = ""
    confidence: float = 1.0
    verified: bool = True


class ClaimVerificationResult(BaseModel):
    """Result of validating a candidate statement/claim against an EvidenceEnvelope."""
    claim: str
    outcome: VerificationOutcome
    matched_fact_id: str | None = None
    numerical_match: bool | None = None
    confidence: float = 1.0
    reason: str = ""


class EvidenceEnvelope(BaseModel):
    """Structured evidence container passed across agents with completeness and provenance."""
    envelope_id: str
    entity: str
    source_doc_id: str = "source_document"
    source_sha256: str = ""
    facts: list[FactRecord] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    evidence_completeness: float = 1.0

    def get_fact(self, category: str) -> FactRecord | None:
        """Returns the first fact matching category, or None."""
        cat_lower = category.lower()
        for fact in self.facts:
            if fact.category.lower() == cat_lower:
                return fact
        return None

    def get_facts(self, category: str) -> list[FactRecord]:
        """Returns all facts matching category."""
        cat_lower = category.lower()
        return [f for f in self.facts if f.category.lower() == cat_lower]

    def to_dict(self) -> dict[str, Any]:
        """Serializes the envelope to a dictionary."""
        return self.model_dump()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvidenceEnvelope":
        """Deserializes an envelope from a dictionary."""
        return cls(**data)

