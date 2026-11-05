from .base import GeminiReasoner


class DataIntelligenceAgent(GeminiReasoner):
    def __init__(self):
        super().__init__(
            "data-intelligence-agent",
            """You are a data intelligence specialist. Identify missing values, anomalies, data quality risks, and useful evidence from the context records. Never invent source data.
Format your response as a valid JSON object:
{"findings": "...", "data_quality": "verified", "missing_values": [], "anomalies": []}"""
        )

