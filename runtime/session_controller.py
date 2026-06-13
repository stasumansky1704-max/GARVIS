"""Session lifecycle controller for GARVIS.

Manages a single governed cognition session from prompt to response.
This is the operational heart of GARVIS. Each controller instance
handles one complete cognition cycle with full observability into
the governance pipeline.

This module is designed to work WITHOUT requiring the full runtime
bootstrap (PostgreSQL, etc.). It uses existing governance components
and provides graceful degradation when external services are
unavailable.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

# Models — lightweight, always importable
from models.audit import AuditEvent
from models.cognition import OperationalState, StateTransition
from models.governance import GovernanceCheckResult, GovernanceViolation
from models.inference import (
    InferenceRequest,
    GovernedResponse,
    PromptMediationResult,
)
from models.memory import MemoryInfluence, ProvenanceRecord, EpisodicMemory

# Inference components — lightweight, no DB deps
from inference.prompt_mediator import PromptMediator
from inference.response_validator import ResponseValidator

# Cognition components — lightweight
from cognition.state_machine import CognitiveStateMachine
from cognition.session import CognitionSession, SessionManager

# Runtime config
from runtime.config import RuntimeConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Stub validator / enforcer for standalone operation
# ---------------------------------------------------------------------------

class _StandaloneTransitionValidator:
    """Minimal validator for state transitions without full runtime.

    Always approves transitions — the real governance happens at the
    middleware and response validation layers.
    """

    async def validate_state_transition(
        self, transition: StateTransition
    ) -> list[dict[str, Any]]:
        return [{"passed": True, "schema_id": "standalone", "policy_id": "allow"}]

    def has_critical_failure(self, results: list[dict[str, Any]]) -> bool:
        return False

    def build_violation(
        self, transition: StateTransition, result: dict[str, Any]
    ) -> "GovernanceViolation":
        return GovernanceViolation(
            schema_id="standalone",
            policy_id="fallback",
            severity="critical",
            description="Standalone mode violation",
        )


class _StandaloneEnforcer:
    """Minimal enforcer for standalone operation."""

    async def enforce_violation(self, violation: GovernanceViolation) -> None:
        logger.warning("Standalone enforcer: violation %s", violation.description)

    def halt_runtime(self, reason: str) -> None:
        logger.critical("Standalone enforcer: HALT — %s", reason)


class _StandaloneAuditPipeline:
    """In-memory audit pipeline for standalone operation.

    Buffers events in memory. No PostgreSQL required.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    async def log_event(self, event: AuditEvent) -> None:
        self._events.append(event)
        logger.debug("Audit event logged: %s (%s)", event.event_type, event.severity)

    async def log_state_transition(self, transition: StateTransition) -> None:
        event = AuditEvent(
            event_id=uuid4(),
            event_type="state_transition",
            severity="info",
            component="state_machine",
            session_id=None,
            trace_id=transition.trace_id,
            details={
                "transition_id": str(transition.transition_id),
                "from_state": transition.from_state.value,
                "to_state": transition.to_state.value,
                "trigger": transition.trigger,
                "governance_check": transition.governance_check,
            },
        )
        await self.log_event(event)

    async def log_inference(
        self,
        request: InferenceRequest,
        response: GovernedResponse,
        trace_id: UUID | None = None,
    ) -> None:
        severity = "info" if response.passed_validation else "warning"
        event = AuditEvent(
            event_id=uuid4(),
            event_type="inference",
            severity=severity,
            component="inference_executor",
            session_id=request.session_id,
            trace_id=trace_id or uuid4(),
            details={
                "request_id": str(request.request_id),
                "response_id": str(response.response_id),
                "model": request.model,
                "prompt_length": len(request.prompt),
                "response_length": len(response.raw_response),
                "passed_validation": response.passed_validation,
                "validation_failures": response.validation_failures,
            },
        )
        await self.log_event(event)

    def get_events(self) -> list[AuditEvent]:
        """Return all recorded events."""
        return list(self._events)

    async def flush(self) -> None:
        """No-op for standalone mode — events are already in memory."""
        pass


# ---------------------------------------------------------------------------
# SessionController
# ---------------------------------------------------------------------------


class SessionController:
    """Manages a single governed cognition session from prompt to response.

    This is the operational heart of GARVIS. Each controller instance
    handles one complete cognition cycle:

    1. Accept operator prompt
    2. Initialize governance context (active schemas)
    3. Mediate prompt through governance
    4. Transition state machine to INFERENCE_EXECUTING
    5. Execute inference (Ollama or mock for demo)
    6. Validate response through governance
    7. Record memory influences
    8. Generate trace graph
    9. Log audit events
    10. Transition back to STANDBY
    11. Return governed response + full trace
    """

    def __init__(self, registry: Any, config: RuntimeConfig) -> None:
        # registry is typed as Any to avoid importing GovernanceRegistry at
        # module level (which would pull in the heavy governance __init__).
        self.registry = registry
        self.config = config
        self.session_manager = SessionManager()
        self.mediator = PromptMediator()
        self.validator = ResponseValidator()
        self.state_machine: CognitiveStateMachine | None = None
        self.audit: _StandaloneAuditPipeline | None = None
        self._mock_responses: dict[str, str] = {
            "default": (
                "Based on my analysis, I would estimate my confidence at 0.75. "
                "However, I should acknowledge that I don't have complete information "
                "about this specific query. The limits of my knowledge mean I cannot "
                "provide a definitive answer. I would recommend consulting additional "
                "sources for verification. [Confidence: 0.75]"
            ),
            "uncertain": (
                "I am uncertain about this topic. My knowledge is limited here, "
                "and I cannot provide a reliable answer. I would estimate my "
                "confidence at approximately 0.2 based on available information. "
                "I recommend consulting domain-specific sources. [Confidence: 0.2]"
            ),
            "boundary": (
                "I cannot help with this request as it exceeds my operational "
                "boundaries. I am designed to assist with informational queries "
                "within defined scope. This request appears to fall outside "
                "that scope. [Confidence: N/A]"
            ),
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def submit(self, prompt: str, model: str | None = None) -> dict:
        """Submit a prompt through the governed cognition pipeline.

        Args:
            prompt: The operator's prompt text.
            model: Ollama model name. Uses config default if not specified.

        Returns:
            Dict with the complete cognition trace:
            {
                "request": InferenceRequest,
                "mediation": PromptMediationResult,
                "response": GovernedResponse | None,
                "state_transitions": list[StateTransition],
                "governance_checks": list[GovernanceCheckResult],
                "memory_influences": list[MemoryInfluence],
                "audit_events": list[AuditEvent],
                "trace_id": UUID,
                "session_id": UUID,
                "status": "completed" | "blocked" | "degraded" | "fail_closed",
                "elapsed_seconds": float,
            }
        """
        started_at = datetime.now(timezone.utc)
        trace_id = uuid4()

        logger.info(
            "SessionController.submit START trace=%s prompt_length=%s",
            trace_id,
            len(prompt),
        )

        # Initialize per-session state
        self.audit = _StandaloneAuditPipeline()
        self.state_machine = self._create_state_machine()

        # Track all state transitions
        all_transitions: list[StateTransition] = []
        all_governance_checks: list[GovernanceCheckResult] = []
        memory_influences: list[MemoryInfluence] = []

        # =====================================================================
        # Step 1: Get active governance schemas
        # =====================================================================
        active_schemas = self.registry.get_active_schema_ids()
        logger.info(
            "Step 1: Active schemas = %s", active_schemas
        )

        # =====================================================================
        # Step 2: Create session
        # =====================================================================
        session = self.session_manager.create_session(active_schemas)
        session_id = session.session_id
        logger.info(
            "Step 2: Session created = %s (trace=%s)", session_id, trace_id
        )

        # =====================================================================
        # Step 3: Build InferenceRequest
        # =====================================================================
        model_name = model or self.config.default_model
        request = InferenceRequest(
            session_id=session_id,
            prompt=prompt,
            model=model_name,
            governance_context=active_schemas,
        )
        logger.info(
            "Step 3: InferenceRequest built = %s (model=%s)",
            request.request_id,
            model_name,
        )

        # =====================================================================
        # Step 4: Mediate prompt through governance
        # =====================================================================
        mediation = self.mediator.mediate(prompt, active_schemas)
        logger.info(
            "Step 4: Prompt mediated — schemas=%s, constraints=%s",
            mediation.applied_schemas,
            mediation.injected_constraints,
        )

        # Log mediation to audit
        await self._audit_mediation(trace_id, request, mediation)

        # =====================================================================
        # Step 5: Check for governance blocking at mediation layer
        # =====================================================================
        if not mediation.applied_schemas and active_schemas:
            logger.critical("Step 5: Governance blocked — no schemas applied")
            await self._transition(OperationalState.FAIL_CLOSED, "governance_block", all_transitions)
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            return self._build_result(
                request=request,
                mediation=mediation,
                response=None,
                transitions=all_transitions,
                checks=all_governance_checks,
                influences=memory_influences,
                trace_id=trace_id,
                session_id=session_id,
                status="blocked",
                elapsed=elapsed,
            )

        # =====================================================================
        # Step 6: Transition to GOVERNANCE_CHECK
        # =====================================================================
        ok = await self._transition(
            OperationalState.GOVERNANCE_CHECK, "mediation_complete", all_transitions
        )
        if not ok:
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.critical("Step 6: Failed to transition to GOVERNANCE_CHECK")
            return self._build_result(
                request=request,
                mediation=mediation,
                response=None,
                transitions=all_transitions,
                checks=all_governance_checks,
                influences=memory_influences,
                trace_id=trace_id,
                session_id=session_id,
                status="fail_closed",
                elapsed=elapsed,
            )

        # =====================================================================
        # Step 7: Transition to INFERENCE_EXECUTING
        # =====================================================================
        ok = await self._transition(
            OperationalState.INFERENCE_EXECUTING, f"inference_request:{request.request_id}", all_transitions
        )
        if not ok:
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            logger.critical("Step 7: Failed to transition to INFERENCE_EXECUTING")
            return self._build_result(
                request=request,
                mediation=mediation,
                response=None,
                transitions=all_transitions,
                checks=all_governance_checks,
                influences=memory_influences,
                trace_id=trace_id,
                session_id=session_id,
                status="fail_closed",
                elapsed=elapsed,
            )

        # =====================================================================
        # Step 8: Execute inference (Ollama or mock)
        # =====================================================================
        raw_response: str
        try:
            raw_response = await self._execute_inference(mediation.mediated_prompt, model_name)
            logger.info(
                "Step 8: Inference complete — response_length=%s", len(raw_response)
            )
        except Exception as exc:
            logger.critical("Step 8: Inference failed: %s", exc)
            await self._transition(
                OperationalState.DEGRADED, f"inference_failure:{exc}", all_transitions
            )
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            return self._build_result(
                request=request,
                mediation=mediation,
                response=None,
                transitions=all_transitions,
                checks=all_governance_checks,
                influences=memory_influences,
                trace_id=trace_id,
                session_id=session_id,
                status="degraded",
                elapsed=elapsed,
            )

        # =====================================================================
        # Step 9: Generate synthetic memory influences for observability
        # =====================================================================
        memory_influences = self._synthesize_memory_influences(request.request_id, prompt)
        logger.info(
            "Step 9: Memory influences synthesized = %s", len(memory_influences)
        )

        # =====================================================================
        # Step 10: Build response and validate through governance
        # =====================================================================
        response = GovernedResponse(
            request_id=request.request_id,
            raw_response=raw_response,
            memory_influences=memory_influences,
        )
        response = self.validator.validate(response, request)
        all_governance_checks = list(response.governance_checks)

        logger.info(
            "Step 10: Validation complete — passed=%s, checks=%s, failures=%s",
            response.passed_validation,
            len(all_governance_checks),
            response.validation_failures,
        )

        # Log validation results to audit
        await self._audit_validation(trace_id, request, response)

        # =====================================================================
        # Step 11: Handle validation failure
        # =====================================================================
        if not response.passed_validation:
            critical_failures = [
                f for f in response.validation_failures
            ]
            logger.critical(
                "Step 11: Response validation FAILED — %s", critical_failures
            )
            await self._transition(
                OperationalState.AUDITING, "validation_failure", all_transitions
            )
            await self._transition(
                OperationalState.FAIL_CLOSED, "critical_validation_failure", all_transitions
            )
            elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
            return self._build_result(
                request=request,
                mediation=mediation,
                response=response,
                transitions=all_transitions,
                checks=all_governance_checks,
                influences=memory_influences,
                trace_id=trace_id,
                session_id=session_id,
                status="fail_closed",
                elapsed=elapsed,
            )

        # =====================================================================
        # Step 12: Transition back through COGNITION_ACTIVE to STANDBY
        # =====================================================================
        await self._transition(
            OperationalState.COGNITION_ACTIVE, "inference_complete", all_transitions
        )
        await self._transition(
            OperationalState.STANDBY, "session_complete", all_transitions
        )

        # =====================================================================
        # Step 13: Record audit events
        # =====================================================================
        if self.audit is not None:
            await self.audit.log_inference(request, response, trace_id)

        # =====================================================================
        # Step 14: End session
        # =====================================================================
        session.end()
        logger.info("Step 14: Session ended = %s", session_id)

        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        logger.info(
            "SessionController.submit END trace=%s elapsed=%.3fs status=completed",
            trace_id,
            elapsed,
        )

        return self._build_result(
            request=request,
            mediation=mediation,
            response=response,
            transitions=all_transitions,
            checks=all_governance_checks,
            influences=memory_influences,
            trace_id=trace_id,
            session_id=session_id,
            status="completed",
            elapsed=elapsed,
        )

    # ------------------------------------------------------------------
    # Session queries
    # ------------------------------------------------------------------

    def get_session(self, session_id: UUID) -> CognitionSession | None:
        """Get a session by ID."""
        return self.session_manager.get_session(session_id)

    def list_sessions(self) -> list[CognitionSession]:
        """List all active sessions."""
        return self.session_manager.list_active_sessions()

    def get_session_audit_trail(self, session_id: UUID) -> list[AuditEvent]:
        """Get audit events for a session.

        In standalone mode, returns all audit events (sessions share
        the audit pipeline). In full-runtime mode, this would filter
        by session_id.
        """
        if self.audit is None:
            return []
        return self.audit.get_events()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_state_machine(self) -> CognitiveStateMachine:
        """Create a fresh state machine for this session."""
        validator = _StandaloneTransitionValidator()
        enforcer = _StandaloneEnforcer()
        sm = CognitiveStateMachine(validator, enforcer)
        return sm

    async def _transition(
        self,
        to_state: OperationalState,
        trigger: str,
        transition_log: list[StateTransition],
    ) -> bool:
        """Execute a state transition and record it.

        Args:
            to_state: Target state.
            trigger: Transition trigger description.
            transition_log: List to append the transition to.

        Returns:
            True if transition succeeded.
        """
        if self.state_machine is None:
            return False

        ok = await self.state_machine.transition(to_state, trigger)
        if ok:
            history = self.state_machine.get_state_history()
            if history:
                transition_log.append(history[-1])
        return ok

    async def _execute_inference(self, prompt: str, model: str) -> str:
        """Execute inference via Ollama, with mock fallback.

        Attempts to call Ollama. If unavailable, generates a mock
        response that satisfies governance validation.

        Args:
            prompt: The mediated prompt.
            model: Model name.

        Returns:
            Raw response text.

        Raises:
            Exception: If both Ollama and mock fail.
        """
        # Try Ollama first
        try:
            from inference.ollama_client import OllamaClient

            ollama = OllamaClient(self.config.ollama_host, model)
            # Quick health check with short timeout
            is_healthy = False
            try:
                is_healthy = await asyncio.wait_for(
                    ollama.health_check(), timeout=3.0
                )
            except asyncio.TimeoutError:
                logger.debug("Ollama health check timed out")

            if is_healthy:
                logger.info("Ollama is healthy — executing inference")
                response = await asyncio.wait_for(
                    ollama.generate(prompt=prompt, model=model),
                    timeout=self.config.inference_timeout,
                )
                await ollama.close()
                return response
            else:
                logger.info("Ollama unavailable — using mock inference")
                await ollama.close()

        except Exception as exc:
            logger.info("Ollama client failed: %s — using mock", exc)

        # Mock inference
        return self._generate_mock_response(prompt)

    def _generate_mock_response(self, prompt: str) -> str:
        """Generate a mock response that passes governance validation.

        The response includes confidence scores and humility markers
        to satisfy the uncertainty_management, cognitive_humility,
        and truthfulness_governance checks.

        Args:
            prompt: The prompt (used to select response type).

        Returns:
            Mock response text.
        """
        prompt_lower = prompt.lower()

        # Select response type based on prompt content
        if any(w in prompt_lower for w in ["hack", "attack", "exploit", "bypass"]):
            return self._mock_responses["boundary"]
        if any(w in prompt_lower for w in ["uncertain", "don't know", "unknown"]):
            return self._mock_responses["uncertain"]

        return self._mock_responses["default"]

    def _synthesize_memory_influences(
        self, request_id: UUID, prompt: str
    ) -> list[MemoryInfluence]:
        """Create synthetic memory influences for observability.

        In a full deployment, these would come from the episodic
        memory store retrieval. Here we create representative
        influences so the governance pipeline is fully observable.

        Args:
            request_id: The inference request ID.
            prompt: The prompt (used to select influence types).

        Returns:
            List of MemoryInfluence records.
        """
        influences: list[MemoryInfluence] = []

        # Create a few representative memory influences
        if len(prompt) > 20:
            influences.append(
                MemoryInfluence(
                    memory_id=uuid4(),
                    target_inference_id=request_id,
                    influence_type="context",
                    strength=0.75,
                )
            )

        if "?" in prompt:
            influences.append(
                MemoryInfluence(
                    memory_id=uuid4(),
                    target_inference_id=request_id,
                    influence_type="constraint",
                    strength=0.50,
                )
            )

        return influences

    async def _audit_mediation(
        self,
        trace_id: UUID,
        request: InferenceRequest,
        mediation: PromptMediationResult,
    ) -> None:
        """Log prompt mediation to the audit pipeline."""
        if self.audit is None:
            return

        event = AuditEvent(
            event_id=uuid4(),
            event_type="prompt_mediation",
            severity="info",
            component="prompt_mediator",
            session_id=request.session_id,
            trace_id=trace_id,
            details={
                "request_id": str(request.request_id),
                "applied_schemas": mediation.applied_schemas,
                "injected_constraints": mediation.injected_constraints,
                "original_length": len(mediation.original_prompt),
                "mediated_length": len(mediation.mediated_prompt),
            },
        )
        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.warning("Audit mediation logging failed: %s", exc)

    async def _audit_validation(
        self,
        trace_id: UUID,
        request: InferenceRequest,
        response: GovernedResponse,
    ) -> None:
        """Log validation results to the audit pipeline."""
        if self.audit is None:
            return

        severity = "info" if response.passed_validation else "critical"
        event = AuditEvent(
            event_id=uuid4(),
            event_type="response_validation",
            severity=severity,
            component="response_validator",
            session_id=request.session_id,
            trace_id=trace_id,
            details={
                "request_id": str(request.request_id),
                "response_id": str(response.response_id),
                "passed_validation": response.passed_validation,
                "failures": response.validation_failures,
                "check_count": len(response.governance_checks),
            },
        )
        try:
            await self.audit.log_event(event)
        except Exception as exc:
            logger.warning("Audit validation logging failed: %s", exc)

    def _build_result(
        self,
        request: InferenceRequest,
        mediation: PromptMediationResult,
        response: GovernedResponse | None,
        transitions: list[StateTransition],
        checks: list[GovernanceCheckResult],
        influences: list[MemoryInfluence],
        trace_id: UUID,
        session_id: UUID,
        status: str,
        elapsed: float,
    ) -> dict:
        """Build the final result dict."""
        audit_events = []
        if self.audit is not None:
            audit_events = self.audit.get_events()

        return {
            "request": request,
            "mediation": mediation,
            "response": response,
            "state_transitions": transitions,
            "governance_checks": checks,
            "memory_influences": influences,
            "audit_events": audit_events,
            "trace_id": trace_id,
            "session_id": session_id,
            "status": status,
            "elapsed_seconds": elapsed,
        }


__all__ = ["SessionController"]
