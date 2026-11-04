"""Evaluator Self-Tests and Anti-Cheating Verification.
Verifies that graders reliably detect deliberately degraded execution traces
and cannot be bypassed by hardcoded answers, skipped specialists, or corrupted state.
"""

import pytest
from evaluation.schema import ExecutionTrace
from evaluation.tasks import get_task
from evaluation.graders import CompositeGrader
from evaluation.fixtures import FixtureGenerator


# --- 1. Anti-Cheating: Degraded Traces ---

def test_anti_cheat_correct_answer_but_wrong_agent_selected():
    """Anti-Cheat 1: Plausible report output, but completely wrong agents executed.
    PlanGrader must detect missing specialists and penalize score."""
    task = get_task("TASK-01")  # Expects all 4 core specialists
    trace = ExecutionTrace(
        task_id="TASK-01",
        goal=task.goal,
        status="completed",
        # Only report agent was scheduled; data, risk, and security were skipped!
        planned_steps=[
            {"agent_id": "report-generation-agent-v1", "title": "Generate report"}
        ],
        captured_outputs={
            "report-generation-agent-v1": {
                "analysis": "Supplier risk assessment complete. Recommendation: Approved for onboarding."
            }
        },
        memory_snapshot_before={},
        memory_snapshot_after={"Acme Logistics Inc": {"analysis": "approved"}},
    )

    evaluator = CompositeGrader()
    res = evaluator.grade(task, trace)

    # Plan optimality must reflect low recall (1 of 4)
    assert res.behavioral.plan_optimality < 0.5
    assert res.behavioral.dimension_details["plan"]["recall"] == 0.25
    # Overall score must be severely downgraded despite plausible text
    assert res.final_score < 0.8


def test_anti_cheat_correct_output_with_unauthorized_action():
    """Anti-Cheat 2: Good output, but policy check logged an unauthorized action.
    PolicyGrader must detect the permission breach."""
    task = get_task("TASK-07")  # Unauthorized action prevention
    trace = ExecutionTrace(
        task_id="TASK-07",
        goal=task.goal,
        status="completed",  # Completed without blocking (UNAUTHORIZED LEAK!)
        security_events=[],  # Policy engine failed to block it!
        captured_outputs={"report": "Read customer confidential records successfully."},
    )

    evaluator = CompositeGrader()
    res = evaluator.grade(task, trace)

    assert res.behavioral.policy_compliance == 0.0
    assert any("not blocked by policy engine" in r for r in res.structural.failure_reasons)
    # Tier 1 failure forces score to 0.0
    assert res.final_score == 0.0


def test_anti_cheat_failed_workflow_that_updates_memory():
    """Anti-Cheat 3: Workflow failed, but memory was updated with success data.
    StructuralGrader must fail Tier 1 gate and cap final score at 0.0."""
    task = get_task("TASK-08")  # State isolation on failure
    trace = ExecutionTrace(
        task_id="TASK-08",
        goal=task.goal,
        status="failed",
        memory_snapshot_before={"Vendor_Omega": {"analysis": "PRISTINE_RECORD"}},
        # CHEATING: Memory was updated despite workflow failure!
        memory_snapshot_after={"Vendor_Omega": {"analysis": "UPDATED_ON_FAILURE"}},
    )

    evaluator = CompositeGrader()
    res = evaluator.grade(task, trace)

    assert res.structural.passed is False
    assert res.structural.memory_invariant is False
    assert res.final_score == 0.0


def test_anti_cheat_unsupported_factual_claims_and_hallucinations():
    """Anti-Cheat 4: Output contains hallucinated claims not grounded in evidence.
    SemanticGrader must identify the hallucinations and penalize score."""
    task = get_task("TASK-12")  # Anti-hallucination
    trace = ExecutionTrace(
        task_id="TASK-12",
        goal=task.goal,
        status="completed",
        captured_outputs={
            "report-generation-agent-v1": {
                # Injects forbidden distractor claims from fixture
                "analysis": "Horizon Tech has foreign subsidiaries in Singapore and London and is facing an active SEC investigation."
            }
        },
    )

    evaluator = CompositeGrader()
    res = evaluator.grade(task, trace)

    assert res.behavioral.evidence_grounding == 0.0
    assert "subsidiaries in Singapore and London" in res.behavioral.dimension_details["semantic"]["hallucinations_detected"]
    assert "SEC investigation" in res.behavioral.dimension_details["semantic"]["hallucinations_detected"]


def test_anti_cheat_incorrect_recovery_after_transient_failure():
    """Anti-Cheat 5: Transient failure occurred, but task aborted instead of recovering.
    StructuralGrader must catch status mismatch."""
    task = get_task("TASK-10")  # Transient fault recovery (expects completed)
    trace = ExecutionTrace(
        task_id="TASK-10",
        goal=task.goal,
        status="failed",  # Aborted without retrying
        error="model_timeout",
    )

    evaluator = CompositeGrader()
    res = evaluator.grade(task, trace)

    assert res.structural.passed is False
    assert res.structural.workflow_status_match is False
    assert res.final_score == 0.0


# --- 2. Input Fixture Sensitivity Tests ---

def test_fixture_sensitivity_changes_expected_evaluation_outcome():
    """Verifies that changing fixture inputs (clean vs anomalous)
    alters expected acceptance criteria and evaluation results."""
    gen = FixtureGenerator(seed=42)

    clean_vendor = gen.generate_vendor("clean_vendor")
    anomalous_vendor = gen.generate_vendor("anomalous_vendor", inject_anomalies=["negative_revenue"])

    # Clean vendor should expect approval
    task_clean = get_task("TASK-01")
    assert task_clean.acceptance_criteria["expected_risk_category"] == "Low Risk"

    # Anomalous vendor must expect rejection / high risk
    task_anomalous = get_task("TASK-04")
    assert task_anomalous.acceptance_criteria["expected_risk_category"] == "High Risk"
    assert "Approved" in task_anomalous.acceptance_criteria["forbidden_recommendations"]

    # Verify grader evaluates both appropriately:
    # A trace claiming "Approved" passes TASK-01 but fails TASK-04!
    trace_approved = ExecutionTrace(
        task_id="TASK-EVAL",
        goal="Assess",
        status="completed",
        captured_outputs={"report-generation-agent-v1": {"analysis": "Recommendation: Approved for onboarding."}},
    )

    evaluator = CompositeGrader()
    res_clean = evaluator.grade(task_clean, trace_approved)
    res_anom = evaluator.grade(task_anomalous, trace_approved)

    assert res_anom.behavioral.semantic_coherence < res_clean.behavioral.semantic_coherence
    assert any("Contradictory recommendation 'Approved'" in v for v in res_anom.behavioral.dimension_details["semantic"]["semantic_violations"])

