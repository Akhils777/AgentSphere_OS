"""Composite Evaluator Grader.
Coordinates Structural, Plan, Policy, and Semantic graders to produce
a comprehensive TaskEvaluationResult with strict Tier 1 gate enforcement.
"""

from typing import Any
from ..config import EvaluationConfig
from ..schema import (
    BehavioralScores,
    ExecutionTrace,
    TaskDefinition,
    TaskEvaluationResult,
)
from .structural_grader import StructuralGrader
from .plan_grader import PlanGrader
from .policy_grader import PolicyGrader
from .semantic_grader import SemanticGrader


class CompositeGrader:
    """Master evaluator coordinating all four independent grading engines."""

    def __init__(self, config: EvaluationConfig | None = None):
        self.config = config or EvaluationConfig()
        self.structural_grader = StructuralGrader()
        self.plan_grader = PlanGrader()
        self.policy_grader = PolicyGrader()
        self.semantic_grader = SemanticGrader()

    def grade(
        self,
        task: TaskDefinition,
        trace: ExecutionTrace,
        context: dict[str, Any] | None = None
    ) -> TaskEvaluationResult:
        context = context or {}

        # 1. Structural Grade (Tier 1 Gate)
        structural_result = self.structural_grader.grade(task, trace, context)

        # 2. Plan Grade (Tier 2)
        plan_score, plan_details = self.plan_grader.grade(task, trace)

        # 3. Policy Grade (Tier 2)
        policy_score, policy_details = self.policy_grader.grade(task, trace)

        # 4. Semantic Grade (Tier 2)
        semantic_score, grounding_score, semantic_details = self.semantic_grader.grade(task, trace)

        # 5. Composite Tier 2 Weighting
        weights = self.config.scoring_weights
        raw_composite = (
            weights.get("plan", 0.25) * plan_score
            + weights.get("grounding", 0.25) * grounding_score
            + weights.get("policy", 0.25) * policy_score
            + weights.get("semantic", 0.25) * semantic_score
        )

        behavioral_scores = BehavioralScores(
            plan_optimality=plan_score,
            evidence_grounding=grounding_score,
            policy_compliance=policy_score,
            semantic_coherence=semantic_score,
            raw_composite_score=round(raw_composite, 4),
            dimension_details={
                "plan": plan_details,
                "policy": policy_details,
                "semantic": semantic_details,
            },
        )

        # 6. Task Evaluation Result (Applies structural override automatically)
        return TaskEvaluationResult(
            task_id=task.task_id,
            name=task.name,
            category=task.category,
            structural=structural_result,
            behavioral=behavioral_scores,
            execution_time_ms=trace.execution_time_ms,
            trace=trace,
        )

