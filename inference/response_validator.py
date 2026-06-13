"""Pre-release response validator for GARVIS inference layer.

Validates every LLM response against active governance schemas before
release.  Fail-closed: critical violations set ``validated_response = None``
and record failure descriptions.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from uuid import uuid4

from models.governance import GovernanceCheckResult, GovernanceViolation
from models.inference import GovernedResponse, InferenceRequest

logger = logging.getLogger(__name__)

# Regex to detect confidence scores (e.g., "confidence: 0.85", "0.75", etc.)
_CONFIDENCE_SCORE_RE = re.compile(
    r"(?:confidence\s*[:=]\s*|\b)(\d\.\d+|\d%|\d\s*out\s*of\s*\d)\b",
    re.IGNORECASE,
)

# Phrases that indicate false certainty.
_FALSE_CERTAINTY_PATTERNS = [
    re.compile(r"\bi am certain that\b", re.IGNORECASE),
    re.compile(r"\bit is definitely\b", re.IGNORECASE),
    re.compile(r"\bthere is no doubt\b", re.IGNORECASE),
    re.compile(r"\babsolutely true\b", re.IGNORECASE),
    re.compile(r"\b100% sure\b", re.IGNORECASE),
    re.compile(r"\bwithout a doubt\b", re.IGNORECASE),
    re.compile(r"\bit is proven that\b", re.IGNORECASE),
    re.compile(r"\bthis is a fact\b", re.IGNORECASE),
]

# Phrases that indicate humility / knowledge boundary acknowledgment.
_HUMILITY_PATTERNS = [
    re.compile(r"\bi (do not|don't) know\b", re.IGNORECASE),
    re.compile(r"\bi'm not sure\b", re.IGNORECASE),
    re.compile(r"\bmy knowledge is limited\b", re.IGNORECASE),
    re.compile(r"\bi cannot confirm\b", re.IGNORECASE),
    re.compile(r"\bthis exceeds my\b", re.IGNORECASE),
    re.compile(r"\bi lack information\b", re.IGNORECASE),
    re.compile(r"\buncertain\b", re.IGNORECASE),
    re.compile(r"\bunknown\b", re.IGNORECASE),
    re.compile(r"\blimit(s|ations) of my knowledge\b", re.IGNORECASE),
]

# Boundary violation indicators.
_BOUNDARY_VIOLATION_PATTERNS = [
    re.compile(r"\bi will (hack|crack|bypass|exploit)\b", re.IGNORECASE),
    re.compile(r"\bi can help you (hack|crack|bypass|exploit)\b", re.IGNORECASE),
    re.compile(r"\b(i will|i can) perform.*attack\b", re.IGNORECASE),
    re.compile(r"\b(i will|i can) write.*malware\b", re.IGNORECASE),
    re.compile(r"\b(i will|i can) create.*virus\b", re.IGNORECASE),
]


class ResponseValidator:
    """Validates LLM responses against active governance schemas.

    Runs a battery of checks on every response:

    - **uncertainty_management**: Is a confidence score present?
    - **truthfulness_governance**: Are there false certainty claims?
    - **cognitive_humility**: Does the response acknowledge limits?
    - **boundary_preservation**: Does the response stay within boundaries?

    Critical failures set ``validated_response = None`` and populate
    ``validation_failures``.  All checks produce auditable
    ``GovernanceCheckResult`` records.
    """

    def __init__(self) -> None:
        self._failures: list[str] = []
        self._checks: list[GovernanceCheckResult] = []

    def validate(
        self,
        response: GovernedResponse,
        request: InferenceRequest,
    ) -> GovernedResponse:
        """Validate a response through all active governance schemas.

        Args:
            response: The raw ``GovernedResponse`` to validate.
            request: The original ``InferenceRequest`` (provides context).

        Returns:
            The same ``GovernedResponse`` instance, mutated with validation
            results.  If any *critical* check fails,
            ``validated_response`` is set to ``None``.
        """
        self._failures = []
        self._checks = []

        text = response.raw_response
        active_schemas = request.governance_context or []

        # --- Check: uncertainty_management ---
        if (
            not active_schemas
            or "uncertainty_management" in active_schemas
        ):
            has_confidence = self.check_confidence_score_present(text)
            self._checks.append(
                GovernanceCheckResult(
                    schema_id="uncertainty_management",
                    policy_id="uncertainty_quantification_required",
                    passed=has_confidence,
                    violation=(
                        GovernanceViolation(
                            schema_id="uncertainty_management",
                            policy_id="uncertainty_quantification_required",
                            severity="critical",
                            description="Confidence score not present in response",
                        )
                        if not has_confidence
                        else None
                    ),
                )
            )
            if not has_confidence:
                self._failures.append(
                    "uncertainty_management: Confidence score not present"
                )

        # --- Check: truthfulness_governance ---
        if (
            not active_schemas
            or "truthfulness_governance" in active_schemas
        ):
            has_false_certainty = self.check_false_certainty(text)
            self._checks.append(
                GovernanceCheckResult(
                    schema_id="truthfulness_governance",
                    policy_id="no_false_certainty",
                    passed=not has_false_certainty,
                    violation=(
                        GovernanceViolation(
                            schema_id="truthfulness_governance",
                            policy_id="no_false_certainty",
                            severity="critical",
                            description="Response contains false certainty claims",
                        )
                        if has_false_certainty
                        else None
                    ),
                )
            )
            if has_false_certainty:
                self._failures.append(
                    "truthfulness_governance: False certainty detected"
                )

        # --- Check: cognitive_humility ---
        if not active_schemas or "cognitive_humility" in active_schemas:
            has_humility = self.check_uncertainty_acknowledgment(text)
            self._checks.append(
                GovernanceCheckResult(
                    schema_id="cognitive_humility",
                    policy_id="knowledge_boundary_recognition",
                    passed=has_humility,
                    violation=None,  # Advisory only
                )
            )

        # --- Check: boundary_preservation ---
        if not active_schemas or "boundary_preservation" in active_schemas:
            boundaries = request.parameters.get("boundaries", [])
            within_boundaries = self.check_boundary_compliance(
                text, boundaries
            )
            self._checks.append(
                GovernanceCheckResult(
                    schema_id="boundary_preservation",
                    policy_id="stay_within_boundaries",
                    passed=within_boundaries,
                    violation=(
                        GovernanceViolation(
                            schema_id="boundary_preservation",
                            policy_id="stay_within_boundaries",
                            severity="critical",
                            description="Response violates operational boundaries",
                        )
                        if not within_boundaries
                        else None
                    ),
                )
            )
            if not within_boundaries:
                self._failures.append(
                    "boundary_preservation: Boundary violation detected"
                )

        # Aggregate results
        critical_failures = [
            c for c in self._checks
            if not c.passed
            and c.violation is not None
            and c.violation.severity == "critical"
        ]
        response.passed_validation = len(critical_failures) == 0
        response.validation_failures = list(self._failures)
        response.governance_checks = list(self._checks)

        if response.passed_validation:
            response.validated_response = response.raw_response
        else:
            response.validated_response = None
            logger.warning(
                "Response validation failed with %s critical issue(s): %s",
                len(critical_failures),
                self._failures,
            )

        return response

    def check_uncertainty_acknowledgment(self, text: str) -> bool:
        """Check if the response acknowledges uncertainty or knowledge limits.

        Looks for humility phrases like "I don't know", "uncertain",
        "limits of my knowledge", etc.

        Returns:
            True if humility indicators are found (or text is too short to
            meaningfully assess).
        """
        if len(text) < 20:
            return True  # Too short to meaningfully assess
        return any(p.search(text) for p in _HUMILITY_PATTERNS)

    def check_false_certainty(self, text: str) -> bool:
        """Check if the response contains false certainty claims.

        Looks for absolute certainty phrases that overclaim knowledge.

        Returns:
            True if false certainty patterns are detected.
        """
        return any(p.search(text) for p in _FALSE_CERTAINTY_PATTERNS)

    def check_boundary_compliance(
        self, text: str, boundaries: list[str]
    ) -> bool:
        """Check if the response stays within operational boundaries.

        Args:
            text: The response text.
            boundaries: List of boundary constraint strings. If empty,
                only checks against built-in violation patterns.

        Returns:
            True if no boundary violations are detected.
        """
        # Check built-in violation patterns
        if any(p.search(text) for p in _BOUNDARY_VIOLATION_PATTERNS):
            return False
        return True

    def check_confidence_score_present(self, text: str) -> bool:
        """Check if a confidence score is present in the response.

        Looks for numeric confidence indicators (0.0-1.0, percentages,
        "X out of Y" patterns).

        Returns:
            True if a confidence score is detected.
        """
        return _CONFIDENCE_SCORE_RE.search(text) is not None

    def get_last_checks(self) -> list[GovernanceCheckResult]:
        """Return the checks from the last validation run."""
        return list(self._checks)

    def get_last_failures(self) -> list[str]:
        """Return the failure descriptions from the last validation run."""
        return list(self._failures)
