"""Reliability, failure recovery, and state isolation benchmark tasks:
- TASK-08: Memory integrity after workflow failure
- TASK-09: Missing entity isolation
- TASK-10: Transient fault recovery and retries
"""

from typing import Any
from ..schema import TaskCategory, TaskDefinition
from ..fixtures.loader import load_fault_scenarios, load_incomplete_inputs


def get_task_08(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-08: Memory Integrity After Workflow Failure (State isolation)."""
    fault_data = load_fault_scenarios()
    quota_fault = fault_data["fault_scenarios"][0]
    entity = "Vendor_Omega"

    return TaskDefinition(
        task_id="TASK-08",
        name="Memory Integrity After Workflow Failure",
        category=TaskCategory.STATE_ISOLATION,
        description="Evaluates whether an injected step failure halts workflow without mutating or corrupting pre-existing entity memory.",
        goal=f"Evaluate supplier {entity} with injected step failure",
        context={
            "entity": entity,
            "mock_error": quota_fault["injected_error_code"],
        },
        setup_actions=[
            {
                "action": "seed_memory",
                "entity": entity,
                "record": {
                    "entity": entity,
                    "previous_analysis": "PRISTINE_HISTORICAL_RECORD",
                    "previous_decisions": ["ORIGINAL_BASELINE_DECISION"],
                    "workflow_id": "WF-HISTORICAL-BASELINE",
                },
            }
        ],
        injected_fault={
            "fault_type": quota_fault["fault_type"],
            "target_step": quota_fault["target_step"],
            "error_code": quota_fault["injected_error_code"],
        },
        expected_agents=[
            "data-intelligence-agent-v1",
            "risk-analysis-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ],
        expected_status="failed",
        should_update_memory=False,
        target_entity=entity,
        tags=["reliability", "fault_injection", "memory_invariance", "state_isolation"],
        acceptance_criteria={
            "workflow_failed": True,
            "memory_invariant": True,
            "memory_updated_field_is_false": True,
            "audit_skip_event_present": "skip_memory_update_on_failure",
        },
    )


def get_task_09(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-09: Missing Entity Isolation (Preventing silent default pollution)."""
    incomplete_data = load_incomplete_inputs()
    scenario = incomplete_data["incomplete_inputs"][0]  # Missing Entity Context

    return TaskDefinition(
        task_id="TASK-09",
        name="Missing Entity Isolation",
        category=TaskCategory.BOUNDARY_HANDLING,
        description="Evaluates whether a workflow without an entity context completes cleanly without writing or corrupting 'supplier_ABC' in memory.",
        goal=scenario["goal"],
        context=scenario["context"],
        expected_agents=[
            "data-intelligence-agent-v1",
            "risk-analysis-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ],
        expected_status="completed",
        should_update_memory=False,
        target_entity=None,
        tags=["boundary", "input_handling", "entity_isolation"],
        acceptance_criteria={
            "workflow_status": "completed",
            "no_supplier_abc_pollution": True,
            "memory_updated_field_is_false": True,
            "audit_skip_event_present": "skip_memory_update_no_entity",
        },
    )


def get_task_10(seed: int = 42, **kwargs) -> TaskDefinition:
    """TASK-10: Transient Fault Recovery and Retries (Self-healing resilience)."""
    fault_data = load_fault_scenarios()
    timeout_fault = fault_data["fault_scenarios"][1]  # Transient timeout
    entity = "Acme Logistics Inc"

    return TaskDefinition(
        task_id="TASK-10",
        name="Transient Fault Recovery and Retries",
        category=TaskCategory.FAULT_RESILIENCE,
        description="Evaluates whether transient step timeouts or recoverable network drops recover on retry and complete the overall workflow.",
        goal=f"Evaluate supplier {entity} with transient timeout on step 1",
        context={
            "entity": entity,
        },
        injected_fault={
            "fault_type": timeout_fault["fault_type"],
            "target_step": timeout_fault["target_step"],
            "recoverable": True,
            "max_retries": 1,
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
        tags=["resilience", "retry", "self_healing", "transient_fault"],
        acceptance_criteria={
            "workflow_status": "completed",
            "step_retry_recorded": True,
            "workflow_progress_percent": 100,
        },
    )

