"""Isolated evaluation sandbox ensuring zero mutation of production data files,
safe environment switching, and seamless compatibility with AgentSphere_OS components.
"""

import hashlib
import json
import random
import sys
import tempfile
from pathlib import Path
from typing import Any

# Ensure backend directory is in sys.path for importing app modules
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.storage import store
from app.registry.agent_registry import registry
from ..config import EvaluationConfig, EvaluationMode


def _compute_file_hash(path: Path) -> str | None:
    """Computes SHA-256 hash of a file if it exists, else returns None."""
    if not path.exists():
        return None
    try:
        content = path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return None


class EvaluationSandbox:
    """Hermetic sandbox manager for evaluation tasks.
    Guarantees that each evaluation run executes in an isolated temporary file store,
    without altering existing user data or requiring cloud credentials."""

    def __init__(self, config: EvaluationConfig | None = None):
        self.config = config or EvaluationConfig()
        self._temp_dir: tempfile.TemporaryDirectory | None = None
        self.sandbox_file: Path | None = None

        # Saved state for restoration
        self._orig_data_file: str | None = None
        self._orig_store_path: Path | None = None
        self._orig_store_client: Any = None
        self._orig_mock_mode: bool | None = None

        # Tracked files to guarantee zero mutation
        self._protected_files = [
            REPO_ROOT / ".data" / "agentsphere.json",
            BACKEND_DIR / ".data" / "agentsphere.json",
        ]
        self._initial_hashes: dict[Path, str | None] = {}

    def __enter__(self) -> "EvaluationSandbox":
        # 1. Snapshot hashes of protected production data files
        for file_path in self._protected_files:
            self._initial_hashes[file_path] = _compute_file_hash(file_path)

        # 2. Save original settings & storage pointers
        self._orig_data_file = settings.local_data_file
        self._orig_store_path = store.path
        self._orig_store_client = store.client
        self._orig_mock_mode = settings.gemini_mock_mode

        # 3. Create isolated temporary directory and store file
        self._temp_dir = tempfile.TemporaryDirectory(prefix="agentsphere_eval_")
        self.sandbox_file = Path(self._temp_dir.name) / "agentsphere_sandbox.json"
        self.sandbox_file.write_text(json.dumps({}), encoding="utf-8")

        # 4. Redirect production storage to isolated sandbox file
        store.path = self.sandbox_file
        store.client = None  # Explicitly disable Firestore connection

        # 5. Apply mock or live mode based on config (mock is default)
        is_mock = self.config.mode == EvaluationMode.MOCK
        settings.gemini_mock_mode = is_mock

        # 6. Apply deterministic seed for reproducibility
        if self.config.seed is not None:
            random.seed(self.config.seed)

        # 7. Seed default agents into the isolated sandbox store
        registry.ensure_defaults()

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # 1. Restore original storage and settings pointers
        if self._orig_store_path is not None:
            store.path = self._orig_store_path
        if self._orig_store_client is not None:
            store.client = self._orig_store_client
        if self._orig_mock_mode is not None:
            settings.gemini_mock_mode = self._orig_mock_mode
        if self._orig_data_file is not None:
            settings.local_data_file = self._orig_data_file

        # 2. Verify that protected production files were never modified
        for file_path, orig_hash in self._initial_hashes.items():
            current_hash = _compute_file_hash(file_path)
            if orig_hash != current_hash:
                raise RuntimeError(
                    f"CRITICAL: Storage isolation failure! Protected file {file_path} was modified "
                    f"during evaluation run (hash changed from {orig_hash} to {current_hash})."
                )

        # 3. Clean up temporary directory
        if self._temp_dir is not None:
            try:
                self._temp_dir.cleanup()
            except Exception:
                pass
            self._temp_dir = None
            self.sandbox_file = None

    async def __aenter__(self) -> "EvaluationSandbox":
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

    # --- Inspection & Query Helpers for Graders and Evaluators ---

    def read_store(self) -> dict[str, Any]:
        """Reads the raw data dictionary from the isolated sandbox store."""
        if not self.sandbox_file or not self.sandbox_file.exists():
            return {}
        try:
            return json.loads(self.sandbox_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def get_collection(self, collection_name: str) -> list[dict[str, Any]]:
        """Retrieves all items from a collection in the isolated sandbox."""
        data = self.read_store()
        col = data.get(collection_name, {})
        return list(col.values()) if isinstance(col, dict) else []

    def get_memories(self) -> list[dict[str, Any]]:
        """Returns all memories recorded inside the isolated sandbox."""
        return self.get_collection("memories")

    def get_memory(self, entity: str) -> dict[str, Any] | None:
        """Retrieves a specific entity's memory from the isolated sandbox."""
        data = self.read_store()
        return data.get("memories", {}).get(entity)

    def get_tasks(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """Returns tasks recorded in the sandbox, optionally filtered by workflow_id."""
        tasks = self.get_collection("tasks")
        if workflow_id:
            return [t for t in tasks if t.get("workflow_id") == workflow_id]
        return tasks

    def get_audit_logs(self, workflow_id: str | None = None) -> list[dict[str, Any]]:
        """Returns audit logs in the sandbox, optionally filtered by workflow_id."""
        logs = self.get_collection("audit_logs")
        if workflow_id:
            return [l for l in logs if l.get("workflow_id") == workflow_id]
        return logs

    def get_security_events(self) -> list[dict[str, Any]]:
        """Returns security events logged inside the isolated sandbox."""
        return self.get_collection("security_events")

    def get_workflows(self) -> list[dict[str, Any]]:
        """Returns all workflows in the isolated sandbox."""
        return self.get_collection("workflows")

