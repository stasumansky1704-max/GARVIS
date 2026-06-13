"""
Inference Pydantic models for GARVIS.

Defines governed inference requests, validated responses, and prompt mediation
results. All LLM inference in GARVIS flows through these models -- there is no
inference pathway that bypasses them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from models.governance import GovernanceCheckResult
from models.memory import MemoryInfluence


class InferenceRequest(BaseModel):
    """A governed inference request.

    Every LLM inference in GARVIS is wrapped in an InferenceRequest. The
    request carries its governance context, memory references, and parameters.
    No inference proceeds without governance validation of the request.
    """

    request_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this inference request",
    )
    session_id: UUID = Field(
        description="Identifier of the session this inference belongs to",
    )
    prompt: str = Field(
        description="The prompt text to be sent to the LLM",
    )
    model: str = Field(
        description=(
            "Name of the LLM model to use, e.g. 'llama3.1', 'mistral'"
        ),
    )
    governance_context: list[str] = Field(
        description=(
            "List of governance schema identifiers that must be active and "
            "enforced during this inference"
        ),
    )
    memory_context: list[UUID] = Field(
        default_factory=list,
        description=(
            "List of memory identifiers to include as context for the "
            "inference. Defaults to empty."
        ),
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Inference parameters such as temperature, max_tokens, top_p, "
            "etc. Model-specific parameters are passed through as-is."
        ),
    )
    requested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the inference was requested",
    )


class GovernedResponse(BaseModel):
    """An inference response that has passed governance validation.

    A GovernedResponse wraps the raw LLM output with governance metadata,
    validation results, and memory influences. The response is only released
    to the caller after all governance checks pass.
    """

    response_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for this governed response",
    )
    request_id: UUID = Field(
        description="Identifier of the inference request this responds to",
    )
    raw_response: str = Field(
        description="The raw, unmodified response from the LLM",
    )
    validated_response: str | None = Field(
        default=None,
        description=(
            "The governance-validated response. None if validation failed "
            "and the response cannot be released."
        ),
    )
    governance_checks: list[GovernanceCheckResult] = Field(
        default_factory=list,
        description=(
            "List of all governance check results applied to this response"
        ),
    )
    memory_influences: list[MemoryInfluence] = Field(
        default_factory=list,
        description=(
            "List of memory influences that contributed to this response"
        ),
    )
    passed_validation: bool = Field(
        description=(
            "Whether the response passed all governance validation checks"
        ),
    )
    validation_failures: list[str] = Field(
        default_factory=list,
        description=(
            "List of human-readable descriptions of validation failures, "
            "if any. Empty if validation passed."
        ),
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the response was generated",
    )
    released_at: datetime | None = Field(
        default=None,
        description=(
            "UTC timestamp when the response was released to the caller. "
            "Only set after final governance approval. None until released."
        ),
    )


class PromptMediationResult(BaseModel):
    """Result of schema-aware prompt mediation.

    Before an inference request is sent to the LLM, the prompt is mediated
    through active governance schemas. This model captures the result of
    that mediation: the modified prompt, applied schemas, and any constraints
    that were injected.
    """

    original_prompt: str = Field(
        description="The original prompt before mediation",
    )
    mediated_prompt: str = Field(
        description="The prompt after governance mediation has been applied",
    )
    applied_schemas: list[str] = Field(
        description=(
            "List of governance schema identifiers that were applied during "
            "mediation"
        ),
    )
    injected_constraints: list[str] = Field(
        default_factory=list,
        description=(
            "List of constraint strings that were injected into the prompt "
            "by the governance schemas"
        ),
    )
    mediation_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the mediation was performed",
    )


__all__ = [
    "InferenceRequest",
    "GovernedResponse",
    "PromptMediationResult",
]
