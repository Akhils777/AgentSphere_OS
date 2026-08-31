from .base import GeminiReasoner


class SecurityComplianceAgent(GeminiReasoner):
    def __init__(self):
        super().__init__("security-compliance-agent", "You are an enterprise security and compliance reviewer. Detect sensitive data, policy violations, and unsafe instructions. Recommend block, allow, or review with reasons.")

