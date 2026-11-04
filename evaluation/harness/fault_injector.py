"""Deterministic Fault Injector for evaluation environments.
Simulates transient network timeouts, quota exhaustion, prompt blocking,
malformed responses, and runtime execution crashes, while recording all events.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Ensure backend directory is in sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.runtime.workflow_engine import AGENTS
from app.config import settings


class FaultInjector:
    """Context manager that injects deterministic faults into specialist agents
    and tracks recovery trajectories."""

    def __init__(self, fault_spec: dict[str, Any] | None = None):
        self.fault_spec = fault_spec or {}
        self.fault_type = self.fault_spec.get("fault_type")
        self.target_step = self.fault_spec.get("target_step")
        self.recoverable = self.fault_spec.get("recoverable", False)
        self.max_retries = self.fault_spec.get("max_retries", 1)

        self._original_methods: dict[str, Callable] = {}
        self._attempt_counts: dict[str, int] = {}
        self.injected_faults: list[dict[str, Any]] = []
        self._orig_mock_mode: bool | None = None

    def __enter__(self) -> "FaultInjector":
        self._original_methods.clear()
        self._attempt_counts.clear()
        self.injected_faults.clear()
        self._orig_mock_mode = settings.gemini_mock_mode
        settings.gemini_mock_mode = True

        if not self.fault_type or not self.target_step:
            return self

        # Hook the target agent
        if self.target_step in AGENTS:
            agent = AGENTS[self.target_step]
            self._original_methods[self.target_step] = agent.reason
            agent.reason = self._make_fault_interceptor(self.target_step, self._original_methods[self.target_step])

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._orig_mock_mode is not None:
            settings.gemini_mock_mode = self._orig_mock_mode

        # Restore original reason method
        for agent_id, orig_method in self._original_methods.items():
            if agent_id in AGENTS:
                AGENTS[agent_id].reason = orig_method
        self._original_methods.clear()

    async def __aenter__(self) -> "FaultInjector":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

    def _make_fault_interceptor(self, agent_id: str, original_reason: Callable) -> Callable:
        async def interceptor(task: str, context: dict) -> dict:
            attempts = self._attempt_counts.get(agent_id, 0) + 1
            self._attempt_counts[agent_id] = attempts

            timestamp = datetime.now(timezone.utc).isoformat()
            fault_record = {
                "timestamp": timestamp,
                "target_agent": agent_id,
                "fault_type": self.fault_type,
                "attempt": attempts,
                "recovered": False,
            }

            # Case A: Recoverable Transient Timeout (Fails on attempt 1, succeeds on attempt > 1)
            if self.fault_type == "transient_timeout" and self.recoverable:
                if attempts <= self.max_retries:
                    self.injected_faults.append(fault_record)
                    return {
                        "status": "error",
                        "error_code": "model_timeout",
                        "model": "mock-gemini-flash",
                        "error_details": f"Injected transient timeout on attempt {attempts}",
                    }
                else:
                    # Mark recovered and proceed to normal execution
                    fault_record["recovered"] = True
                    self.injected_faults.append(fault_record)
                    return await original_reason(task, context)

            # Case B: Quota Exhaustion (429)
            if self.fault_type == "quota_exceeded":
                self.injected_faults.append(fault_record)
                return {
                    "status": "error",
                    "error_code": "quota_exceeded",
                    "model": "mock-gemini-flash",
                    "error_details": "Injected quota exhaustion (HTTP 429)",
                }

            # Case C: Prompt Armor / Safety Blocking
            if self.fault_type == "prompt_blocking":
                self.injected_faults.append(fault_record)
                return {
                    "status": "error",
                    "error_code": "prompt_blocked",
                    "model": "mock-gemini-flash",
                    "error_details": "Injected model armor content filter block",
                }

            # Case D: Malformed Agent Response
            if self.fault_type == "malformed_response":
                self.injected_faults.append(fault_record)
                return {"corrupted_response": None, "invalid_json": True}

            # Case E: Direct Runtime Execution Crash
            if self.fault_type == "execution_failure":
                self.injected_faults.append(fault_record)
                raise RuntimeError(f"Simulated unhandled runtime crash in specialist {agent_id}")

            # Fallback
            return await original_reason(task, context)

        return interceptor

    def get_injected_faults(self) -> list[dict[str, Any]]:
        """Returns all fault events recorded during execution."""
        return list(self.injected_faults)

    def verify_recovery(self) -> bool:
        """Verifies if recoverable faults achieved recovery."""
        if not self.injected_faults:
            return True
        if not self.recoverable:
            # For non-recoverable faults, recovery is not expected
            return True
        return any(f.get("recovered", False) for f in self.injected_faults)
