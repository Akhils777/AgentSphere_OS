"""Runtime Resilience & Transient Fault Recovery Policy.
Provides configurable bounded retry logic, exponential backoff,
and strict classification of recoverable transient errors versus
non-recoverable permission/validation/security failures.
"""

import asyncio
from typing import Any
from ..config import settings

# Whitelist of transient error codes and keywords (recoverable)
TRANSIENT_ERROR_CODES = {
    "model_timeout",
    "api_timeout",
    "timeout",
    "quota_exceeded",
    "resource_exhausted",
    "rate_limit",
    "429",
    "503_unavailable",
    "service_unavailable",
    "model_unavailable",
    "connection_error",
    "connection_reset",
    "internal_server_error",
    "provider_error",
    "500",
    "502",
    "503",
    "504",
}

# Strict whitelist of transient Exception types
TRANSIENT_EXCEPTION_TYPES = (
    TimeoutError,
    asyncio.TimeoutError,
    ConnectionError,
    ConnectionResetError,
    ConnectionRefusedError,
    ConnectionAbortedError,
)

# Strict blacklist of non-recoverable error codes and keywords (NEVER retry)
NON_RECOVERABLE_ERROR_CODES = {
    "permission_denied",
    "unauthorized",
    "unauthorized_access",
    "agent_identity_unavailable",
    "prompt_blocked",
    "safety_blocked",
    "invalid_argument",
    "invalid_schema",
    "agent_runtime_missing",
    "no_valid_plan_available",
    "security_violation",
    "forbidden",
}

# Strict blacklist of non-recoverable Exception types (NEVER retry)
NON_RECOVERABLE_EXCEPTION_TYPES = (
    PermissionError,
    ValueError,
    TypeError,
    KeyError,
    IndexError,
)


def classify_error(error: Exception | str) -> str:
    """Classifies an error into a standardized audit category:
    - timeout
    - rate_limit
    - service_unavailable
    - connection_error
    - permission_denied
    - validation_error
    - safety_violation
    - unknown_error
    """
    err_str = str(error).lower()

    if isinstance(error, PermissionError) or any(
        k in err_str for k in ("permission", "unauthorized", "agent_identity_unavailable", "forbidden", "401", "403")
    ):
        return "permission_denied"

    if any(k in err_str for k in ("prompt_blocked", "safety", "injection", "security_violation")):
        return "safety_violation"

    if isinstance(error, (ValueError, TypeError, KeyError, IndexError)) or any(
        k in err_str for k in ("invalid_schema", "agent_runtime_missing", "no_valid_plan")
    ):
        return "validation_error"

    if isinstance(error, (TimeoutError, asyncio.TimeoutError)) or "timeout" in err_str:
        return "timeout"

    if any(k in err_str for k in ("quota", "429", "rate limit", "resource exhausted", "resource_exhausted")):
        return "rate_limit"

    if any(k in err_str for k in ("503", "502", "504", "500", "unavailable", "service_unavailable", "internal_server_error")):
        return "service_unavailable"

    if isinstance(error, ConnectionError) or "connection" in err_str:
        return "connection_error"

    return "unknown_error"


def is_transient_error(error: Exception | str) -> bool:
    """Determines if an error is transient and safe to retry.
    Strictly excludes permission, validation, and security violations.
    """
    if isinstance(error, NON_RECOVERABLE_EXCEPTION_TYPES):
        return False

    err_str = str(error).lower()

    # Explicit exclusion check first
    if any(code in err_str for code in NON_RECOVERABLE_ERROR_CODES):
        return False

    if isinstance(error, TRANSIENT_EXCEPTION_TYPES):
        return True

    # Check transient codes
    if any(code in err_str for code in TRANSIENT_ERROR_CODES):
        return True

    return False


class RetryPolicy:
    """Configurable exponential backoff retry policy for workflow steps."""

    def __init__(
        self,
        max_retries: int | None = None,
        initial_delay_ms: int | None = None,
        backoff_multiplier: float | None = None,
        fast_in_mock: bool | None = None,
    ):
        self.max_retries = max_retries if max_retries is not None else settings.workflow_max_retries
        self.initial_delay_ms = initial_delay_ms if initial_delay_ms is not None else settings.workflow_retry_initial_delay_ms
        self.backoff_multiplier = backoff_multiplier if backoff_multiplier is not None else settings.workflow_retry_backoff_multiplier
        self.fast_in_mock = fast_in_mock if fast_in_mock is not None else settings.workflow_fast_retry_in_mock

    def calculate_delay(self, attempt: int) -> float:
        """Calculates sleep delay in seconds for a retry attempt.
        attempt is 1-indexed (attempt 1 is first retry).
        Returns 0.0 in fast mock mode.
        """
        if self.fast_in_mock and settings.gemini_mock_mode:
            return 0.0

        if attempt < 1:
            return 0.0

        # Backoff: initial_delay * (multiplier ** (attempt - 1))
        delay_ms = self.initial_delay_ms * (self.backoff_multiplier ** (attempt - 1))
        return round(delay_ms / 1000.0, 4)

    def should_retry(self, attempt: int, error: Exception | str) -> bool:
        """Evaluates whether another retry attempt is authorized.
        attempt is the number of retries already performed.
        """
        if attempt >= self.max_retries:
            return False
        return is_transient_error(error)

