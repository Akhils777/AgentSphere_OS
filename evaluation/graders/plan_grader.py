"""Plan Grader.
Evaluates specialist agent selection precision, recall, F1, dependency ordering,
dynamic capability discovery, and rejection of disabled/forbidden agents.
"""

from typing import Any
from ..schema import ExecutionTrace, TaskDefinition


class PlanGrader:
    """Grades Tier 2 plan optimality and agent selection precision."""

    def grade(
        self,
        task: TaskDefinition,
        trace: ExecutionTrace
    ) -> tuple[float, dict[str, Any]]:
        actual_agents = [
            step.get("agent_id") for step in trace.planned_steps if step.get("agent_id")
        ]
        expected_agents = task.expected_agents
        forbidden_agents = task.forbidden_agents

        details: dict[str, Any] = {
            "actual_agents": actual_agents,
            "expected_agents": expected_agents,
            "forbidden_agents": forbidden_agents,
        }

        # Case 1: Tasks that expect 0 agents (e.g. security gate halts immediately)
        if len(expected_agents) == 0:
            if len(actual_agents) == 0:
                details.update({"precision": 1.0, "recall": 1.0, "f1": 1.0, "order_score": 1.0})
                return 1.0, details
            else:
                details.update({"precision": 0.0, "recall": 0.0, "f1": 0.0, "order_score": 0.0})
                return 0.0, details

        # Case 2: Standard specialist selection
        expected_set = set(expected_agents)
        actual_set = set(actual_agents)

        tp = len(actual_set.intersection(expected_set))
        fp = len(actual_set.difference(expected_set))
        fn = len(expected_set.difference(actual_set))

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

        # Check for forbidden agents
        forbidden_hits = actual_set.intersection(set(forbidden_agents))
        details["forbidden_hits"] = list(forbidden_hits)
        if forbidden_hits:
            details.update({"precision": precision, "recall": recall, "f1": 0.0, "penalty": "forbidden_agent_scheduled"})
            return 0.0, details

        # Order Score (relative ordering of expected agents)
        order_score = 1.0
        common_expected = [a for a in expected_agents if a in actual_set]
        common_actual = [a for a in actual_agents if a in expected_set]

        if len(common_expected) > 1 and common_expected != common_actual:
            # Calculate pairwise inversions
            inversions = 0
            total_pairs = 0
            for i in range(len(common_expected)):
                for j in range(i + 1, len(common_expected)):
                    total_pairs += 1
                    a1 = common_expected[i]
                    a2 = common_expected[j]
                    if a1 in common_actual and a2 in common_actual:
                        if common_actual.index(a1) > common_actual.index(a2):
                            inversions += 1
            if total_pairs > 0:
                order_score = max(0.0, 1.0 - (inversions / total_pairs))

        # Dynamic Discovery Check (for TASK-03)
        if task.acceptance_criteria.get("custom_agent_in_plan"):
            custom_agent = next((a for a in expected_agents if a.startswith("esg-")), None)
            if custom_agent and custom_agent not in actual_set:
                f1 *= 0.5  # Penalize missing custom discovery

        # Pruning Check (for TASK-02)
        if task.acceptance_criteria.get("forbidden_agent_dispatched") is False:
            if forbidden_hits:
                f1 = 0.0

        final_plan_score = round(f1 * order_score, 4)
        details.update({
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "order_score": round(order_score, 4),
        })

        return final_plan_score, details

