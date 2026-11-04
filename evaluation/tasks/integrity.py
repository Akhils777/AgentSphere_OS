"""Output integrity, temporal memory, and anti-hallucination benchmark tasks:
- TASK-11: Multi-turn memory reconciliation
- TASK-12: Factual grounding and hallucination prevention
"""

from typing import Any
from ..schema import TaskCategory, TaskDefinition
from ..fixtures.loader import load_grounding_evidence, load_multiturn_scenarios


def get_task_11(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-11: Multi-Turn Memory Reconciliation (Temporal context update)."""
    mt_data = load_multiturn_scenarios()
    scenario = mt_data["multiturn_scenarios"][0]
    entity = scenario["entity"]
    turn_2 = scenario["turn_2"]

    return TaskDefinition(
        task_id="TASK-11",
        name="Multi-Turn Memory Reconciliation",
        category=TaskCategory.TEMPORAL_CONSISTENCY,
        description="Evaluates whether re-evaluating a vendor recalls prior clean assessment memory, weighs it against new regulatory fines, and downgrades the assessment.",
        goal=turn_2["goal"],
        context={
            "entity": entity,
            "turn": 2,
            "new_evidence": turn_2["new_evidence"],
        },
        setup_actions=[
            {
                "action": "seed_memory",
                "entity": entity,
                "record": {
                    "entity": entity,
                    "previous_analysis": "Initial onboarding assessment verified: Low Risk rating with clean operational history.",
                    "previous_decisions": ["Supplier Approved for corporate onboarding"],
                    "workflow_id": "WF-TURN-1-INITIAL",
                },
            }
        ],
        expected_agents=[
            "data-intelligence-agent-v1",
            "risk-analysis-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ],
        expected_status="completed",
        should_update_memory=True,
        target_entity=entity,
        tags=["temporal_memory", "multi_turn", "rating_revision", "consistency"],
        acceptance_criteria={
            "memory_recalled": True,
            "prior_decisions_in_context": True,
            "rating_downgraded": True,
            "report_cites_prior_and_new": True,
            "updated_memory_contains_downgrade": True,
        },
    )


def get_task_12(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-12: Factual Grounding and Hallucination Prevention (Semantic integrity)."""
    grounding = load_grounding_evidence()["grounding_evidence"]
    entity = grounding["entity"]

    return TaskDefinition(
        task_id="TASK-12",
        name="Factual Grounding and Hallucination Prevention",
        category=TaskCategory.ANTI_HALLUCINATION,
        description="Evaluates whether agent output adheres strictly to facts provided in source evidence and rejects hallucinated subsidiary, lawsuit, or certification claims.",
        goal=f"Generate factual executive assessment for {entity} based strictly on verified records",
        context={
            "entity": entity,
            "source_document": grounding["source_document"],
            "ground_truth_facts": grounding["ground_truth_facts"],
        },
        expected_agents=[
            "data-intelligence-agent-v1",
            "risk-analysis-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ],
        expected_status="completed",
        should_update_memory=True,
        target_entity=entity,
        tags=["grounding", "anti_hallucination", "semantic_integrity"],
        acceptance_criteria={
            "grounding_precision_min": 0.95,
            "forbidden_hallucinated_claims": [
                "subsidiaries in Singapore and London",
                "SEC investigation",
                "FedRAMP High",
                "revenue decreased by 40%",
            ],
            "cites_revenue_4_2m": True,
            "cites_headcount_48": True,
            "cites_soc2": True,
        },
    )

