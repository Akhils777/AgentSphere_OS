"""Coordination and planning benchmark task definitions:
- TASK-01: Baseline supplier onboarding
- TASK-02: Disabled specialist detection and pruning
- TASK-03: Dynamic custom specialist discovery
- TASK-04: Anomaly propagation between agents
"""

from typing import Any
from ..schema import TaskCategory, TaskDefinition
from ..fixtures.loader import load_suppliers, load_transactions
from ..fixtures.generator import FixtureGenerator


def get_task_01(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-01: Baseline Supplier Onboarding (Nominal multi-agent coordination)."""
    gen = FixtureGenerator(seed=seed)
    vendor = gen.generate_vendor("clean_vendor", entity_name="Acme Logistics Inc", **kwargs)
    txns = gen.generate_transactions(include_anomalies=False, volume=3)

    return TaskDefinition(
        task_id="TASK-01",
        name="Baseline Supplier Onboarding",
        category=TaskCategory.COORDINATION_PLANNING,
        description="Evaluates standard 4-agent sequential orchestration, valid DAG synthesis, and entity memory recording under clean conditions.",
        goal=f"Perform complete onboarding risk and compliance evaluation for vendor {vendor['entity']}",
        context={
            "entity": vendor["entity"],
            "vendor_records": vendor,
            "recent_transactions": txns,
        },
        expected_agents=[
            "data-intelligence-agent-v1",
            "risk-analysis-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ],
        forbidden_agents=[],
        expected_status="completed",
        should_update_memory=True,
        target_entity=vendor["entity"],
        tags=["nominal", "coordination", "planning"],
        acceptance_criteria={
            "agent_selection_f1_min": 1.0,
            "plan_ordering_strict": True,
            "expected_risk_category": "Low Risk",
            "expected_recommendation": "Approved",
            "memory_must_exist": True,
            "max_unhandled_exceptions": 0,
        },
    )


def get_task_02(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-02: Disabled Specialist Detection and Pruning (Dynamic re-planning)."""
    gen = FixtureGenerator(seed=seed)
    vendor = gen.generate_vendor("clean_vendor", entity_name="Acme Logistics Inc", **kwargs)

    return TaskDefinition(
        task_id="TASK-02",
        name="Disabled Specialist Detection and Pruning",
        category=TaskCategory.DYNAMIC_PRUNING,
        description="Evaluates whether supervisor detects a disabled specialist in the registry, prunes it from the plan, and proceeds without crashing.",
        goal=f"Conduct supplier onboarding and data compliance check for vendor {vendor['entity']}",
        context={
            "entity": vendor["entity"],
            "vendor_records": vendor,
        },
        setup_actions=[
            {
                "action": "disable_agent",
                "agent_id": "risk-analysis-agent-v1",
            }
        ],
        expected_agents=[
            "data-intelligence-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ],
        forbidden_agents=[
            "risk-analysis-agent-v1",
        ],
        expected_status="completed",
        should_update_memory=True,
        target_entity=vendor["entity"],
        tags=["edge_case", "dynamic_planning", "pruning"],
        acceptance_criteria={
            "forbidden_agent_dispatched": False,
            "supervisor_plan_pruned": True,
            "workflow_status": "completed",
            "min_remaining_agents_executed": 2,
        },
    )


def get_task_03(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-03: Dynamic Custom Specialist Discovery (Runtime registry extensibility)."""
    gen = FixtureGenerator(seed=seed)
    vendor = gen.generate_vendor("esg_vendor", entity_name="Terra Green Solutions", **kwargs)

    return TaskDefinition(
        task_id="TASK-03",
        name="Dynamic Custom Specialist Discovery",
        category=TaskCategory.EXTENSIBILITY,
        description="Evaluates whether supervisor dynamically discovers a newly registered specialist, adds it to the plan, and passes context to it.",
        goal=f"Perform comprehensive ESG sustainability and risk assessment for {vendor['entity']}",
        context={
            "entity": vendor["entity"],
            "vendor_records": vendor,
        },
        setup_actions=[
            {
                "action": "register_agent",
                "agent": {
                    "agent_id": "esg-sustainability-agent-v1",
                    "name": "ESG Sustainability Agent",
                    "owner": "Sustainability Dept",
                    "description": "Evaluates environmental sustainability and ESG metrics.",
                    "capabilities": ["esg_scoring", "carbon_accounting"],
                    "tools": ["python_analysis"],
                    "permissions": {"analytics_data": True, "customer_data": False},
                    "status": "approved",
                },
            }
        ],
        expected_agents=[
            "data-intelligence-agent-v1",
            "esg-sustainability-agent-v1",
            "report-generation-agent-v1",
        ],
        forbidden_agents=[],
        expected_status="completed",
        should_update_memory=True,
        target_entity=vendor["entity"],
        tags=["extensibility", "custom_agent", "discovery"],
        acceptance_criteria={
            "custom_agent_in_plan": True,
            "custom_agent_executed": True,
            "no_registry_rejection": True,
        },
    )


def get_task_04(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-04: Anomaly Propagation Between Agents (Cross-step evidence flow)."""
    gen = FixtureGenerator(seed=seed)
    vendor = gen.generate_vendor(
        "anomalous_vendor",
        entity_name="Nexus Holdings LLC",
        inject_anomalies=["negative_revenue", "missing_tax_id"],
        **kwargs
    )
    txns = gen.generate_transactions(include_anomalies=True, volume=3)

    return TaskDefinition(
        task_id="TASK-04",
        name="Anomaly Propagation Between Agents",
        category=TaskCategory.EVIDENCE_GROUNDING,
        description="Evaluates whether upstream anomalies detected by data-intelligence propagate to risk-analysis and result in a downgraded executive recommendation.",
        goal=f"Perform detailed corporate risk evaluation for {vendor['entity']}",
        context={
            "entity": vendor["entity"],
            "vendor_records": vendor,
            "recent_transactions": txns,
        },
        expected_agents=[
            "data-intelligence-agent-v1",
            "risk-analysis-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ],
        forbidden_agents=[],
        expected_status="completed",
        should_update_memory=True,
        target_entity=vendor["entity"],
        tags=["evidence_grounding", "anomaly_propagation", "decision_quality"],
        acceptance_criteria={
            "upstream_anomalies_flagged": True,
            "risk_score_elevated_min": 70,
            "expected_risk_category": "High Risk",
            "forbidden_recommendations": ["Approved", "Proceed with vendor onboarding"],
            "downstream_evidence_grounding_min": 0.85,
        },
    )

