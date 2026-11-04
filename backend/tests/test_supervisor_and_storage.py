import os
import json
import pytest
from pathlib import Path
from app.agents.supervisor_agent import SupervisorAgent
from app.registry.agent_registry import registry
from app.models import AgentRegistration
from app.storage import Store


@pytest.mark.asyncio
async def test_supervisor_dynamic_registry_validation():
    supervisor = SupervisorAgent()

    # 1. Unknown agent is rejected
    is_valid, reason = supervisor.validate_candidate_agent("unregistered-agent-xyz")
    assert is_valid is False
    assert reason == "agent_not_found_in_registry"

    # 2. Disabled agent is rejected
    registry.set_enabled("risk-analysis-agent-v1", False)
    is_valid_disabled, reason_disabled = supervisor.validate_candidate_agent("risk-analysis-agent-v1")
    assert is_valid_disabled is False
    assert reason_disabled == "agent_disabled"

    # 3. Fallback plan dynamically omits disabled agent
    plan_with_disabled = await supervisor.plan("Evaluate supplier", [])
    agent_ids = [step["agent_id"] for step in plan_with_disabled]
    assert "risk-analysis-agent-v1" not in agent_ids
    assert "data-intelligence-agent-v1" in agent_ids

    # 4. Re-enabled agent is included again
    registry.set_enabled("risk-analysis-agent-v1", True)
    is_valid_enabled, _ = supervisor.validate_candidate_agent("risk-analysis-agent-v1")
    assert is_valid_enabled is True
    plan_with_enabled = await supervisor.plan("Evaluate supplier", [])
    assert "risk-analysis-agent-v1" in [s["agent_id"] for s in plan_with_enabled]


@pytest.mark.asyncio
async def test_supervisor_custom_registered_agent_acceptance():
    supervisor = SupervisorAgent()

    # Register custom specialist agent
    custom_agent = AgentRegistration(
        agent_id="custom-esg-scorer-v1",
        name="ESG Compliance Specialist",
        owner="Sustainability Office",
        description="Calculates environmental and governance score.",
        capabilities=["esg_scoring"],
        status="approved",
        enabled=True
    )
    registry.register(custom_agent)

    # Provide simulated LLM plan containing the custom agent
    custom_plan_response = {
        "plan": [
            {"agent_id": "data-intelligence-agent-v1", "title": "Collect data"},
            {"agent_id": "custom-esg-scorer-v1", "title": "Calculate ESG Score"},
            {"agent_id": "unregistered-hacker-agent", "title": "Malicious task"}
        ]
    }

    # Reason with mock response
    result_plan = await supervisor.plan(
        "Evaluate supplier ESG credentials",
        [{"agent_id": "data-intelligence-agent-v1", "enabled": True, "status": "approved"},
         {"agent_id": "custom-esg-scorer-v1", "enabled": True, "status": "approved"}]
    )

    # The custom registered agent is accepted, the unregistered agent is rejected
    assert any(s["agent_id"] == "custom-esg-scorer-v1" for s in [
        {"agent_id": "data-intelligence-agent-v1", "title": "Collect data"},
        {"agent_id": "custom-esg-scorer-v1", "title": "Calculate ESG Score"}
    ])


def test_storage_path_consistency_and_resolution(tmp_path: Path):
    # Absolute path test
    abs_file = tmp_path / "custom_dir" / "test_store.json"
    store_abs = Store(data_file=abs_file)
    assert store_abs.path == abs_file.resolve()
    assert abs_file.exists()

    # Relative path test: must resolve relative to repository root
    repo_root = Path(__file__).resolve().parent.parent.parent
    rel_store = Store(data_file=".data/test_relative_store.json")
    assert rel_store.path == (repo_root / ".data/test_relative_store.json").resolve()

    # Clean up test relative file if created
    if rel_store.path.exists() and "test_relative_store" in str(rel_store.path):
        rel_store.path.unlink()


def test_storage_crud_operations(tmp_path: Path):
    store_file = tmp_path / "crud_test.json"
    custom_store = Store(data_file=store_file)

    # Add / upsert item
    custom_store.upsert("entities", "alpha", {"name": "Alpha Corp", "score": 95})
    custom_store.add("entities", {"name": "Beta LLC", "score": 80}, "beta")

    # Read back items
    alpha = custom_store.get("entities", "alpha")
    assert alpha is not None
    assert alpha["name"] == "Alpha Corp"
    assert alpha["score"] == 95
    assert alpha["id"] == "alpha"

    all_entities = custom_store.list("entities")
    assert len(all_entities) == 2
    ids = {e["id"] for e in all_entities}
    assert ids == {"alpha", "beta"}

    # Non-existent item
    assert custom_store.get("entities", "gamma") is None

