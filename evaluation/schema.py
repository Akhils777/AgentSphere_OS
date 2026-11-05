"""Pydantic schemas for the evaluation framework.
Defines task definitions, execution traces, structural results, behavioral scores,
and evaluation metrics with strict structural-failure score overrides.
"""

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator
from .config import EvaluationConfig, EvaluationMode


class TaskCategory(str, Enum):
    """Functional benchmark categories for agent capability assessment."""
    COORDINATION_PLANNING = "coordination_planning"
    DYNAMIC_PRUNING = "dynamic_pruning"
    EXTENSIBILITY = "extensibility"
    EVIDENCE_GROUNDING = "evidence_grounding"
    INPUT_SECURITY = "input_security"
    DATA_GOVERNANCE = "data_governance"
    POLICY_GOVERNANCE = "policy_governance"
    STATE_ISOLATION = "state_isolation"
    BOUNDARY_HANDLING = "boundary_handling"
    FAULT_RESILIENCE = "fault_resilience"
    TEMPORAL_CONSISTENCY = "temporal_consistency"
    ANTI_HALLUCINATION = "anti_hallucination"


class TaskDefinition(BaseModel):
    """Declarative specification of an evaluation benchmark task."""
    task_id: str = Field(description="Unique task identifier, e.g. TASK-01")
    name: str = Field(description="Human-readable task title")
    category: TaskCategory = Field(description="Task capability domain")
    description: str = Field(description="Detailed description of task intent and expectations")
    goal: str = Field(description="Prompt or workflow goal provided to the agent/supervisor")
    context: dict[str, Any] = Field(default_factory=dict, description="Initial context payload (entity, records, etc.)")
    expected_agents: list[str] = Field(default_factory=list, description="Ordered list of agent IDs expected in optimal plan")
    forbidden_agents: list[str] = Field(default_factory=list, description="Agent IDs that must NOT be scheduled or executed")
    expected_status: str = Field(default="completed", description="Expected final workflow status (completed, failed, blocked)")
    expected_security_reason: str | None = Field(default=None, description="Security filter reason if workflow should be blocked")
    should_update_memory: bool = Field(default=True, description="Whether entity memory should be updated on completion")
    target_entity: str | None = Field(default=None, description="Target entity expected in memory, if any")
    injected_fault: dict[str, Any] | None = Field(default=None, description="Fault injection spec (timeout, error_code, etc.)")
    tags: list[str] = Field(default_factory=list, description="Categorization tags for filtering benchmark subsets")
    setup_actions: list[dict[str, Any]] = Field(default_factory=list, description="Pre-task runtime setup steps (e.g. disable agent, seed memory)")
    acceptance_criteria: dict[str, Any] = Field(default_factory=dict, description="Measurable pass/fail criteria and evaluation bounds")


class ExecutionTrace(BaseModel):
    """Granular record of an agent workflow execution under evaluation."""
    task_id: str
    workflow_id: str | None = None
    goal: str
    status: str
    progress: int = 0
    planned_steps: list[dict[str, Any]] = Field(default_factory=list)
    dispatched_tasks: list[dict[str, Any]] = Field(default_factory=list)
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    security_events: list[dict[str, Any]] = Field(default_factory=list)
    memory_snapshot_before: dict[str, Any] | None = None
    memory_snapshot_after: dict[str, Any] | None = None
    captured_outputs: dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: float = 0.0
    error: str | None = None
    token_usage: dict[str, Any] | None = None
    cost_inr: float = 0.0
    cost_usd: float = 0.0
    model_name: str | None = None
    provider: str | None = None


class StructuralResult(BaseModel):
    """Tier 1 Gate: Hard operational and safety criteria.
    Any failure here caps the entire task score at zero."""
    passed: bool = Field(default=True, description="Overall Tier 1 gate status")
    workflow_status_match: bool = Field(default=True, description="Final workflow status matched expected_status")
    no_unhandled_exceptions: bool = Field(default=True, description="Workflow completed without unexpected Python exceptions")
    memory_invariant: bool = Field(default=True, description="Memory remained uncorrupted on failure or missing entity")
    security_gate_respected: bool = Field(default=True, description="No unauthorized actions or bypass of safety filters")
    failure_reasons: list[str] = Field(default_factory=list, description="Detailed list of Tier 1 violations, if any")

    @model_validator(mode="after")
    def compute_passed(self) -> "StructuralResult":
        # Any individual failure implies passed = False
        all_passed = (
            self.workflow_status_match
            and self.no_unhandled_exceptions
            and self.memory_invariant
            and self.security_gate_respected
            and len(self.failure_reasons) == 0
        )
        self.passed = all_passed
        return self


class BehavioralScores(BaseModel):
    """Tier 2 Rubric: Graduated multi-dimensional quality assessment (0.0 to 1.0)."""
    plan_optimality: float = Field(default=1.0, ge=0.0, le=1.0, description="Plan precision, recall, and ordering")
    evidence_grounding: float = Field(default=1.0, ge=0.0, le=1.0, description="Citations and evidence flow from context")
    policy_compliance: float = Field(default=1.0, ge=0.0, le=1.0, description="Respect for agent permissions and scopes")
    semantic_coherence: float = Field(default=1.0, ge=0.0, le=1.0, description="Alignment between findings and recommendation")
    raw_composite_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Weighted composite score before Tier 1 gate")
    dimension_details: dict[str, Any] = Field(default_factory=dict, description="Fine-grained metric breakdowns")


class TaskEvaluationResult(BaseModel):
    """Comprehensive evaluation result for an individual benchmark task."""
    task_id: str
    name: str
    category: TaskCategory
    structural: StructuralResult
    behavioral: BehavioralScores
    final_score: float = Field(default=0.0, ge=0.0, le=1.0, description="Final graded score (0.0 if structural failed)")
    execution_time_ms: float = 0.0
    trace: ExecutionTrace | None = None
    token_usage: dict[str, Any] | None = None
    cost_inr: float = 0.0
    cost_usd: float = 0.0
    model_name: str | None = None
    provider: str | None = None

    @model_validator(mode="after")
    def enforce_structural_override(self) -> "TaskEvaluationResult":
        """Strict Requirement 4: Structural failure overrides and caps the final score at 0.0."""
        if not self.structural.passed:
            self.final_score = 0.0
        else:
            self.final_score = self.behavioral.raw_composite_score
        return self


class EvaluationMetrics(BaseModel):
    """Aggregate benchmark metrics calculated across all evaluated tasks."""
    total_tasks: int = Field(ge=0)
    passed_tasks: int = Field(ge=0)
    failed_tasks: int = Field(ge=0)
    task_success_rate: float = Field(ge=0.0, le=1.0, description="Percentage of tasks passing both Tier 1 and quality bar")
    agent_selection_f1: float = Field(ge=0.0, le=1.0, description="Mean agent selection F1 across planning tasks")
    workflow_completion_rate: float = Field(ge=0.0, le=1.0, description="Completion rate for nominal workflows")
    failure_recovery_rate: float = Field(ge=0.0, le=1.0, description="Percentage of injected faults gracefully handled")
    memory_integrity_violations: int = Field(default=0, ge=0, description="Count of state corruption or leak events")
    unauthorized_action_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Rate of unpermitted action attempts")
    evidence_grounding_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Mean evidence grounding score across evaluated tasks")
    mean_quality_score: float = Field(ge=0.0, le=1.0, description="Average composite quality score across all tasks")
    mean_latency_ms: float = Field(default=0.0, ge=0.0, description="Mean task execution latency in milliseconds")
    median_latency_ms: float = Field(default=0.0, ge=0.0, description="Median (P50) task execution latency in milliseconds")
    p95_latency_ms: float = Field(ge=0.0, description="95th percentile task execution latency")
    run_to_run_consistency: float = Field(default=1.0, ge=0.0, le=1.0, description="Determinism metric across repeated runs")


class BenchmarkReport(BaseModel):
    """Machine-readable top-level benchmark evaluation report."""
    evaluation_id: str = Field(description="Unique evaluation identifier, e.g. EVAL-20261105-010532")
    timestamp: str = Field(description="ISO-8601 UTC execution timestamp")
    mode: EvaluationMode = Field(description="Execution mode (deterministic_mock or live_model)")
    config: EvaluationConfig = Field(description="Configuration settings active for this benchmark run")
    metrics: EvaluationMetrics = Field(description="Summary metrics across the benchmark suite")
    task_results: list[TaskEvaluationResult] = Field(default_factory=list, description="Per-task evaluation outcomes")
    total_tokens: int | None = None
    cost_inr: float = 0.0
    cost_usd: float = 0.0
    provider: str = "mock_provider"

