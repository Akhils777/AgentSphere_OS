"""Unit tests for Stage 2.2: Benchmark Task Suite & Deterministic Fixtures.
Verifies loading of all 12 tasks, Pydantic schema validation, deterministic seeding,
parameterization, independent expected behaviors, adversarial representation,
and storage isolation.
"""

import copy
import hashlib
import json
import pytest
from pathlib import Path

from evaluation.schema import TaskCategory, TaskDefinition
from evaluation.tasks import (
    TASK_BUILDERS,
    get_all_tasks,
    get_task,
    get_tasks_by_category,
    get_tasks_by_tag,
    list_task_metadata,
)
from evaluation.fixtures import (
    FixtureGenerator,
    load_fault_scenarios,
    load_grounding_evidence,
    load_incomplete_inputs,
    load_multiturn_scenarios,
    load_security_inputs,
    load_suppliers,
    load_transactions,
    load_unauthorized_scenarios,
)


# --- 1. Task Loading & Discovery Tests ---

def test_all_12_benchmark_tasks_load_successfully():
    """Requirement 1: All 12 benchmark task definitions must load successfully."""
    assert len(TASK_BUILDERS) == 12
    tasks = get_all_tasks()
    assert len(tasks) == 12

    expected_ids = [f"TASK-{i:02d}" for i in range(1, 13)]
    actual_ids = [t.task_id for t in tasks]
    assert actual_ids == expected_ids

    # Verify individual get_task resolution
    for task_id in expected_ids:
        t = get_task(task_id)
        assert t.task_id == task_id
        assert len(t.name) > 0
        assert len(t.goal) > 0


def test_every_task_passes_schema_validation():
    """Requirement 2: Every task must strictly pass Stage 2.1 Pydantic schema validation."""
    tasks = get_all_tasks()
    for t in tasks:
        # Pydantic serialization round-trip
        json_data = t.model_dump_json()
        reloaded = TaskDefinition.model_validate_json(json_data)
        assert reloaded.task_id == t.task_id
        assert reloaded.name == t.name
        assert isinstance(reloaded.category, TaskCategory)
        assert isinstance(reloaded.context, dict)
        assert isinstance(reloaded.acceptance_criteria, dict)
        assert len(reloaded.acceptance_criteria) > 0


def test_task_filtering_by_category_and_tags():
    """Verifies that task filtering by category and tags works accurately."""
    coordination_tasks = get_tasks_by_category(TaskCategory.COORDINATION_PLANNING)
    assert len(coordination_tasks) >= 1
    assert any(t.task_id == "TASK-01" for t in coordination_tasks)

    security_tasks = get_tasks_by_tag("security")
    assert len(security_tasks) >= 3
    security_ids = [t.task_id for t in security_tasks]
    assert "TASK-05" in security_ids
    assert "TASK-06" in security_ids
    assert "TASK-07" in security_ids

    metadata = list_task_metadata()
    assert len(metadata) == 12
    assert all("task_id" in m and "category" in m for m in metadata)


# --- 2. Deterministic Fixture & Seeding Tests ---

def test_fixtures_produce_deterministic_results_with_same_seed():
    """Requirement 3: Fixture generator must produce identical outputs given identical seeds."""
    gen_a = FixtureGenerator(seed=1337)
    gen_b = FixtureGenerator(seed=1337)

    vendor_a = gen_a.generate_vendor("clean_vendor", noise_factor=0.15)
    vendor_b = gen_b.generate_vendor("clean_vendor", noise_factor=0.15)
    assert vendor_a == vendor_b

    txns_a = gen_a.generate_transactions(include_anomalies=True, volume=5, noise_factor=0.2)
    txns_b = gen_b.generate_transactions(include_anomalies=True, volume=5, noise_factor=0.2)
    assert txns_a == txns_b


def test_different_parameters_produce_meaningfully_different_scenarios():
    """Requirement 4: Different parameters or seeds must produce meaningfully distinct scenarios."""
    gen = FixtureGenerator(seed=42)

    # Clean vs Anomalous vendor
    clean = gen.generate_vendor("clean_vendor")
    anomalous = gen.generate_vendor("anomalous_vendor", inject_anomalies=["negative_revenue", "missing_tax_id"])
    assert clean["annual_revenue_usd"] > 0
    assert anomalous["annual_revenue_usd"] < 0
    assert "missing_tax_id" in anomalous["data_quality_flags"]
    assert clean["sanctions_check"] == "passed"
    assert anomalous["sanctions_check"] == "warning"

    # Seed sensitivity on numerical noise
    gen_1 = FixtureGenerator(seed=101)
    gen_2 = FixtureGenerator(seed=999)
    v1 = gen_1.generate_vendor("clean_vendor", noise_factor=0.25)
    v2 = gen_2.generate_vendor("clean_vendor", noise_factor=0.25)
    assert v1["annual_revenue_usd"] != v2["annual_revenue_usd"]
    assert v1["employee_count"] != v2["employee_count"]


def test_static_fixture_loaders():
    """Verifies all static JSON fixture files load and have valid content."""
    suppliers = load_suppliers()
    assert "clean_vendor" in suppliers
    assert "anomalous_vendor" in suppliers
    assert "grounded_vendor" in suppliers
    assert "esg_vendor" in suppliers

    txns = load_transactions()
    assert len(txns["normal_transactions"]) >= 3
    assert len(txns["anomalous_transactions"]) >= 3

    sec = load_security_inputs()
    assert len(sec["prompt_injections"]) >= 3
    assert len(sec["pii_payloads"]) >= 2

    unauth = load_unauthorized_scenarios()
    assert len(unauth["unauthorized_access_scenarios"]) >= 3

    incomp = load_incomplete_inputs()
    assert len(incomp["incomplete_inputs"]) >= 3

    faults = load_fault_scenarios()
    assert len(faults["fault_scenarios"]) >= 3

    multiturn = load_multiturn_scenarios()
    assert len(multiturn["multiturn_scenarios"]) >= 1

    grounding = load_grounding_evidence()
    assert "ground_truth_facts" in grounding["grounding_evidence"]
    assert "hallucinated_distractors" in grounding["grounding_evidence"]


# --- 3. Independent Expected Behaviors & Adversarial Tests ---

def test_expected_behaviors_independent_of_mock_provider():
    """Requirement 5: Expected behaviors must be independently formulated from mock outputs.
    E.g. TASK-04 expects high risk / rejection, whereas the static mock outputs low risk / approved."""
    task_04 = get_task("TASK-04")
    # Criteria demands High Risk and forbids Approved recommendation
    assert task_04.acceptance_criteria["expected_risk_category"] == "High Risk"
    assert "Approved" in task_04.acceptance_criteria["forbidden_recommendations"]

    # TASK-08 expects failure and memory invariance
    task_08 = get_task("TASK-08")
    assert task_08.expected_status == "failed"
    assert task_08.should_update_memory is False
    assert task_08.acceptance_criteria["memory_invariant"] is True

    # TASK-09 expects missing entity to NOT update supplier_ABC
    task_09 = get_task("TASK-09")
    assert task_09.target_entity is None
    assert task_09.should_update_memory is False
    assert task_09.acceptance_criteria["no_supplier_abc_pollution"] is True

    # TASK-12 defines explicit forbidden hallucinated claims
    task_12 = get_task("TASK-12")
    assert "forbidden_hallucinated_claims" in task_12.acceptance_criteria
    assert len(task_12.acceptance_criteria["forbidden_hallucinated_claims"]) >= 3


def test_adversarial_and_negative_test_cases_represented():
    """Requirement 6: Adversarial prompt injection, PII leakage, and unauthorized access
    must be represented as negative test cases."""
    # TASK-05: Prompt injection
    task_05 = get_task("TASK-05")
    assert task_05.expected_status == "failed"
    assert task_05.expected_security_reason == "prompt_injection"
    assert task_05.expected_agents == []  # Must NOT schedule agents
    assert len(task_05.forbidden_agents) >= 4

    # TASK-06: PII protection
    task_06 = get_task("TASK-06")
    assert task_06.expected_status == "failed"
    assert task_06.expected_security_reason == "sensitive_data"
    assert task_06.should_update_memory is False

    # TASK-07: Unauthorized action
    task_07 = get_task("TASK-07")
    assert task_07.expected_status == "failed"
    assert task_07.acceptance_criteria["expected_http_status"] == 403


# --- 4. Production Storage Invariance Test ---

def test_no_production_storage_files_modified():
    """Requirement 7: Task definition loading and fixture generation must never
    alter production storage files."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    root_data = repo_root / ".data" / "agentsphere.json"
    backend_data = repo_root / "backend" / ".data" / "agentsphere.json"

    def get_hash(p: Path) -> str | None:
        return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None

    root_hash_before = get_hash(root_data)
    backend_hash_before = get_hash(backend_data)

    # Instantiate all tasks and fixtures multiple times with varied seeds
    for s in [1, 42, 999]:
        _ = get_all_tasks(seed=s)
        gen = FixtureGenerator(seed=s)
        _ = gen.generate_vendor("clean_vendor", noise_factor=0.2)
        _ = gen.generate_vendor("anomalous_vendor", inject_anomalies=["negative_revenue"])
        _ = gen.generate_transactions(include_anomalies=True, volume=10)

    # Check hashes remain identical
    assert get_hash(root_data) == root_hash_before
    assert get_hash(backend_data) == backend_hash_before

