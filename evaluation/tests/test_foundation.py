"""Unit tests for Stage 2.1: Foundation, Schemas, Configuration, and Sandbox Isolation.
Verifies zero data pollution, strict structural score overrides, and framework compatibility.
"""

import json
import pytest
import random
from pathlib import Path
from pydantic import ValidationError

from evaluation.config import EvaluationConfig, EvaluationMode
from evaluation.schema import (
    BehavioralScores,
    BenchmarkReport,
    EvaluationMetrics,
    ExecutionTrace,
    StructuralResult,
    TaskCategory,
    TaskDefinition,
    TaskEvaluationResult,
)
from evaluation.harness.sandbox import EvaluationSandbox


# --- 1. Configuration Tests ---

def test_default_configuration():
    """Verifies default evaluation settings adhere strictly to safe mock execution."""
    config = EvaluationConfig()
    assert config.mode == EvaluationMode.MOCK
    assert config.model_name == "mock-gemini-flash"
    assert config.seed == 42
    assert config.runs_per_task == 3
    assert config.timeout_seconds == 30.0
    assert config.isolate_storage is True

    # Check scoring weights sum to 1.0
    assert sum(config.scoring_weights.values()) == pytest.approx(1.0, 1e-4)
    assert config.scoring_weights["plan"] == 0.25
    assert config.scoring_weights["grounding"] == 0.25
    assert config.scoring_weights["policy"] == 0.25
    assert config.scoring_weights["semantic"] == 0.25

    # Check default thresholds
    assert config.metric_thresholds["task_success_rate"] == 0.90
    assert config.metric_thresholds["agent_selection_f1"] == 0.95
    assert config.metric_thresholds["memory_integrity_violations"] == 0.0


def test_configuration_validation_modes_and_weights():
    """Verifies validation rules for scoring weights, modes, and bounds."""
    # Weights not summing to 1.0 must fail
    with pytest.raises(ValidationError, match="Scoring weights must sum to 1.0"):
        EvaluationConfig(scoring_weights={"plan": 0.5, "grounding": 0.2})

    # Negative seed must fail
    with pytest.raises(ValidationError):
        EvaluationConfig(seed=-1)

    # Zero timeout must fail
    with pytest.raises(ValidationError):
        EvaluationConfig(timeout_seconds=0.0)

    # Runs per task bounds
    with pytest.raises(ValidationError):
        EvaluationConfig(runs_per_task=0)

    # Mock mode prefix auto-normalization
    cfg = EvaluationConfig(mode=EvaluationMode.MOCK, model_name="gemini-1.5-flash")
    assert cfg.model_name == "mock-gemini-1.5-flash"

    # Live mode acceptance
    live_cfg = EvaluationConfig(mode=EvaluationMode.LIVE, model_name="gemini-1.5-pro")
    assert live_cfg.mode == EvaluationMode.LIVE
    assert live_cfg.model_name == "gemini-1.5-pro"


# --- 2. Schema and Structural Override Tests ---

def test_schema_structural_override_capping_at_zero():
    """Strict Requirement 4: Any Tier 1 structural failure MUST cap final score at 0.0,
    even if the behavioral score is high."""
    # Scenario A: Structural failure (memory corrupted), but high behavioral score
    structural_fail = StructuralResult(
        workflow_status_match=True,
        no_unhandled_exceptions=True,
        memory_invariant=False,  # Memory failure!
        security_gate_respected=True,
        failure_reasons=["Memory updated on failed workflow"]
    )
    assert structural_fail.passed is False

    high_behavioral = BehavioralScores(
        plan_optimality=1.0,
        evidence_grounding=0.95,
        policy_compliance=1.0,
        semantic_coherence=0.90,
        raw_composite_score=0.9625
    )

    res_fail = TaskEvaluationResult(
        task_id="TASK-TEST-FAIL",
        name="Memory Corruption Test",
        category=TaskCategory.STATE_ISOLATION,
        structural=structural_fail,
        behavioral=high_behavioral
    )
    # The validator MUST force final_score to 0.0!
    assert res_fail.final_score == 0.0

    # Scenario B: Structural passed, final score inherits raw_composite_score
    structural_pass = StructuralResult(
        workflow_status_match=True,
        no_unhandled_exceptions=True,
        memory_invariant=True,
        security_gate_respected=True
    )
    assert structural_pass.passed is True

    res_pass = TaskEvaluationResult(
        task_id="TASK-TEST-PASS",
        name="Valid Workflow Test",
        category=TaskCategory.COORDINATION_PLANNING,
        structural=structural_pass,
        behavioral=high_behavioral
    )
    assert res_pass.final_score == pytest.approx(0.9625, 1e-4)


def test_schema_serialization_and_deserialization():
    """Verifies that all schemas round-trip cleanly through JSON."""
    task_def = TaskDefinition(
        task_id="TASK-01",
        name="Supplier Onboarding",
        category=TaskCategory.COORDINATION_PLANNING,
        description="Full multi-agent assessment",
        goal="Evaluate vendor Acme Corp",
        context={"entity": "Acme Corp"},
        expected_agents=["data-intelligence-agent-v1", "risk-analysis-agent-v1"],
        expected_status="completed"
    )
    json_str = task_def.model_dump_json()
    reloaded = TaskDefinition.model_validate_json(json_str)
    assert reloaded.task_id == "TASK-01"
    assert reloaded.category == TaskCategory.COORDINATION_PLANNING

    metrics = EvaluationMetrics(
        total_tasks=12,
        passed_tasks=12,
        failed_tasks=0,
        task_success_rate=1.0,
        agent_selection_f1=0.98,
        workflow_completion_rate=1.0,
        failure_recovery_rate=1.0,
        memory_integrity_violations=0,
        unauthorized_action_rate=0.0,
        mean_quality_score=0.95,
        p95_latency_ms=45.0,
        run_to_run_consistency=0.99
    )
    report = BenchmarkReport(
        evaluation_id="EVAL-20261105-001",
        timestamp="2026-11-05T01:00:00Z",
        mode=EvaluationMode.MOCK,
        config=EvaluationConfig(),
        metrics=metrics,
        task_results=[]
    )
    report_json = report.model_dump_json()
    reloaded_report = BenchmarkReport.model_validate_json(report_json)
    assert reloaded_report.evaluation_id == "EVAL-20261105-001"
    assert reloaded_report.metrics.task_success_rate == 1.0


# --- 3. Sandbox Storage Isolation & Production Data Protection Tests ---

def test_sandbox_storage_isolation_and_file_protection():
    """Requirement 2: Evaluation runs must use isolated temporary storage
    and leave production data files completely untouched."""
    from app.storage import store

    original_store_path = store.path
    root_data_file = Path(__file__).resolve().parent.parent.parent / ".data" / "agentsphere.json"
    root_data_before = root_data_file.read_text(encoding="utf-8") if root_data_file.exists() else None

    cfg = EvaluationConfig(mode=EvaluationMode.MOCK)
    with EvaluationSandbox(cfg) as sandbox:
        # Confirm store path is redirected to a temporary location
        assert store.path != original_store_path
        assert sandbox.sandbox_file == store.path
        assert "agentsphere_eval_" in str(store.path)

        # Write test data into the sandbox store
        store.upsert("test_eval_collection", "item_123", {"value": "sandbox_isolated"})

        # Verify sandbox helper reads the test item
        data = sandbox.read_store()
        assert "test_eval_collection" in data
        assert data["test_eval_collection"]["item_123"]["value"] == "sandbox_isolated"

    # After exit: confirm store path is restored
    assert store.path == original_store_path

    # Confirm production data file was 100% unaltered
    if root_data_before is not None:
        root_data_after = root_data_file.read_text(encoding="utf-8")
        assert root_data_before == root_data_after

    # Confirm sandbox test collection does not exist in production store
    assert store.get("test_eval_collection", "item_123") is None


# --- 4. Compatibility with Existing Registry & Workflow Engine ---

@pytest.mark.asyncio
async def test_sandbox_compatibility_with_registry_and_workflow_engine():
    """Requirement 5: Sandbox must integrate seamlessly with AgentRegistry and WorkflowEngine
    without modifying production code."""
    from app.registry.agent_registry import registry
    from app.runtime.workflow_engine import WorkflowEngine
    from app.config import settings

    with EvaluationSandbox(EvaluationConfig(mode=EvaluationMode.MOCK)) as sandbox:
        assert settings.gemini_mock_mode is True

        # Check default agents are seeded into the isolated sandbox
        agents = registry.list()
        assert len(agents) >= 4
        agent_ids = [a["agent_id"] for a in agents]
        assert "data-intelligence-agent-v1" in agent_ids
        assert "report-generation-agent-v1" in agent_ids

        # Test dynamic registry modification inside the sandbox
        registry.set_enabled("data-intelligence-agent-v1", False)
        updated = registry.get("data-intelligence-agent-v1")
        assert updated["enabled"] is False

        # Run a simulated workflow inside the sandbox
        engine = WorkflowEngine()
        workflow = engine.create(
            goal="Evaluate vendor Sandbox Test Corp",
            requested_by="eval_runner",
            context={"entity": "Sandbox Test Corp"}
        )
        await engine.run(workflow)

        # Verify workflow executed and recorded within the sandbox
        wf_record = sandbox.get_workflows()
        assert len(wf_record) >= 1
        assert wf_record[0]["status"] in ("completed", "running")

        # Verify tasks recorded in sandbox
        sandbox_tasks = sandbox.get_tasks()
        assert len(sandbox_tasks) > 0

        # Verify audit logs captured in sandbox
        sandbox_audit = sandbox.get_audit_logs()
        assert len(sandbox_audit) > 0


# --- 5. Reproducibility & Seeding Tests ---

def test_sandbox_reproducibility_and_seeding():
    """Verifies that seed configuration produces deterministic random states."""
    config_1 = EvaluationConfig(seed=12345)
    with EvaluationSandbox(config_1):
        sample_1 = [random.randint(0, 1000) for _ in range(5)]

    config_2 = EvaluationConfig(seed=12345)
    with EvaluationSandbox(config_2):
        sample_2 = [random.randint(0, 1000) for _ in range(5)]

    # Exactly identical sequences
    assert sample_1 == sample_2

