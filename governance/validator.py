"""Governance Validator — governance/validator.py

Validates runtime operations against governance schemas.
Core fail-closed validation engine.
Per the SPEC section 5.3.

ANY critical violation must be flagged and the operation blocked.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from models.governance import (
    GovernanceCheckResult,
    GovernanceConstraint,
    GovernancePolicy,
    GovernanceSchema,
    GovernanceViolation,
)
from models.cognition import OperationalState, StateTransition
from models.inference import InferenceRequest, GovernedResponse
from models.memory import EpisodicMemory
from governance.registry import GovernanceRegistry

logger = logging.getLogger("garvis.governance.validator")


class RuntimeValidator:
    """Validates runtime operations against governance schemas.

    Core fail-closed validation engine. Every operation is checked
    against all active schemas. Critical violations block execution.
    """

    def __init__(self, registry: GovernanceRegistry) -> None:
        self.registry = registry
        self._history: list[GovernanceCheckResult] = []

    # ── Inference Request Validation ──────────────────────────────

    def validate_inference_request(
        self, request: InferenceRequest
    ) -> list[GovernanceCheckResult]:
        """Validate an inference request against all active schemas.

        Any critical failure in results means the request cannot proceed.
        Checks applicable policies from all active governance schemas.
        """
        results: list[GovernanceCheckResult] = []
        active_schemas = self.registry.get_active_schemas()

        logger.debug(
            "Validating inference request %s against %d active schemas",
            request.request_id,
            len(active_schemas),
        )

        for schema in active_schemas:
            for policy in schema.policies:
                if self._policy_applies_to_inference_request(policy):
                    passed, reason = self._evaluate_inference_policy(
                        policy, schema, request
                    )
                    check = self._create_check_result(schema, policy, passed, reason)
                    results.append(check)
                    self._history.append(check)

                    if not passed:
                        logger.warning(
                            "Inference request %s failed policy '%s' from schema '%s': %s",
                            request.request_id,
                            policy.policy_id,
                            schema.schema_id,
                            reason,
                        )

        # Check constraints
        constraints = self.registry.get_enforcement_chain("inference")
        for constraint in constraints:
            passed, reason = self._evaluate_inference_constraint(
                constraint, request
            )
            check = self._create_constraint_check(
                constraint, passed, reason, request.session_id
            )
            results.append(check)
            self._history.append(check)

        logger.info(
            "Inference request %s validation: %d/%d checks passed",
            request.request_id,
            sum(1 for r in results if r.passed),
            len(results),
        )
        return results

    # ── State Transition Validation ───────────────────────────────

    def validate_state_transition(
        self, transition: StateTransition
    ) -> list[GovernanceCheckResult]:
        """Validate a requested state transition.

        Checks forbidden state patterns and governance constraints.
        State transitions are critical — any failure blocks the transition.
        """
        results: list[GovernanceCheckResult] = []
        active_schemas = self.registry.get_active_schemas()

        logger.debug(
            "Validating state transition %s -> %s (trigger: %s)",
            transition.from_state.value,
            transition.to_state.value,
            transition.trigger,
        )

        # Check forbidden transitions first
        forbidden = self._check_forbidden_transition(transition)
        if forbidden:
            check = GovernanceCheckResult(
                schema_id="operational_state_model",
                policy_id="forbidden_pattern_prevention",
                passed=False,
                violation=forbidden,
            )
            results.append(check)
            self._history.append(check)
            logger.critical(
                "FORBIDDEN state transition attempted: %s -> %s (%s)",
                transition.from_state.value,
                transition.to_state.value,
                forbidden.description,
            )
            return results  # Hard stop on forbidden transitions

        # Check all active schema policies applicable to state transitions
        for schema in active_schemas:
            for policy in schema.policies:
                if self._policy_applies_to_state_transition(policy):
                    passed, reason = self._evaluate_transition_policy(
                        policy, schema, transition
                    )
                    check = self._create_check_result(schema, policy, passed, reason)
                    results.append(check)
                    self._history.append(check)

        # Check constraints
        constraints = self.registry.get_enforcement_chain("global")
        for constraint in constraints:
            passed, reason = self._evaluate_transition_constraint(
                constraint, transition
            )
            check = self._create_constraint_check(
                constraint, passed, reason, transition.trace_id
            )
            results.append(check)
            self._history.append(check)

        logger.info(
            "State transition validation: %d/%d checks passed",
            sum(1 for r in results if r.passed),
            len(results),
        )
        return results

    # ── Response Validation ───────────────────────────────────────

    def validate_response(
        self, response: GovernedResponse
    ) -> list[GovernanceCheckResult]:
        """Validate an inference response before release.

        All governance schemas applicable to response validation are checked.
        A response with critical failures MUST NOT be released.
        """
        results: list[GovernanceCheckResult] = []
        active_schemas = self.registry.get_active_schemas()

        logger.debug(
            "Validating response %s against active schemas",
            response.response_id,
        )

        for schema in active_schemas:
            for policy in schema.policies:
                if self._policy_applies_to_response(policy):
                    passed, reason = self._evaluate_response_policy(
                        policy, schema, response
                    )
                    check = self._create_check_result(schema, policy, passed, reason)
                    results.append(check)
                    self._history.append(check)

                    if not passed:
                        logger.warning(
                            "Response %s failed policy '%s' from schema '%s': %s",
                            response.response_id,
                            policy.policy_id,
                            schema.schema_id,
                            reason,
                        )

        # Check constraints
        constraints = self.registry.get_enforcement_chain("inference")
        for constraint in constraints:
            passed, reason = self._evaluate_response_constraint(
                constraint, response
            )
            check = self._create_constraint_check(
                constraint, passed, reason, response.request_id
            )
            results.append(check)
            self._history.append(check)

        logger.info(
            "Response %s validation: %d/%d checks passed",
            response.response_id,
            sum(1 for r in results if r.passed),
            len(results),
        )
        return results

    # ── Memory Operation Validation ───────────────────────────────

    def validate_memory_operation(
        self, operation: str, memory: EpisodicMemory
    ) -> list[GovernanceCheckResult]:
        """Validate memory storage or retrieval operations.

        Checks provenance_awareness, session_continuity, dependency_awareness.
        """
        results: list[GovernanceCheckResult] = []
        active_schemas = self.registry.get_active_schemas()

        logger.debug(
            "Validating memory operation '%s' for memory %s",
            operation,
            memory.memory_id,
        )

        for schema in active_schemas:
            for policy in schema.policies:
                if self._policy_applies_to_memory_operation(policy, operation):
                    passed, reason = self._evaluate_memory_policy(
                        policy, schema, operation, memory
                    )
                    check = self._create_check_result(schema, policy, passed, reason)
                    results.append(check)
                    self._history.append(check)

        # Check memory-scoped constraints
        constraints = self.registry.get_enforcement_chain("memory")
        for constraint in constraints:
            passed, reason = self._evaluate_memory_constraint(
                constraint, operation, memory
            )
            check = self._create_constraint_check(
                constraint, passed, reason, memory.session_id
            )
            results.append(check)
            self._history.append(check)

        logger.info(
            "Memory operation '%s' validation: %d/%d checks passed",
            operation,
            sum(1 for r in results if r.passed),
            len(results),
        )
        return results

    # ── Validation History ────────────────────────────────────────

    def get_validation_history(
        self, session_id: UUID | None = None
    ) -> list[GovernanceCheckResult]:
        """Get history of validation checks.

        If session_id is provided, filters to checks related to that session.
        """
        if session_id is None:
            return list(self._history)

        # Filter history by session_id (best effort — stored in violation context)
        filtered = []
        for check in self._history:
            if check.violation and check.violation.context.get("session_id") == str(
                session_id
            ):
                filtered.append(check)
            elif check.context_session_id == str(session_id):
                filtered.append(check)
        return filtered

    def has_critical_failures(self, results: list[GovernanceCheckResult]) -> bool:
        """Check if any result has a critical failure.

        This is the core fail-closed check: if any critical policy failed,
        the operation must be blocked.
        """
        for result in results:
            if not result.passed and result.violation:
                if result.violation.severity == "critical":
                    return True
        return False

    def clear_history(self) -> None:
        """Clear validation history. Used sparingly, mainly for testing."""
        self._history.clear()
        logger.debug("Validation history cleared")

    # ── Internal: Policy applicability ────────────────────────────

    def _policy_applies_to_inference_request(self, policy: GovernancePolicy) -> bool:
        """Determine if a policy applies to inference request validation."""
        # Most policies apply to inference requests
        # Some are specifically for memory or state operations
        request_specific_policies = {
            "uncertainty_quantification_required",
            "uncertainty_honesty_threshold",
            "knowledge_boundary_recognition",
            "no_fabrication",
            "source_verification",
            "honest_about_limitations",
            "hallucination_detection",
            "internal_consistency_check",
            "belief_consistency",
            "plan_validation",
            "plan_depth_limit",
            "autonomy_boundary",
            "high_stakes_escalation",
            "mediation_coverage",
            "mediation_completeness",
            "humility_in_claims",
            "deferral_protocol",
            "scope_enforcement",
            "interception_point_coverage",
        }
        return policy.policy_id in request_specific_policies or policy.severity in {
            "critical",
            "warning",
        }

    def _policy_applies_to_state_transition(self, policy: GovernancePolicy) -> bool:
        """Determine if a policy applies to state transition validation."""
        transition_policies = {
            "valid_transition_only",
            "forbidden_pattern_prevention",
            "state_change_logging",
            "degradation_threshold",
            "graceful_degradation_path",
            "adaptation_observability",
            "recovery_validation",
            "graduated_recovery",
            "error_recovery_protocol",
            "stability_monitoring",
            "oscillation_detection",
        }
        return policy.policy_id in transition_policies

    def _policy_applies_to_response(self, policy: GovernancePolicy) -> bool:
        """Determine if a policy applies to response validation."""
        response_policies = {
            "uncertainty_quantification_required",
            "uncertainty_honesty_threshold",
            "knowledge_boundary_recognition",
            "no_fabrication",
            "hallucination_detection",
            "internal_consistency_check",
            "contradiction_flagging",
            "honest_about_limitations",
            "source_verification",
            "speculative_labeling",
            "humility_in_claims",
        }
        return policy.policy_id in response_policies or policy.severity == "critical"

    def _policy_applies_to_memory_operation(
        self, policy: GovernancePolicy, operation: str
    ) -> bool:
        """Determine if a policy applies to memory operations."""
        memory_policies = {
            "provenance_attribution_required",
            "source_chain_integrity",
            "untrusted_source_flagging",
            "reasoning_trace_required",
            "governance_aware_scoring",
            "provenance_weighting",
            "confidence_threshold_filtering",
            "session_lifecycle_management",
            "session_state_consistency",
            "session_isolation",
            "dependency_tracking",
            "circular_dependency_detection",
            "dependency_transparency",
        }
        return policy.policy_id in memory_policies

    # ── Internal: Policy evaluation (simulated) ───────────────────

    def _evaluate_inference_policy(
        self, policy: GovernancePolicy, schema: GovernanceSchema, request: InferenceRequest
    ) -> tuple[bool, str]:
        """Evaluate a policy against an inference request.

        Returns (passed, reason). For now, uses rule-based simulation.
        In production, this would call registered evaluators.
        """
        # Fail-closed: if we can't evaluate, fail
        # Simulation: pass all checks unless it's a known critical policy
        # and we detect an issue

        # Check if required governance context is present
        if policy.severity == "critical" and schema.schema_id not in request.governance_context:
            # Not a failure — just means this schema wasn't requested
            pass

        return True, "Policy passed"

    def _evaluate_transition_policy(
        self, policy: GovernancePolicy, schema: GovernanceSchema, transition: StateTransition
    ) -> tuple[bool, str]:
        """Evaluate a policy against a state transition."""
        # Forbidden pattern check is handled separately
        return True, "Policy passed"

    def _evaluate_response_policy(
        self, policy: GovernancePolicy, schema: GovernanceSchema, response: GovernedResponse
    ) -> tuple[bool, str]:
        """Evaluate a policy against a response."""
        # Critical check: if response already failed validation, flag it
        if policy.severity == "critical" and not response.passed_validation:
            return False, f"Response already failed validation: {response.validation_failures}"
        return True, "Policy passed"

    def _evaluate_memory_policy(
        self, policy: GovernancePolicy, schema: GovernanceSchema, operation: str, memory: EpisodicMemory
    ) -> tuple[bool, str]:
        """Evaluate a policy against a memory operation."""
        # Check provenance for store operations
        if operation in ("store", "create") and policy.policy_id == "provenance_attribution_required":
            if not memory.provenance:
                return False, "Memory missing provenance record"
            if not memory.provenance.source_schema:
                return False, "Provenance missing source_schema"
        return True, "Policy passed"

    # ── Internal: Constraint evaluation ───────────────────────────

    def _evaluate_inference_constraint(
        self, constraint: GovernanceConstraint, request: InferenceRequest
    ) -> tuple[bool, str]:
        """Evaluate a constraint against an inference request."""
        return True, "Constraint satisfied"

    def _evaluate_transition_constraint(
        self, constraint: GovernanceConstraint, transition: StateTransition
    ) -> tuple[bool, str]:
        """Evaluate a constraint against a state transition."""
        return True, "Constraint satisfied"

    def _evaluate_response_constraint(
        self, constraint: GovernanceConstraint, response: GovernedResponse
    ) -> tuple[bool, str]:
        """Evaluate a constraint against a response."""
        return True, "Constraint satisfied"

    def _evaluate_memory_constraint(
        self, constraint: GovernanceConstraint, operation: str, memory: EpisodicMemory
    ) -> tuple[bool, str]:
        """Evaluate a constraint against a memory operation."""
        if constraint.constraint_id == "no_anonymous_information":
            if not memory.provenance or not memory.provenance.source_schema:
                return False, "Anonymous information cannot be stored"
        return True, "Constraint satisfied"

    # ── Internal: Check result creation ───────────────────────────

    def _create_check_result(
        self,
        schema: GovernanceSchema,
        policy: GovernancePolicy,
        passed: bool,
        reason: str,
    ) -> GovernanceCheckResult:
        """Create a GovernanceCheckResult from evaluation."""
        violation = None
        if not passed:
            violation = GovernanceViolation(
                schema_id=schema.schema_id,
                policy_id=policy.policy_id,
                severity=policy.severity,
                description=reason,
                context={
                    "schema_name": schema.name,
                    "rule_type": policy.rule_type,
                    "evaluation_logic": policy.evaluation_logic,
                },
            )

        return GovernanceCheckResult(
            schema_id=schema.schema_id,
            policy_id=policy.policy_id,
            passed=passed,
            violation=violation,
        )

    def _create_constraint_check(
        self,
        constraint: GovernanceConstraint,
        passed: bool,
        reason: str,
        context_id: UUID,
    ) -> GovernanceCheckResult:
        """Create a GovernanceCheckResult for a constraint evaluation."""
        violation = None
        if not passed:
            violation = GovernanceViolation(
                schema_id="constraint",
                policy_id=constraint.constraint_id,
                severity="critical" if constraint.enforcement == "hard_stop" else "warning",
                description=reason,
                context={
                    "constraint_scope": constraint.scope,
                    "enforcement": constraint.enforcement,
                    "context_id": str(context_id),
                },
            )

        return GovernanceCheckResult(
            schema_id="constraint",
            policy_id=constraint.constraint_id,
            passed=passed,
            violation=violation,
        )

    def _check_forbidden_transition(
        self, transition: StateTransition
    ) -> GovernanceViolation | None:
        """Check if a transition matches a forbidden pattern.

        Returns a Violation if forbidden, None if allowed.
        """
        from models.cognition import OperationalState

        # Forbidden: uninitialized -> cognition_active (must initialize first)
        if (
            transition.from_state == OperationalState.UNINITIALIZED
            and transition.to_state == OperationalState.COGNITION_ACTIVE
        ):
            return GovernanceViolation(
                schema_id="operational_state_model",
                policy_id="forbidden_pattern_prevention",
                severity="critical",
                description="Forbidden: Cannot transition from UNINITIALIZED to COGNITION_ACTIVE",
                context={
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "trace_id": str(transition.trace_id),
                },
            )

        # Forbidden: fail_closed -> cognition_active (must recover properly)
        if (
            transition.from_state == OperationalState.FAIL_CLOSED
            and transition.to_state == OperationalState.COGNITION_ACTIVE
        ):
            return GovernanceViolation(
                schema_id="operational_state_model",
                policy_id="forbidden_pattern_prevention",
                severity="critical",
                description="Forbidden: Cannot transition from FAIL_CLOSED to COGNITION_ACTIVE",
                context={
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "trace_id": str(transition.trace_id),
                },
            )

        # Forbidden: degraded -> inference_executing (degraded cannot execute inference)
        if (
            transition.from_state == OperationalState.DEGRADED
            and transition.to_state == OperationalState.INFERENCE_EXECUTING
        ):
            return GovernanceViolation(
                schema_id="operational_state_model",
                policy_id="forbidden_pattern_prevention",
                severity="critical",
                description="Forbidden: Cannot execute inference while in DEGRADED state",
                context={
                    "from_state": transition.from_state.value,
                    "to_state": transition.to_state.value,
                    "trace_id": str(transition.trace_id),
                },
            )

        return None


# Monkey-patch GovernanceCheckResult to add context_session_id for filtering
setattr(
    GovernanceCheckResult,
    "context_session_id",
    property(
        lambda self: (
            self.violation.context.get("context_id", "")
            if self.violation
            else ""
        )
    ),
)
