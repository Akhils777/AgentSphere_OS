from .base import GeminiReasoner
from .capability_matcher import CapabilityMatcher
from ..registry.agent_registry import registry


class SupervisorAgent(GeminiReasoner):
    def __init__(self):
        super().__init__(
            "supervisor-orchestrator-agent",
            """You are a supervisor for a governed multi-agent enterprise workflow.
Select only approved specialist agents from the provided available agents.
Produce an ordered execution plan.
Format your response as a valid JSON object:
{"plan": [{"agent_id": "...", "title": "..."}]}
Each step must contain a valid agent_id from the provided available_agents list."""
        )

    @staticmethod
    def validate_candidate_agent(agent_id: str) -> tuple[bool, str | None]:
        """Validate candidate agent against the live registry without hardcoded whitelists."""
        agent = registry.get(agent_id)
        if not agent:
            return False, "agent_not_found_in_registry"
        if not agent.get("enabled", True):
            return False, "agent_disabled"
        if agent.get("status") != "approved":
            return False, f"agent_not_approved (status={agent.get('status')})"
        return True, None

    async def plan(self, goal: str, available_agents: list[dict]) -> list[dict]:
        # Filter available agent IDs from registry
        available_ids = [
            a.get("agent_id")
            for a in available_agents
            if a.get("agent_id") and a.get("enabled", True) and a.get("status") == "approved"
        ]

        result = await self.reason(
            goal,
            {
                "available_agents": available_ids,
                "available_agent_records": available_agents,
            }
        )

        rejection_reasons = []

        # Validate Gemini-generated plan using registry metadata
        if isinstance(result, dict) and isinstance(result.get("plan"), list):
            valid_plan = []
            for step in result["plan"]:
                if not isinstance(step, dict):
                    rejection_reasons.append({"step": step, "reason": "step_must_be_dict"})
                    continue

                agent_id = step.get("agent_id")
                if not agent_id:
                    rejection_reasons.append({"step": step, "reason": "missing_agent_id"})
                    continue

                is_valid, reason = self.validate_candidate_agent(agent_id)
                if is_valid:
                    valid_plan.append({
                        "agent_id": agent_id,
                        "title": step.get("title", "Execute agent task")
                    })
                else:
                    rejection_reasons.append({"agent_id": agent_id, "reason": reason})

            if valid_plan:
                if rejection_reasons:
                    print(f"[SupervisorAgent] Valid plan constructed; some steps discarded with reasons: {rejection_reasons}")
                return valid_plan
            elif rejection_reasons:
                print(f"[SupervisorAgent] Discarded invalid plan. Reasons: {rejection_reasons}")

        # Fallback to dynamic capability matcher validating candidate agents against live registry
        fallback_plan = CapabilityMatcher.match_plan(goal, available_agents)
        valid_fallback = []
        for step in fallback_plan:
            is_valid, _ = self.validate_candidate_agent(step["agent_id"])
            if is_valid:
                valid_fallback.append(step)

        return valid_fallback
