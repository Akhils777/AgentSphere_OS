import asyncio
import pytest
from app.config import settings
from app.runtime.retry_policy import (
    RetryPolicy,
    classify_error,
    is_transient_error,
)
from app.runtime.workflow_engine import engine, AGENTS
from app.registry.agent_registry import registry
from app.memory.firestore_memory import memory_bank
from app.storage import store


def test_retry_policy_delay_calculation():
    """Verify exponential backoff calculations and fast mock mode bypass."""
    # Fast mock mode: delay is 0.0s
    policy_mock = RetryPolicy(max_retries=2, initial_delay_ms=50, backoff_multiplier=2.0, fast_in_mock=True)
    orig_mock = settings.gemini_mock_mode
    try:
        settings.gemini_mock_mode = True
        assert policy_mock.calculate_delay(1) == 0.0
        assert policy_mock.calculate_delay(2) == 0.0

        # Normal mode (non-mock or fast_in_mock=False):
        policy_real = RetryPolicy(max_retries=2, initial_delay_ms=50, backoff_multiplier=2.0, fast_in_mock=False)
        assert policy_real.calculate_delay(1) == 0.05
        assert policy_real.calculate_delay(2) == 0.10
        assert policy_real.calculate_delay(3) == 0.20
        assert policy_real.calculate_delay(0) == 0.0
    finally:
        settings.gemini_mock_mode = orig_mock


def test_error_classification_transient_vs_permanent():
    """Verify whitelist and blacklist error classification."""
    # Transient strings & exceptions
    assert is_transient_error("model_timeout") is True
    assert is_transient_error("quota_exceeded") is True
    assert is_transient_error("503_unavailable") is True
    assert is_transient_error("connection_error") is True
    assert is_transient_error(TimeoutError("Read timed out")) is True
    assert is_transient_error(asyncio.TimeoutError()) is True
    assert is_transient_error(ConnectionError("Connection reset by peer")) is True

    # Permanent strings & exceptions
    assert is_transient_error("permission_denied") is False
    assert is_transient_error("unauthorized_access") is False
    assert is_transient_error("agent_identity_unavailable") is False
    assert is_transient_error("prompt_blocked") is False
    assert is_transient_error("invalid_schema") is False
    assert is_transient_error("agent_runtime_missing") is False
    assert is_transient_error(PermissionError("unauthorized")) is False
    assert is_transient_error(ValueError("invalid arguments")) is False

    # Classification categories
    assert classify_error(TimeoutError()) == "timeout"
    assert classify_error("model_timeout") == "timeout"
    assert classify_error("quota_exceeded") == "rate_limit"
    assert classify_error("503_unavailable") == "service_unavailable"
    assert classify_error(ConnectionError()) == "connection_error"
    assert classify_error(PermissionError("agent_identity_unavailable")) == "permission_denied"
    assert classify_error("prompt_blocked") == "safety_violation"
    assert classify_error(ValueError("invalid_schema")) == "validation_error"


@pytest.mark.asyncio
async def test_single_transient_retry_recovery():
    """Verify recovery after a single transient failure on step 1."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    orig_reason = data_agent.reason

    attempts = 0

    async def flaky_reason(task, context):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return {"status": "error", "error_code": "model_timeout", "error_details": "Transient timeout"}
        return await orig_reason(task, context)

    data_agent.reason = flaky_reason
    entity_name = "test_retry_supplier_single"

    try:
        wf = engine.create("Evaluate supplier single retry", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "completed"
        assert updated_wf["progress"] == 100
        assert updated_wf["memory_updated"] is True

        tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
        step_1_task = next(t for t in tasks if t["agent_id"] == "data-intelligence-agent-v1")
        assert step_1_task["status"] == "completed"
        assert step_1_task["retries"] == 1
        assert attempts == 2

        # Verify audit logs
        wf_audit = [a for a in store.list("audit_logs") if a.get("workflow_id") == wf["workflow_id"]]
        retry_events = [a for a in wf_audit if a.get("action") == "task_transient_retry"]
        assert len(retry_events) == 1
        assert retry_events[0]["detail"]["attempt"] == 1
        assert retry_events[0]["detail"]["error_type"] == "timeout"

        recovered_events = [a for a in wf_audit if a.get("action") == "task_transient_retry_recovered"]
        assert len(recovered_events) == 1
        assert recovered_events[0]["detail"]["attempts_required"] == 1
    finally:
        data_agent.reason = orig_reason


@pytest.mark.asyncio
async def test_two_transient_retries_recovery():
    """Verify recovery after two transient failures (success on 3rd attempt)."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    orig_reason = data_agent.reason

    attempts = 0

    async def flaky_reason(task, context):
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            return {"status": "error", "error_code": "quota_exceeded", "error_details": f"Rate limited attempt {attempts}"}
        return await orig_reason(task, context)

    data_agent.reason = flaky_reason
    entity_name = "test_retry_supplier_double"

    try:
        wf = engine.create("Evaluate supplier double retry", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "completed"
        assert updated_wf["progress"] == 100
        assert updated_wf["memory_updated"] is True

        tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
        step_1_task = next(t for t in tasks if t["agent_id"] == "data-intelligence-agent-v1")
        assert step_1_task["status"] == "completed"
        assert step_1_task["retries"] == 2
        assert attempts == 3

        # Verify audit logs
        wf_audit = [a for a in store.list("audit_logs") if a.get("workflow_id") == wf["workflow_id"]]
        retry_events = [a for a in wf_audit if a.get("action") == "task_transient_retry"]
        assert len(retry_events) == 2
        assert retry_events[0]["detail"]["attempt"] == 1
        assert retry_events[1]["detail"]["attempt"] == 2

        recovered_events = [a for a in wf_audit if a.get("action") == "task_transient_retry_recovered"]
        assert len(recovered_events) == 1
        assert recovered_events[0]["detail"]["attempts_required"] == 2
    finally:
        data_agent.reason = orig_reason


@pytest.mark.asyncio
async def test_retry_exhaustion_permanent_failure():
    """Verify that retries exhaust at max_retries and fail permanently."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    orig_reason = data_agent.reason

    attempts = 0

    async def persistently_failing_reason(task, context):
        nonlocal attempts
        attempts += 1
        return {"status": "error", "error_code": "model_timeout", "error_details": "Persistent timeout"}

    data_agent.reason = persistently_failing_reason
    entity_name = "test_retry_exhaustion_vendor"

    try:
        wf = engine.create("Evaluate vendor exhaustion", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "failed"
        assert updated_wf["memory_updated"] is False
        assert updated_wf.get("error") == "model_timeout"

        tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
        step_1_task = next(t for t in tasks if t["agent_id"] == "data-intelligence-agent-v1")
        assert step_1_task["status"] == "failed"
        assert step_1_task["retries"] == 2
        assert attempts == 3  # 1 initial + 2 retries

        # Verify audit decision
        wf_audit = [a for a in store.list("audit_logs") if a.get("workflow_id") == wf["workflow_id"]]
        decision_events = [a for a in wf_audit if a.get("action") == "task_retry_decision"]
        assert len(decision_events) == 1
        assert decision_events[0]["status"] == "retries_exhausted"
        assert decision_events[0]["detail"]["attempts"] == 2
    finally:
        data_agent.reason = orig_reason


@pytest.mark.asyncio
async def test_permanent_error_not_retried():
    """Verify non-transient errors (e.g. prompt_blocked) are NOT retried."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    orig_reason = data_agent.reason

    attempts = 0

    async def blocked_reason(task, context):
        nonlocal attempts
        attempts += 1
        return {"status": "error", "error_code": "prompt_blocked", "error_details": "Blocked by filter"}

    data_agent.reason = blocked_reason
    entity_name = "test_blocked_vendor"

    try:
        wf = engine.create("Evaluate blocked vendor", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "failed"
        assert updated_wf["memory_updated"] is False

        tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
        step_1_task = next(t for t in tasks if t["agent_id"] == "data-intelligence-agent-v1")
        assert step_1_task["status"] == "failed"
        assert step_1_task["retries"] == 0
        assert attempts == 1  # Exactly 1 attempt, zero retries

        wf_audit = [a for a in store.list("audit_logs") if a.get("workflow_id") == wf["workflow_id"]]
        decision_events = [a for a in wf_audit if a.get("action") == "task_retry_decision"]
        assert len(decision_events) == 1
        assert decision_events[0]["status"] == "aborted"
        assert decision_events[0]["detail"]["error_type"] == "safety_violation"
    finally:
        data_agent.reason = orig_reason


@pytest.mark.asyncio
async def test_permission_error_not_retried():
    """Verify agent permission failures (HTTP 403 unauthorized action) are NOT retried."""
    data_record = store.get("agents", "data-intelligence-agent-v1")
    assert data_record is not None
    orig_permissions = dict(data_record.get("permissions", {}))
    # Revoke analytics_data permission to provoke 403 authorization block
    data_record["permissions"]["analytics_data"] = False
    store.upsert("agents", "data-intelligence-agent-v1", data_record)

    entity_name = "test_unauthorized_agent_vendor"

    try:
        wf = engine.create("Evaluate vendor permission check", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "failed"
        assert updated_wf["memory_updated"] is False

        tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
        assert len(tasks) == 1
        data_task = tasks[0]
        assert data_task["agent_id"] == "data-intelligence-agent-v1"
        assert data_task["status"] == "failed"
        assert data_task["retries"] == 0
        assert "403" in data_task["error"] or "Policy blocked" in data_task["error"]

        wf_audit = [a for a in store.list("audit_logs") if a.get("workflow_id") == wf["workflow_id"]]
        decision_events = [a for a in wf_audit if a.get("action") == "task_retry_decision"]
        assert len(decision_events) >= 1
        data_decision = next(a for a in decision_events if a.get("agent") == "data-intelligence-agent-v1")
        assert data_decision["status"] == "aborted"
        assert data_decision["detail"]["error_type"] == "permission_denied"
    finally:
        data_record["permissions"] = orig_permissions
        store.upsert("agents", "data-intelligence-agent-v1", data_record)


@pytest.mark.asyncio
async def test_non_duplication_of_successful_steps():
    """Verify that prior successful steps are not re-executed when a later step retries."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    risk_agent = AGENTS["risk-analysis-agent-v1"]
    orig_data_reason = data_agent.reason
    orig_risk_reason = risk_agent.reason

    data_invocations = 0
    risk_invocations = 0

    async def counting_data_reason(task, context):
        nonlocal data_invocations
        data_invocations += 1
        return await orig_data_reason(task, context)

    async def flaky_risk_reason(task, context):
        nonlocal risk_invocations
        risk_invocations += 1
        if risk_invocations == 1:
            return {"status": "error", "error_code": "model_timeout", "error_details": "Transient timeout"}
        return await orig_risk_reason(task, context)

    data_agent.reason = counting_data_reason
    risk_agent.reason = flaky_risk_reason
    entity_name = "test_non_duplication_vendor"

    try:
        wf = engine.create("Evaluate non duplication", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "completed"

        # Step 1 was executed exactly once
        assert data_invocations == 1
        # Step 2 was executed twice (initial + 1 retry)
        assert risk_invocations == 2
    finally:
        data_agent.reason = orig_data_reason
        risk_agent.reason = orig_risk_reason


@pytest.mark.asyncio
async def test_downstream_halting_on_failure():
    """Verify that execution halts immediately when a step fails permanently."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    risk_agent = AGENTS["risk-analysis-agent-v1"]
    orig_data_reason = data_agent.reason
    orig_risk_reason = risk_agent.reason

    risk_executed = False

    async def fatal_data_reason(task, context):
        raise ValueError("fatal_data_corruption")

    async def tracking_risk_reason(task, context):
        nonlocal risk_executed
        risk_executed = True
        return await orig_risk_reason(task, context)

    data_agent.reason = fatal_data_reason
    risk_agent.reason = tracking_risk_reason
    entity_name = "test_halting_vendor"

    try:
        wf = engine.create("Evaluate halting vendor", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "failed"

        # Risk agent must NEVER have been called
        assert risk_executed is False

        # Only step 1 task was dispatched
        tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
        assert len(tasks) == 1
        assert tasks[0]["agent_id"] == "data-intelligence-agent-v1"
    finally:
        data_agent.reason = orig_data_reason
        risk_agent.reason = orig_risk_reason


@pytest.mark.asyncio
async def test_memory_integrity_on_retry_exhaustion():
    """Verify memory remains invariant when all retries are exhausted."""
    entity_name = "pristine_vendor_retry_test"
    memory_bank.remember(
        entity_name,
        "PRISTINE_MEMORY_BEFORE_RETRY_FAILURE",
        ["HISTORICAL_DECISION"],
        "WF-PREV-001"
    )

    data_agent = AGENTS["data-intelligence-agent-v1"]
    orig_reason = data_agent.reason

    async def failing_reason(task, context):
        return {"status": "error", "error_code": "503_unavailable", "error_details": "Service down"}

    data_agent.reason = failing_reason

    try:
        wf = engine.create("Evaluate vendor memory invariance", "test-user", {"entity": entity_name})
        await engine.run(wf)

        updated_wf = engine.get(wf["workflow_id"])
        assert updated_wf["status"] == "failed"
        assert updated_wf["memory_updated"] is False

        # Verify memory was not mutated or overwritten
        mem = memory_bank.recall(entity_name)
        assert mem is not None
        assert mem["previous_analysis"] == "PRISTINE_MEMORY_BEFORE_RETRY_FAILURE"
        assert mem["workflow_id"] == "WF-PREV-001"
        assert mem["previous_decisions"] == ["HISTORICAL_DECISION"]

        # Audit skip event
        wf_audit = [a for a in store.list("audit_logs") if a.get("workflow_id") == wf["workflow_id"]]
        skip_events = [a for a in wf_audit if a.get("action") == "skip_memory_update_on_failure"]
        assert len(skip_events) == 1
    finally:
        data_agent.reason = orig_reason


@pytest.mark.asyncio
async def test_deterministic_mock_reproducibility():
    """Verify repeated runs under identical transient fault produce identical outcomes."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    orig_reason = data_agent.reason

    def make_flaky_reason():
        attempt = 0
        async def flaky(task, context):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                return {"status": "error", "error_code": "model_timeout", "error_details": "Timeout"}
            return await orig_reason(task, context)
        return flaky

    entity_name = "reproducible_vendor"

    try:
        # Run 1
        data_agent.reason = make_flaky_reason()
        wf1 = engine.create("Evaluate reproducible run 1", "test-user", {"entity": entity_name})
        await engine.run(wf1)
        r1 = engine.get(wf1["workflow_id"])

        # Run 2
        data_agent.reason = make_flaky_reason()
        wf2 = engine.create("Evaluate reproducible run 2", "test-user", {"entity": entity_name})
        await engine.run(wf2)
        r2 = engine.get(wf2["workflow_id"])

        assert r1["status"] == r2["status"] == "completed"
        assert r1["progress"] == r2["progress"] == 100
        assert r1["memory_updated"] == r2["memory_updated"] == True

        tasks1 = [t for t in store.list("tasks") if t.get("workflow_id") == wf1["workflow_id"]]
        tasks2 = [t for t in store.list("tasks") if t.get("workflow_id") == wf2["workflow_id"]]
        assert len(tasks1) == len(tasks2) == 4
        assert tasks1[0]["retries"] == tasks2[0]["retries"] == 1
    finally:
        data_agent.reason = orig_reason
