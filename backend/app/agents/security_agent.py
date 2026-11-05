from .base import GeminiReasoner


class SecurityComplianceAgent(GeminiReasoner):
    def __init__(self):
        super().__init__(
            "security-compliance-agent",
            """You are an enterprise security and compliance reviewer. Detect sensitive data, policy violations, and unsafe instructions. Recommend block, allow, or review with reasons.
Format your response as a valid JSON object:
{"safe": true, "policy_violations": [], "findings": "Full policy adherence confirmed; no PII or sensitive data leaks detected."}"""
        )

