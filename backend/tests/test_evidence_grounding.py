import pytest
import hashlib
from app.evidence.schema import (
    FactCategory,
    FactRecord,
    EvidenceEnvelope,
    VerificationOutcome,
)
from app.evidence.extractor import (
    EvidenceExtractor,
    normalize_currency,
    normalize_integer,
)
from app.evidence.verifier import GroundingVerifier
from app.runtime.workflow_engine import engine, AGENTS
from app.storage import store


# --- 1. Extraction and Normalization Tests with Randomized Values ---

def test_evidence_extraction_randomized_company_and_metrics():
    """Verify generic extraction from arbitrary company names, revenues, headcounts, and states."""
    company = "Vanguard Dynamics Corp"
    state = "Minnesota"
    year = 2016
    revenue = "$24.5M"
    employees = 175
    cert = "ISO 27001"
    settlement = "$45,000"

    doc = (
        f"{company} was founded in {state} in {year}. "
        f"It reported annual revenue of {revenue} with {employees} full-time employees. "
        f"The company maintains an active {cert} certification verified by KPMG in August 2024. "
        f"It had a commercial litigation in 2021 settled out of court for {settlement}. "
        f"No regulatory sanctions or tax liens exist."
    )

    extractor = EvidenceExtractor(doc_id="test_doc_01")
    envelope = extractor.extract(doc, entity=company)

    assert envelope.entity == company
    assert envelope.source_sha256 == hashlib.sha256(doc.encode("utf-8")).hexdigest()
    assert envelope.evidence_completeness == 1.0
    assert len(envelope.contradictions) == 0

    # Incorporation
    inc = envelope.get_fact(FactCategory.INCORPORATION.value)
    assert inc is not None
    assert inc.normalized_value["location"] == state
    assert inc.normalized_value["year"] == year
    assert inc.source_offset is not None

    # Financial
    fin = envelope.get_fact(FactCategory.FINANCIAL.value)
    assert fin is not None
    assert fin.normalized_value == 24_500_000.0
    assert fin.unit == "USD"
    assert fin.original_value == revenue

    # Headcount
    hc = envelope.get_fact(FactCategory.HEADCOUNT.value)
    assert hc is not None
    assert hc.normalized_value == employees
    assert hc.unit == "employees"

    # Compliance
    comp = envelope.get_fact(FactCategory.COMPLIANCE.value)
    assert comp is not None
    assert comp.normalized_value["standard"] == cert
    assert comp.normalized_value["auditor"] == "KPMG"

    # Legal
    legal = envelope.get_fact(FactCategory.LEGAL.value)
    assert legal is not None
    assert legal.normalized_value["amount"] == 45_000.0
    assert legal.normalized_value["status"] == "settled"


def test_currency_and_numerical_normalization_edges():
    """Verify various currency and numerical representations normalize accurately."""
    assert normalize_currency("$4.2M") == (4_200_000.0, "USD")
    assert normalize_currency("$500K") == (500_000.0, "USD")
    assert normalize_currency("$1.5B") == (1_500_000_000.0, "USD")
    assert normalize_currency("$15,000") == (15_000.0, "USD")
    assert normalize_currency("€2.5M") == (2_500_000.0, "EUR")
    assert normalize_currency("£100,000") == (100_000.0, "GBP")

    assert normalize_integer("48") == 48
    assert normalize_integer("1,250") == 1250
    assert normalize_integer("invalid") is None


# --- 2. Claim Verification & Anti-Hallucination Tests ---

def test_unsupported_numerical_claims_rejected():
    """Verify that unevidenced numerical claims are strictly flagged as UNSUPPORTED."""
    doc = "Apex Corp reported annual revenue of $3.5M with 25 full-time employees."
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Apex Corp")
    verifier = GroundingVerifier()

    # Valid supported claim
    res_valid = verifier.verify_claim("Apex Corp reported annual revenue of $3.5M.", envelope)
    assert res_valid.outcome == VerificationOutcome.VERIFIED

    # Unsupported fabricated revenue claim
    res_unsupported = verifier.verify_claim("Apex Corp reported annual revenue of $9.2M.", envelope)
    assert res_unsupported.outcome == VerificationOutcome.UNSUPPORTED
    assert "9.2m" in res_unsupported.reason.lower()

    # Unsupported fabricated headcount
    res_hc = verifier.verify_claim("Apex Corp employs 500 full-time employees.", envelope)
    assert res_hc.outcome == VerificationOutcome.UNSUPPORTED


def test_forbidden_distractor_hallucinations_rejected():
    """Verify high-risk distractor claims (Singapore/London subsidiaries, SEC investigations, FedRAMP High)."""
    doc = "Horizon Tech Ltd maintains active SOC 2 Type II certification. No regulatory sanctions exist."
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Horizon Tech Ltd")
    verifier = GroundingVerifier()

    # Distractor 1: Fabricated foreign subsidiaries
    res_sub = verifier.verify_claim("Horizon Tech has operating subsidiaries in Singapore and London.", envelope)
    assert res_sub.outcome == VerificationOutcome.FORBIDDEN_HALLUCINATION
    assert "subsidiary" in res_sub.reason.lower()

    # Distractor 2: Fabricated regulatory investigation
    res_sec = verifier.verify_claim("Horizon Tech is subject to an active SEC investigation.", envelope)
    assert res_sec.outcome == VerificationOutcome.FORBIDDEN_HALLUCINATION

    # Distractor 3: Fabricated FedRAMP High certification
    res_fed = verifier.verify_claim("The vendor holds FedRAMP High authorization.", envelope)
    assert res_fed.outcome == VerificationOutcome.FORBIDDEN_HALLUCINATION

    # Distractor 4: Fabricated financial decline trend
    res_trend = verifier.verify_claim("Company revenue decreased by 40% year-over-year.", envelope)
    assert res_trend.outcome == VerificationOutcome.FORBIDDEN_HALLUCINATION


def test_contradictory_source_claims_detected():
    """Verify that statements contradicting verified facts are classified as CONTRADICTORY."""
    doc = "Beacon Systems has a commercial litigation in 2022 settled out of court for $10,000. No regulatory sanctions exist."
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Beacon Systems")
    verifier = GroundingVerifier()

    # Contradiction: claiming active litigation when settled
    res_lit = verifier.verify_claim("Beacon Systems is currently defending against active litigation.", envelope)
    assert res_lit.outcome == VerificationOutcome.CONTRADICTORY

    # Contradiction: claiming regulatory sanctions when zero exist
    res_sanc = verifier.verify_claim("Regulatory sanctions and fines were imposed on Beacon Systems.", envelope)
    assert res_sanc.outcome == VerificationOutcome.CONTRADICTORY


def test_missing_evidence_and_abstention():
    """Verify that claims regarding absent attributes are flagged as unsupported."""
    doc = "Delta Corp was founded in Nevada in 2019."
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Delta Corp")
    verifier = GroundingVerifier()

    assert "financial" in envelope.missing_fields
    assert "compliance" in envelope.missing_fields

    # Claim asserting financial status without source evidence
    res_fin = verifier.verify_claim("Delta Corp has excellent financial revenue performance.", envelope)
    assert res_fin.outcome == VerificationOutcome.UNSUPPORTED


def test_conflicting_source_document_detection():
    """Verify conflicting statements within a source document are flagged in contradictions."""
    doc = "Echo Corp reported annual revenue of $5.0M. Later audit shows revenue of $2.5M."
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Echo Corp")

    assert len(envelope.contradictions) >= 1
    assert envelope.contradictions[0]["category"] == "financial"


def test_empty_and_absent_source_document():
    """Verify absent source document handles gracefully with zero hallucinations."""
    extractor = EvidenceExtractor()
    envelope = extractor.extract(None, entity="Empty Corp")

    assert len(envelope.facts) == 0
    assert len(envelope.missing_fields) == 5
    assert envelope.evidence_completeness == 0.0

    verifier = GroundingVerifier()
    res = verifier.verify_claim("Empty Corp reported revenue of $1M.", envelope)
    assert res.outcome == VerificationOutcome.UNSUPPORTED


# --- 3. Full Workflow & Cross-Agent Handoff Integration Tests ---

@pytest.mark.asyncio
async def test_full_workflow_evidence_handoff_and_grounded_report():
    """Verify complete multi-agent pipeline extracts evidence, passes envelope, and produces verified report."""
    company = "OmniTech Solutions"
    doc = (
        f"{company} was founded in Colorado in 2018. "
        f"It reported annual revenue of $4.2M with 48 full-time employees. "
        f"The company maintains an active SOC 2 Type II certification verified by Ernst & Young in November 2025. "
        f"It has had a single commercial litigation in 2023 settled out of court for $15,000. "
        f"No regulatory sanctions or tax liens exist."
    )

    wf = engine.create(
        f"Evaluate supplier {company} based strictly on verified records",
        "eval-user",
        {
            "entity": company,
            "source_document": doc,
        }
    )

    await engine.run(wf)

    updated_wf = engine.get(wf["workflow_id"])
    assert updated_wf["status"] == "completed"
    assert updated_wf["progress"] == 100

    tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
    assert len(tasks) == 4

    # 1. Verify Data Agent emitted evidence envelope
    data_task = next(t for t in tasks if t["agent_id"] == "data-intelligence-agent-v1")
    assert "evidence_envelope" in data_task["output"]
    env_dict = data_task["output"]["evidence_envelope"]
    assert len(env_dict["facts"]) >= 5

    # 2. Verify Risk Agent cited evidenced facts
    risk_task = next(t for t in tasks if t["agent_id"] == "risk-analysis-agent-v1")
    assert "settled" in risk_task["output"]["key_findings"]

    # 3. Verify Security Agent cited active certification
    sec_task = next(t for t in tasks if t["agent_id"] == "security-compliance-agent-v1")
    assert "SOC 2" in sec_task["output"]["findings"]

    # 4. Verify Report Agent generated grounded executive assessment citing all 5 facts
    rep_task = next(t for t in tasks if t["agent_id"] == "report-generation-agent-v1")
    rep_out = rep_task["output"]
    analysis = rep_out["analysis"]

    # Check key citations
    assert "Colorado" in analysis
    assert "2018" in analysis
    assert "$4.2M" in analysis
    assert "48" in analysis
    assert "SOC 2 Type II" in analysis
    assert "$15,000" in analysis

    # Check zero hallucinations in report verification
    v_res = rep_out.get("grounding_verification", {})
    assert v_res.get("status") == "VERIFIED"
    assert v_res.get("hallucinations_count") == 0
    assert v_res.get("unsupported_claims_count") == 0


@pytest.mark.asyncio
async def test_workflow_backward_compatibility_when_no_source_document():
    """Verify that workflows without source_document (TASK-01 to TASK-11) execute without errors."""
    wf = engine.create("Standard supplier evaluation", "test-user", {"entity": "Standard Vendor"})
    await engine.run(wf)

    updated_wf = engine.get(wf["workflow_id"])
    assert updated_wf["status"] == "completed"
    assert updated_wf["progress"] == 100

    tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
    assert len(tasks) == 4
    for t in tasks:
        assert t["status"] == "completed"


def test_provenance_integrity_and_offsets():
    """Verify that source offsets accurately index original substrings in the raw source text."""
    doc = "Zephyr Dynamics was founded in Washington in 2012. It reported annual revenue of $8.5M with 64 full-time employees."
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Zephyr Dynamics")

    for fact in envelope.facts:
        if fact.source_offset:
            start, end = fact.source_offset
            sliced = doc[start:end]
            assert fact.original_value in sliced or sliced in fact.original_value


def test_filter_hallucinations_replaces_with_abstention():
    """Verify filter_hallucinations strips forbidden claims and attaches clean abstentions."""
    doc = "Nova Corp maintains active SOC 2 Type II certification. No regulatory sanctions exist."
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Nova Corp")
    verifier = GroundingVerifier()

    report = (
        "Nova Corp maintains active SOC 2 Type II certification. "
        "The company has operating subsidiaries in Singapore and London. "
        "Recommendation: Proceed with onboarding."
    )

    filtered = verifier.filter_hallucinations(report, envelope)
    assert "SOC 2 Type II" in filtered
    assert "Singapore and London" not in filtered
    assert "[Omitted uncorroborated claim" in filtered
    assert "Recommendation: Proceed with onboarding." in filtered


def test_contradictory_headcount_and_financials_in_document():
    """Verify multiple conflicting figures within the same document are flagged."""
    doc = (
        "Polaris Corp reported annual revenue of $10.0M with 50 full-time employees. "
        "Internal audit reports annual revenue of $5.0M with 100 full-time employees."
    )
    extractor = EvidenceExtractor()
    envelope = extractor.extract(doc, entity="Polaris Corp")

    assert len(envelope.contradictions) >= 1
    fin_conflict = next((c for c in envelope.contradictions if c["category"] == "financial"), None)
    assert fin_conflict is not None


def test_structured_ground_truth_facts_fallback_extraction():
    """Verify extraction from structured ground_truth_facts dicts when source text is absent."""
    gt_facts = [
        {"claim": "founded in Texas in 2020", "type": "incorporation"},
        {"claim": "annual revenue of $6.0M", "type": "financial"},
        {"claim": "55 full-time employees", "type": "headcount"},
        {"claim": "ISO 27001 certification", "type": "compliance"},
    ]
    extractor = EvidenceExtractor()
    envelope = extractor.extract(source_text=None, entity="Orion Corp", ground_truth_facts=gt_facts)

    assert envelope.entity == "Orion Corp"
    assert len(envelope.facts) == 4
    fin = envelope.get_fact("financial")
    assert fin is not None
    assert fin.normalized_value == 6_000_000.0
