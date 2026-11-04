"""Deterministic fixture loaders for benchmark tasks.
Loads static ground-truth test data from evaluation/fixtures/data/.
"""

import json
from pathlib import Path
from typing import Any

FIXTURES_DATA_DIR = Path(__file__).resolve().parent / "data"


def load_fixture(filename: str) -> Any:
    """Loads a JSON fixture file from evaluation/fixtures/data/."""
    file_path = FIXTURES_DATA_DIR / filename
    if not file_path.exists():
        raise FileNotFoundError(f"Fixture file not found: {file_path}")
    return json.loads(file_path.read_text(encoding="utf-8"))


def load_suppliers() -> dict[str, Any]:
    """Loads standard vendor baseline datasets."""
    return load_fixture("suppliers.json")


def load_transactions() -> dict[str, Any]:
    """Loads normal and anomalous transaction records."""
    return load_fixture("transactions.json")


def load_security_inputs() -> dict[str, Any]:
    """Loads prompt injection and PII payload fixtures."""
    return load_fixture("security_inputs.json")


def load_unauthorized_scenarios() -> dict[str, Any]:
    """Loads unauthorized access and policy violation fixtures."""
    return load_fixture("unauthorized_scenarios.json")


def load_incomplete_inputs() -> dict[str, Any]:
    """Loads boundary inputs (missing, null, whitespace entities)."""
    return load_fixture("incomplete_inputs.json")


def load_fault_scenarios() -> dict[str, Any]:
    """Loads fault injection specifications (quotas, timeouts, availability)."""
    return load_fixture("fault_scenarios.json")


def load_multiturn_scenarios() -> dict[str, Any]:
    """Loads multi-turn temporal memory reconciliation scenarios."""
    return load_fixture("multiturn_scenarios.json")


def load_grounding_evidence() -> dict[str, Any]:
    """Loads evidence documents and ground-truth facts for hallucination detection."""
    return load_fixture("grounding_evidence.json")

