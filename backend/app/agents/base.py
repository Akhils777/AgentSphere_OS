import asyncio
import json
from ..config import settings

try:
    from google import genai
except ImportError:
    genai = None

try:
    from google.adk.agents import LlmAgent as AdkAgent
except ImportError:
    try:
        from google.adk.agents import Agent as AdkAgent
    except ImportError:
        AdkAgent = None


class GeminiReasoner:
    def __init__(self, name: str, instruction: str):
        self.name = name
        self.instruction = instruction
        self.adk_agent = None
        if AdkAgent:
            try:
                self.adk_agent = AdkAgent(name=name, model=settings.gemini_model, instruction=instruction)
            except Exception:
                self.adk_agent = None

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

    async def reason(self, task: str, context: dict) -> dict:
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
