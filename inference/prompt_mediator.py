"""Schema-aware prompt mediator for GARVIS inference layer.

Injects governance constraints into every prompt before inference.
Tracks which schemas were applied and what was injected.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from models.inference import PromptMediationResult

logger = logging.getLogger(__name__)

# Mapping of governance schema IDs to their injected instruction text.
_GOVERNANCE_INSTRUCTIONS: dict[str, str] = {
    "uncertainty_management": (
        "Acknowledge uncertainty where present. "
        "Quantify your confidence on a scale from 0.0 to 1.0. "
        "When evidence is insufficient, state 'unknown'."
    ),
    "truthfulness_governance": (
        "Do not state as fact what is uncertain. "
        "Distinguish between established facts, inferences, and speculation. "
        "Never present uncertain information as certain."
    ),
    "cognitive_humility": (
        "Acknowledge the limits of your knowledge. "
        "When you do not know something, say so clearly. "
        "Do not overstate your capabilities or the reliability of your outputs."
    ),
    "boundary_preservation": (
        "Stay within your declared operational boundaries. "
        "Do not attempt tasks outside your designated scope. "
        "If a request exceeds boundaries, decline and explain why."
    ),
    "provenance_awareness": (
        "Cite sources and reasoning chains where applicable. "
        "Distinguish between your own reasoning and externally provided facts. "
        "Track the provenance of all claims made."
    ),
}

# Suffix reminders (lighter-weight reinforcement).
_GOVERNANCE_SUFFIXES: dict[str, str] = {
    "uncertainty_management": (
        "[Uncertainty Check: Have you acknowledged uncertainty and provided "
        "confidence scores where appropriate?]"
    ),
    "truthfulness_governance": (
        "[Truthfulness Check: Have you distinguished facts from inferences "
        "and avoided false certainty?]"
    ),
    "cognitive_humility": (
        "[Humility Check: Have you acknowledged the limits of your knowledge "
        "and avoided overclaiming?]"
    ),
    "boundary_preservation": (
        "[Boundary Check: Have you stayed within your operational scope "
        "and declined out-of-bounds requests?]"
    ),
    "provenance_awareness": (
        "[Provenance Check: Have you cited sources and tracked the origin "
        "of your claims?]"
    ),
}


class PromptMediator:
    """Mediates prompts by injecting active governance schema constraints.

    Every prompt that passes through the inference layer is wrapped with:
    1. A **governance instruction block** (prefix) containing directives
       from all active schemas.
    2. The **original user prompt** (preserved verbatim).
    3. A **governance reminder block** (suffix) with lightweight checks.

    The mediator tracks which schemas were applied and what constraints
    were injected, making governance influence fully auditable.
    """

    def __init__(self) -> None:
        self._applied_schemas: list[str] = []
        self._injected_constraints: list[str] = []

    def mediate(
        self,
        prompt: str,
        active_schemas: list[str] | None = None,
    ) -> PromptMediationResult:
        """Apply active governance schemas to modify/inject into a prompt.

        Args:
            prompt: The original user prompt.
            active_schemas: List of schema IDs to apply. If empty or None,
                no governance instructions are injected.

        Returns:
            A ``PromptMediationResult`` containing the mediated prompt
            and metadata about what was applied.
        """
        schemas = active_schemas or []
        self._applied_schemas = []
        self._injected_constraints = []

        mediated = self._build_mediated_prompt(prompt, schemas)

        logger.debug(
            "Prompt mediation applied schemas: %s", self._applied_schemas
        )

        return PromptMediationResult(
            original_prompt=prompt,
            mediated_prompt=mediated,
            applied_schemas=list(self._applied_schemas),
            injected_constraints=list(self._injected_constraints),
            mediation_timestamp=datetime.now(timezone.utc),
        )

    def _build_mediated_prompt(
        self, prompt: str, active_schemas: list[str]
    ) -> str:
        """Build the full mediated prompt with prefix, original, and suffix."""
        prefix = self.inject_governance_prefix(prompt, active_schemas)
        suffix = self.inject_governance_suffix(prompt, active_schemas)

        parts: list[str] = []
        if prefix:
            parts.append(prefix)
            parts.append("---")
        parts.append(f"Original: {prompt}")
        if suffix:
            parts.append("---")
            parts.append(suffix)

        return "\n".join(parts)

    def inject_governance_prefix(
        self, prompt: str, active_schemas: list[str]
    ) -> str:
        """Create a governance instruction block prepended to the prompt.

        Args:
            prompt: The original prompt (unused but kept for API symmetry).
            active_schemas: Schema IDs to include.

        Returns:
            The governance instruction block text, or empty string if no
            schemas are active.
        """
        if not active_schemas:
            return ""

        instructions: list[str] = [
            "[GOVERNANCE INSTRUCTIONS — These directives govern your response]"
        ]
        for schema_id in active_schemas:
            if schema_id in _GOVERNANCE_INSTRUCTIONS:
                instructions.append(f"\n[{schema_id}]")
                instructions.append(_GOVERNANCE_INSTRUCTIONS[schema_id])
                self._applied_schemas.append(schema_id)
                self._injected_constraints.append(
                    f"prefix:{schema_id}"
                )

        return "\n".join(instructions)

    def inject_governance_suffix(
        self, prompt: str, active_schemas: list[str]
    ) -> str:
        """Create a governance reminder appended to the prompt.

        Args:
            prompt: The original prompt (unused but kept for API symmetry).
            active_schemas: Schema IDs to include.

        Returns:
            The governance reminder block text, or empty string if no
            schemas are active.
        """
        if not active_schemas:
            return ""

        reminders: list[str] = [
            "[GOVERNANCE REMINDERS — Review before finalizing your response]"
        ]
        for schema_id in active_schemas:
            if schema_id in _GOVERNANCE_SUFFIXES:
                reminders.append(_GOVERNANCE_SUFFIXES[schema_id])
                if schema_id not in self._applied_schemas:
                    self._applied_schemas.append(schema_id)
                self._injected_constraints.append(
                    f"suffix:{schema_id}"
                )

        return "\n".join(reminders)

    def get_applied_schemas(self) -> list[str]:
        """Return the list of schema IDs applied in the last mediation."""
        return list(self._applied_schemas)

    def get_injected_constraints(self) -> list[str]:
        """Return the list of constraints injected in the last mediation.

        Each entry is formatted as ``prefix:<schema_id>`` or
        ``suffix:<schema_id>``.
        """
        return list(self._injected_constraints)
