"""Evidence Extraction, Provenance Tracking, and Factual Grounding Package."""

from .schema import (
    FactCategory,
    FactRecord,
    EvidenceEnvelope,
    VerificationOutcome,
    ClaimVerificationResult,
)
from .extractor import EvidenceExtractor
from .verifier import GroundingVerifier

__all__ = [
    "FactCategory",
    "FactRecord",
    "EvidenceEnvelope",
    "VerificationOutcome",
    "ClaimVerificationResult",
    "EvidenceExtractor",
    "GroundingVerifier",
]

