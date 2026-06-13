"""Governance Negotiation View — cognition/negotiation.py

When governance blocks or modifies something, this system explains WHY.

Core principles:
- Every block is explained with full reasoning
- The operator can see exactly which schemas were triggered
- The operator can see what would need to change for approval
- Uncertainty is always disclosed
- Escalation paths are documented (require multi-step approval)

This is NOT an appeal system — it is a TRANSPARENCY system.
The goal is full reasoning visibility, not override capability.
"""

from __future__ import annotations

import logging
from typing import Any

from models.governance import GovernanceViolation, GovernanceCheckResult, GovernanceSchema

logger = logging.getLogger("garvis.cognition.negotiation")


# ---------------------------------------------------------------------------
# GovernanceNegotiation — explains governance decisions
# ---------------------------------------------------------------------------


class GovernanceNegotiation:
    """Explains WHY governance made decisions.

    When governance blocks or modifies something, this system:
    - Explains which schemas were triggered
    - Explains why the action was blocked/modified
    - Shows what would need to change for approval
    - Provides uncertainty disclosures
    - Shows escalation path if operator disagrees
    """

    def __init__(self) -> None:
        self._block_explanations: list[dict[str, Any]] = []
        self._modification_explanations: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Explain a block
    # ------------------------------------------------------------------

    def explain_block(
        self, violation: GovernanceViolation, blocked_action: str | None = None
    ) -> dict[str, Any]:
        """Explain why an action was blocked.

        Returns a comprehensive explanation that includes:
        - What was blocked
        - Which schema blocked it
        - Which specific policy
        - Human-readable explanation of why
        - What to do instead
        - Escalation path (requires multi-step approval)
        - Uncertainty disclosure

        Args:
            violation: The governance violation that caused the block
            blocked_action: Optional description of the blocked action

        Returns:
            Dict with full block explanation
        """
        action = blocked_action or "the requested action"

        explanation = self._generate_block_explanation(violation, action)
        recommendation = self._generate_recommendation(violation, action)
        escalation = self._generate_escalation_path(violation)
        uncertainty = self._generate_uncertainty_disclosure(violation)

        result = {
            "explanation_type": "block",
            "blocked_action": action,
            "blocking_schema": violation.schema_id,
            "blocking_policy": violation.policy_id,
            "severity": violation.severity,
            "explanation": explanation,
            "recommendation": recommendation,
            "escalation_path": escalation,
            "uncertainty_disclosure": uncertainty,
            "operator_can_escalate": True,
            "escalation_requirements": [
                "secondary_operator_review",
                "governance_admin_approval",
                "document_rationale",
            ],
            "timestamp": violation.timestamp.isoformat() if hasattr(violation.timestamp, "isoformat") else str(violation.timestamp),
        }

        # Store for history
        self._block_explanations.append(result)

        logger.info(
            "Block explained: schema=%s, policy=%s, action='%s...'",
            violation.schema_id,
            violation.policy_id,
            action[:50] if action else "",
        )

        return result

    # ------------------------------------------------------------------
    # Explain a modification
    # ------------------------------------------------------------------

    def explain_modification(
        self,
        original: str,
        mediated: str,
        schemas_applied: list[str],
        checks: list[GovernanceCheckResult] | None = None,
    ) -> dict[str, Any]:
        """Explain how governance modified a prompt/action.

        When governance doesn't block outright but modifies the content,
        this explains what changed and why.

        Args:
            original: The original content before modification
            mediated: The content after governance mediation
            schemas_applied: List of schema IDs that were applied
            checks: Optional list of governance checks that triggered modification

        Returns:
            Dict with full modification explanation
        """
        # Identify what changed
        differences = self._identify_differences(original, mediated)

        explanation = self._generate_modification_explanation(
            original, mediated, schemas_applied, differences
        )

        result = {
            "explanation_type": "modification",
            "original_preview": original[:200] + "..." if len(original) > 200 else original,
            "mediated_preview": mediated[:200] + "..." if len(mediated) > 200 else mediated,
            "schemas_applied": schemas_applied,
            "differences": differences,
            "explanation": explanation,
            "recommendation": (
                "The modified version is governance-safe and ready for use. "
                "If the modifications materially change your intent, "
                "you may escalate for review."
            ),
            "uncertainty_disclosure": (
                "Governance mediation is based on active schemas and may not "
                "catch all edge cases. The mediated output should still be "
                "reviewed by the operator for semantic correctness."
            ),
            "escalation_path": (
                "To use the original unmediated version, escalate to governance "
                "admin with documentation of why the original is necessary."
            ),
            "checks_triggered": [
                {
                    "schema_id": c.schema_id,
                    "policy_id": c.policy_id,
                    "passed": c.passed,
                    "violation": (
                        {
                            "description": c.violation.description,
                            "severity": c.violation.severity,
                        }
                        if c.violation
                        else None
                    ),
                }
                for c in (checks or [])
            ],
        }

        self._modification_explanations.append(result)

        logger.info(
            "Modification explained: schemas=%s, differences=%d",
            schemas_applied,
            len(differences),
        )

        return result

    # ------------------------------------------------------------------
    # Explain uncertainty
    # ------------------------------------------------------------------

    def explain_uncertainty(self, context: dict[str, Any]) -> dict[str, Any]:
        """Explain uncertainty in a given context.

        Provides transparency about what is known, what is uncertain,
        and the basis for confidence levels.

        Args:
            context: Dict with keys like:
                - confidence_score: float
                - reasoning_steps: list[str]
                - memory_sources: list[dict]
                - governance_checks: list[GovernanceCheckResult]
                - topic: str

        Returns:
            Dict with structured uncertainty explanation
        """
        confidence = context.get("confidence_score", 0.5)
        topic = context.get("topic", "the requested analysis")
        reasoning_steps = context.get("reasoning_steps", [])
        memory_sources = context.get("memory_sources", [])
        checks = context.get("governance_checks", [])

        # Categorize uncertainty
        uncertainty_level = self._categorize_uncertainty(confidence)

        # Identify sources of uncertainty
        uncertainty_sources = []

        if confidence < 0.6:
            uncertainty_sources.append(
                "Limited confidence in reasoning chain"
            )
        if not memory_sources:
            uncertainty_sources.append("No relevant memory sources available")
        elif len(memory_sources) < 2:
            uncertainty_sources.append("Only one memory source — limited corroboration")

        failed_checks = [c for c in checks if not c.passed]
        if failed_checks:
            for fc in failed_checks:
                if fc.violation and fc.violation.severity == "warning":
                    uncertainty_sources.append(
                        f"Warning-level governance check: {fc.schema_id}/{fc.policy_id}"
                    )

        if not reasoning_steps:
            uncertainty_sources.append("No reasoning trace available")

        # Build basis of confidence
        confidence_basis = []
        if checks:
            passed = sum(1 for c in checks if c.passed)
            confidence_basis.append(
                f"{passed}/{len(checks)} governance checks passed"
            )
        if memory_sources:
            confidence_basis.append(
                f"{len(memory_sources)} memory source(s) informing this analysis"
            )
        if reasoning_steps:
            confidence_basis.append(
                f"{len(reasoning_steps)} reasoning step(s) documented"
            )

        return {
            "explanation_type": "uncertainty",
            "topic": topic,
            "confidence_score": confidence,
            "uncertainty_level": uncertainty_level,
            "uncertainty_sources": uncertainty_sources or ["Standard epistemic uncertainty"],
            "confidence_basis": confidence_basis or ["General reasoning capability"],
            "what_is_known": self._describe_what_is_known(context),
            "what_is_uncertain": self._describe_what_is_uncertain(context),
            "recommendation": self._uncertainty_recommendation(confidence, uncertainty_sources),
            "epistemic_boundary_note": (
                "All reasoning is bounded by the governance schemas in effect "
                "and the available memory. New information or schema changes "
                "could alter these conclusions."
            ),
        }

    # ------------------------------------------------------------------
    # Generate negotiation view for a session
    # ------------------------------------------------------------------

    def generate_negotiation_view(
        self, session_id: str, interactions: list[dict[str, Any]] | None = None
    ) -> dict[str, Any]:
        """Generate a complete negotiation view for a session.

        Shows all governance decisions with explanations.

        Args:
            session_id: The collaboration session ID
            interactions: Optional list of interaction dicts to analyze

        Returns:
            Complete negotiation view with all governance decisions
        """
        view = {
            "session_id": session_id,
            "view_type": "negotiation",
            "description": (
                "This view shows all governance decisions made during the session "
                "with full explanations. It is the transparency layer between "
                "operators and governance."
            ),
            "block_decisions": [],
            "modification_decisions": [],
            "approval_paths": [],
            "statistics": {},
        }

        # Use stored explanations or provided interactions
        if interactions:
            # Analyze interactions to find blocks and modifications
            for interaction in interactions:
                response = interaction.get("response", {})
                response_type = response.get("response_type", "")

                if response_type == "block":
                    gov_checks = interaction.get("governance_checks", [])
                    failed = [c for c in gov_checks if not c.get("passed", True)]
                    for f in failed:
                        view["block_decisions"].append({
                            "interaction_id": interaction.get("interaction_id"),
                            "blocked_schema": f.get("schema_id"),
                            "blocked_policy": f.get("policy_id"),
                            "has_violation": f.get("has_violation", False),
                            "explanation": (
                                f"Blocked by {f.get('schema_id')}/{f.get('policy_id')}: "
                                f"violation detected"
                            ),
                        })

        # Add stored block explanations
        for exp in self._block_explanations:
            view["block_decisions"].append({
                "blocking_schema": exp["blocking_schema"],
                "blocking_policy": exp["blocking_policy"],
                "severity": exp["severity"],
                "explanation": exp["explanation"],
                "recommendation": exp["recommendation"],
            })

        # Add stored modification explanations
        for exp in self._modification_explanations:
            view["modification_decisions"].append({
                "schemas_applied": exp["schemas_applied"],
                "differences_count": len(exp["differences"]),
                "explanation": exp["explanation"],
            })

        # Calculate statistics
        total_blocks = len(view["block_decisions"])
        total_mods = len(view["modification_decisions"])
        critical_blocks = sum(
            1 for b in view["block_decisions"]
            if b.get("severity") == "critical"
        )

        view["statistics"] = {
            "total_blocks": total_blocks,
            "total_modifications": total_mods,
            "critical_blocks": critical_blocks,
            "warning_blocks": total_blocks - critical_blocks,
            "approval_paths_available": total_blocks > 0,
        }

        # Add approval paths for blocked actions
        if total_blocks > 0:
            view["approval_paths"].append(
                self.suggest_approval_path("general_blocked_action")
            )

        view["transparency_note"] = (
            "Every decision above was made by active governance schemas. "
            "No decision was made autonomously. All reasoning is visible."
        )

        return view

    # ------------------------------------------------------------------
    # Suggest approval path
    # ------------------------------------------------------------------

    def suggest_approval_path(self, blocked_action: str) -> dict[str, Any]:
        """Suggest what the operator can do to get a blocked action approved.

        Returns step-by-step path with governance requirements.

        Args:
            blocked_action: Description of the blocked action

        Returns:
            Dict with step-by-step approval path
        """
        return {
            "blocked_action": blocked_action,
            "approval_possible": True,
            "path_type": "multi_step_operator_approval",
            "steps": [
                {
                    "step": 1,
                    "title": "Review Block Explanation",
                    "description": (
                        "Read the full explanation above to understand WHY "
                        "the action was blocked. This is not arbitrary — "
                        "it is based on active governance schemas."
                    ),
                    "required": True,
                    "actor": "operator",
                },
                {
                    "step": 2,
                    "title": "Modify Request",
                    "description": (
                        "Adjust the blocked action to comply with the governance "
                        "schema that triggered the block. The recommendation above "
                        "suggests how to modify."
                    ),
                    "required": False,
                    "actor": "operator",
                    "alternative": "Skip to escalation if modification is not possible",
                },
                {
                    "step": 3,
                    "title": "Resubmit for Governance Check",
                    "description": (
                        "Submit the modified action. It will go through the same "
                        "governance validation pipeline. If it passes, it proceeds."
                    ),
                    "required": True,
                    "actor": "system",
                },
                {
                    "step": 4,
                    "title": "Escalation Review (if still blocked)",
                    "description": (
                        "If the modified action is still blocked, escalate to "
                        "governance admin for multi-operator review."
                    ),
                    "required": False,
                    "actor": "governance_admin",
                    "conditions": "Only if Steps 1-3 do not resolve the block",
                },
                {
                    "step": 5,
                    "title": "Document Override Rationale",
                    "description": (
                        "If governance admin approves override, document the "
                        "rationale in the audit log. All overrides are traceable."
                    ),
                    "required": True,
                    "actor": "governance_admin",
                    "only_if": "override_approved",
                },
                {
                    "step": 6,
                    "title": "Temporary Schema Adjustment",
                    "description": (
                        "As last resort, the governance schema itself may be "
                        "deactivated (requires admin). This reduces governance "
                        "coverage and is NOT recommended."
                    ),
                    "required": False,
                    "actor": "governance_admin",
                    "warning": (
                        "Deactivating schemas reduces safety. This should only be "
                        "done with full understanding of the consequences."
                    ),
                },
            ],
            "estimated_time": "5-15 minutes depending on complexity",
            "override_always_audited": True,
            "single_operator_cannot_override": True,
        }

    # ------------------------------------------------------------------
    # Internal: Explanation generation
    # ------------------------------------------------------------------

    def _generate_block_explanation(
        self, violation: GovernanceViolation, action: str
    ) -> str:
        """Generate a human-readable explanation of why an action was blocked."""
        explanations = {
            "boundary_enforcement": (
                f"The action '{action[:60]}...' was blocked because it violates "
                f"boundary enforcement policy {violation.policy_id}. "
                f"This policy prevents operations that could compromise system "
                f"integrity or security boundaries. "
                f"Specifically: {violation.description}"
            ),
            "epistemic_safety": (
                f"The action was blocked by epistemic safety policy {violation.policy_id}. "
                f"This policy ensures the system does not overclaim knowledge or "
                f"certainty. {violation.description}"
            ),
            "operational_integrity": (
                f"The action was blocked by operational integrity policy {violation.policy_id}. "
                f"This maintains runtime stability and resource constraints. "
                f"{violation.description}"
            ),
            "ethical_guidelines": (
                f"The action was blocked by ethical guidelines policy {violation.policy_id}. "
                f"This protects against harmful outputs. "
                f"{violation.description}"
            ),
            "session_management": (
                f"The action was blocked by session management policy {violation.policy_id}. "
                f"This ensures proper session lifecycle and resource limits. "
                f"{violation.description}"
            ),
            "traceability_requirement": (
                f"The action was blocked because traceability requirements were not met. "
                f"Policy {violation.policy_id}: {violation.description}"
            ),
            "operational_state_model": (
                f"The action was blocked by the operational state model. "
                f"The requested state transition is forbidden. "
                f"{violation.description}"
            ),
        }

        return explanations.get(
            violation.schema_id,
            (
                f"The action '{action[:60]}...' was blocked by governance schema "
                f"'{violation.schema_id}' (policy: {violation.policy_id}). "
                f"Severity: {violation.severity}. "
                f"Reason: {violation.description}"
            ),
        )

    def _generate_recommendation(
        self, violation: GovernanceViolation, action: str
    ) -> str:
        """Generate a recommendation for what to do instead."""
        recommendations = {
            "boundary_enforcement": (
                "Remove any code, shell commands, or network references from your request. "
                "Rephrase as a conceptual question or use the approved analysis tools."
            ),
            "epistemic_safety": (
                "Frame your request with appropriate uncertainty qualifiers. "
                "Avoid asking for absolute certainty. Request analysis with "
                "confidence intervals instead."
            ),
            "operational_integrity": (
                "Reduce the scope of the request or break it into smaller steps. "
                "Check that the request stays within resource and timeout limits."
            ),
            "ethical_guidelines": (
                "Rephrase the request to remove potentially harmful elements. "
                "If this is for legitimate research, escalate for admin review."
            ),
            "session_management": (
                "Close idle sessions or wait for existing operations to complete. "
                "Check session limits in the governance configuration."
            ),
            "traceability_requirement": (
                "Ensure the request can produce a complete trace. "
                "Avoid operations that bypass the audit pipeline."
            ),
            "operational_state_model": (
                "Follow the proper state transition sequence. "
                "Use RECOVERING state before transitioning from FAIL_CLOSED."
            ),
        }

        return recommendations.get(
            violation.schema_id,
            (
                "Review the governance schema documentation and modify your request "
                "to comply with the stated policy. If you believe this is an error, "
                "use the escalation path."
            ),
        )

    def _generate_escalation_path(self, violation: GovernanceViolation) -> str:
        """Generate the escalation path for a blocked action."""
        if violation.severity == "critical":
            return (
                "CRITICAL escalation path:\n"
                "1. A second operator must review and confirm the escalation request\n"
                "2. Governance admin must approve the override\n"
                "3. Full rationale must be documented in the audit log\n"
                "4. The override is temporary and time-bounded\n"
                "5. All activity during the override is logged at TRACE level\n"
                "Note: Critical blocks should NOT be overridden without extremely "
                "strong justification."
            )
        elif violation.severity == "warning":
            return (
                "WARNING escalation path:\n"
                "1. Operator documents why the warning should be overridden\n"
                "2. Governance admin reviews and approves\n"
                "3. Override is logged with full rationale\n"
                "4. The action proceeds with enhanced monitoring\n"
                "Warning-level blocks are less restrictive but still require "
                "multi-step approval."
            )
        else:
            return (
                "INFO escalation path:\n"
                "1. Operator acknowledges the governance note\n"
                "2. Override is auto-logged\n"
                "3. No additional approval required for info-level items"
            )

    def _generate_uncertainty_disclosure(
        self, violation: GovernanceViolation
    ) -> str:
        """Generate uncertainty disclosure for a block explanation."""
        return (
            f"This block explanation is based on governance schema '{violation.schema_id}' "
            f"version currently active in the runtime. The explanation reflects the "
            f"best available understanding of why the action was blocked. If the "
            f"schema has been recently updated, the explanation may not reflect the "
            f"latest policy intent. All schema versions and change history are "
            f"available in the governance audit log."
        )

    # ------------------------------------------------------------------
    # Internal: Modification helpers
    # ------------------------------------------------------------------

    def _identify_differences(self, original: str, mediated: str) -> list[dict[str, str]]:
        """Identify differences between original and mediated content."""
        differences = []

        # Simple word-level diff simulation
        orig_words = set(original.lower().split())
        med_words = set(mediated.lower().split())

        removed = orig_words - med_words
        added = med_words - orig_words

        if removed:
            differences.append({
                "type": "removed",
                "description": f"Removed terms: {', '.join(list(removed)[:5])}",
                "reason": "Terms violated governance policies",
            })
        if added:
            differences.append({
                "type": "added",
                "description": f"Added qualifying language",
                "reason": "Governance requires additional context",
            })

        if not differences:
            differences.append({
                "type": "none_significant",
                "description": "No significant changes required",
                "reason": "Content was already governance-compliant",
            })

        return differences

    def _generate_modification_explanation(
        self,
        original: str,
        mediated: str,
        schemas_applied: list[str],
        differences: list[dict],
    ) -> str:
        """Generate human-readable modification explanation."""
        schema_names = ", ".join(schemas_applied)

        explanation = (
            f"Your original input was reviewed by {len(schemas_applied)} governance "
            f"schema(s): {schema_names}.\n\n"
        )

        if any(d["type"] == "removed" for d in differences):
            explanation += (
                "Some content was removed because it triggered governance policies. "
                "This is to ensure safe and compliant operation.\n\n"
            )

        explanation += (
            "The mediated version preserves your intent while ensuring "
            "full governance compliance. If the mediation has materially "
            "changed your request, you may escalate for review."
        )

        return explanation

    # ------------------------------------------------------------------
    # Internal: Uncertainty helpers
    # ------------------------------------------------------------------

    def _categorize_uncertainty(self, confidence: float) -> str:
        """Categorize uncertainty level from confidence score."""
        if confidence < 0.2:
            return "very_high"
        elif confidence < 0.4:
            return "high"
        elif confidence < 0.6:
            return "moderate"
        elif confidence < 0.8:
            return "low"
        else:
            return "very_low"

    def _describe_what_is_known(self, context: dict[str, Any]) -> str:
        """Describe what is known with reasonable confidence."""
        parts = []
        checks = context.get("governance_checks", [])
        passed = [c for c in checks if getattr(c, "passed", c.get("passed", False))]
        if passed:
            parts.append(
                f"{len(passed)} governance checks have passed, providing "
                f"validation baseline."
            )
        memory = context.get("memory_sources", [])
        if memory:
            parts.append(
                f"{len(memory)} memory source(s) provide historical context."
            )
        if not parts:
            parts.append("Basic reasoning capability is available.")
        return " ".join(parts)

    def _describe_what_is_uncertain(self, context: dict[str, Any]) -> str:
        """Describe what remains uncertain."""
        parts = []
        confidence = context.get("confidence_score", 0.5)
        if confidence < 0.6:
            parts.append(
                "The confidence score indicates significant remaining uncertainty."
            )
        memory = context.get("memory_sources", [])
        if not memory:
            parts.append("No memory sources are available to corroborate.")
        checks = context.get("governance_checks", [])
        failed = [c for c in checks if not getattr(c, "passed", c.get("passed", False))]
        if failed:
            parts.append(
                f"{len(failed)} governance check(s) raised warnings."
            )
        if not parts:
            parts.append("Standard epistemic uncertainty applies.")
        return " ".join(parts)

    def _uncertainty_recommendation(
        self, confidence: float, uncertainty_sources: list[str]
    ) -> str:
        """Generate recommendation based on uncertainty."""
        if confidence < 0.3:
            return (
                "Given high uncertainty, operator review is strongly advised before "
                "acting on this analysis. Consider gathering more information."
            )
        elif confidence < 0.6:
            return (
                "Moderate uncertainty exists. The analysis provides reasonable "
                "guidance but should be supplemented with operator judgment."
            )
        elif uncertainty_sources and len(uncertainty_sources) > 2:
            return (
                "Despite reasonable confidence, multiple uncertainty sources exist. "
                "Review the specific sources listed above."
            )
        else:
            return (
                "Confidence is good. The analysis is well-supported, but always "
                "remain open to new information that may change conclusions."
            )
