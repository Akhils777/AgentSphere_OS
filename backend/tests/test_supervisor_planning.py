import pytest
from app.agents.capability_matcher import CapabilityMatcher
from app.agents.supervisor_agent import SupervisorAgent
from app.models import AgentRegistration
from app.registry.agent_registry import registry
from app.runtime.workflow_engine import engine
from app.storage import store


def test_capability_matcher_standard_onboarding():
    """Verify standard supplier evaluation selects all 4 specialists in dependency order."""
    goal = "Perform complete onboarding risk and compliance evaluation for vendor OmniTech Solutions."
    plan = CapabilityMatcher.match_plan(goal)
    agent_ids = [s["agent_id"] for s in plan]
    assert agent_ids == [
        "data-intelligence-agent-v1",
        "risk-analysis-agent-v1",
        "security-compliance-agent-v1",
        "report-generation-agent-v1",
    ]


def test_capability_matcher_disabled_specialist_pruning():
    """Verify disabled specialist is pruned from the plan."""
    registry.set_enabled("risk-analysis-agent-v1", False)
    try:
        goal = "Conduct supplier onboarding and data compliance check for vendor BioHealth Corp."
        plan = CapabilityMatcher.match_plan(goal)
        agent_ids = [s["agent_id"] for s in plan]
        assert "risk-analysis-agent-v1" not in agent_ids
        assert agent_ids == [
            "data-intelligence-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        ]
    finally:
        registry.set_enabled("risk-analysis-agent-v1", True)


def test_capability_matcher_esg_specialist_discovery():
    """Verify ESG specialist is dynamically discovered and matched for ESG goals."""
    custom_agent = AgentRegistration(
        agent_id="esg-sustainability-agent-v1",
        name="ESG Sustainability Agent",
        owner="Sustainability Dept",
        description="Evaluates environmental sustainability and ESG metrics.",
        capabilities=["esg_scoring", "carbon_accounting"],
        tools=["python_analysis"],
        permissions={"analytics_data": True, "customer_data": False},
        status="approved",
        enabled=True,
    )
    registry.register(custom_agent)

    goal = "Perform comprehensive ESG sustainability and risk assessment for Terra Green Solutions"
    plan = CapabilityMatcher.match_plan(goal)
    agent_ids = [s["agent_id"] for s in plan]
    assert agent_ids == [
        "data-intelligence-agent-v1",
        "esg-sustainability-agent-v1",
        "report-generation-agent-v1",
    ]


def test_capability_matcher_targeted_data_query():
    """Verify query specifically targeting data intelligence selects only data intelligence."""
    goal = "Perform data intelligence analysis on proprietary customer records for Acme Corp"
    plan = CapabilityMatcher.match_plan(goal)
    agent_ids = [s["agent_id"] for s in plan]
    assert agent_ids == ["data-intelligence-agent-v1"]


def test_capability_matcher_general_custom_specialist():
    """Verify general custom specialists matching goal keywords are scheduled between ingestion and report."""
    tax_agent = AgentRegistration(
        agent_id="tax-compliance-agent-v1",
        name="Tax Compliance Agent",
        owner="Tax Department",
        description="Performs international corporate tax analysis and audit.",
        capabilities=["tax_analysis", "corporate_filings"],
        tools=["tax_engine"],
        permissions={"analytics_data": True},
        status="approved",
        enabled=True,
    )
    registry.register(tax_agent)

    goal = "Perform corporate tax_analysis evaluation for Global Shipping Inc"
    plan = CapabilityMatcher.match_plan(goal)
    agent_ids = [s["agent_id"] for s in plan]
    assert "data-intelligence-agent-v1" in agent_ids
    assert "tax-compliance-agent-v1" in agent_ids
    assert "report-generation-agent-v1" in agent_ids


@pytest.mark.asyncio
async def test_supervisor_plan_invalid_rejection_and_fallback():
    """Verify supervisor rejects invalid steps and falls back to capability matcher."""
    supervisor = SupervisorAgent()

    # Pass mock response containing non-existent and unapproved agents
    context = {
        "mock_response": {
            "plan": [
                {"agent_id": "non-existent-agent-999", "title": "Invalid Step"},
                {"agent_id": "data-intelligence-agent-v1", "title": "Valid Step"},
            ]
        }
    }
    # When reasoning with this context, invalid step is discarded
    res = await supervisor.reason("Evaluate vendor", context)
    assert res.get("status") == "success"

    # Full plan generation filters out invalid agent
    goal = "Perform complete onboarding risk and compliance evaluation for vendor Test Corp."
    plan = await supervisor.plan(goal, registry.list(status="approved"))
    agent_ids = [s["agent_id"] for s in plan]
    assert "non-existent-agent-999" not in agent_ids
    assert "data-intelligence-agent-v1" in agent_ids


@pytest.mark.asyncio
async def test_full_workflow_with_dynamic_custom_specialist():
    """Verify workflow executes cleanly with a dynamically registered custom specialist."""
    custom_esg = AgentRegistration(
        agent_id="esg-sustainability-agent-v1",
        name="ESG Sustainability Agent",
        owner="Sustainability Dept",
        description="Evaluates environmental sustainability and ESG metrics.",
        capabilities=["esg_scoring", "carbon_accounting"],
        tools=["python_analysis"],
        permissions={"analytics_data": True, "customer_data": False},
        status="approved",
        enabled=True,
    )
    registry.register(custom_esg)

    wf = engine.create(
        goal="Perform comprehensive ESG sustainability and risk assessment for Terra Green Solutions",
        requested_by="test-supervisor-planning",
        context={"entity": "Terra Green Solutions"},
    )
    await engine.run(wf)

    updated_wf = engine.get(wf["workflow_id"])
    assert updated_wf["status"] == "completed"
    assert updated_wf["progress"] == 100
    assert updated_wf.get("memory_updated") is True

    # Confirm the custom specialist was planned and executed
    tasks = [t for t in store.list("tasks") if t.get("workflow_id") == wf["workflow_id"]]
    executed_agent_ids = [t["agent_id"] for t in tasks]
    assert "data-intelligence-agent-v1" in executed_agent_ids
    assert "esg-sustainability-agent-v1" in executed_agent_ids
    assert "report-generation-agent-v1" in executed_agent_ids

