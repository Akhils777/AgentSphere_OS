from .base import GeminiReasoner


class ReportGenerationAgent(GeminiReasoner):
    def __init__(self):
        super().__init__(
            "report-generation-agent",
            """You are an executive reporting agent. Combine specialist outputs into a concise recommendation, clearly separating evidence, uncertainty, and next actions. Ground all findings strictly in provided prior specialist outputs. Never invent figures or facts.
Format your response as a valid JSON object:
{"analysis": "...", "executive_summary": {"status": "Approved", "recommendation": "...", "risk_score": 18, "risk_category": "Low Risk", "confidence_score": 90}}"""
        )

