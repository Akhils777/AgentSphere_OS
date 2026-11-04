"""AgentSphere_OS Evaluation Framework & Benchmark Task Suite (Phase 2).
Provides hermetic, reproducible, multi-dimensional evaluation for autonomous agents.
"""

import sys
from pathlib import Path

# Ensure backend directory is in sys.path for importing app modules
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from .config import EvaluationConfig, EvaluationMode
from .schema import (
    BenchmarkReport,
    BehavioralScores,
    EvaluationMetrics,
    ExecutionTrace,
    StructuralResult,
    TaskCategory,
    TaskDefinition,
    TaskEvaluationResult,
)
from .harness.sandbox import EvaluationSandbox
from .tasks.catalog import get_all_tasks, get_task
from .fixtures.generator import FixtureGenerator

__all__ = [
    "EvaluationConfig",
    "EvaluationMode",
    "EvaluationSandbox",
    "FixtureGenerator",
    "BenchmarkReport",
    "BehavioralScores",
    "EvaluationMetrics",
    "ExecutionTrace",
    "StructuralResult",
    "TaskCategory",
    "TaskDefinition",
    "TaskEvaluationResult",
    "get_all_tasks",
    "get_task",
]

