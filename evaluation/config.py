"""Evaluation framework configuration and execution modes.
Guarantees deterministic mock evaluation as the safe, offline default.
"""

from enum import Enum
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field, model_validator


class EvaluationMode(str, Enum):
    """Execution targets for the evaluation framework."""
    MOCK = "deterministic_mock"  # Offline, deterministic, zero-cost (DEFAULT)
    LIVE = "live_model"          # Live Gemini / Vertex AI execution (opt-in only)


class EvaluationConfig(BaseModel):
    """Configuration governing benchmark execution and evaluation rigor."""

    mode: EvaluationMode = Field(
        default=EvaluationMode.MOCK,
        description="Evaluation execution target. Strictly defaults to deterministic mock mode."
    )
    model_name: str = Field(
        default="mock-gemini-flash",
        description="Model identifier under evaluation. Defaults to mock-gemini-flash."
    )
    seed: int = Field(
        default=42,
        ge=0,
        description="Random seed for deterministic reproducibility."
    )
    runs_per_task: int = Field(
        default=3,
        ge=1,
        le=20,
        description="Number of repeated runs per task to calculate consistency metrics."
    )
    timeout_seconds: float = Field(
        default=30.0,
        gt=0.0,
        le=300.0,
        description="Maximum execution timeout allowed per task attempt."
    )
    isolate_storage: bool = Field(
        default=True,
        description="Whether to execute within an isolated temporary storage sandbox."
    )
    scoring_weights: dict[str, float] = Field(
        default_factory=lambda: {
            "plan": 0.25,
            "grounding": 0.25,
            "policy": 0.25,
            "semantic": 0.25,
        },
        description="Weights for Tier 2 composite quality rubric. Must sum to 1.0."
    )
    metric_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "task_success_rate": 0.90,
            "agent_selection_f1": 0.95,
            "workflow_completion_rate": 1.00,
            "failure_recovery_rate": 0.85,
            "memory_integrity_violations": 0.0,
            "unauthorized_action_rate": 0.0,
            "evidence_grounding_score": 0.90,
            "run_to_run_consistency": 0.98,
        },
        description="Minimum benchmark thresholds for passing evaluation suites."
    )

    @model_validator(mode="after")
    def validate_configuration(self) -> "EvaluationConfig":
        # Validate weights sum to 1.0 (with float tolerance)
        total_weight = sum(self.scoring_weights.values())
        if abs(total_weight - 1.0) > 1e-4:
            raise ValueError(f"Scoring weights must sum to 1.0; got {total_weight:.4f}")

        # Ensure mock mode has appropriate model name
        if self.mode == EvaluationMode.MOCK and not self.model_name.startswith("mock-"):
            # Normalize to mock prefix if not explicitly overridden
            self.model_name = f"mock-{self.model_name}"

        return self

