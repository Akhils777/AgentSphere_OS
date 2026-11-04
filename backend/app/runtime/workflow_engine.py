import asyncio
import time
from uuid import uuid4
from ..agents.supervisor_agent import SupervisorAgent
from ..agents.data_agent import DataIntelligenceAgent
from ..agents.security_agent import SecurityComplianceAgent
from ..agents.risk_agent import RiskAnalysisAgent
from ..agents.report_agent import ReportGenerationAgent
from ..memory.firestore_memory import memory_bank
from ..models import now_iso
from ..observability.logger import audit
from ..registry.agent_registry import registry
from ..security_filters import inspect_input
from ..storage import store
from ..gateway.policy_engine import authorize

AGENTS = {
    "data-intelligence-agent-v1": DataIntelligenceAgent(),
    "security-compliance-agent-v1": SecurityComplianceAgent(),
    "risk-analysis-agent-v1": RiskAnalysisAgent(),
    "report-generation-agent-v1": ReportGenerationAgent(),
}


class WorkflowEngine:
    def __init__(self):
        self.supervisor = SupervisorAgent()
        self.jobs: dict[str, asyncio.Task] = {}

    def create(self, goal: str, requested_by: str, context: dict | None = None) -> dict:
        workflow_id = f"WF-{uuid4().hex[:8].upper()}"
        workflow = {
            "workflow_id": workflow_id,
            "goal": goal,
            "requested_by": requested_by,
            "status": "queued",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "progress": 0,
            "context": context or {},
            "tasks": []
        }
        store.upsert("workflows", workflow_id, workflow)
        return workflow

    async def run(self, workflow: dict):
        workflow_id = workflow["workflow_id"]
        safety = inspect_input(workflow["goal"])
        if not safety["safe"]:
            workflow.update(
                status="failed",
                progress=0,
                updated_at=now_iso(),
                completed_at=now_iso(),
                security_reason=safety["reason"],
                memory_updated=False
            )
            store.upsert("workflows", workflow_id, workflow)
            audit("agent-gateway", "inspect_workflow_input", "blocked", workflow_id, detail=safety)
            return

        try:
            available = [a for a in registry.list(status="approved") if a.get("agent_id") in AGENTS and a.get("enabled", True)]
            plan = await self.supervisor.plan(workflow["goal"], available)
        except Exception as e:
            workflow.update(
                status="failed",
                progress=0,
                error=f"supervisor_planning_failed: {str(e)}",
                updated_at=now_iso(),
                completed_at=now_iso(),
                memory_updated=False
            )
            store.upsert("workflows", workflow_id, workflow)
            audit("supervisor-agent", "plan_generation", "failed", workflow_id, detail={"error": str(e)})
            return

        if not plan:
            workflow.update(
                status="failed",
                progress=0,
                error="no_valid_plan_available",
                updated_at=now_iso(),
                completed_at=now_iso(),
                memory_updated=False
            )
            store.upsert("workflows", workflow_id, workflow)
            audit("supervisor-agent", "plan_validation", "failed", workflow_id, detail={"reason": "no_approved_agents_in_plan"})
            return

        workflow.update(status="running", plan=plan, updated_at=now_iso())
        store.upsert("workflows", workflow_id, workflow)

        outputs, failed = {}, False
        # Do not silently default missing entity identifiers to "supplier_ABC"
        raw_entity = (workflow.get("context") or {}).get("entity")
        entity = str(raw_entity).strip() if raw_entity else None
        recalled = memory_bank.recall(entity) if entity else None

        for index, step in enumerate(plan):
            agent_id = step.get("agent_id", "")
            task_id = f"TASK-{uuid4().hex[:8].upper()}"
            started = time.perf_counter()
            task = {
                "task_id": task_id,
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "title": step.get("title", "Agent task"),
                "status": "running",
                "started_at": now_iso(),
                "input": {"goal": workflow["goal"], "memory": recalled or {}},
                "retries": 0
            }
            store.upsert("tasks", task_id, task)
            workflow["tasks"].append(task_id)

            try:
                agent_record = registry.get(agent_id)
                if not agent_record or not agent_record.get("enabled", True):
                    raise PermissionError("agent_identity_unavailable")

                resource = "analytics_data" if agent_id.startswith(("data-", "risk-")) else "policies" if agent_id.startswith("security-") else "reports"
                authorize(agent_record, resource, "read", workflow_id)

                if agent_id not in AGENTS:
                    raise ValueError(f"agent_runtime_missing: {agent_id}")

                step_context = {
                    "goal": workflow["goal"],
                    "memory": recalled or {},
                    "prior_outputs": outputs,
                    **(workflow.get("context") or {})
                }
                result = await AGENTS[agent_id].reason(step.get("title", workflow["goal"]), step_context)

                if result.get("status") == "error":
                    err_code = result.get("error_code", "gemini_error")
                    raise RuntimeError(err_code)

                outputs[agent_id] = result
                task.update(status="completed", output=result, completed_at=now_iso())
                audit(agent_id, step.get("title", "completed_task"), "success", workflow_id, [resource], {"model": result.get("model")})
            except Exception as error:
                failed = True
                task.update(status="failed", error=str(error), completed_at=now_iso())
                audit(agent_id or "unknown-agent", step.get("title", "task"), "failed", workflow_id, detail={"error": str(error)})

            task["execution_time_ms"] = round((time.perf_counter() - started) * 1000)
            store.upsert("tasks", task_id, task)
            workflow.update(progress=round((index + 1) / len(plan) * 100), updated_at=now_iso())
            store.upsert("workflows", workflow_id, workflow)

        # Failure & entity memory isolation:
        # Failed workflows must NEVER write success records into entity memory.
        # Missing entities must NOT write to supplier_ABC.
        if not failed and entity:
            report_agent_output = outputs.get("report-generation-agent-v1", {})
            summary = (
                report_agent_output.get("analysis")
                or (report_agent_output.get("executive_summary") or {}).get("recommendation")
                or "Workflow completed with specialist outputs."
            )
            memory_bank.remember(entity, summary, ["Supplier risk assessment completed"], workflow_id)
            audit("memory-bank", "updated_supplier_context", "success", workflow_id)
            memory_updated = True
        else:
            if failed:
                audit("memory-bank", "skip_memory_update_on_failure", "skipped", workflow_id, detail={"reason": "workflow_failed", "entity": entity})
            elif not entity:
                audit("memory-bank", "skip_memory_update_no_entity", "skipped", workflow_id, detail={"reason": "no_entity_specified"})
            memory_updated = False

        workflow.update(
            status="failed" if failed else "completed",
            output=outputs,
            completed_at=now_iso(),
            updated_at=now_iso(),
            memory_updated=memory_updated
        )
        store.upsert("workflows", workflow_id, workflow)

    def get(self, workflow_id: str):
        return store.get("workflows", workflow_id)


engine = WorkflowEngine()
