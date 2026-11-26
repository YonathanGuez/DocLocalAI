import re

from pydantic import BaseModel, Field, field_validator


class Citation(BaseModel):
    chunk_id: int = Field(..., description="Reference to source chunk [N]")
    source_file: str = Field(..., description="Source runbook filename")


class RunbookResponse(BaseModel):
    """Structured LLM output schema for optional JSON-mode generation.

    Not wired into generate_response by default (local/small LLMs may not
    reliably support response_format=json_object), but available for
    deployments that enable `settings.enable_structured_output`.
    """

    answer: str = Field(..., min_length=1, max_length=2000)
    citations: list[Citation] = Field(default_factory=list)
    confidence: str = Field(...)
    missing_info: str | None = None

    @field_validator("confidence")
    @classmethod
    def valid_confidence(cls, v: str) -> str:
        if v not in ("high", "medium", "low"):
            raise ValueError("confidence must be: high, medium, or low")
        return v


_DANGEROUS_COMMAND_PATTERNS = (
    re.compile(r"rm\s+-rf\s+/(?!\w)"),
    re.compile(r"\bmkfs\b"),
    re.compile(r"dd\s+if=\S+\s+of=/dev/"),
    re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:"),  # fork bomb
)

_CREDENTIAL_PATTERNS = (
    re.compile(r"password\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*\S+", re.IGNORECASE),
    re.compile(r"token\s*[:=]\s*[A-Za-z0-9]{20,}", re.IGNORECASE),
)


class BusinessRuleValidator:
    """Post-generation safety checks applied to every LLM response."""

    @staticmethod
    def find_dangerous_command(response: str) -> str | None:
        """Return the offending snippet if the response contains a destructive command."""
        for pattern in _DANGEROUS_COMMAND_PATTERNS:
            match = pattern.search(response)
            if match:
                return match.group(0)
        return None

    @staticmethod
    def find_credential_leak(response: str) -> str | None:
        """Return the offending snippet if the response appears to leak a credential."""
        for pattern in _CREDENTIAL_PATTERNS:
            match = pattern.search(response)
            if match:
                return match.group(0)
        return None
