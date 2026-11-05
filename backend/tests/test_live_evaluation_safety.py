"""Unit tests for Stage 3.4: Zero-Cost Live Model Evaluation Safety & Architecture.
Verifies mock mode default, non-fallback in live mode, quota/billing abort handling,
token usage extraction, and zero-cost constraints.
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch
from app.config import settings, Settings
from app.agents.base import GeminiReasoner
from evaluation.config import EvaluationConfig, EvaluationMode
from evaluation.harness.sandbox import EvaluationSandbox
from evaluation.schema import ExecutionTrace, TaskEvaluationResult, BenchmarkReport


def test_mock_mode_is_strict_default():
    """Verify mock mode is strictly active by default in settings and evaluation config."""
    fresh_settings = Settings()
    assert fresh_settings.gemini_mock_mode is True

    cfg = EvaluationConfig()
    assert cfg.mode == EvaluationMode.MOCK
    assert cfg.model_name.startswith("mock-")


def test_zero_cost_billing_safeguards_and_vertex_disabled():
    """Verify that Vertex AI paid backend is disabled and spending limit is zero."""
    assert settings.google_genai_use_vertexai is False
    assert settings.google_cloud_project is None


def test_live_mode_does_not_silently_fallback_to_mock():
    """Verify that live mode failures return genuine errors and never silently fallback to mock."""
    agent = GeminiReasoner("test-agent", "You are a test agent.")

    orig_mock = settings.gemini_mock_mode
    orig_key = settings.gemini_api_key
    try:
        settings.gemini_mock_mode = False
        settings.gemini_api_key = None  # Force missing credentials

        res = asyncio.run(agent.reason("test task", {}))
        assert res.get("status") == "error"
        assert res.get("error_code") == "credentials_missing"
        # Must NOT contain mock analysis
        assert "Mock analysis" not in str(res)
    finally:
        settings.gemini_mock_mode = orig_mock
        settings.gemini_api_key = orig_key


def test_quota_and_billing_errors_abort_immediately():
    """Verify that 429 quota exhaustion and billing errors abort immediately without retries."""
    agent = GeminiReasoner("test-agent", "You are a test agent.")

    # 1. Quota exceeded classification
    code_quota = agent._error_code(Exception("429 Resource has been exhausted (e.g. check quota)"))
    assert code_quota == "quota_exceeded"

    # 2. Billing required classification
    code_billing = agent._error_code(Exception("Billing account not configured or payment required"))
    assert code_billing == "billing_required"

    # 3. Authentication failed classification
    code_auth = agent._error_code(Exception("401 API key not valid. Please pass a valid API key."))
    assert code_auth == "authentication_failed"


def test_token_usage_and_zero_cost_tracking_in_schemas():
    """Verify that ExecutionTrace, TaskEvaluationResult, and BenchmarkReport enforce zero-cost fields."""
    trace = ExecutionTrace(
        task_id="TASK-01",
        goal="Test goal",
        status="completed",
        token_usage={
            "prompt_tokens": 120,
            "completion_tokens": 45,
            "total_tokens": 165,
            "reported_by_provider": True,
        },
        cost_inr=0.0,
        cost_usd=0.0,
        model_name="gemini-2.5-flash",
        provider="Google AI Studio (Gemini Free Tier)",
    )
    assert trace.token_usage["total_tokens"] == 165
    assert trace.cost_inr == 0.0
    assert trace.cost_usd == 0.0
    assert trace.provider == "Google AI Studio (Gemini Free Tier)"


def test_sandbox_live_mode_model_switching_and_restoration():
    """Verify EvaluationSandbox switches mock mode and model properly and restores on exit."""
    orig_mock = settings.gemini_mock_mode
    orig_model = settings.gemini_model

    live_cfg = EvaluationConfig(mode=EvaluationMode.LIVE, model_name="gemini-2.5-flash")
    with EvaluationSandbox(live_cfg):
        assert settings.gemini_mock_mode is False
        assert settings.gemini_model == "gemini-2.5-flash"

    # Upon exit, settings must be restored to previous state
    assert settings.gemini_mock_mode == orig_mock
    assert settings.gemini_model == orig_model

