from .base import GeminiReasoner


class DataIntelligenceAgent(GeminiReasoner):
    def __init__(self):
        super().__init__("data-intelligence-agent", "You are a data intelligence specialist. Identify missing values, anomalies, data quality risks, and useful evidence. Never invent source data.")

