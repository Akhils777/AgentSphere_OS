from ..models import now_iso
import hashlib
import json
import time
from ..storage import store


def audit(agent: str, action: str, status: str, workflow_id: str, tools_used: list[str] | None = None, detail: dict | None = None):
    event_id = f"audit-{now_iso().replace(':', '').replace('.', '')}-{agent}"
    return store.add("audit_logs", {"agent": agent, "action": action, "timestamp": now_iso(), "status": status,
        "workflow_id": workflow_id, "tools_used": tools_used or [], "detail": detail or {}, "input_hash": hashlib.sha256(json.dumps(detail or {}, sort_keys=True, default=str).encode()).hexdigest(), "output_summary": (detail or {}).get("summary", ""), "latency": (detail or {}).get("latency_ms")}, event_id)

