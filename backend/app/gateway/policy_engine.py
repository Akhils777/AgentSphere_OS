from fastapi import HTTPException
from ..models import now_iso
from ..storage import store


def authorize(agent: dict, resource: str, action: str, workflow_id: str | None = None) -> bool:
    allowed = bool(agent.get("permissions", {}).get(resource, False))
    if not allowed:
        store.add("security_events", {
            "agent": agent.get("agent_id"), "resource": resource, "action": action,
            "workflow_id": workflow_id, "status": "blocked", "reason": "permission_denied", "timestamp": now_iso()
        }, f"security-{now_iso().replace(':', '').replace('.', '')}")
        raise HTTPException(status_code=403, detail=f"Policy blocked {agent.get('agent_id')} from {action} on {resource}")
    return True

