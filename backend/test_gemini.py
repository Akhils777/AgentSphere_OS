import asyncio
from app.agents.base import GeminiReasoner
from app.config import settings


async def main():
    result = await GeminiReasoner("gemini-smoke-test", "Explain enterprise agent orchestration in one sentence.").reason("health check", {})
    print({"model": settings.gemini_model, "status": result.get("status"), "error_code": result.get("error_code")})
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
