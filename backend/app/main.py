from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .agents.supervisor_agent import SupervisorAgent
from .config import settings
from .models import AgentRegistration, WorkflowRequest, now_iso
from .registry.agent_registry import registry
from .runtime.workflow_engine import engine
from .security_filters import inspect_input
from .storage import store


DEFAULT_AGENTS = [
    AgentRegistration(agent_id="data-intelligence-agent-v1", name="Data Intelligence Agent", owner="Data Department", description="Checks enterprise datasets for quality and anomalies.", capabilities=["data_validation", "anomaly_detection"], tools=["bigquery", "python_analysis"], permissions={"analytics_data": True, "customer_data": False}, status="approved"),
    AgentRegistration(agent_id="security-compliance-agent-v1", name="Security Compliance Agent", owner="Security Department", description="Validates policy, sensitive data, and unsafe requests.", capabilities=["pii_detection", "policy_validation"], tools=["model_armor", "policy_engine"], permissions={"policies": True, "customer_data": False}, status="approved"),
    AgentRegistration(agent_id="risk-analysis-agent-v1", name="Risk Analysis Agent", owner="Finance Department", description="Scores supplier risk using evidence and historical context.", capabilities=["risk_scoring", "recommendations"], tools=["bigquery", "firestore_memory"], permissions={"analytics_data": True, "customer_data": False}, status="approved"),
    AgentRegistration(agent_id="report-generation-agent-v1", name="Report Generation Agent", owner="Operations Department", description="Creates executive recommendations from specialist outputs.", capabilities=["executive_reporting"], tools=["gemini", "firestore"], permissions={"reports": True, "analytics_data": True}, status="approved"),
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    registry.ensure_defaults()
    yield


app = FastAPI(title="AgentSphere OS API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agentsphere-api", "persistence": "firestore" if store.client else "local-json"}


@app.get("/api/agents")
async def list_agents(q: str | None = None, status: str | None = None):
    return {"items": registry.list(q, status)}


@app.post("/api/agents", status_code=201)
async def register_agent(agent: AgentRegistration):
    return registry.register(agent)


@app.get("/api/agents/capabilities")
async def list_agent_capabilities():
    agents = registry.list()
    capabilities = sorted({capability for agent in agents for capability in agent.get("capabilities", [])})
    return {"items": capabilities}


@app.get("/api/agents/{agent_id}")
async def get_agent(agent_id: str, capability: str | None = None):
    if agent_id == "search":
        return {"items": registry.list(capability=capability)}
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@app.post("/api/workflows", status_code=202)
async def create_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    safety = inspect_input(request.goal)
    workflow = engine.create(request.goal, request.requested_by, request.context)
    background_tasks.add_task(engine.run, workflow)
    if not safety["safe"]:
        return {**workflow, "status": "blocked", "security": safety}
    return workflow


@app.get("/api/workflows")
async def list_workflows():
    fields = ("workflow_id", "goal", "status", "progress", "created_at", "updated_at")
    items = sorted(store.list("workflows"), key=lambda x: x.get("created_at", ""), reverse=True)
    return {"items": [{key: item.get(key) for key in fields} for item in items]}

@app.get("/api/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    workflow = engine.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    return workflow


@app.get("/api/workflows/{workflow_id}/tasks")
async def workflow_tasks(workflow_id: str):
    return {"items": [task for task in store.list("tasks") if task.get("workflow_id") == workflow_id]}


@app.get("/api/audit-logs")
async def audit_logs(workflow_id: str | None = None):
    items = store.list("audit_logs")
    return {"items": [x for x in items if not workflow_id or x.get("workflow_id") == workflow_id]}


@app.get("/api/security-events")
async def security_events():
    return {"items": sorted(store.list("security_events"), key=lambda x: x.get("timestamp", ""), reverse=True)}


@app.get("/api/memories")
async def memories():
    return {"items": store.list("memories")}


@app.post("/api/safety/inspect")
async def inspect(payload: dict):
    return inspect_input(str(payload.get("text", "")))


@app.post("/api/events/dataset-upload", status_code=202)
async def dataset_event(payload: dict, background_tasks: BackgroundTasks):
    goal = f"Analyze newly uploaded dataset {payload.get('dataset', 'unknown')} for quality and risk"
    workflow = engine.create(goal, "pubsub:event", {"entity": payload.get("entity", "supplier_ABC"), "event": "dataset.uploaded"})
    background_tasks.add_task(engine.run, workflow)
    return workflow


@app.get("/api/agents/search")
async def search_agents(capability: str = Query(..., min_length=1)):
    return {"items": registry.list(capability=capability)}


@app.patch("/api/agents/{agent_id}/enabled")
async def set_agent_enabled(agent_id: str, enabled: bool):
    agent = registry.set_enabled(agent_id, enabled)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@app.get("/api/system/auth-status")
async def system_auth_status():
    from .config import settings
    use_vertex = settings.google_genai_use_vertexai
    has_key = bool(settings.gemini_api_key)
    has_project = bool(settings.google_cloud_project)
    
    provider = "vertex_ai" if use_vertex else "gemini_api"
    credentials_configured = has_project if use_vertex else has_key
    
    if not credentials_configured:
        status_code = "CREDENTIALS_MISSING"
        reason = "Google Cloud Project ID is not configured in backend/.env" if use_vertex else "GEMINI_API_KEY is not configured in backend/.env"
        action = "Add GOOGLE_CLOUD_PROJECT to backend/.env and authenticate with gcloud" if use_vertex else "Add a valid GEMINI_API_KEY from Google AI Studio to backend/.env"
    else:
        from .agents.base import GeminiReasoner
        test_agent = GeminiReasoner("auth-verifier", "Respond with OK")
        res = await test_agent.reason("auth check", {})
        if res.get("status") == "success":
            status_code = "READY"
            reason = "Authentication verified cleanly."
            action = "System is ready for live model execution."
        else:
            code = res.get("error_code", "provider_error")
            status_code = code.upper()
            reason = f"Provider test returned error code: {code}"
            action = "Re-check API key permissions or Vertex AI ADC login."

    return {
        "provider": provider,
        "model": settings.gemini_model,
        "credentials_configured": credentials_configured,
        "authentication_ready": status_code == "READY",
        "status_code": status_code,
        "reason": reason,
        "recommended_action": action
    }


@app.get("/api/gemini/verify")
async def verify_gemini():
    from .runtime.workflow_engine import AGENTS
    results = {}
    for agent_id, agent in {"supervisor": engine.supervisor, **AGENTS}.items():
        results[agent_id] = await agent.reason("health check", {"verification": True})
    return {"model": __import__("app.config", fromlist=["settings"]).settings.gemini_model, "results": results}

@app.get("/api/workflows/{workflow_id}/summary")
async def workflow_summary(workflow_id: str):
    workflow = engine.get(workflow_id)
    if not workflow:
        raise HTTPException(404, "Workflow not found")
    tasks = [task for task in store.list("tasks") if task.get("workflow_id") == workflow_id]
    completed = [task.get("agent_id") for task in tasks if task.get("status") == "completed"]
    failed = [task.get("agent_id") for task in tasks if task.get("status") == "failed"]
    execution_time = None
    if workflow.get("created_at") and workflow.get("completed_at"):
        from datetime import datetime
        execution_time = round((datetime.fromisoformat(workflow["completed_at"]) - datetime.fromisoformat(workflow["created_at"])).total_seconds(), 2)
    return {"workflow_id": workflow_id, "status": workflow.get("status"), "completed_agents": completed,
            "failed_agents": failed, "execution_time": execution_time,
            "final_report_output": (workflow.get("output") or {}).get("report-generation-agent-v1")}


# --- Static Frontend Serving for Container / Unified Production Deployments ---
import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist_paths = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend_dist"),
]

frontend_dist = next((p for p in frontend_dist_paths if os.path.exists(p) and os.path.exists(os.path.join(p, "index.html"))), None)

if frontend_dist:
    assets_dir = os.path.join(frontend_dist, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "health":
            raise HTTPException(404, "API route not found")
        target_file = os.path.join(frontend_dist, full_path)
        if os.path.exists(target_file) and os.path.isfile(target_file):
            return FileResponse(target_file)
        return FileResponse(os.path.join(frontend_dist, "index.html"))

