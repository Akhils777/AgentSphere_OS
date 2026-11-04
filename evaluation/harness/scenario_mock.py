"""Scenario Mock Adapter for evaluation environments.
Enables deterministic configuration of specialist behaviors (normal, incorrect,
missing evidence, contradictory evidence, malformed outputs, and controlled errors)
without modifying production code.
"""

import copy
import sys
from pathlib import Path
from typing import Any, Callable

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import AGENTS dictionary from backend runtime
from app.runtime.workflow_engine import AGENTS
from app.config import settings


class ScenarioMockAdapter:
    """Context manager that temporarily wraps specialist agent reasoning methods
    with scenario-driven behaviors for evaluation."""

    def __init__(
        self,
        scenario_type: str = "normal",
        overrides: dict[str, Any] | None = None,
        custom_handlers: dict[str, Callable] | None = None
    ):
        self.scenario_type = scenario_type
        self.overrides = overrides or {}
        self.custom_handlers = custom_handlers or {}
        self._original_methods: dict[str, Callable] = {}
        self._orig_mock_mode: bool | None = None

    def __enter__(self) -> "ScenarioMockAdapter":
        self._original_methods.clear()
        self._orig_mock_mode = settings.gemini_mock_mode
        settings.gemini_mock_mode = True

        for agent_id, agent in AGENTS.items():
            self._original_methods[agent_id] = agent.reason

            # Bind interceptor
            agent.reason = self._make_interceptor(agent_id, self._original_methods[agent_id])

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original agent methods and mock mode
        if self._orig_mock_mode is not None:
            settings.gemini_mock_mode = self._orig_mock_mode

        for agent_id, orig_method in self._original_methods.items():
            if agent_id in AGENTS:
                AGENTS[agent_id].reason = orig_method
        self._original_methods.clear()

    async def __aenter__(self) -> "ScenarioMockAdapter":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

    def _make_interceptor(self, agent_id: str, original_reason: Callable) -> Callable:
        async def interceptor(task: str, context: dict) -> dict:
            # 1. Check custom handler first
            if agent_id in self.custom_handlers:
                return await self.custom_handlers[agent_id](task, context)

            # 2. Check explicit output override
            if agent_id in self.overrides:
                override = self.overrides[agent_id]
                return copy.deepcopy(override)

            # 3. Scenario Type Behaviors
            if self.scenario_type == "malformed_output":
                return {"corrupted_payload": "NOT_A_VALID_SCHEMA", "status": "corrupted"}

            if self.scenario_type == "missing_evidence":
                return {
                    "status": "success",
                    "model": "mock-gemini-flash",
                    "task": task,
                    "data_quality": "incomplete",
                    "missing_values": ["revenue", "tax_id", "credit_rating"],
                    "anomalies": ["insufficient_source_evidence"],
                    "findings": "Critical financial metrics were completely omitted from input records.",
                }

            if self.scenario_type == "contradictory_evidence":
                if agent_id == "risk-analysis-agent-v1":
                    # Emit severe risk despite clean upstream
                    return {
                        "status": "success",
                        "model": "mock-gemini-flash",
                        "task": task,
                        "risk_score": 95,
                        "risk_category": "Extreme Risk",
                        "key_findings": "Severe regulatory sanctions imminent without supporting data.",
                    }

            if self.scenario_type == "incorrect_specialist":
                if agent_id == "data-intelligence-agent-v1":
                    # Fails to detect obvious anomalies
                    return {
                        "status": "success",
                        "model": "mock-gemini-flash",
                        "task": task,
                        "data_quality": "verified_clean",
                        "missing_values": [],
                        "anomalies": [],
                        "findings": "No irregularities detected (false negative assertion).",
                    }

            if self.scenario_type == "controlled_failure":
                return {
                    "status": "error",
                    "error_code": "scenario_controlled_error",
                    "model": "mock-gemini-flash",
                    "error_details": "Controlled scenario failure injection",
                }

            # Default: delegate to normal reasoning implementation
            return await original_reason(task, context)

        return interceptor
