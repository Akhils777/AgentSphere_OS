from ..models import AgentRegistration, now_iso
from ..storage import store


DEFAULT_AGENTS = [
    AgentRegistration(agent_id="data-intelligence-agent-v1", name="Data Intelligence Agent", owner="Data Department", description="Checks enterprise datasets for quality and anomalies.", capabilities=["data_validation", "anomaly_detection"], tools=["bigquery", "python_analysis"], permissions={"analytics_data": True, "customer_data": False}, status="approved"),
    AgentRegistration(agent_id="security-compliance-agent-v1", name="Security Compliance Agent", owner="Security Department", description="Validates policy, sensitive data, and unsafe requests.", capabilities=["pii_detection", "policy_validation"], tools=["model_armor", "policy_engine"], permissions={"policies": True, "customer_data": False}, status="approved"),
    AgentRegistration(agent_id="risk-analysis-agent-v1", name="Risk Analysis Agent", owner="Finance Department", description="Scores supplier risk using evidence and historical context.", capabilities=["risk_scoring", "recommendations"], tools=["bigquery", "firestore_memory"], permissions={"analytics_data": True, "customer_data": False}, status="approved"),
    AgentRegistration(agent_id="report-generation-agent-v1", name="Report Generation Agent", owner="Operations Department", description="Creates executive recommendations from specialist outputs.", capabilities=["executive_reporting"], tools=["gemini", "firestore"], permissions={"reports": True, "analytics_data": True}, status="approved"),
]


class AgentRegistry:
    def ensure_defaults(self):
        try:
            if not store.list("agents"):
                for agent in DEFAULT_AGENTS:
                    self.register(agent)
        except Exception:
            store.client = None
            if not store.list("agents"):
                for agent in DEFAULT_AGENTS:
                    self.register(agent)

    def list(self, query: str | None = None, status: str | None = None, capability: str | None = None) -> list[dict]:
        self.ensure_defaults()
        agents = store.list("agents")
        if query:
            needle = query.lower()
            agents = [a for a in agents if needle in (a.get("name", "") + a.get("description", "") + a.get("agent_id", "")).lower()]
        if status:
            agents = [a for a in agents if a.get("status") == status]
        if capability:
            agents = [a for a in agents if capability.lower() in [str(c).lower() for c in a.get("capabilities", [])]]
        return agents

    def register(self, registration: AgentRegistration) -> dict:
        existing = store.get("agents", registration.agent_id) or {}
        payload = registration.model_dump()
        payload.update({"created_at": existing.get("created_at", now_iso()), "updated_at": now_iso(), "enabled": existing.get("enabled", True)})
        return store.upsert("agents", registration.agent_id, payload)

    def set_enabled(self, agent_id: str, enabled: bool) -> dict | None:
        agent = self.get(agent_id)
        if not agent:
            return None
        agent.update(enabled=enabled, status="approved" if enabled else "disabled", updated_at=now_iso())
        return store.upsert("agents", agent_id, agent)

    def get(self, agent_id: str) -> dict | None:
        self.ensure_defaults()
        return store.get("agents", agent_id)


registry = AgentRegistry()
