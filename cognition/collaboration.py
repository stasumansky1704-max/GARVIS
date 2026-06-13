"""Operator-Cognition Collaboration Model — cognition/collaboration.py

This module implements the GOVERNED COLLABORATIVE COGNITION layer for GARVIS.
It models the interaction between operators and GARVIS as a structured dialogue
where EVERY response is governance-checked, uncertainty is ALWAYS disclosed, and
ALL reasoning is observable and traceable.

This is NOT a chatbot. It is a GOVERNED COGNITION COLLABORATION system.
Every operator input is processed through governance validation before any
response is generated. Every response includes the full reasoning trail,
governance checks applied, uncertainty disclosures, and memory influences.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from uuid import uuid4

from pydantic import BaseModel, Field

from models.governance import GovernanceCheckResult, GovernanceViolation

if TYPE_CHECKING:
    from governance.validator import RuntimeValidator
    from traceability.audit import AuditPipeline

logger = logging.getLogger("garvis.cognition.collaboration")


# ---------------------------------------------------------------------------
# CollaborationInteraction — single interaction record
# ---------------------------------------------------------------------------


class CollaborationInteraction(BaseModel):
    """A single interaction in a collaboration session.

    Every interaction captures the full governance context so that
    operators can see WHY governance made every decision.
    """

    interaction_id: str
    session_id: str
    timestamp: datetime
    operator_input: dict  # What the operator submitted
    governance_checks: list[GovernanceCheckResult]
    response: dict  # The governed response
    memory_influences: list[dict]
    uncertainty_disclosed: bool
    confidence_score: float
    processing_time_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the interaction to a plain dict."""
        return {
            "interaction_id": self.interaction_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "operator_input": self.operator_input,
            "governance_checks": [
                {
                    "schema_id": c.schema_id,
                    "policy_id": c.policy_id,
                    "passed": c.passed,
                    "violation": (
                        {
                            "schema_id": c.violation.schema_id,
                            "policy_id": c.violation.policy_id,
                            "severity": c.violation.severity,
                            "description": c.violation.description,
                        }
                        if c.violation
                        else None
                    ),
                }
                for c in self.governance_checks
            ],
            "response": self.response,
            "memory_influences": self.memory_influences,
            "uncertainty_disclosed": self.uncertainty_disclosed,
            "confidence_score": self.confidence_score,
            "processing_time_ms": self.processing_time_ms,
        }


# ---------------------------------------------------------------------------
# OperatorInput — validated operator input
# ---------------------------------------------------------------------------


class OperatorInput(BaseModel):
    """Validated operator input into a collaboration session."""

    input_type: str  # "query", "propose_action", "request_analysis", "governance_review"
    content: str
    context: dict[str, Any] = Field(default_factory=dict)
    operator_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @classmethod
    def validate_input_type(cls, input_type: str) -> bool:
        """Validate that the input type is supported."""
        return input_type in {
            "query",
            "propose_action",
            "request_analysis",
            "governance_review",
            "status_check",
            "explain_decision",
        }


# ---------------------------------------------------------------------------
# GovernedResponse — a response that has passed governance checks
# ---------------------------------------------------------------------------


class GovernedCollaborationResponse(BaseModel):
    """A governed response from GARVIS to an operator.

    Every response carries the full governance context so operators
    can see exactly what checks were applied and why.
    """

    interaction_id: str
    session_id: str
    timestamp: datetime
    response_type: str  # "answer", "recommendation", "block", "uncertainty", "error"
    content: str  # The human-readable response
    governance_checks_applied: list[dict]
    uncertainty_disclosure: str | None = None
    confidence_level: float  # 0.0 - 1.0
    confidence_interpretation: str  # Human-readable confidence meaning
    memory_influences: list[dict]
    reasoning_trace: list[str]  # Step-by-step reasoning
    operator_can_override: bool = False
    override_requirements: list[str] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dict for API responses."""
        return {
            "interaction_id": self.interaction_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "response_type": self.response_type,
            "content": self.content,
            "governance_checks_applied": self.governance_checks_applied,
            "uncertainty_disclosure": self.uncertainty_disclosure,
            "confidence_level": self.confidence_level,
            "confidence_interpretation": self.confidence_interpretation,
            "memory_influences": self.memory_influences,
            "reasoning_trace": self.reasoning_trace,
            "operator_can_override": self.operator_can_override,
            "override_requirements": self.override_requirements,
        }


# ---------------------------------------------------------------------------
# CollaborationSession — the main collaboration orchestrator
# ---------------------------------------------------------------------------


class CollaborationSession:
    """A session of collaboration between operator and GARVIS.

    Models the interaction as a structured dialogue where:
    - Operator proposes actions or asks questions
    - GARVIS responds with governed reasoning
    - All interactions are audited and traceable
    - Governance mediates every response

    This is NOT a chatbot. It is a GOVERNED COGNITION COLLABORATION.
    """

    # Session registry for looking up sessions by ID
    _SESSION_REGISTRY: dict[str, "CollaborationSession"] = {}

    def __init__(
        self,
        session_id: str,
        operator_id: str,
        project_id: str,
        validator: Any,
        audit: Any,
    ) -> None:
        self.session_id = session_id
        self.operator_id = operator_id
        self.project_id = project_id
        self.validator = validator
        self.audit = audit
        self._interactions: list[CollaborationInteraction] = []
        self._governance_context: list[str] = []
        self._started_at = datetime.now(timezone.utc)
        self._status = "active"
        self._ended_at: datetime | None = None
        self._lock = asyncio.Lock()
        self._uncertainty_disclosure_rate = 1.0  # Always disclose
        self._total_checks_passed = 0
        self._total_checks_failed = 0
        self._memory_influence_count = 0

        # Register this session
        CollaborationSession._SESSION_REGISTRY[session_id] = self

        logger.info(
            "Collaboration session started: id=%s, operator=%s, project=%s",
            session_id,
            operator_id,
            project_id,
        )

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Whether the session is still active."""
        return self._status == "active"

    @property
    def interaction_count(self) -> int:
        """Number of interactions in this session."""
        return len(self._interactions)

    @property
    def duration_seconds(self) -> float:
        """Duration of the session in seconds."""
        end = self._ended_at or datetime.now(timezone.utc)
        return (end - self._started_at).total_seconds()

    @property
    def governance_context(self) -> list[str]:
        """Active governance schemas for this session."""
        return list(self._governance_context)

    # ------------------------------------------------------------------
    # Core: Operator Input Processing
    # ------------------------------------------------------------------

    async def submit_operator_input(
        self,
        input_type: str,
        content: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process operator input through governance.

        This is the main entry point for operator-GARVIS collaboration.
        Every input goes through the full governance pipeline:

        1. Validate input type
        2. Build OperatorInput record
        3. Run governance checks on the input
        4. If checks pass → generate governed response
        5. If checks fail → explain WHY and return block
        6. Audit everything

        Args:
            input_type: "query", "propose_action", "request_analysis",
                        "governance_review", "status_check", "explain_decision"
            content: The operator's input text
            context: Optional additional context

        Returns:
            Dict with the governed response, governance checks, and
            full reasoning visibility.
        """
        start_time = datetime.now(timezone.utc)

        async with self._lock:
            if not self.is_active:
                return self._create_session_inactive_response()

            # Step 1: Validate input type
            if not OperatorInput.validate_input_type(input_type):
                return self._create_invalid_input_response(input_type)

            # Step 2: Build operator input record
            op_input = OperatorInput(
                input_type=input_type,
                content=content,
                context=context or {},
                operator_id=self.operator_id,
            )

            # Step 3: Run governance checks on the input
            governance_checks = await self._run_governance_checks(op_input)

            # Track check statistics
            for check in governance_checks:
                if check.passed:
                    self._total_checks_passed += 1
                else:
                    self._total_checks_failed += 1

            # Step 4: Check for critical failures (fail-closed)
            has_critical = self._has_critical_failures(governance_checks)

            if has_critical:
                # Governance blocked this input
                response = self._create_blocked_response(
                    op_input, governance_checks
                )
            else:
                # Step 5: Generate governed response
                response = await self.generate_governed_response({
                    "input": op_input,
                    "governance_checks": governance_checks,
                    "context": context or {},
                })

            # Step 6: Build and record the interaction
            end_time = datetime.now(timezone.utc)
            processing_time_ms = (end_time - start_time).total_seconds() * 1000

            interaction = CollaborationInteraction(
                interaction_id=f"int_{uuid4().hex[:12]}",
                session_id=self.session_id,
                timestamp=start_time,
                operator_input={
                    "input_type": input_type,
                    "content": content,
                    "context": context or {},
                },
                governance_checks=governance_checks,
                response=response,
                memory_influences=response.get("memory_influences", []),
                uncertainty_disclosed=response.get("uncertainty_disclosed", True),
                confidence_score=response.get("confidence_score", 0.5),
                processing_time_ms=processing_time_ms,
            )

            self._interactions.append(interaction)

            # Step 7: Audit the interaction
            await self._audit_interaction(interaction)

            # Return the full response with governance context
            result = {
                "interaction_id": interaction.interaction_id,
                "session_id": self.session_id,
                "status": self._status,
                "operator_input": {
                    "input_type": input_type,
                    "content": content,
                },
                "governance_checks": [
                    {
                        "schema_id": c.schema_id,
                        "policy_id": c.policy_id,
                        "passed": c.passed,
                        "has_violation": c.violation is not None,
                        "violation_severity": (
                            c.violation.severity if c.violation else None
                        ),
                    }
                    for c in governance_checks
                ],
                "response": response,
                "uncertainty_disclosed": interaction.uncertainty_disclosed,
                "confidence_score": interaction.confidence_score,
                "processing_time_ms": processing_time_ms,
                "interaction_number": len(self._interactions),
            }

            return result

    # ------------------------------------------------------------------
    # Core: Governed Response Generation
    # ------------------------------------------------------------------

    async def generate_governed_response(
        self, input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Generate a response that passes all governance checks.

        Response includes:
        - The answer/recommendation
        - Governance checks applied
        - Uncertainty disclosures
        - Confidence levels
        - Memory influences
        - Full reasoning trace

        Args:
            input_data: Dict with "input", "governance_checks", "context"

        Returns:
            Dict with the full governed response.
        """
        op_input: OperatorInput = input_data["input"]
        governance_checks: list[GovernanceCheckResult] = input_data[
            "governance_checks"
        ]
        context: dict[str, Any] = input_data.get("context", {})

        # Determine response type based on input
        response_type = self._determine_response_type(op_input.input_type)

        # Simulate memory influence (in production, query episodic memory)
        memory_influences = self._simulate_memory_influences(op_input)
        self._memory_influence_count += len(memory_influences)

        # Build reasoning trace
        reasoning_trace = self._build_reasoning_trace(
            op_input, governance_checks, memory_influences
        )

        # Calculate confidence based on governance checks and memory
        confidence = self._calculate_confidence(governance_checks, memory_influences)

        # Determine uncertainty disclosure
        uncertainty = self._build_uncertainty_disclosure(
            op_input, confidence, governance_checks
        )

        # Generate response content (simulated — in production, this would
        # call the inference engine with full governance context)
        content = self._generate_response_content(
            op_input, confidence, governance_checks, memory_influences
        )

        # Build the governed response
        response: dict[str, Any] = {
            "response_type": response_type,
            "content": content,
            "governance_checks_applied": [
                {
                    "schema_id": c.schema_id,
                    "policy_id": c.policy_id,
                    "passed": c.passed,
                    "description": (
                        c.violation.description if c.violation else "Check passed"
                    ),
                }
                for c in governance_checks
            ],
            "uncertainty_disclosure": uncertainty,
            "uncertainty_disclosed": uncertainty is not None,
            "confidence_score": confidence,
            "confidence_level": confidence,
            "confidence_interpretation": self._interpret_confidence(confidence),
            "memory_influences": memory_influences,
            "reasoning_trace": reasoning_trace,
            "operator_can_override": False,  # Governance decisions are not overrideable by default
            "override_requirements": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        return response

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_interaction_history(self) -> list[CollaborationInteraction]:
        """Get full interaction history."""
        return list(self._interactions)

    def get_interaction_history_as_dicts(self) -> list[dict[str, Any]]:
        """Get interaction history serialized as dicts."""
        return [i.to_dict() for i in self._interactions]

    def get_governance_summary(self) -> dict[str, Any]:
        """Get summary of governance checks in this session.

        Returns:
            Dict with check statistics, violation counts, and
            uncertainty disclosure rate.
        """
        total_checks = self._total_checks_passed + self._total_checks_failed
        violation_count = sum(
            1
            for i in self._interactions
            for c in i.governance_checks
            if c.violation is not None
        )

        by_schema: dict[str, dict[str, int]] = {}
        for i in self._interactions:
            for c in i.governance_checks:
                schema = c.schema_id
                if schema not in by_schema:
                    by_schema[schema] = {"passed": 0, "failed": 0}
                if c.passed:
                    by_schema[schema]["passed"] += 1
                else:
                    by_schema[schema]["failed"] += 1

        # Uncertainty disclosure rate
        if self._interactions:
            disclosure_rate = sum(
                1 for i in self._interactions if i.uncertainty_disclosed
            ) / len(self._interactions)
        else:
            disclosure_rate = 1.0  # Default to full disclosure

        return {
            "session_id": self.session_id,
            "total_interactions": len(self._interactions),
            "total_checks": total_checks,
            "checks_passed": self._total_checks_passed,
            "checks_failed": self._total_checks_failed,
            "violation_count": violation_count,
            "by_schema": by_schema,
            "uncertainty_disclosure_rate": disclosure_rate,
            "memory_influence_count": self._memory_influence_count,
            "session_duration_seconds": self.duration_seconds,
            "governance_context": self._governance_context,
        }

    def end_session(self) -> dict[str, Any]:
        """End the collaboration session with full audit.

        Returns:
            Session summary with full audit trail.
        """
        if self._status != "active":
            return {"error": "Session already ended", "session_id": self.session_id}

        self._status = "ended"
        self._ended_at = datetime.now(timezone.utc)

        # Unregister
        CollaborationSession._SESSION_REGISTRY.pop(self.session_id, None)

        summary = {
            "session_id": self.session_id,
            "operator_id": self.operator_id,
            "project_id": self.project_id,
            "status": self._status,
            "started_at": self._started_at.isoformat(),
            "ended_at": self._ended_at.isoformat() if self._ended_at else None,
            "duration_seconds": self.duration_seconds,
            "total_interactions": len(self._interactions),
            "governance_summary": self.get_governance_summary(),
        }

        logger.info(
            "Collaboration session ended: id=%s, interactions=%d, duration=%.1fs",
            self.session_id,
            len(self._interactions),
            self.duration_seconds,
        )

        return summary

    # ------------------------------------------------------------------
    # Session registry
    # ------------------------------------------------------------------

    @classmethod
    def get_session_by_id(cls, session_id: str) -> "CollaborationSession | None":
        """Retrieve a session by ID from the registry."""
        return cls._SESSION_REGISTRY.get(session_id)

    @classmethod
    def list_active_sessions(cls) -> list["CollaborationSession"]:
        """List all active collaboration sessions."""
        return [s for s in cls._SESSION_REGISTRY.values() if s.is_active]

    # ------------------------------------------------------------------
    # Internal: Governance checking
    # ------------------------------------------------------------------

    async def _run_governance_checks(
        self, op_input: OperatorInput
    ) -> list[GovernanceCheckResult]:
        """Run governance checks on operator input.

        In production, this calls the RuntimeValidator. Here we simulate
        checks based on input type and content.
        """
        checks: list[GovernanceCheckResult] = []

        # Check 1: Input type validation
        checks.append(
            GovernanceCheckResult(
                schema_id="session_management",
                policy_id="valid_input_type",
                passed=True,
                violation=None,
            )
        )

        # Check 2: Content safety (boundary enforcement)
        # Simulate content scanning
        content_lower = op_input.content.lower()
        blocked_keywords = ["exec(", "system(", "subprocess", "os.system", "eval("]
        has_blocked = any(kw in content_lower for kw in blocked_keywords)

        if has_blocked:
            checks.append(
                GovernanceCheckResult(
                    schema_id="boundary_enforcement",
                    policy_id="be_01",
                    passed=False,
                    violation=GovernanceViolation(
                        schema_id="boundary_enforcement",
                        policy_id="be_01",
                        severity="critical",
                        description="Input contains potentially executable code patterns",
                        context={
                            "input_type": op_input.input_type,
                            "blocked_keywords_found": [
                                kw for kw in blocked_keywords if kw in content_lower
                            ],
                        },
                    ),
                )
            )
        else:
            checks.append(
                GovernanceCheckResult(
                    schema_id="boundary_enforcement",
                    policy_id="be_01",
                    passed=True,
                    violation=None,
                )
            )

        # Check 3: Epistemic safety — check for overconfidence claims
        if "i am certain" in content_lower or "100% sure" in content_lower:
            checks.append(
                GovernanceCheckResult(
                    schema_id="epistemic_safety",
                    policy_id="ep_01",
                    passed=False,
                    violation=GovernanceViolation(
                        schema_id="epistemic_safety",
                        policy_id="ep_01",
                        severity="warning",
                        description="Input contains absolute certainty claims that require validation",
                        context={"trigger_phrase": "absolute certainty"},
                    ),
                )
            )
        else:
            checks.append(
                GovernanceCheckResult(
                    schema_id="epistemic_safety",
                    policy_id="ep_01",
                    passed=True,
                    violation=None,
                )
            )

        # Check 4: Ethical guidelines
        checks.append(
            GovernanceCheckResult(
                schema_id="ethical_guidelines",
                policy_id="eg_01",
                passed=True,
                violation=None,
            )
        )

        # Check 5: Traceability
        checks.append(
            GovernanceCheckResult(
                schema_id="traceability_requirement",
                policy_id="tr_01",
                passed=True,
                violation=None,
            )
        )

        return checks

    def _has_critical_failures(
        self, checks: list[GovernanceCheckResult]
    ) -> bool:
        """Check if any governance check has a critical failure.

        This is the fail-closed check: if any critical policy failed,
        the operation must be blocked.
        """
        for check in checks:
            if not check.passed and check.violation:
                if check.violation.severity == "critical":
                    return True
        return False

    # ------------------------------------------------------------------
    # Internal: Response creation
    # ------------------------------------------------------------------

    def _create_blocked_response(
        self,
        op_input: OperatorInput,
        governance_checks: list[GovernanceCheckResult],
    ) -> dict[str, Any]:
        """Create a response when governance blocks the input.

        The response explains WHY the input was blocked and what
        the operator can do instead.
        """
        violations = [c for c in governance_checks if not c.passed and c.violation]
        critical = [v for v in violations if v.violation.severity == "critical"]

        blocking_schemas = [v.schema_id for v in violations]
        blocking_policies = [v.policy_id for v in violations]

        content = (
            f"Your input has been blocked by governance.\n\n"
            f"**Blocked by schemas:** {', '.join(blocking_schemas)}\n"
            f"**Blocking policies:** {', '.join(blocking_policies)}\n\n"
        )

        for v in violations:
            content += (
                f"- **{v.schema_id}** / {v.policy_id}: "
                f"{v.violation.description}\n"
            )

        if critical:
            content += (
                "\nThis action contains critical violations and cannot proceed. "
                "Please modify your request and try again."
            )
        else:
            content += (
                "\nThis action has warnings only. You may revise and resubmit, "
                "or escalate for operator review."
            )

        return {
            "response_type": "block",
            "content": content,
            "governance_checks_applied": [
                {
                    "schema_id": c.schema_id,
                    "policy_id": c.policy_id,
                    "passed": c.passed,
                    "violation": (
                        {
                            "severity": c.violation.severity,
                            "description": c.violation.description,
                        }
                        if c.violation
                        else None
                    ),
                }
                for c in governance_checks
            ],
            "uncertainty_disclosure": None,
            "uncertainty_disclosed": False,
            "confidence_score": 0.0,
            "confidence_level": 0.0,
            "confidence_interpretation": "blocked — no confidence applicable",
            "memory_influences": [],
            "reasoning_trace": [
                f"Received {op_input.input_type} input",
                "Ran governance validation",
                f"Found {len(violations)} violation(s)",
                f"{len(critical)} critical — blocking response",
                "Generated block explanation with escalation path",
            ],
            "operator_can_override": len(critical) == 0,
            "override_requirements": (
                ["operator_approval", "secondary_review"] if len(critical) == 0 else []
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _create_session_inactive_response(self) -> dict[str, Any]:
        """Create a response when the session is not active."""
        return {
            "response_type": "error",
            "content": f"Session {self.session_id} is not active (status: {self._status}).",
            "governance_checks_applied": [],
            "uncertainty_disclosure": None,
            "uncertainty_disclosed": False,
            "confidence_score": 0.0,
            "confidence_level": 0.0,
            "confidence_interpretation": "session inactive",
            "memory_influences": [],
            "reasoning_trace": ["Session is not active"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _create_invalid_input_response(self, input_type: str) -> dict[str, Any]:
        """Create a response for invalid input type."""
        return {
            "response_type": "error",
            "content": (
                f"Invalid input type: '{input_type}'. "
                f"Valid types: query, propose_action, request_analysis, "
                f"governance_review, status_check, explain_decision"
            ),
            "governance_checks_applied": [],
            "uncertainty_disclosure": None,
            "uncertainty_disclosed": False,
            "confidence_score": 0.0,
            "confidence_level": 0.0,
            "confidence_interpretation": "invalid input",
            "memory_influences": [],
            "reasoning_trace": [f"Invalid input type: {input_type}"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal: Response content generation
    # ------------------------------------------------------------------

    def _determine_response_type(self, input_type: str) -> str:
        """Determine the response type based on input type."""
        mapping = {
            "query": "answer",
            "propose_action": "recommendation",
            "request_analysis": "analysis",
            "governance_review": "review",
            "status_check": "status",
            "explain_decision": "explanation",
        }
        return mapping.get(input_type, "answer")

    def _simulate_memory_influences(
        self, op_input: OperatorInput
    ) -> list[dict[str, Any]]:
        """Simulate memory influences on the response.

        In production, this queries the episodic memory store for
        relevant memories and their influence on the current response.
        """
        # Simulate some memory influences based on input type
        influences = []

        if op_input.input_type == "query":
            influences.append({
                "memory_id": f"mem_{uuid4().hex[:8]}",
                "influence_type": "context",
                "strength": 0.75,
                "description": "Previous query context about governance schemas",
            })
        elif op_input.input_type == "propose_action":
            influences.append({
                "memory_id": f"mem_{uuid4().hex[:8]}",
                "influence_type": "constraint",
                "strength": 0.90,
                "description": "Boundary enforcement constraint from previous action",
            })
        elif op_input.input_type == "governance_review":
            influences.append({
                "memory_id": f"mem_{uuid4().hex[:8]}",
                "influence_type": "retrieval",
                "strength": 0.85,
                "description": "Retrieved governance schema history",
            })

        return influences

    def _build_reasoning_trace(
        self,
        op_input: OperatorInput,
        governance_checks: list[GovernanceCheckResult],
        memory_influences: list[dict],
    ) -> list[str]:
        """Build a step-by-step reasoning trace.

        This makes the reasoning fully observable and traceable.
        """
        trace = [
            f"Received {op_input.input_type} input from operator {self.operator_id}",
            f"Running {len(governance_checks)} governance checks...",
        ]

        for check in governance_checks:
            status = "PASSED" if check.passed else "FAILED"
            trace.append(f"  [{status}] {check.schema_id}/{check.policy_id}")

        if memory_influences:
            trace.append(f"Applying {len(memory_influences)} memory influence(s):")
            for inf in memory_influences:
                trace.append(
                    f"  - {inf['influence_type']} (strength: {inf['strength']})"
                )

        trace.append("Calculating confidence based on governance + memory")
        trace.append("Generating uncertainty disclosure")
        trace.append("Response complete — all checks visible above")

        return trace

    def _calculate_confidence(
        self,
        governance_checks: list[GovernanceCheckResult],
        memory_influences: list[dict],
    ) -> float:
        """Calculate confidence score based on governance and memory.

        Confidence is bounded by governance check results and
        memory influence quality.
        """
        # Start with baseline
        confidence = 0.7

        # Adjust for governance checks
        if not governance_checks:
            confidence *= 0.8  # Lower confidence with no checks
        else:
            pass_rate = sum(1 for c in governance_checks if c.passed) / len(
                governance_checks
            )
            confidence *= (0.5 + 0.5 * pass_rate)

        # Adjust for memory influences
        if memory_influences:
            avg_strength = sum(i["strength"] for i in memory_influences) / len(
                memory_influences
            )
            confidence *= (0.7 + 0.3 * avg_strength)

        # Cap at 0.85 per epistemic safety policy
        confidence = min(confidence, 0.85)

        # Floor at 0.1 — always some uncertainty
        confidence = max(confidence, 0.1)

        return round(confidence, 3)

    def _build_uncertainty_disclosure(
        self,
        op_input: OperatorInput,
        confidence: float,
        governance_checks: list[GovernanceCheckResult],
    ) -> str | None:
        """Build uncertainty disclosure based on confidence and context.

        Uncertainty is ALWAYS disclosed when confidence < 0.6.
        Even when confidence is high, we disclose the basis.
        """
        # Always disclose basis
        if confidence < 0.3:
            return (
                f"High uncertainty: confidence is {confidence:.2f}. "
                f"This {op_input.input_type} involves significant unknowns. "
                f"The governance checks passed, but memory support is limited. "
                f"Recommend operator review before acting."
            )
        elif confidence < 0.6:
            return (
                f"Moderate uncertainty: confidence is {confidence:.2f}. "
                f"Some aspects of this {op_input.input_type} are well-supported, "
                f"but there are gaps. Consider additional analysis."
            )
        elif confidence < 0.8:
            return (
                f"Reasonable confidence: {confidence:.2f}. "
                f"This {op_input.input_type} is supported by governance checks "
                f"and available memory, but not all edge cases are covered."
            )
        else:
            return (
                f"Good confidence: {confidence:.2f}. "
                f"This {op_input.input_type} is well-supported, but remember "
                f"that all reasoning is bounded and new information could change conclusions."
            )

    def _interpret_confidence(self, confidence: float) -> str:
        """Return human-readable confidence interpretation."""
        if confidence < 0.2:
            return "very low — significant uncertainty, operator review strongly advised"
        elif confidence < 0.4:
            return "low — notable gaps in reasoning, proceed with caution"
        elif confidence < 0.6:
            return "moderate — reasonable basis but incomplete coverage"
        elif confidence < 0.75:
            return "reasonable — good support from governance and memory"
        else:
            return "good — strong support, but always subject to new evidence"

    def _generate_response_content(
        self,
        op_input: OperatorInput,
        confidence: float,
        governance_checks: list[GovernanceCheckResult],
        memory_influences: list[dict],
    ) -> str:
        """Generate the actual response content.

        This simulates what the inference engine would produce.
        In production, this would call the governed inference executor.
        """
        if op_input.input_type == "query":
            return (
                f"Governed response to query: '{op_input.content[:80]}...'\n\n"
                f"This response has been validated against {len(governance_checks)} "
                f"governance schema(s). All critical checks passed.\n\n"
                f"Confidence: {confidence:.2f} — {self._interpret_confidence(confidence)}\n\n"
                f"The reasoning trace above shows every step of the analysis."
            )
        elif op_input.input_type == "propose_action":
            return (
                f"Action proposal reviewed: '{op_input.content[:80]}...'\n\n"
                f"Governance assessment: All checks passed. The action is within "
                f"operational boundaries.\n\n"
                f"Confidence in recommendation: {confidence:.2f}\n\n"
                f"Memory influences: {len(memory_influences)} source(s) considered."
            )
        elif op_input.input_type == "request_analysis":
            return (
                f"Analysis of: '{op_input.content[:80]}...'\n\n"
                f"Governed analysis complete. {len(governance_checks)} checks applied.\n"
                f"Confidence level: {confidence:.2f}\n\n"
                f"All reasoning is traceable above."
            )
        elif op_input.input_type == "governance_review":
            return (
                f"Governance review of: '{op_input.content[:80]}...'\n\n"
                f"Active schemas: {len([c for c in governance_checks if c.passed])} "
                f"policies validated.\n"
                f"No critical violations detected.\n"
                f"Confidence: {confidence:.2f}"
            )
        elif op_input.input_type == "status_check":
            return (
                f"Session status for {self.session_id}:\n"
                f"- Status: {self._status}\n"
                f"- Interactions: {self.interaction_count}\n"
                f"- Duration: {self.duration_seconds:.1f}s\n"
                f"- Governance checks passed: {self._total_checks_passed}\n"
                f"- Governance checks failed: {self._total_checks_failed}"
            )
        elif op_input.input_type == "explain_decision":
            return (
                f"Decision explanation for: '{op_input.content[:80]}...'\n\n"
                f"This decision was reached through governed reasoning with "
                f"{len(governance_checks)} validation checks.\n\n"
                f"The reasoning trace shows every step and influence."
            )
        else:
            return f"Governed response to {op_input.input_type}: '{op_input.content[:80]}...'"

    # ------------------------------------------------------------------
    # Internal: Audit logging
    # ------------------------------------------------------------------

    async def _audit_interaction(self, interaction: CollaborationInteraction) -> None:
        """Log the interaction to the audit pipeline."""
        if self.audit is None:
            return

        try:
            from models.audit import AuditEvent

            event = AuditEvent(
                event_id=uuid4(),
                event_type="collaboration_interaction",
                severity="info",
                component="cognition.collaboration",
                trace_id=uuid4(),
                timestamp=interaction.timestamp,
                details={
                    "interaction_id": interaction.interaction_id,
                    "session_id": self.session_id,
                    "operator_id": self.operator_id,
                    "input_type": interaction.operator_input.get("input_type"),
                    "checks_count": len(interaction.governance_checks),
                    "checks_passed": sum(1 for c in interaction.governance_checks if c.passed),
                    "uncertainty_disclosed": interaction.uncertainty_disclosed,
                    "confidence_score": interaction.confidence_score,
                    "processing_time_ms": interaction.processing_time_ms,
                },
                governance_context=self._governance_context,
            )

            if hasattr(self.audit, "log_event"):
                await self.audit.log_event(event)

        except Exception as exc:
            logger.error("Failed to audit interaction: %s", exc)
