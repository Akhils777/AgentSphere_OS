from .base import GeminiReasoner


class ReportGenerationAgent(GeminiReasoner):
    def __init__(self):
        super().__init__("report-generation-agent", "You are an executive reporting agent. Combine specialist outputs into a concise recommendation, clearly separating evidence, uncertainty, and next actions.")

