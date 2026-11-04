import asyncio
import json
from ..config import settings

try:
    from google import genai
except ImportError:
    genai = None


def get_adk_agent_class():
    """Lazily and safely resolves Google ADK Agent class if installed and compatible.
    Isolates heavy background imports until ADK functionality is explicitly accessed."""
    try:
        from google.adk.agents import LlmAgent as AdkAgent
        return AdkAgent
    except (ImportError, Exception):
        try:
            from google.adk.agents import Agent as AdkAgent
            return AdkAgent
        except (ImportError, Exception):
            return None


class GeminiReasoner:
    """Agent reasoner supporting live Gemini (via Google Gen AI SDK), Google ADK declarations,
    and a zero-cost deterministic mock provider for hermetic testing and evaluation."""

    def __init__(self, name: str, instruction: str):
        self.name = name
        self.instruction = instruction
        self._adk_agent = None

    @property
    def adk_agent(self):
        """Declarative Google ADK agent instance.
        Preserves backward compatibility while keeping ADK integration clearly isolated.
        Direct execution uses the Google Gen AI client or MockProvider for explicit retry,
        timeout, and fallback semantics."""
        if self._adk_agent is None:
            AdkAgentClass = get_adk_agent_class()
            if AdkAgentClass:
                try:
                    self._adk_agent = AdkAgentClass(name=self.name, model=settings.gemini_model, instruction=self.instruction)
                except Exception:
                    self._adk_agent = None
        return self._adk_agent

    @adk_agent.setter
    def adk_agent(self, value):
        self._adk_agent = value

    @staticmethod
    def _error_code(error: Exception) -> str:
        text = str(error).lower()
        if isinstance(error, (TimeoutError, asyncio.TimeoutError)) or "timeout" in text:
            return "api_timeout"
        if any(value in text for value in ("401", "403", "400", "unauthenticated", "permission denied", "api key", "api_key_invalid", "defaultcredentialserror", "invalid_argument")):
            return "authentication_failed"
        if any(value in text for value in ("429", "quota", "resource exhausted", "rate limit")):
            return "quota_exceeded"
        if any(value in text for value in ("404", "not_found", "not found", "no longer available", "unsupported for generatecontent")):
            return "model_unavailable"
        return "provider_error"

    def _mock_reason(self, task: str, context: dict) -> dict:
        """Deterministic mock provider responses for offline testing and evaluation."""
        if context.get("mock_error") or task == "mock_failure":
            err_code = context.get("mock_error", "mock_simulated_failure")
            return {"status": "error", "error_code": err_code, "model": "mock-gemini-flash", "error_details": f"Simulated mock failure: {err_code}"}

        if "mock_response" in context:
            return {"status": "success", "model": "mock-gemini-flash", **context["mock_response"]}

        if self.name == "supervisor-orchestrator-agent":
            available = context.get("available_agents", [])
            plan = []
            if "data-intelligence-agent-v1" in available or not available:
                plan.append({"agent_id": "data-intelligence-agent-v1", "title": "Collect and validate supplier evidence"})
            if "risk-analysis-agent-v1" in available or not available:
                plan.append({"agent_id": "risk-analysis-agent-v1", "title": "Calculate supplier risk score"})
            if "security-compliance-agent-v1" in available or not available:
                plan.append({"agent_id": "security-compliance-agent-v1", "title": "Check policies and sensitive data"})
            if "report-generation-agent-v1" in available or not available:
                plan.append({"agent_id": "report-generation-agent-v1", "title": "Generate executive recommendation"})
            return {"status": "success", "model": "mock-gemini-flash", "plan": plan}

        if self.name == "data-intelligence-agent":
            return {
                "status": "success",
                "model": "mock-gemini-flash",
                "task": task,
                "data_quality": "verified",
                "missing_values": [],
                "anomalies": [],
                "findings": "All supplier corporate records validated successfully."
            }

        if self.name == "risk-analysis-agent":
            return {
                "status": "success",
                "model": "mock-gemini-flash",
                "task": task,
                "risk_score": 18,
                "risk_category": "Low Risk",
                "confidence": "high",
                "key_findings": "Stable operational history, low regulatory risk."
            }

        if self.name == "security-compliance-agent":
            return {
                "status": "success",
                "model": "mock-gemini-flash",
                "task": task,
                "safe": True,
                "policy_violations": [],
                "findings": "Full policy adherence confirmed; no PII or sensitive data leaks detected."
            }

        if self.name == "report-generation-agent":
            return {
                "status": "success",
                "model": "mock-gemini-flash",
                "task": task,
                "analysis": "Supplier risk assessment complete. Recommendation: Proceed with vendor onboarding.",
                "executive_summary": {
                    "status": "Approved",
                    "recommendation": "Proceed with vendor onboarding. Low risk profile verified.",
                    "risk_score": 18,
                    "risk_category": "Low Risk",
                    "confidence_score": 90
                }
            }

        return {
            "status": "success",
            "model": "mock-gemini-flash",
            "task": task,
            "analysis": f"Mock analysis completed for {self.name}."
        }

    async def reason(self, task: str, context: dict) -> dict:
        # Deterministic mock branch: isolates tests and prevents external network calls/costs
        if settings.gemini_mock_mode or context.get("force_mock"):
            return self._mock_reason(task, context)

        prompt = f"{self.instruction}\nReturn valid JSON only.\nTask: {task}\nContext: {json.dumps(context, default=str)}"
        if not genai:
            return {"status": "error", "error_code": "sdk_missing", "model": settings.gemini_model}
        if not (settings.gemini_api_key or settings.google_cloud_project):
            return {"status": "error", "error_code": "credentials_missing", "model": settings.gemini_model}

        def call():
            if settings.google_genai_use_vertexai:
                return genai.Client(vertexai=True, project=settings.google_cloud_project, location=settings.google_cloud_location)
            return genai.Client(api_key=settings.gemini_api_key)

        models_to_try = [settings.gemini_model]
        if settings.gemini_model not in ("gemini-flash-latest", "gemini-2.5-flash"):
            models_to_try.append("gemini-flash-latest")

        last_error = None
        for model_name in models_to_try:
            for attempt in range(settings.gemini_max_retries + 1):
                try:
                    client = call()
                    response = await asyncio.wait_for(
                        asyncio.to_thread(client.models.generate_content, model=model_name, contents=prompt), 
                        settings.gemini_timeout_seconds
                    )
                    raw = (response.text or "").replace("```json", "").replace("```", "").strip()
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = {"analysis": raw}
                    return {"status": "success", "model": model_name, **parsed}
                except Exception as error:
                    last_error = error
                    code = self._error_code(error)
                    # Non-retryable errors abort immediately to prevent wasteful loops
                    if code in {"authentication_failed", "credentials_missing", "model_unavailable", "quota_exceeded"}:
                        if code == "model_unavailable" and model_name != models_to_try[-1]:
                            break  # Fallback to next model
                        return {"status": "error", "error_code": code, "model": model_name, "error_details": str(error)}
                    if attempt >= settings.gemini_max_retries:
                        return {"status": "error", "error_code": code, "model": model_name, "error_details": str(error)}
                    await asyncio.sleep(1)

        return {"status": "error", "error_code": self._error_code(last_error), "model": settings.gemini_model}
