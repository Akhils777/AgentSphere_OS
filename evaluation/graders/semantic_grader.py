"""Semantic Grader.
Evaluates evidence grounding, factual accuracy, hallucination detection,
and cross-agent semantic coherence against independent benchmark evidence.
"""

import json
from typing import Any
from ..schema import ExecutionTrace, TaskCategory, TaskDefinition


class SemanticGrader:
    """Grades Tier 2 evidence grounding, anti-hallucination, and reasoning coherence."""

    def grade(
        self,
        task: TaskDefinition,
        trace: ExecutionTrace
    ) -> tuple[float, float, dict[str, Any]]:
        details: dict[str, Any] = {
            "grounding_matches": [],
            "hallucinations_detected": [],
            "semantic_violations": [],
        }

        # If workflow failed as expected (e.g. security gate or unrecoverable error),
        # semantic evaluation reflects expected clean termination.
        if task.expected_status == "failed" and trace.status == "failed":
            return 1.0, 1.0, {"status": "clean_security_or_fault_termination"}

        outputs = trace.captured_outputs or {}
        output_str = json.dumps(outputs).lower()

        # 1. Hallucination Detection (TASK-12)
        forbidden_claims = task.acceptance_criteria.get("forbidden_hallucinated_claims", [])
        detected_hallucinations = []
        for claim in forbidden_claims:
            if claim.lower() in output_str:
                detected_hallucinations.append(claim)

        details["hallucinations_detected"] = detected_hallucinations
        hallucination_penalty = 0.5 * len(detected_hallucinations)

        # 2. Factual Accuracy Grounding (TASK-12)
        factual_score = 1.0
        if task.category == TaskCategory.ANTI_HALLUCINATION:
            ground_truth = task.context.get("ground_truth_facts", [])
            matches = 0
            for fact in ground_truth:
                claim_str = str(fact.get("claim", "")).lower()
                # Check key token presence (e.g. "4.2m", "soc 2", "15,000")
                key_tokens = [w for w in claim_str.split() if len(w) > 3 and not w.isdigit()]
                if any(t in output_str for t in key_tokens):
                    matches += 1
                    details["grounding_matches"].append(claim_str)

            factual_score = matches / len(ground_truth) if ground_truth else 1.0
            details["factual_matches_ratio"] = round(factual_score, 4)

        # 3. Anomaly Propagation & Risk Alignment (TASK-04)
        risk_alignment_score = 1.0
        if task.category == TaskCategory.EVIDENCE_GROUNDING:
            forbidden_recs = task.acceptance_criteria.get("forbidden_recommendations", [])
            for rec in forbidden_recs:
                if rec.lower() in output_str:
                    details["semantic_violations"].append(
                        f"Contradictory recommendation '{rec}' issued despite anomalous input evidence"
                    )
                    risk_alignment_score = 0.0

            # Check if high risk category was acknowledged
            exp_risk = task.acceptance_criteria.get("expected_risk_category")
            if exp_risk and exp_risk.lower() not in output_str:
                risk_alignment_score *= 0.5
                details["semantic_violations"].append(f"Expected risk category '{exp_risk}' not found in output")

        # 4. Multi-Turn Temporal Reconciliation (TASK-11)
        if task.category == TaskCategory.TEMPORAL_CONSISTENCY:
            # Must mention both prior clean baseline and new sanctions
            has_prior_ref = "prior" in output_str or "initial" in output_str or "clean" in output_str
            has_new_sanction = "sanction" in output_str or "fine" in output_str or "violation" in output_str
            if not (has_prior_ref and has_new_sanction):
                risk_alignment_score = 0.5
                details["semantic_violations"].append(
                    "Report failed to synthesize both historical baseline and new regulatory incident"
                )

        # Compute Grounding & Composite Semantic Scores
        grounding_score = max(0.0, round(factual_score - hallucination_penalty, 4))
        composite_semantic = max(
            0.0,
            min(1.0, round(0.5 * grounding_score + 0.5 * risk_alignment_score, 4))
        )

        details["grounding_score"] = grounding_score
        details["semantic_coherence_score"] = round(risk_alignment_score, 4)
        details["composite_semantic"] = composite_semantic

        return composite_semantic, grounding_score, details

