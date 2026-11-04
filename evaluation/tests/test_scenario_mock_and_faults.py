"""Unit tests for Stage 2.3: ScenarioMockAdapter and FaultInjector.
Verifies deterministic scenario configuration and fault injection without
modifying production code.
"""

import pytest
from app.runtime.workflow_engine import AGENTS
from evaluation.harness.scenario_mock import ScenarioMockAdapter
from evaluation.harness.fault_injector import FaultInjector


# --- 1. Scenario Mock Adapter Tests ---

@pytest.mark.asyncio
async def test_scenario_mock_adapter_normal_delegation():
    """Verifies that normal scenario delegates to baseline agent reasoner."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    with ScenarioMockAdapter(scenario_type="normal"):
        res = await data_agent.reason("Test task", {})
        assert res["status"] == "success"
        assert res["data_quality"] == "verified"


@pytest.mark.asyncio
async def test_scenario_mock_adapter_missing_evidence():
    """Verifies scenario mock returns missing evidence indicators."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    with ScenarioMockAdapter(scenario_type="missing_evidence"):
        res = await data_agent.reason("Verify records", {})
        assert res["data_quality"] == "incomplete"
        assert "revenue" in res["missing_values"]


@pytest.mark.asyncio
async def test_scenario_mock_adapter_contradictory_evidence():
    """Verifies scenario mock produces contradictory risk score."""
    risk_agent = AGENTS["risk-analysis-agent-v1"]
    with ScenarioMockAdapter(scenario_type="contradictory_evidence"):
        res = await risk_agent.reason("Assess risk", {})
        assert res["risk_score"] == 95
        assert res["risk_category"] == "Extreme Risk"


@pytest.mark.asyncio
async def test_scenario_mock_adapter_malformed_output():
    """Verifies scenario mock simulates malformed output payloads."""
    report_agent = AGENTS["report-generation-agent-v1"]
    with ScenarioMockAdapter(scenario_type="malformed_output"):
        res = await report_agent.reason("Generate report", {})
        assert "corrupted_payload" in res


@pytest.mark.asyncio
async def test_scenario_mock_adapter_custom_overrides_and_cleanup():
    """Verifies explicit output overrides and clean restoration on exit."""
    report_agent = AGENTS["report-generation-agent-v1"]
    orig_reason = report_agent.reason

    custom_resp = {"status": "success", "custom_key": "custom_eval_value"}
    with ScenarioMockAdapter(overrides={"report-generation-agent-v1": custom_resp}):
        res = await report_agent.reason("Custom task", {})
        assert res["custom_key"] == "custom_eval_value"

    # Confirm original method is restored
    assert report_agent.reason == orig_reason


# --- 2. Fault Injector Tests ---

@pytest.mark.asyncio
async def test_fault_injector_transient_timeout_recovery():
    """Verifies transient timeout fails on attempt 1, recovers on attempt 2, and logs both."""
    data_agent = AGENTS["data-intelligence-agent-v1"]
    fault_spec = {
        "fault_type": "transient_timeout",
        "target_step": "data-intelligence-agent-v1",
        "recoverable": True,
        "max_retries": 1,
    }

    with FaultInjector(fault_spec) as injector:
        # Attempt 1: Injected timeout
        res_1 = await data_agent.reason("Task attempt 1", {})
        assert res_1["status"] == "error"
        assert res_1["error_code"] == "model_timeout"

        # Attempt 2: Recovered
        res_2 = await data_agent.reason("Task attempt 2", {})
        assert res_2["status"] == "success"

        # Check fault audit log
        faults = injector.get_injected_faults()
        assert len(faults) == 2
        assert faults[0]["attempt"] == 1
        assert faults[0]["recovered"] is False
        assert faults[1]["attempt"] == 2
        assert faults[1]["recovered"] is True
        assert injector.verify_recovery() is True


@pytest.mark.asyncio
async def test_fault_injector_quota_exceeded():
    """Verifies quota exhaustion injection (HTTP 429)."""
    security_agent = AGENTS["security-compliance-agent-v1"]
    fault_spec = {
        "fault_type": "quota_exceeded",
        "target_step": "security-compliance-agent-v1",
    }

    with FaultInjector(fault_spec) as injector:
        res = await security_agent.reason("Policy check", {})
        assert res["status"] == "error"
        assert res["error_code"] == "quota_exceeded"

        faults = injector.get_injected_faults()
        assert len(faults) == 1
        assert faults[0]["fault_type"] == "quota_exceeded"


@pytest.mark.asyncio
async def test_fault_injector_runtime_crash():
    """Verifies direct execution failure raising exception."""
    risk_agent = AGENTS["risk-analysis-agent-v1"]
    fault_spec = {
        "fault_type": "execution_failure",
        "target_step": "risk-analysis-agent-v1",
    }

    with FaultInjector(fault_spec):
        with pytest.raises(RuntimeError, match="Simulated unhandled runtime crash"):
            await risk_agent.reason("Crash test", {})

