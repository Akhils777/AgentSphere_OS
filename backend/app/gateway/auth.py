from fastapi import Header, HTTPException


async def authenticate(x_agent_identity: str | None = Header(default=None)) -> str:
    identity = x_agent_identity or "enterprise-user"
    if len(identity) > 120 or " " in identity:
        raise HTTPException(status_code=401, detail="Invalid agent identity")
    return identity

