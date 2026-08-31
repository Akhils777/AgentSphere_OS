from datetime import datetime, timezone
from typing import Any
from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentRegistration(BaseModel):
    agent_id: str
    name: str
    version: str = "1.0"
    owner: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)
    status: str = "pending"
    role: str = "specialist"
    enabled: bool = True
    created_at: str | None = None
    updated_at: str | None = None


class WorkflowRequest(BaseModel):
    goal: str
    requested_by: str = "enterprise-user"
    context: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    task_id: str
    workflow_id: str
    agent_id: str
    title: str
    status: str = "queued"
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    execution_time_ms: int | None = None
    retries: int = 0

