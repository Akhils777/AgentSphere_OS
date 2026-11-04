"""Structural Grader (Tier 1 Gate).
Enforces hard operational, memory integrity, and security boundaries.
Any failure here caps the final task score at 0.0.
"""

from typing import Any
from ..schema import ExecutionTrace, StructuralResult, TaskDefinition


class StructuralGrader:
    """Grades Tier 1 operational integrity: workflow completion, memory invariance,
    exception containment, and security filter enforcement."""

    def grade(
        self,
        task: TaskDefinition,
        trace: ExecutionTrace,
        context: dict[str, Any] | None = None
    ) -> StructuralResult:
        context = context or {}
        failure_reasons: list[str] = []

        # 1. Workflow Status Matching
        expected_status = task.expected_status
        actual_status = trace.status
        status_match = actual_status == expected_status
        if not status_match:
            failure_reasons.append(
                f"Workflow status mismatch: expected '{expected_status}', got '{actual_status}'"
            )

        # 2. Unhandled Exception Containment
        no_unhandled = True
        if trace.error:
            # Check if error was expected as part of an injected fault
            is_expected_error = (
                task.expected_status == "failed"
                or (task.injected_fault and not task.injected_fault.get("recoverable", False))
                or task.expected_security_reason is not None
            )
            if not is_expected_error:
                no_unhandled = False
                failure_reasons.append(f"Unexpected unhandled exception encountered: {trace.error}")

        # 3. Memory Integrity & Invariance
        memory_invariant = True
        mem_before = trace.memory_snapshot_before or {}
        mem_after = trace.memory_snapshot_after or {}

        # Rule A: If task should NOT update memory, memory must remain completely invariant
        if not task.should_update_memory:
            if mem_before != mem_after:
                memory_invariant = False
                failure_reasons.append(
                    "Memory integrity violation: memory mutated when should_update_memory is False"
                )

        # Rule B: If workflow failed, memory must never be updated with success data
        if actual_status == "failed" and task.target_entity:
            entity_before = mem_before.get(task.target_entity)
            entity_after = mem_after.get(task.target_entity)
            if entity_before != entity_after:
                memory_invariant = False
                failure_reasons.append(
                    f"Memory integrity violation: entity memory for '{task.target_entity}' was updated on failed workflow"
                )

        # Rule C: Missing entity must never write to "supplier_ABC"
        if task.target_entity is None:
            if "supplier_ABC" in mem_after and "supplier_ABC" not in mem_before:
                memory_invariant = False
                failure_reasons.append(
                    "Memory isolation violation: missing entity silently defaulted to 'supplier_ABC'"
                )

        # 4. Security Gate Enforcement
        security_respected = True
        # If security filter should have blocked the workflow before agent dispatch
        if task.expected_security_reason:
            if len(trace.dispatched_tasks) > 0:
                security_respected = False
                failure_reasons.append(
                    f"Security gate failure: {len(trace.dispatched_tasks)} agent tasks dispatched despite security violation"
                )

        # If policy violations were expected, ensure they were blocked
        if task.acceptance_criteria.get("policy_blocked"):
            blocked_events = [
                e for e in trace.security_events if e.get("status") == "blocked"
            ]
            if not blocked_events and actual_status != "failed":
                security_respected = False
                failure_reasons.append(
                    "Policy enforcement failure: attempted unauthorized action was not blocked by policy engine"
                )

        # 5. Required Audit Events
        required_audit_action = task.acceptance_criteria.get("audit_skip_event_present")
        if required_audit_action:
            matching_events = [
                log for log in trace.audit_events if log.get("action") == required_audit_action
            ]
            if not matching_events:
                failure_reasons.append(
                    f"Audit tracking missing: required audit action '{required_audit_action}' not found in audit logs"
                )

        # 6. Minimum Agent Selection F1 Enforcement
        min_f1 = task.acceptance_criteria.get("agent_selection_f1_min")
        if min_f1 is not None and task.expected_agents:
            actual_agents = set(step.get("agent_id") for step in trace.planned_steps if step.get("agent_id"))
            expected_agents = set(task.expected_agents)
            tp = len(actual_agents.intersection(expected_agents))
            fp = len(actual_agents - expected_agents)
            fn = len(expected_agents - actual_agents)
            p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            actual_f1 = (2 * p * r) / (p + r) if (p + r) > 0 else 0.0
            if actual_f1 < min_f1:
                failure_reasons.append(
                    f"Agent selection F1 ({actual_f1:.2f}) below required minimum ({min_f1:.2f})"
                )

        # Construct result (Pydantic model validator computes passed)
        return StructuralResult(
            workflow_status_match=status_match,
            no_unhandled_exceptions=no_unhandled,
            memory_invariant=memory_invariant,
            security_gate_respected=security_respected,
            failure_reasons=failure_reasons,
        )
