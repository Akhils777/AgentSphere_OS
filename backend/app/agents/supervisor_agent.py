from .base import GeminiReasoner


class SupervisorAgent(GeminiReasoner):
    def __init__(self):
        super().__init__(
            "supervisor-orchestrator-agent",
            """
            You are a supervisor for a governed multi-agent enterprise workflow.
            Select only approved specialist agents.
            Produce an ordered execution plan.
            Each step must contain a valid agent_id from the provided available agents.
            """
        )

    async def plan(self, goal: str, available_agents: list[dict]) -> list[dict]:

        available_ids = [
            a.get("agent_id")
            for a in available_agents
            if a.get("agent_id")
        ]

        result = await self.reason(
            goal,
            {
                "available_agents": available_ids
            }
        )

        print("SUPERVISOR RESULT:", result)

        allowed_agents = {
            "data-intelligence-agent-v1",
            "risk-analysis-agent-v1",
            "security-compliance-agent-v1",
            "report-generation-agent-v1",
        }

        # Validate Gemini generated plan
        if isinstance(result, dict) and isinstance(result.get("plan"), list):

            valid_plan = []

            for step in result["plan"]:

                if not isinstance(step, dict):
                    continue

                agent_id = step.get("agent_id")

                if agent_id in allowed_agents:
                    valid_plan.append(
                        {
                            "agent_id": agent_id,
                            "title": step.get(
                                "title",
                                "Execute agent task"
                            )
                        }
                    )

            # Only use Gemini plan if all agents are valid
            if valid_plan:
                return valid_plan


        # Safe fallback plan
        return [
            {
                "agent_id": "data-intelligence-agent-v1",
                "title": "Collect and validate supplier evidence",
            },
            {
                "agent_id": "risk-analysis-agent-v1",
                "title": "Calculate supplier risk score",
            },
            {
                "agent_id": "security-compliance-agent-v1",
                "title": "Check policies and sensitive data",
            },
            {
                "agent_id": "report-generation-agent-v1",
                "title": "Generate executive recommendation",
            },
        ]