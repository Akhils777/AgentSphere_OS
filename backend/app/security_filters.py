import re

INJECTION_PATTERNS = [r"ignore\s+(all\s+)?previous", r"reveal\s+.*(password|secret|key)", r"system\s+prompt", r"bypass\s+.*(policy|security)"]
PII_PATTERNS = [r"\b\d{3}-\d{2}-\d{4}\b", r"\b(?:\d[ -]*?){13,16}\b"]


def inspect_input(text: str) -> dict:
    normalized = text.lower()
    injection = any(re.search(pattern, normalized) for pattern in INJECTION_PATTERNS)
    pii = any(re.search(pattern, text) for pattern in PII_PATTERNS)
    return {"safe": not (injection or pii), "prompt_injection": injection, "sensitive_data": pii,
            "reason": "prompt_injection" if injection else "sensitive_data" if pii else None}

