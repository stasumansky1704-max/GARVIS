"""Governance Middleware — governance/middleware.py

Middleware that wraps all cognition operations.
Every cognition pathway passes through here.
This is the governance firewall.

Per the SPEC section 5.4.

None = FAIL-CLOSED. Governance blocked the operation.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from models.governance import GovernanceCheckResult, GovernanceViolation
from models.cognition import StateTransition
from models.inference import InferenceRequest, GovernedResponse
from models.memory import EpisodicMemory
from governance.validator import RuntimeValidator
from governance.enforcer import EnforcementEngine

logger = logging.getLogger("garvis.governance.middleware")


class GovernanceMiddleware:
    """Middleware that wraps all cognition operations.

    Every cognition pathway passes through here before execution.
    This is the governance firewall — the final gatekeeper.

    Key principle: None = FAIL-CLOSED. If governance blocks an operation,
    None is returned and the operation halts.
    """

    def __init__(
        self,
        validator: RuntimeValidator,
        enforcer: EnforcementEngine,
    ) -> None:
        self.validator = validator
        self.enforcer = enforcer
        self._active = False

    # ── Lifecycle ─────────────────────────────────────────────────

    def activate(self) -> None:
        """Activate the middleware. Governance is now enforced.

        All subsequent cognition operations will be validated.
        """
        self._active = True
        logger.critical(
            "GovernanceMiddleware ACTIVATED — all cognition operations are now governed"
        )

    def deactivate(self) -> None:
        """Deactivate the middleware. Governance checks are paused.

        WARNING: This is an emergency operation only.
        Requires operator authorization.
        """
        self._active = False
        logger.critical(
            "GovernanceMiddleware DEACTIVATED — cognition operations are UNGOVERNED. "
            "This should only be used for emergency maintenance."
        )

    @property
    def is_active(self) -> bool:
        """Whether the middleware is currently active."""
        return self._active

    # ── Inference Request Processing ──────────────────────────────

    async def process_inference_request(
        self, request: InferenceRequest
    ) -> InferenceRequest | None:
        """Process an inference request through governance.

        Validates the request against all active governance schemas.
        Returns the original request (allowed to proceed) or None (blocked).

        None = fail-closed. The request is NOT processed.
        """
        if not self._active:
            logger.warning(
                "Middleware is INACTIVE — allowing inference request %s without governance",
                request.request_id,
            )
            return request

        logger.debug(
            "Processing inference request %s through governance middleware",
            request.request_id,
        )

        # Run validation
        results = self.validator.validate_inference_request(request)

        # Check for critical failures
        if self._has_critical_failure(results):
            # Build violation record and enforce
            violation = self._build_violation_from_results(results, request.request_id)
            self.enforcer.enforce_violation(violation)
            logger.critical(
                "Inference request %s BLOCKED by governance (critical violation)",
                request.request_id,
            )
            return None  # FAIL-CLOSED

        # Log warnings if any
        warning_count = sum(
            1 for r in results if not r.passed and r.violation and r.violation.severity == "warning"
        )
        if warning_count > 0:
            logger.warning(
                "Inference request %s has %d warning(s) but proceeding",
                request.request_id,
                warning_count,
            )

        logger.info(
            "Inference request %s APPROVED by governance (%d checks passed)",
            request.request_id,
            sum(1 for r in results if r.passed),
        )
        return request

    # ── Inference Response Processing ─────────────────────────────

    async def process_inference_response(
        self, response: GovernedResponse
    ) -> GovernedResponse | None:
        """Process an inference response through governance.

        Validates the response against all active governance schemas.
        Returns the validated response (allowed to release) or None (blocked).

        None = fail-closed. Response is NOT released.
        """
        if not self._active:
            logger.warning(
                "Middleware is INACTIVE — allowing response %s without governance",
                response.response_id,
            )
            return response

        logger.debug(
            "Processing inference response %s through governance middleware",
            response.response_id,
        )

        # Run validation
        results = self.validator.validate_response(response)

        # Check for critical failures
        if self._has_critical_failure(results):
            violation = self._build_violation_from_results(results, response.response_id)
            self.enforcer.enforce_violation(violation)
            logger.critical(
                "Inference response %s BLOCKED by governance — NOT released",
                response.response_id,
            )
            return None  # FAIL-CLOSED

        # Mark response as ready for release
        response.passed_validation = True

        logger.info(
            "Inference response %s APPROVED by governance — ready for release",
            response.response_id,
        )
        return response

    # ── Memory Store Processing ───────────────────────────────────

    async def process_memory_store(
        self, memory: EpisodicMemory
    ) -> EpisodicMemory | None:
        """Process a memory storage operation.

        Returns memory with governance annotations, or None if blocked.
        """
        if not self._active:
            logger.warning(
                "Middleware is INACTIVE — allowing memory store %s without governance",
                memory.memory_id,
            )
            return memory

        logger.debug(
            "Processing memory store %s through governance middleware",
            memory.memory_id,
        )

        # Run validation
        results = self.validator.validate_memory_operation("store", memory)

        # Check for critical failures
        if self._has_critical_failure(results):
            violation = self._build_violation_from_results(results, memory.memory_id)
            self.enforcer.enforce_violation(violation)
            logger.critical(
                "Memory store %s BLOCKED by governance",
                memory.memory_id,
            )
            return None  # FAIL-CLOSED

        # Annotate memory with active governance schemas
        active_schema_ids = self.validator.registry.get_active_schema_ids()
        memory.governance_influences = active_schema_ids

        logger.info(
            "Memory store %s APPROVED by governance",
            memory.memory_id,
        )
        return memory

    # ── Memory Retrieval Processing ───────────────────────────────

    async def process_memory_retrieval(
        self, query: str, session_id: UUID
    ) -> list[EpisodicMemory] | None:
        """Process a memory retrieval.

        Returns governed retrieval results, or None if blocked.

        Note: The actual retrieval happens in the memory layer.
        This method validates that retrieval is allowed and applies
        governance filtering to results.
        """
        if not self._active:
            logger.warning(
                "Middleware is INACTIVE — allowing memory retrieval without governance"
            )
            return []

        logger.debug(
            "Processing memory retrieval for session %s through governance",
            session_id,
        )

        # For retrieval validation, we check the operation is allowed
        # Build a minimal memory object for validation
        from models.memory import EpisodicMemory, ProvenanceRecord

        temp_memory = EpisodicMemory(
            session_id=session_id,
            episode_type="retrieval",
            content=query,
            provenance=ProvenanceRecord(
                source_schema="retrieval_scoring",
                creator_component="governance_middleware",
            ),
        )

        results = self.validator.validate_memory_operation("retrieve", temp_memory)

        if self._has_critical_failure(results):
            violation = self._build_violation_from_results(results, session_id)
            self.enforcer.enforce_violation(violation)
            logger.critical(
                "Memory retrieval BLOCKED for session %s",
                session_id,
            )
            return None  # FAIL-CLOSED

        logger.info(
            "Memory retrieval APPROVED for session %s",
            session_id,
        )
        # Return empty list — actual retrieval is done by memory layer
        # This indicates the retrieval is APPROVED to proceed
        return []

    # ── State Transition Processing ───────────────────────────────

    async def process_state_transition(
        self, transition: StateTransition
    ) -> StateTransition | None:
        """Process a state transition request.

        Returns approved transition, or None if blocked.
        """
        if not self._active:
            logger.warning(
                "Middleware is INACTIVE — allowing state transition without governance"
            )
            return transition

        logger.debug(
            "Processing state transition %s -> %s (trigger: %s)",
            transition.from_state.value,
            transition.to_state.value,
            transition.trigger,
        )

        # Run validation
        results = self.validator.validate_state_transition(transition)

        # Check for critical failures
        if self._has_critical_failure(results):
            violation = self._build_violation_from_results(results, transition.transition_id)
            self.enforcer.enforce_violation(violation)
            logger.critical(
                "State transition %s -> %s BLOCKED by governance",
                transition.from_state.value,
                transition.to_state.value,
            )
            return None  # FAIL-CLOSED

        # Mark as governance-approved
        transition.governance_check = True

        logger.info(
            "State transition %s -> %s APPROVED by governance",
            transition.from_state.value,
            transition.to_state.value,
        )
        return transition

    # ── Internal helpers ──────────────────────────────────────────

    def _has_critical_failure(self, results: list[GovernanceCheckResult]) -> bool:
        """Check if results contain any critical failure."""
        for result in results:
            if not result.passed and result.violation:
                if result.violation.severity == "critical":
                    return True
        return False

    def _build_violation_from_results(
        self,
        results: list[GovernanceCheckResult],
        context_id: Any,
    ) -> GovernanceViolation:
        """Build a primary violation from a set of check results.

        Returns the first critical violation found, or the first failed check.
        """
        # Find first critical failure
        for result in results:
            if not result.passed and result.violation and result.violation.severity == "critical":
                # Enhance context
                result.violation.context["blocked_context_id"] = str(context_id)
                result.violation.context["total_checks"] = len(results)
                result.violation.context["failed_checks"] = sum(
                    1 for r in results if not r.passed
                )
                return result.violation

        # Fallback: return first any failure
        for result in results:
            if not result.passed and result.violation:
                result.violation.context["blocked_context_id"] = str(context_id)
                return result.violation

        # Should not reach here — no failure found
        return GovernanceViolation(
            schema_id="governance_middleware",
            policy_id="fallback_violation",
            severity="critical",
            description="Governance middleware detected unspecified violation",
            context={"blocked_context_id": str(context_id)},
        )
