"""Unit and integration tests for Stage 2.4: Evaluation Runner, Metrics Engine,
Reporting Engine, CLI validation, and Reproducibility.
"""

import json
import pytest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from evaluation.config import EvaluationConfig, EvaluationMode
from evaluation.runner import (
    BenchmarkRunner,
    MetricsCalculator,
    ReportGenerator,
    parse_args,
)
from evaluation.schema import (
    ExecutionTrace,
    StructuralResult,
    TaskCategory,
    TaskDefinition,
    TaskEvaluationResult,
)
from evaluation.tasks import get_task


# --- 1. Runner & Task Selection Tests ---

@pytest.mark.asyncio
async def test_runner_individual_task_selection():
    """Requirement 1: Verify runner executes selected individual tasks by ID."""
    config = EvaluationConfig(runs_per_task=1, seed=42)
    runner = BenchmarkRunner(config)

    report, task_runs = await runner.run_all(task_ids=["TASK-01"])
    assert report.metrics.total_tasks == 1
    assert "TASK-01" in task_runs
    assert len(task_runs["TASK-01"]) == 1
    assert task_runs["TASK-01"][0].task_id == "TASK-01"
    assert task_runs["TASK-01"][0].structural.passed is True


@pytest.mark.asyncio
async def test_runner_repeated_runs_execution():
    """Requirement 1 & 5: Verify repeated runs per task produce consistent results."""
    config = EvaluationConfig(runs_per_task=3, seed=100)
    runner = BenchmarkRunner(config)

    report, task_runs = await runner.run_all(task_ids=["TASK-02"])
    assert len(task_runs["TASK-02"]) == 3
    scores = [r.final_score for r in task_runs["TASK-02"]]
    # All runs for deterministic mock should be identical
    assert scores[0] == scores[1] == scores[2]
    assert report.metrics.run_to_run_consistency == 1.0


# --- 2. Metrics Engine Tests ---

def test_metrics_calculator_accuracy():
    """Requirement 2: Verify mathematical accuracy of MetricsCalculator."""
    task_def_pass = get_task("TASK-01")
    task_def_fail = get_task("TASK-08")

    # Synthetic run 1: passed
    res_pass = TaskEvaluationResult(
        task_id="TASK-01",
        name="Nominal",
        category=TaskCategory.COORDINATION_PLANNING,
        structural=StructuralResult(passed=True),
        behavioral={"plan_optimality": 1.0, "raw_composite_score": 0.95, "dimension_details": {"plan": {"f1": 1.0}}},
        execution_time_ms=100.0,
        trace=ExecutionTrace(task_id="TASK-01", goal="Test", status="completed"),
    )

    # Synthetic run 2: failed
    res_fail = TaskEvaluationResult(
        task_id="TASK-08",
        name="Failure",
        category=TaskCategory.STATE_ISOLATION,
        structural=StructuralResult(passed=False, memory_invariant=False, failure_reasons=["Memory mutated"]),
        behavioral={"raw_composite_score": 0.5},
        execution_time_ms=50.0,
        trace=ExecutionTrace(task_id="TASK-08", goal="Test", status="failed"),
    )

    task_runs = {
        "TASK-01": [res_pass],
        "TASK-08": [res_fail],
    }
    tasks_map = {
        "TASK-01": task_def_pass,
        "TASK-08": task_def_fail,
    }

    metrics = MetricsCalculator.calculate(task_runs, tasks_map)
    assert metrics.total_tasks == 2
    assert metrics.passed_tasks == 1
    assert metrics.failed_tasks == 1
    assert metrics.task_success_rate == 0.5
    assert metrics.memory_integrity_violations == 1
    assert metrics.p95_latency_ms == 100.0


# --- 3. Reporting Engine Tests ---

@pytest.mark.asyncio
async def test_json_and_markdown_report_generation(tmp_path: Path):
    """Requirement 3: Verify JSON and Markdown reports are generated accurately."""
    config = EvaluationConfig(runs_per_task=1, seed=42)
    runner = BenchmarkRunner(config)
    report, task_runs = await runner.run_all(task_ids=["TASK-05"])

    json_out = tmp_path / "test_report.json"
    md_out = tmp_path / "test_report.md"

    ReportGenerator.generate_json_report(report, task_runs, json_out)
    ReportGenerator.generate_markdown_report(report, task_runs, md_out)

    assert json_out.exists()
    assert md_out.exists()

    # Validate JSON content
    data = json.loads(json_out.read_text(encoding="utf-8"))
    assert data["evaluation_id"] == report.evaluation_id
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["task_id"] == "TASK-05"

    # Validate Markdown content
    md_text = md_out.read_text(encoding="utf-8")
    assert "AgentSphere_OS — Benchmark Evaluation Report" in md_text
    assert "TASK-05" in md_text
    assert "Executive Performance vs Proposed Targets" in md_text


# --- 4. CLI Argument Validation Tests ---

def test_cli_argument_validation():
    """Requirement 4: Verify CLI arguments parse and validate correctly."""
    # Valid arguments
    with patch("sys.argv", ["runner.py", "--task", "TASK-04", "--runs", "2", "--seed", "99"]):
        args = parse_args()
        assert args.task == "TASK-04"
        assert args.runs == 2
        assert args.seed == 99

    # Defaults
    with patch("sys.argv", ["runner.py"]):
        args = parse_args()
        assert args.runs == 3
        assert args.mode == "deterministic_mock"
        assert args.all is False


# --- 5. Storage Isolation & Reproducibility ---

@pytest.mark.asyncio
async def test_runner_storage_isolation():
    """Requirement 5: Verify runner execution leaves production files untouched."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    root_data = repo_root / ".data" / "agentsphere.json"
    content_before = root_data.read_text(encoding="utf-8") if root_data.exists() else None

    config = EvaluationConfig(runs_per_task=1, seed=42)
    runner = BenchmarkRunner(config)
    await runner.run_all(task_ids=["TASK-01", "TASK-09"])

    if content_before is not None:
        content_after = root_data.read_text(encoding="utf-8")
        assert content_before == content_after

