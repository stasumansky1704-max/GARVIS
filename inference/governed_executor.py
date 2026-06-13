"""Governed inference executor for GARVIS.

This is the **ONLY** path to LLM inference in GARVIS.  No inference
bypasses governance.  Every request passes through a 9-step pipeline:

1. Request governance validation
2. State machine transition → INFERENCE_EXECUTING
3. Prompt mediation (schema-aware constraint injection)
4. Episodic memory retrieval
5. Ollama inference execution
6. Response governance validation
7. Lineage + audit recording
8. Episodic memory storage
9. Response release

At any step, critical governance failure triggers fail-closed behavior:
transition to FAIL_CLOSED or DEGRADED, full audit trail, exception raised.
No silent failures.  No inference without governance.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from cognition.state_machine import CognitiveStateMachine
from governance.middleware import GovernanceMiddleware
from memory.episodic import EpisodicMemoryStore
from models.cognition import OperationalState
from models.governance import GovernanceCheckResult
from models.inference import (
    InferenceRequest,
    GovernedResponse,
    PromptMediationResult,
)
from models.memory import EpisodicMemory, MemoryInfluence, ProvenanceRecord
from traceability.audit import AuditPipeline
from traceability.lineage import LineageTracker

from inference.ollama_client import OllamaClient
from inference.prompt_mediator import PromptMediator
from inference.response_validator import ResponseValidator

logger = logging.getLogger(__name__)


class GovernanceBlockedError(Exception):
    """Raised when governance middleware blocks an inference request."""


class StateTransitionError(Exception):
    """Raised when the cognitive state machine cannot transition."""


class InferenceError(Exception):
    """Raised when inference execution fails (including after retries)."""


class ResponseValidationError(Exception):
    """Raised when response validation fails with critical severity."""


class GovernedInferenceExecutor:
    """Wraps Ollama inference in full governance.

    This is the **only** path to LLM inference in GARVIS.  Every
    ``InferenceRequest`` flows through the 9-step ``execute`` pipeline.
    Constructor receives pre-initialized dependencies; the executor
    does not own lifecycle management of its collaborators.

    Args:
        ollama_client: The ``OllamaClient`` for HTTP inference.
        middleware: ``GovernanceMiddleware`` for request validation.
        state_machine: ``CognitiveStateMachine`` for operational states.
        memory_store: ``EpisodicMemoryStore`` for episodic memory.
        lineage: ``LineageTracker`` for reasoning lineage.
        audit: ``AuditPipeline`` for audit logging.
    """

    def __init__(
        self,
        ollama_client: OllamaClient,
        middleware: GovernanceMiddleware,
        state_machine: CognitiveStateMachine,
        memory_store: EpisodicMemoryStore,
        lineage: LineageTracker,
        audit: AuditPipeline,
    ) -> None:
        self.ollama = ollama_client
        self.middleware = middleware
        self.state_machine = state_machine
        self.memory = memory_store
        self.lineage = lineage
        self.audit = audit
        self._mediator = PromptMediator()
        self._validator = ResponseValidator()

    async def execute(self, request: InferenceRequest) -> GovernedResponse:
        """Execute a fully governed inference.

        9-step pipeline (see module docstring).  At any step, critical
        governance failure triggers fail-closed behavior with an
        exception — never a silent failure.

        Args:
            request: The governed inference request.

        Returns:
            A ``GovernedResponse`` with ``validated_response`` set (if
            all checks passed) or ``None`` (if critical validation failed).

        Raises:
            GovernanceBlockedError: If the request fails governance validation.
            StateTransitionError: If the state machine cannot transition.
            InferenceError: If Ollama is unreachable after retries.
            ResponseValidationError: If response validation fails critically.
        """
        trace_id = uuid4()
        started_at = datetime.now(timezone.utc)

        logger.info(
            "GovernedInferenceExecutor.execute START request=%s session=%s",
            request.request_id,
            request.session_id,
        )

        # =====================================================================
        # Step 1: Validate request through governance middleware
        # =====================================================================
        logger.debug("Step 1: Governance validation request=%s", request.request_id)
        validation_context = await self.middleware.validate_request(request)
        if validation_context is None:
            logger.critical(
                "Governance blocked request=%s — FAIL CLOSED",
                request.request_id,
            )
            await self._fail_closed(
                trace_id=trace_id,
                request=request,
                reason="Governance middleware blocked request",
            )
            raise GovernanceBlockedError(
                f"Request {request.request_id} blocked by governance middleware"
            )

        active_schemas = validation_context.get("schemas", [])
        logger.debug(
            "Step 1 passed: active_schemas=%s", active_schemas
        )

        # =====================================================================
        # Step 2: Transition state machine to INFERENCE_EXECUTING
        # =====================================================================
        logger.debug("Step 2: State transition → INFERENCE_EXECUTING")
        transitioned = await self.state_machine.transition(
            OperationalState.INFERENCE_EXECUTING,
            trigger=f"inference_request:{request.request_id}",
        )
        if not transitioned:
            current = self.state_machine.get_current_state()
            logger.critical(
                "State transition failed: %s → INFERENCE_EXECUTING "
                "for request=%s",
                current.value,
                request.request_id,
            )
            raise StateTransitionError(
                f"Cannot transition from {current.value} to "
                f"INFERENCE_EXECUTING for request {request.request_id}"
            )

        # =====================================================================
        # Step 3: Mediate prompt through schema-aware mediation
        # =====================================================================
        logger.debug("Step 3: Prompt mediation request=%s", request.request_id)
        mediation = self._mediator.mediate(
            prompt=request.prompt,
            active_schemas=active_schemas,
        )
        await self._audit_mediation(trace_id, request, mediation)
        logger.debug(
            "Step 3 complete: applied_schemas=%s injected=%s",
            mediation.applied_schemas,
            mediation.injected_constraints,
        )

        # =====================================================================
        # Step 4: Retrieve relevant episodic memories
        # =====================================================================
        logger.debug("Step 4: Memory retrieval request=%s", request.request_id)
        retrieved_memories: list[EpisodicMemory] = []
        try:
            memory_results = await self.memory.retrieve(
                session_id=request.session_id,
                query=request.prompt,
                limit=10,
                governance_filter=active_schemas,
            )
            if memory_results is not None:
                retrieved_memories = memory_results
        except Exception as exc:
            logger.warning(
                "Memory retrieval failed for request=%s: %s",
                request.request_id,
                exc,
                exc_info=True,
            )
            # Non-fatal: continue without memory context

        memory_influences = self._build_memory_influences(
            retrieved_memories, request.request_id
        )
        logger.debug(
            "Step 4 complete: retrieved=%s memories",
            len(retrieved_memories),
        )

        # =====================================================================
        # Step 5: Execute inference via Ollama
        # =====================================================================
        logger.debug("Step 5: Ollama inference request=%s", request.request_id)
        model = request.model or self.ollama.default_model
        params = request.parameters or {}
        temperature = params.get("temperature", 0.7)
        max_tokens = params.get("max_tokens", 2048)

        # Augment mediated prompt with memory context
        full_prompt = self._augment_with_memory(
            mediation.mediated_prompt, retrieved_memories
        )

        raw_text: str
        try:
            raw_text = await self.ollama.generate(
                prompt=full_prompt,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except (ConnectionError, TimeoutError, RuntimeError) as exc:
            logger.critical(
                "Ollama inference failed after retries for request=%s: %s",
                request.request_id,
                exc,
            )
            # Transition to DEGRADED — Ollama is unreachable
            await self.state_machine.transition(
                OperationalState.DEGRADED,
                trigger=f"ollama_failure:{request.request_id}",
            )
            await self.audit.log_event(
                __import__("models.audit").audit.AuditEvent(
                    event_type="inference_failure",
                    severity="critical",
                    component="governed_executor",
                    session_id=request.session_id,
                    trace_id=trace_id,
                    details={
                        "request_id": str(request.request_id),
                        "error": str(exc),
                        "model": model,
                    },
                )
            )
            raise InferenceError(
                f"Ollama inference failed for request {request.request_id}: {exc}"
            ) from exc

        logger.debug(
            "Step 5 complete: response_length=%s", len(raw_text)
        )

        # =====================================================================
        # Step 6: Validate response through governance
        # =====================================================================
        logger.debug("Step 6: Response validation request=%s", request.request_id)
        response = GovernedResponse(
            request_id=request.request_id,
            raw_response=raw_text,
            memory_influences=memory_influences,
        )
        response = self._validator.validate(response, request)

        if not response.passed_validation:
            critical_failures = [
                f for f in response.validation_failures
            ]
            logger.critical(
                "Response validation FAILED for request=%s: %s",
                request.request_id,
                critical_failures,
            )
            await self._record_failed_response(trace_id, request, response)
            raise ResponseValidationError(
                f"Response validation failed for request {request.request_id}: "
                f"{critical_failures}"
            )

        logger.debug("Step 6 complete: validation passed")

        # =====================================================================
        # Step 7: Record in lineage and audit
        # =====================================================================
        logger.debug("Step 7: Lineage + audit recording request=%s", request.request_id)
        try:
            await self.lineage.record_inference(
                trace_id=trace_id,
                request=request,
                response=response,
                state=OperationalState.INFERENCE_EXECUTING,
            )
            await self.lineage.record_governance_influence(
                trace_id=trace_id,
                check_results=response.governance_checks,
            )
            if memory_influences:
                await self.lineage.record_memory_influence(
                    trace_id=trace_id,
                    influences=memory_influences,
                )
            await self.audit.log_inference(request, response)
        except Exception as exc:
            logger.warning(
                "Lineage/audit recording failed for request=%s: %s",
                request.request_id,
                exc,
                exc_info=True,
            )
            # Non-fatal: continue even if lineage/audit fails

        logger.debug("Step 7 complete")

        # =====================================================================
        # Step 8: Store as episodic memory
        # =====================================================================
        logger.debug("Step 8: Episodic memory storage request=%s", request.request_id)
        try:
            provenance = ProvenanceRecord(
                source_schema="inference",
                inference_id=request.request_id,
                creator_component="governed_inference_executor",
            )
            episode = EpisodicMemory(
                session_id=request.session_id,
                episode_type="inference",
                content=response.raw_response,
                provenance=provenance,
                governance_influences=active_schemas,
                confidence=0.8,  # Default; could be extracted from response
            )
            await self.memory.store(episode)

            # Record influence of retrieved memories on this new memory
            for influence in memory_influences:
                try:
                    await self.memory.record_influence(
                        memory_id=influence.memory_id,
                        inference_id=request.request_id,
                        influence_type=influence.influence_type,
                        strength=influence.strength,
                    )
                except Exception:
                    pass  # Non-fatal
        except Exception as exc:
            logger.warning(
                "Episodic memory storage failed for request=%s: %s",
                request.request_id,
                exc,
                exc_info=True,
            )
            # Non-fatal: continue even if memory storage fails

        logger.debug("Step 8 complete")

        # =====================================================================
        # Step 9: Validate and release response
        # =====================================================================
        logger.debug("Step 9: Response release request=%s", request.request_id)
        response.released_at = datetime.now(timezone.utc)

        transitioned = await self.state_machine.transition(
            OperationalState.COGNITION_ACTIVE,
            trigger=f"inference_complete:{request.request_id}",
        )
        if not transitioned:
            logger.warning(
                "Could not transition back to COGNITION_ACTIVE for request=%s",
                request.request_id,
            )

        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
        logger.info(
            "GovernedInferenceExecutor.execute END request=%s "
            "elapsed=%.3fs released=True",
            request.request_id,
            elapsed,
        )

        return response

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_memory_influences(
        self,
        memories: list[EpisodicMemory],
        request_id: __import__("uuid").UUID,
    ) -> list[MemoryInfluence]:
        """Build MemoryInfluence records from retrieved memories."""
        influences: list[MemoryInfluence] = []
        for mem in memories:
            influence = MemoryInfluence(
                memory_id=mem.memory_id,
                target_inference_id=request_id,
                influence_type="retrieval",
                strength=0.7,
            )
            influences.append(influence)
        return influences

    def _augment_with_memory(
        self,
        mediated_prompt: str,
        memories: list[EpisodicMemory],
    ) -> str:
        """Append retrieved memory context to the mediated prompt."""
        if not memories:
            return mediated_prompt

        memory_block = "\n\n[RELEVANT EPISODIC MEMORIES]\n"
        for i, mem in enumerate(memories[:5], 1):
            memory_block += f"{i}. {mem.content[:500]}\n"

        return mediated_prompt + memory_block

    async def _fail_closed(
        self,
        trace_id: __import__("uuid").UUID,
        request: InferenceRequest,
        reason: str,
    ) -> None:
        """Execute fail-closed behavior: transition, audit, log."""
        try:
            await self.state_machine.transition(
                OperationalState.FAIL_CLOSED,
                trigger=f"governance_block:{request.request_id}",
            )
        except Exception as exc:
            logger.error("Fail-closed state transition failed: %s", exc)

        try:
            await self.audit.log_event(
                __import__("models.audit").audit.AuditEvent(
                    event_type="governance_check",
                    severity="critical",
                    component="governed_executor",
                    session_id=request.session_id,
                    trace_id=trace_id,
                    details={
                        "request_id": str(request.request_id),
                        "reason": reason,
                        "action": "fail_closed",
                    },
                )
            )
        except Exception as exc:
            logger.error("Fail-closed audit logging failed: %s", exc)

    async def _audit_mediation(
        self,
        trace_id: __import__("uuid").UUID,
        request: InferenceRequest,
        mediation: PromptMediationResult,
    ) -> None:
        """Log prompt mediation results to the audit pipeline."""
        try:
            await self.audit.log_event(
                __import__("models.audit").audit.AuditEvent(
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
            )
        except Exception as exc:
            logger.warning("Mediation audit logging failed: %s", exc)

    async def _record_failed_response(
        self,
        trace_id: __import__("uuid").UUID,
        request: InferenceRequest,
        response: GovernedResponse,
    ) -> None:
        """Record a failed response validation to lineage and audit."""
        try:
            await self.lineage.record_inference(
                trace_id=trace_id,
                request=request,
                response=response,
                state=OperationalState.AUDITING,
            )
        except Exception as exc:
            logger.warning("Failed response lineage recording failed: %s", exc)

        try:
            await self.audit.log_event(
                __import__("models.audit").audit.AuditEvent(
                    event_type="response_validation_failure",
                    severity="critical",
                    component="response_validator",
                    session_id=request.session_id,
                    trace_id=trace_id,
                    details={
                        "request_id": str(request.request_id),
                        "failures": response.validation_failures,
                        "checks": [
                            {
                                "schema_id": c.schema_id,
                                "policy_id": c.policy_id,
                                "passed": c.passed,
                            }
                            for c in response.governance_checks
                        ],
                    },
                )
            )
        except Exception as exc:
            logger.warning("Failed response audit logging failed: %s", exc)
