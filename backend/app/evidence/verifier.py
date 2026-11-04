"""Claim Verification and Anti-Hallucination Engine.
Validates candidate statements, numerical assertions, certifications,
and ownership claims against an EvidenceEnvelope with strict hallucination rejection.
"""

import re
from typing import Any
from .schema import (
    FactCategory,
    FactRecord,
    EvidenceEnvelope,
    VerificationOutcome,
    ClaimVerificationResult,
)
from .extractor import normalize_currency, normalize_integer

# High-risk patterns that constitute fabricated distractor claims unless explicitly verified in source evidence
FORBIDDEN_DISTRACTOR_PATTERNS = [
    (r"(?i)subsidiaries\s+in\s+(?:Singapore|London|Europe|Asia|Dubai)", "fabricated_foreign_subsidiary"),
    (r"(?i)(?:SEC|regulatory|FTC|DOJ)\s+investigation", "fabricated_regulatory_investigation"),
    (r"(?i)FedRAMP\s+High", "fabricated_high_security_authorization"),
    (r"(?i)revenue\s+decreased\s+by\s+\d+%", "fabricated_financial_trend"),
    (r"(?i)tax\s+liens\s+totaling", "fabricated_tax_liability"),
]


class GroundingVerifier:
    """Rigorous verification engine that validates agent claims against source evidence."""

    def __init__(self, numerical_tolerance: float = 0.01):
        self.numerical_tolerance = numerical_tolerance

    def verify_claim(self, claim: str, envelope: EvidenceEnvelope) -> ClaimVerificationResult:
        """Verifies a single statement/claim against the EvidenceEnvelope."""
        claim_cleaned = claim.strip()
        claim_lower = claim_cleaned.lower()

        # 1. Forbidden Hallucination / Distractor Check
        for pattern, distractor_type in FORBIDDEN_DISTRACTOR_PATTERNS:
            if re.search(pattern, claim_cleaned):
                # Check if this distractor was actually in the verified source facts
                matched_fact = next(
                    (f for f in envelope.facts if re.search(pattern, f.claim or "") or re.search(pattern, f.source_citation or "")),
                    None
                )
                if not matched_fact:
                    return ClaimVerificationResult(
                        claim=claim_cleaned,
                        outcome=VerificationOutcome.FORBIDDEN_HALLUCINATION,
                        numerical_match=False,
                        confidence=1.0,
                        reason=f"Detected forbidden hallucinated distractor: {distractor_type}",
                    )

        # 2. Contradiction Check
        # Check A: Contradicting legal / regulatory status
        if "investigation" in claim_lower or "sanction" in claim_lower:
            no_sanc_fact = next(
                (f for f in envelope.facts if f.category == FactCategory.LEGAL.value and "no regulatory sanctions" in f.claim.lower()),
                None
            )
            if no_sanc_fact and "no " not in claim_lower and "zero" not in claim_lower:
                return ClaimVerificationResult(
                    claim=claim_cleaned,
                    outcome=VerificationOutcome.CONTRADICTORY,
                    matched_fact_id=no_sanc_fact.fact_id,
                    confidence=1.0,
                    reason="Claim asserts regulatory sanctions or investigations, contradicting verified zero-sanction record.",
                )

        if "active litigation" in claim_lower or "unresolved lawsuit" in claim_lower:
            settled_fact = next(
                (f for f in envelope.facts if f.category == FactCategory.LEGAL.value and "settled" in f.claim.lower()),
                None
            )
            if settled_fact:
                return ClaimVerificationResult(
                    claim=claim_cleaned,
                    outcome=VerificationOutcome.CONTRADICTORY,
                    matched_fact_id=settled_fact.fact_id,
                    confidence=1.0,
                    reason="Claim asserts active litigation, contradicting verified settled status.",
                )

        # 3. Numerical Assertion Verification
        # Check explicit currency amounts (must have $, €, £, or currency keyword)
        cur_in_claim = re.findall(
            r"([\$€£]\s*[\d\.,]+(?:\s*(?:[MmBbKk]|million|billion|thousand))?|\b\d[\d\.,]*\s*(?:USD|EUR|GBP|dollars|million\s+dollars)\b)",
            claim_cleaned,
            re.IGNORECASE
        )
        for cur_str in cur_in_claim:
            norm_val, _ = normalize_currency(cur_str)
            if norm_val is not None:
                # Check if this number matches any financial or legal fact
                matching_fact = None
                for f in envelope.facts:
                    f_val = f.normalized_value
                    if isinstance(f_val, (int, float)):
                        diff = abs(f_val - norm_val) / max(f_val, 1.0)
                        if diff <= self.numerical_tolerance:
                            matching_fact = f
                            break
                    elif isinstance(f_val, dict) and "amount" in f_val and f_val["amount"] is not None:
                        diff = abs(f_val["amount"] - norm_val) / max(f_val["amount"], 1.0)
                        if diff <= self.numerical_tolerance:
                            matching_fact = f
                            break

                if not matching_fact:
                    return ClaimVerificationResult(
                        claim=claim_cleaned,
                        outcome=VerificationOutcome.UNSUPPORTED,
                        numerical_match=False,
                        confidence=1.0,
                        reason=f"Numerical value '{cur_str}' ({norm_val}) has no matching record in verified evidence.",
                    )

        # Check headcount numbers
        hc_match = re.search(r"(\d[\d,]*)\s+(?:full-time\s+|part-time\s+|fte\s+)?(?:employees|workers|headcount)", claim_cleaned, re.IGNORECASE)
        if hc_match:
            claimed_hc = normalize_integer(hc_match.group(1))
            matching_fact = next(
                (f for f in envelope.facts if f.category == FactCategory.HEADCOUNT.value and f.normalized_value == claimed_hc),
                None
            )
            if not matching_fact:
                return ClaimVerificationResult(
                    claim=claim_cleaned,
                    outcome=VerificationOutcome.UNSUPPORTED,
                    numerical_match=False,
                    confidence=1.0,
                    reason=f"Claimed headcount '{claimed_hc}' does not match verified employee records.",
                )

        # 4. Factual Grounding & Matching
        best_match: FactRecord | None = None
        for fact in envelope.facts:
            # Check key tokens match
            fact_tokens = [w.lower() for w in re.findall(r"[A-Za-z0-9\$\.]+", fact.claim) if len(w) > 2]
            if fact_tokens and sum(1 for t in fact_tokens if t in claim_lower) >= max(1, len(fact_tokens) // 2):
                best_match = fact
                break

        if best_match:
            return ClaimVerificationResult(
                claim=claim_cleaned,
                outcome=VerificationOutcome.VERIFIED,
                matched_fact_id=best_match.fact_id,
                numerical_match=True,
                confidence=1.0,
                reason="Claim is directly corroborated by verified source facts.",
            )

        # If claim asserts facts about a missing field, flag as unsupported
        for m_field in envelope.missing_fields:
            if m_field in claim_lower:
                return ClaimVerificationResult(
                    claim=claim_cleaned,
                    outcome=VerificationOutcome.UNSUPPORTED,
                    numerical_match=None,
                    confidence=1.0,
                    reason=f"Claim asserts data regarding '{m_field}', which was absent from source records.",
                )

        # Fallback: unsupported generic assertion
        return ClaimVerificationResult(
            claim=claim_cleaned,
            outcome=VerificationOutcome.UNSUPPORTED,
            matched_fact_id=None,
            numerical_match=None,
            confidence=0.8,
            reason="Statement cannot be corroborated against verified evidence.",
        )

    def verify_report(self, report_text: str, envelope: EvidenceEnvelope) -> dict[str, Any]:
        """Audits a complete multi-sentence report against the EvidenceEnvelope."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", report_text) if len(s.strip()) > 5]
        results: list[ClaimVerificationResult] = []

        verified_claims = []
        unsupported_claims = []
        contradictions = []
        hallucinations = []

        for sent in sentences:
            # Skip purely structural/heading/recommendation statements that don't make empirical factual assertions
            sent_low = sent.lower()
            if any(sent_low.startswith(p) for p in (
                "recommendation:", "proceed with", "overall:", "in conclusion",
                "executive assessment", "assessment for", "summary for", "evaluation for"
            )):
                continue

            res = self.verify_claim(sent, envelope)
            results.append(res)

            if res.outcome == VerificationOutcome.VERIFIED:
                verified_claims.append(sent)
            elif res.outcome == VerificationOutcome.UNSUPPORTED:
                unsupported_claims.append(sent)
            elif res.outcome == VerificationOutcome.CONTRADICTORY:
                contradictions.append(sent)
            elif res.outcome == VerificationOutcome.FORBIDDEN_HALLUCINATION:
                hallucinations.append(sent)

        total_checked = len(results)
        grounding_score = len(verified_claims) / total_checked if total_checked > 0 else 1.0

        is_clean = len(unsupported_claims) == 0 and len(contradictions) == 0 and len(hallucinations) == 0

        return {
            "status": "VERIFIED" if is_clean else "UNVERIFIED",
            "total_claims_checked": total_checked,
            "verified_claims_count": len(verified_claims),
            "unsupported_claims_count": len(unsupported_claims),
            "contradictions_count": len(contradictions),
            "hallucinations_count": len(hallucinations),
            "grounding_score": round(grounding_score, 4),
            "verified_claims": verified_claims,
            "unsupported_claims": unsupported_claims,
            "contradictions": contradictions,
            "hallucinations": hallucinations,
            "detailed_results": [r.model_dump() for r in results],
        }

    def filter_hallucinations(self, report_text: str, envelope: EvidenceEnvelope) -> str:
        """Filters out unverified or hallucinated sentences from a report."""
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", report_text) if s.strip()]
        cleaned_sentences: list[str] = []

        for sent in sentences:
            res = self.verify_claim(sent, envelope)
            if res.outcome == VerificationOutcome.VERIFIED or any(
                sent.lower().startswith(p) for p in ("recommendation:", "proceed with", "overall:", "in conclusion")
            ):
                cleaned_sentences.append(sent)
            else:
                cleaned_sentences.append(f"[Omitted uncorroborated claim: {res.reason}]")

        return " ".join(cleaned_sentences)
