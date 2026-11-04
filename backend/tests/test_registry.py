import pytest
from app.registry.agent_registry import registry
from app.models import AgentRegistration


def test_agent_registry_ensure_defaults():
    agents = registry.list()
    assert len(agents) >= 4
    ids = {a["agent_id"] for a in agents}
    assert "data-intelligence-agent-v1" in ids
    assert "risk-analysis-agent-v1" in ids
    assert "security-compliance-agent-v1" in ids
    assert "report-generation-agent-v1" in ids


def test_agent_registration_and_get(client):
    new_agent = {
        "agent_id": "custom-audit-agent-v1",
        "name": "Custom Audit Agent",
        "version": "1.0",
        "owner": "Compliance Team",
        "description": "Specialized audit verification specialist.",
        "capabilities": ["audit_verification", "custom_scoring"],
        "tools": ["custom_tool"],
        "permissions": {"analytics_data": True},
        "status": "approved",
        "role": "specialist",
        "enabled": True
    }
    response = client.post("/api/agents", json=new_agent)
    assert response.status_code == 201
    created = response.json()
    assert created["agent_id"] == "custom-audit-agent-v1"

    # Fetch agent directly
    get_res = client.get("/api/agents/custom-audit-agent-v1")
    assert get_res.status_code == 200
    assert get_res.json()["name"] == "Custom Audit Agent"


def test_agent_discovery_and_search(client):
    # Search by capability
    res = client.get("/api/agents/search?capability=risk_scoring")
    assert res.status_code == 200
    items = res.json()["items"]
    assert any(a["agent_id"] == "risk-analysis-agent-v1" for a in items)

    # Search capabilities list
    res_caps = client.get("/api/agents/capabilities")
    assert res_caps.status_code == 200
    caps = res_caps.json()["items"]
    assert "risk_scoring" in caps
    assert "data_validation" in caps

    # Search by text query
    res_q = client.get("/api/agents?q=intelligence")
    assert res_q.status_code == 200
    items_q = res_q.json()["items"]
    assert any(a["agent_id"] == "data-intelligence-agent-v1" for a in items_q)


def test_agent_enable_disable_toggle(client):
    agent_id = "risk-analysis-agent-v1"

    # Disable agent
    patch_res = client.patch(f"/api/agents/{agent_id}/enabled?enabled=false")
    assert patch_res.status_code == 200
    assert patch_res.json()["enabled"] is False
    assert patch_res.json()["status"] == "disabled"

    # Confirm in registry get
    get_res = client.get(f"/api/agents/{agent_id}")
    assert get_res.json()["enabled"] is False

    # Re-enable agent
    patch_res2 = client.patch(f"/api/agents/{agent_id}/enabled?enabled=true")
    assert patch_res2.status_code == 200
    assert patch_res2.json()["enabled"] is True
    assert patch_res2.json()["status"] == "approved"


def test_agent_not_found(client):
    res = client.get("/api/agents/non-existent-agent-id-12345")
    assert res.status_code == 404

    patch_res = client.patch("/api/agents/non-existent-agent-id-12345/enabled?enabled=false")
    assert patch_res.status_code == 404

