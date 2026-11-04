"""Generic Evidence Extractor.
Parses raw unstructured text and structured records to extract atomic facts,
normalize numerical values and units, compute source provenance,
and detect contradictions and missing data.
"""

import hashlib
import re
from uuid import uuid4
from typing import Any
from .schema import FactCategory, FactRecord, EvidenceEnvelope

STANDARD_CATEGORIES = [
    FactCategory.INCORPORATION.value,
    FactCategory.FINANCIAL.value,
    FactCategory.HEADCOUNT.value,
    FactCategory.COMPLIANCE.value,
    FactCategory.LEGAL.value,
]


def normalize_currency(val_str: str) -> tuple[float | None, str | None]:
    """Normalizes currency representations (e.g. $4.2M, $15,000, 500K USD) to float and unit."""
    cleaned = val_str.replace(",", "").strip()
    unit = "USD"
    if "€" in cleaned or "eur" in cleaned.lower():
        unit = "EUR"
    elif "£" in cleaned or "gbp" in cleaned.lower():
        unit = "GBP"

    num_part = re.sub(r"[^\d\.]", "", cleaned)
    if not num_part:
        return None, None

    try:
        base_val = float(num_part)
    except ValueError:
        return None, None

    lower = cleaned.lower()
    if "b" in lower or "billion" in lower:
        return base_val * 1_000_000_000, unit
    if "m" in lower or "million" in lower:
        return base_val * 1_000_000, unit
    if "k" in lower or "thousand" in lower:
        return base_val * 1_000, unit

    return base_val, unit


def normalize_integer(val_str: str) -> int | None:
    """Extracts integer value from string, stripping formatting."""
    digits = re.sub(r"[^\d]", "", val_str)
    return int(digits) if digits else None


class EvidenceExtractor:
    """Generic, parameterized factual extraction engine with provenance tracking."""

    def __init__(self, doc_id: str = "source_document"):
        self.doc_id = doc_id

    def extract(
        self,
        source_text: str | None = None,
        entity: str = "Unknown Entity",
        ground_truth_facts: list[dict[str, Any]] | None = None
    ) -> EvidenceEnvelope:
        """Extracts facts from raw source document text and/or ground_truth_facts dicts."""
        envelope_id = f"ENV-{uuid4().hex[:8].upper()}"

        if not source_text and not ground_truth_facts:
            # Empty / absent source document
            return EvidenceEnvelope(
                envelope_id=envelope_id,
                entity=entity,
                source_doc_id=self.doc_id,
                source_sha256="",
                facts=[],
                missing_fields=list(STANDARD_CATEGORIES),
                uncertainties=["No source document or verified records provided"],
                contradictions=[],
                evidence_completeness=0.0,
            )

        text = source_text or ""
        sha256_hash = hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""
        facts: list[FactRecord] = []
        fact_idx = 1

        def find_offsets(snippet: str) -> tuple[int, int] | None:
            if not text or not snippet:
                return None
            idx = text.find(snippet)
            return (idx, idx + len(snippet)) if idx != -1 else None

        # Split into sentences for citation extraction
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

        # 1. Extraction from raw source_text
        if text:
            # A. Incorporation and Location
            inc_match = re.search(
                r"(?i)(?:founded|incorporated|established)\s+in\s+([A-Za-z\s]+?)\s+in\s+(\d{4})",
                text
            )
            if inc_match:
                loc = inc_match.group(1).strip()
                yr = int(inc_match.group(2))
                raw_span = inc_match.group(0)
                sent = next((s for s in sentences if raw_span in s), raw_span)
                facts.append(
                    FactRecord(
                        fact_id=f"FACT-{fact_idx:03d}",
                        subject=entity,
                        category=FactCategory.INCORPORATION.value,
                        claim=f"founded in {loc} in {yr}",
                        normalized_value={"location": loc, "year": yr},
                        original_value=raw_span,
                        source_doc_id=self.doc_id,
                        source_sha256=sha256_hash,
                        source_offset=find_offsets(raw_span),
                        source_citation=sent,
                        confidence=1.0,
                    )
                )
                fact_idx += 1

            # B. Financials (Revenue)
            rev_matches = re.findall(
                r"(?i)(?:annual\s+revenue(?:\s+of)?|revenue\s*(?:of|was|is|reached)?)\s*([\$€£]?\s*[\d\.,]+(?:\s*(?:[MmBbKk]|million|billion|thousand))?)",
                text
            )
            for raw_rev in rev_matches:
                norm_val, unit = normalize_currency(raw_rev)
                raw_claim = f"annual revenue of {raw_rev.strip()}"
                sent = next((s for s in sentences if raw_rev in s), raw_rev)
                facts.append(
                    FactRecord(
                        fact_id=f"FACT-{fact_idx:03d}",
                        subject=entity,
                        category=FactCategory.FINANCIAL.value,
                        claim=raw_claim,
                        normalized_value=norm_val,
                        original_value=raw_rev.strip(),
                        unit=unit,
                        source_doc_id=self.doc_id,
                        source_sha256=sha256_hash,
                        source_offset=find_offsets(raw_rev),
                        source_citation=sent,
                        confidence=1.0,
                    )
                )
                fact_idx += 1

            # C. Headcount
            hc_match = re.search(
                r"(?i)(\d[\d,]*)\s+(?:full-time\s+|part-time\s+|fte\s+)?(?:employees|workers|staff|headcount)",
                text
            )
            if hc_match:
                raw_hc = hc_match.group(0)
                norm_hc = normalize_integer(hc_match.group(1))
                sent = next((s for s in sentences if raw_hc in s), raw_hc)
                facts.append(
                    FactRecord(
                        fact_id=f"FACT-{fact_idx:03d}",
                        subject=entity,
                        category=FactCategory.HEADCOUNT.value,
                        claim=raw_hc.strip(),
                        normalized_value=norm_hc,
                        original_value=hc_match.group(1),
                        unit="employees",
                        source_doc_id=self.doc_id,
                        source_sha256=sha256_hash,
                        source_offset=find_offsets(raw_hc),
                        source_citation=sent,
                        confidence=1.0,
                    )
                )
                fact_idx += 1

            # D. Certifications (SOC 2, ISO, FedRAMP, etc.)
            cert_matches = re.finditer(
                r"(?i)(SOC\s*2(?:\s+Type\s+(?:II|I|2|1))?|ISO\s*\d+(?:[-:]\d+)?|FedRAMP\s*(?:High|Moderate|Low)?|HIPAA|PCI-DSS)",
                text
            )
            for cm in cert_matches:
                raw_cert = cm.group(0).strip()
                # Check for auditor and verification date in same sentence
                sent = next((s for s in sentences if raw_cert in s), raw_cert)
                auditor_match = re.search(r"(?i)verified\s+by\s+([A-Za-z0-9\s&]+?)(?:\s+in\s+([A-Za-z]+\s+\d{4})|\.|$)", sent)
                auditor = auditor_match.group(1).strip() if auditor_match else None
                vdate = auditor_match.group(2).strip() if (auditor_match and auditor_match.group(2)) else None

                facts.append(
                    FactRecord(
                        fact_id=f"FACT-{fact_idx:03d}",
                        subject=entity,
                        category=FactCategory.COMPLIANCE.value,
                        claim=f"{raw_cert} certification",
                        normalized_value={
                            "standard": raw_cert,
                            "auditor": auditor,
                            "verification_date": vdate,
                        },
                        original_value=raw_cert,
                        source_doc_id=self.doc_id,
                        source_sha256=sha256_hash,
                        source_offset=find_offsets(raw_cert),
                        source_citation=sent,
                        confidence=1.0,
                    )
                )
                fact_idx += 1

            # E. Legal and Litigation
            lit_match = re.search(
                r"(?i)(?:single|commercial|civil)?\s*litigation\s*(?:in\s+\d{4})?\s*settled(?:\s+out\s+of\s+court)?\s+for\s+([\$€£\d\.,MBKmbk]+)",
                text
            )
            if lit_match:
                raw_lit = lit_match.group(0)
                amount_str = lit_match.group(1)
                norm_amt, unit = normalize_currency(amount_str)
                sent = next((s for s in sentences if raw_lit in s), raw_lit)
                facts.append(
                    FactRecord(
                        fact_id=f"FACT-{fact_idx:03d}",
                        subject=entity,
                        category=FactCategory.LEGAL.value,
                        claim=f"single litigation settled for {amount_str}",
                        normalized_value={"status": "settled", "amount": norm_amt, "sanctions": False},
                        original_value=amount_str,
                        unit=unit,
                        source_doc_id=self.doc_id,
                        source_sha256=sha256_hash,
                        source_offset=find_offsets(raw_lit),
                        source_citation=sent,
                        confidence=1.0,
                    )
                )
                fact_idx += 1

            sanctions_match = re.search(r"(?i)no\s+regulatory\s+sanctions(?:\s+or\s+tax\s+liens)?(?:\s+exist)?", text)
            if sanctions_match:
                raw_sanc = sanctions_match.group(0)
                sent = next((s for s in sentences if raw_sanc in s), raw_sanc)
                facts.append(
                    FactRecord(
                        fact_id=f"FACT-{fact_idx:03d}",
                        subject=entity,
                        category=FactCategory.LEGAL.value,
                        claim="no regulatory sanctions or tax liens exist",
                        normalized_value={"sanctions": False, "tax_liens": False},
                        original_value=raw_sanc,
                        source_doc_id=self.doc_id,
                        source_sha256=sha256_hash,
                        source_offset=find_offsets(raw_sanc),
                        source_citation=sent,
                        confidence=1.0,
                    )
                )
                fact_idx += 1

            # F. Subsidiaries
            sub_match = re.search(r"(?i)(?:operating\s+)?subsidiaries\s+in\s+([A-Za-z\s,and]+)", text)
            if sub_match:
                raw_subs = sub_match.group(1).strip()
                sent = next((s for s in sentences if raw_subs in s), raw_subs)
                facts.append(
                    FactRecord(
                        fact_id=f"FACT-{fact_idx:03d}",
                        subject=entity,
                        category=FactCategory.SUBSIDIARY.value,
                        claim=f"operating subsidiaries in {raw_subs}",
                        normalized_value=raw_subs,
                        original_value=raw_subs,
                        source_doc_id=self.doc_id,
                        source_sha256=sha256_hash,
                        source_offset=find_offsets(raw_subs),
                        source_citation=sent,
                        confidence=1.0,
                    )
                )
                fact_idx += 1

        # 2. Integration of explicit ground_truth_facts if present
        if ground_truth_facts:
            existing_claims = {f.claim.lower() for f in facts}
            for gtf in ground_truth_facts:
                c_text = gtf.get("claim", "")
                c_type = gtf.get("type", "other")
                if c_text.lower() not in existing_claims:
                    norm_val, unit = None, None
                    if "$" in c_text or any(cur in c_text.lower() for cur in ("usd", "revenue", "settled")):
                        cur_match = re.search(r"[\$€£]?\s*[\d\.,]+(?:\s*(?:[MmBbKk]|million|billion|thousand))?", c_text)
                        if cur_match:
                            norm_val, unit = normalize_currency(cur_match.group(0))
                    elif any(w in c_text.lower() for w in ("employees", "workers", "headcount")):
                        hc_m = re.search(r"\d+", c_text)
                        if hc_m:
                            norm_val = int(hc_m.group(0))
                            unit = "employees"

                    facts.append(
                        FactRecord(
                            fact_id=f"FACT-{fact_idx:03d}",
                            subject=entity,
                            category=c_type,
                            claim=c_text,
                            normalized_value=norm_val,
                            original_value=c_text,
                            unit=unit,
                            source_doc_id=self.doc_id,
                            source_sha256=sha256_hash,
                            source_offset=find_offsets(c_text),
                            source_citation=c_text,
                            confidence=1.0,
                        )
                    )
                    fact_idx += 1
                    existing_claims.add(c_text.lower())

        # 3. Contradiction Detection across Extracted Facts
        contradictions: list[dict[str, Any]] = []
        fin_facts = [f for f in facts if f.category == FactCategory.FINANCIAL.value and f.normalized_value is not None]
        if len(fin_facts) > 1:
            values = set(f.normalized_value for f in fin_facts)
            if len(values) > 1:
                contradictions.append({
                    "category": "financial",
                    "description": f"Conflicting financial figures detected: {[f.original_value for f in fin_facts]}",
                    "fact_ids": [f.fact_id for f in fin_facts],
                })

        # 4. Missing Fields & Completeness
        present_categories = {f.category.lower() for f in facts}
        missing_fields = [cat for cat in STANDARD_CATEGORIES if cat not in present_categories]
        completeness = round(len(present_categories.intersection(STANDARD_CATEGORIES)) / len(STANDARD_CATEGORIES), 2)

        return EvidenceEnvelope(
            envelope_id=envelope_id,
            entity=entity,
            source_doc_id=self.doc_id,
            source_sha256=sha256_hash,
            facts=facts,
            missing_fields=missing_fields,
            uncertainties=[f"Missing source evidence for: {m}" for m in missing_fields],
            contradictions=contradictions,
            evidence_completeness=completeness,
        )
