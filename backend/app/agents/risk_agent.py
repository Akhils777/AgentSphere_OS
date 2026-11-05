from .base import GeminiReasoner


class RiskAnalysisAgent(GeminiReasoner):
    def __init__(self):
        super().__init__(
            "risk-analysis-agent",
            """You are a supplier risk analyst. Assess evidence, historical context, uncertainty, and produce a cautious risk score from 0 to 100 with recommendations.
Format your response as a valid JSON object:
{"risk_score": 18, "risk_category": "Low Risk", "confidence": "high", "key_findings": "..."}"""
        )

