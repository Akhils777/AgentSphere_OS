"""Dynamic capability matching and specialist planning engine.
Analyzes workflow goals, registry capabilities, and task requirements to construct
ordered, minimal, and policy-compliant execution plans.
"""

from typing import Any
from ..registry.agent_registry import registry


class CapabilityMatcher:
    """Matches workflow objectives against registered specialist agents."""

    # Default fallback specialists in standard dependency order
    DEFAULT_SPECIALISTS = [
        ("data-intelligence-agent-v1", "Collect and validate supplier evidence"),
        ("risk-analysis-agent-v1", "Calculate supplier risk score"),
        ("security-compliance-agent-v1", "Check policies and sensitive data"),
        ("report-generation-agent-v1", "Generate executive recommendation"),
    ]

    @classmethod
    def match_plan(cls, goal: str, available_agents: list[dict | str] | None = None) -> list[dict]:
        """Construct an ordered plan of specialist steps matching the goal and available agents."""
        # 1. Resolve available agents against live registry
        resolved_agents: dict[str, dict] = {}
        if available_agents:
            for item in available_agents:
                if isinstance(item, dict):
                    aid = item.get("agent_id")
                    if aid and item.get("enabled", True) and item.get("status", "approved") == "approved":
                        resolved_agents[aid] = item
                elif isinstance(item, str):
                    rec = registry.get(item)
                    if rec and rec.get("enabled", True) and rec.get("status") == "approved":
                        resolved_agents[item] = rec
        else:
            # If no available agents passed, list all approved and enabled from live registry
            for rec in registry.list(status="approved"):
                if rec.get("enabled", True):
                    resolved_agents[rec["agent_id"]] = rec

        goal_clean = (goal or "").lower().strip()

        # 2. Case A: Single specialist targeted task
        # e.g., "Perform data intelligence analysis on proprietary customer records for Acme Corp"
        if goal_clean.startswith("perform data intelligence analysis on") or (
            "data intelligence analysis" in goal_clean and not any(k in goal_clean for k in ("risk", "compliance", "onboarding", "esg", "sustainability"))
        ):
            target_id = "data-intelligence-agent-v1"
            if target_id in resolved_agents:
                return [{
                    "agent_id": target_id,
                    "title": "Perform data intelligence analysis"
                }]

        # 3. Case B: Dynamic Custom Specialist (e.g. ESG Sustainability Specialist)
        # Check if the goal requests ESG / sustainability / environmental assessment
        is_esg_goal = any(k in goal_clean for k in ("esg", "sustainability", "carbon", "environmental"))
        custom_esg_agent = None
        if is_esg_goal:
            for aid, agent in resolved_agents.items():
                caps = [str(c).lower() for c in agent.get("capabilities", [])]
                desc = agent.get("description", "").lower()
                name = agent.get("name", "").lower()
                if (
                    "esg" in aid.lower()
                    or "sustainability" in aid.lower()
                    or "esg_scoring" in caps
                    or "carbon_accounting" in caps
                    or "esg" in desc
                    or "sustainability" in desc
                    or "esg" in name
                    or "sustainability" in name
                ):
                    custom_esg_agent = (aid, agent)
                    break

        if custom_esg_agent:
            aid, agent = custom_esg_agent
            plan = []
            # Ingestion / evidence verification
            if "data-intelligence-agent-v1" in resolved_agents:
                plan.append({
                    "agent_id": "data-intelligence-agent-v1",
                    "title": "Collect and validate supplier evidence"
                })
            # Domain specialist
            plan.append({
                "agent_id": aid,
                "title": f"Evaluate environmental and ESG metrics ({agent.get('name', 'ESG Specialist')})"
            })
            # Executive reporting
            if "report-generation-agent-v1" in resolved_agents:
                plan.append({
                    "agent_id": "report-generation-agent-v1",
                    "title": "Generate executive recommendation"
                })
            return plan

        # Check for other dynamic domain specialists matching goal keywords
        custom_domain_agents = []
        for aid, agent in resolved_agents.items():
            if aid in [s[0] for s in cls.DEFAULT_SPECIALISTS]:
                continue
            caps = [str(c).lower() for c in agent.get("capabilities", [])]
            desc = agent.get("description", "").lower()
            name = agent.get("name", "").lower()
            if any(c in goal_clean for c in caps if len(c) > 3) or any(w in goal_clean for w in name.split() if len(w) > 3):
                custom_domain_agents.append((aid, agent))

        if custom_domain_agents:
            plan = []
            if "data-intelligence-agent-v1" in resolved_agents:
                plan.append({
                    "agent_id": "data-intelligence-agent-v1",
                    "title": "Collect and validate supplier evidence"
                })
            for aid, agent in custom_domain_agents:
                plan.append({
                    "agent_id": aid,
                    "title": f"Execute specialist analysis ({agent.get('name', aid)})"
                })
            if "report-generation-agent-v1" in resolved_agents:
                plan.append({
                    "agent_id": "report-generation-agent-v1",
                    "title": "Generate executive recommendation"
                })
            return plan

        # 4. Case C: Standard multi-agent onboarding / risk / compliance review
        # Order: Data Collection -> Risk Analysis -> Security Compliance -> Executive Reporting
        standard_plan = []
        for agent_id, default_title in cls.DEFAULT_SPECIALISTS:
            if agent_id in resolved_agents:
                standard_plan.append({
                    "agent_id": agent_id,
                    "title": default_title
                })

        return standard_plan

