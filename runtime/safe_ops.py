"""Safe Operation Guardrails — runtime/safe_ops.py

Prevents unsafe operations without explicit operator approval.

Guardrails:
- Block destructive operations without confirmation
- Warn before schema changes
- Prevent workflow expansion without approval
- Preserve fail-closed state
- Log all guardrail interventions

All guardrails are fail-closed: if in doubt, block.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("garvis.runtime.safe_ops")


# ---------------------------------------------------------------------------
# SafeOperationGuardrails — prevents unsafe operations
# ---------------------------------------------------------------------------


class SafeOperationGuardrails:
    """Prevents unsafe operations without explicit operator approval.

    Guardrails:
    - Block destructive operations without confirmation
    - Warn before schema changes
    - Prevent workflow expansion without approval
    - Preserve fail-closed state
    - Log all guardrail interventions

    All guardrails are fail-closed: if in doubt, block.
    """

    # Destructive shell commands that are always blocked
    DESTRUCTIVE_COMMANDS: list[str] = [
        "rm -rf",
        "docker volume rm",
        "docker system prune",
        "git reset --hard",
        "git clean -fd",
        "docker compose down -v",
        "docker-compose down -v",
        "dd if=",
        "> /dev/",
        "mkfs.",
        "fdisk",
    ]

    # Commands that require explicit confirmation
    CONFIRMATION_REQUIRED: list[str] = [
        "docker stop",
        "docker rm",
        "docker rmi",
        "docker compose down",
        "docker-compose down",
        "git push --force",
        "git push -f",
        "git branch -D",
        "drop table",
        "drop database",
        "delete from",
        "truncate",
    ]

    # Schema changes that are considered risky
    RISKY_SCHEMA_CHANGES: list[str] = [
        "deactivate",
        "delete",
        "modify_enforcement",
        "fail_closed_disable",
    ]

    def __init__(self) -> None:
        self._intervention_log: list[dict[str, Any]] = []
        self._guardrails_enabled = True

    # ------------------------------------------------------------------
    # Command validation
    # ------------------------------------------------------------------

    def validate_command(self, command: str) -> dict[str, Any]:
        """Validate a shell command before execution.

        Checks against known destructive commands and patterns.
        All guardrails are fail-closed.

        Args:
            command: The shell command to validate.

        Returns:
            Dict with:
            - safe: True if command is safe
            - reason: Explanation of the decision
            - requires_confirmation: True if operator must confirm
            - blocked: True if command was blocked
        """
        command_lower = command.lower().strip()

        # Check 1: Guardrails disabled
        if not self._guardrails_enabled:
            self.log_guardrail_intervention(
                "validate_command",
                "Guardrails are disabled — command allowed without check",
            )
            return {
                "safe": True,
                "reason": "Guardrails are disabled — NO PROTECTION ACTIVE",
                "requires_confirmation": False,
                "blocked": False,
                "warning": "GUARDRAILS ARE DISABLED",
            }

        # Check 2: Destructive commands — always block
        for destructive in self.DESTRUCTIVE_COMMANDS:
            if destructive.lower() in command_lower:
                self.log_guardrail_intervention(
                    "validate_command",
                    f"Destructive command detected: '{destructive}' in '{command}'",
                )
                return {
                    "safe": False,
                    "reason": f"Destructive command pattern detected: '{destructive}'",
                    "requires_confirmation": True,
                    "blocked": True,
                    "action": "BLOCKED — operator must use alternative approach",
                }

        # Check 3: Commands requiring confirmation
        for confirm_req in self.CONFIRMATION_REQUIRED:
            if confirm_req.lower() in command_lower:
                self.log_guardrail_intervention(
                    "validate_command",
                    f"Confirmation-required command: '{confirm_req}' in '{command}'",
                )
                return {
                    "safe": False,
                    "reason": f"Command requires confirmation: '{confirm_req}'",
                    "requires_confirmation": True,
                    "blocked": False,
                    "action": "Requires explicit operator confirmation",
                }

        # Check 4: Pattern-based heuristics
        # Detect rm with wildcards or recursive flags
        if re.search(r"\brm\s+.*-(r|f|rf|fr)", command_lower):
            self.log_guardrail_intervention(
                "validate_command",
                f"Potentially destructive rm detected: '{command}'",
            )
            return {
                "safe": False,
                "reason": "Potentially destructive rm with recursive/force flags",
                "requires_confirmation": True,
                "blocked": True,
                "action": "BLOCKED — use safer deletion method",
            }

        # Check 5: SQL injection patterns
        sql_patterns = [
            r";\s*drop\s+",
            r";\s*delete\s+from\s+",
            r";\s*truncate\s+",
        ]
        for pattern in sql_patterns:
            if re.search(pattern, command_lower):
                self.log_guardrail_intervention(
                    "validate_command",
                    f"SQL injection pattern detected: '{command}'",
                )
                return {
                    "safe": False,
                    "reason": "SQL injection pattern detected in command",
                    "requires_confirmation": True,
                    "blocked": True,
                    "action": "BLOCKED — potential SQL injection",
                }

        # Command passed all checks
        return {
            "safe": True,
            "reason": "Command passed all guardrail checks",
            "requires_confirmation": False,
            "blocked": False,
        }

    # ------------------------------------------------------------------
    # Schema change validation
    # ------------------------------------------------------------------

    def validate_schema_change(
        self, change_type: str, schema_id: str
    ) -> dict[str, Any]:
        """Validate a governance schema change.

        Warns or blocks depending on the change type and schema.

        Args:
            change_type: Type of schema change (deactivate, modify, etc.)
            schema_id: ID of the schema being changed.

        Returns:
            Validation result dict.
        """
        change_lower = change_type.lower()

        # Check if this is a risky change
        is_risky = change_lower in [c.lower() for c in self.RISKY_SCHEMA_CHANGES]

        # Critical schemas that should never be deactivated
        critical_schemas = [
            "boundary_enforcement",
            "epistemic_safety",
            "ethical_guidelines",
        ]
        is_critical = schema_id in critical_schemas

        if is_risky and is_critical:
            self.log_guardrail_intervention(
                "validate_schema_change",
                f"CRITICAL: Attempted {change_type} on critical schema '{schema_id}'",
            )
            return {
                "allowed": False,
                "reason": (
                    f"'{schema_id}' is a CRITICAL governance schema. "
                    f"{change_type} is NOT ALLOWED without multi-operator approval."
                ),
                "requires_confirmation": True,
                "blocked": True,
                "risk_level": "critical",
                "required_approval": "operator_multi",
            }

        if is_risky:
            self.log_guardrail_intervention(
                "validate_schema_change",
                f"Risky schema change: {change_type} on '{schema_id}'",
            )
            return {
                "allowed": False,
                "reason": f"{change_type} is a risky operation on schema '{schema_id}'",
                "requires_confirmation": True,
                "blocked": False,
                "risk_level": "high",
                "required_approval": "operator_explicit",
            }

        return {
            "allowed": True,
            "reason": f"Schema change '{change_type}' on '{schema_id}' is allowed",
            "requires_confirmation": False,
            "blocked": False,
            "risk_level": "low",
        }

    # ------------------------------------------------------------------
    # Workflow validation
    # ------------------------------------------------------------------

    def validate_workflow_proposal(self, workflow: dict[str, Any]) -> dict[str, Any]:
        """Validate a proposed workflow before approval.

        Checks:
        - Workflow has required fields
        - Operations are not destructive
        - Scope is valid
        - Risk level is acceptable

        Args:
            workflow: The proposed workflow dict.

        Returns:
            Validation result dict.
        """
        # Check required fields
        required_fields = ["name", "operations"]
        missing = [f for f in required_fields if f not in workflow]
        if missing:
            return {
                "valid": False,
                "reason": f"Missing required fields: {missing}",
                "allowed": False,
            }

        workflow_name = workflow.get("name", "unnamed")
        operations = workflow.get("operations", [])

        # Check each operation
        destructive_ops: list[str] = []
        external_ops: list[str] = []

        for op in operations:
            op_type = op.get("type", "")
            if op_type in ("delete", "drop", "truncate", "rm", "purge"):
                destructive_ops.append(op_type)
            if op_type in ("api_call", "external_request", "webhook", "upload"):
                external_ops.append(op_type)

        # Classify risk
        if destructive_ops:
            risk_level = "critical"
            approval_required = "operator_multi"
        elif external_ops:
            risk_level = "high"
            approval_required = "operator_explicit"
        elif len(operations) > 5:
            risk_level = "medium"
            approval_required = "operator"
        else:
            risk_level = "low"
            approval_required = "self"

        if destructive_ops:
            self.log_guardrail_intervention(
                "validate_workflow_proposal",
                f"Workflow '{workflow_name}' contains destructive operations: {destructive_ops}",
            )
            return {
                "valid": True,
                "allowed": False,
                "risk_level": risk_level,
                "approval_required": approval_required,
                "requires_confirmation": True,
                "blocked_operations": destructive_ops,
                "reason": (
                    f"Workflow contains destructive operations: {destructive_ops}. "
                    "Multi-operator approval required."
                ),
            }

        if external_ops:
            self.log_guardrail_intervention(
                "validate_workflow_proposal",
                f"Workflow '{workflow_name}' contains external operations: {external_ops}",
            )
            return {
                "valid": True,
                "allowed": False,
                "risk_level": risk_level,
                "approval_required": approval_required,
                "requires_confirmation": True,
                "external_operations": external_ops,
                "reason": (
                    f"Workflow contains external operations: {external_ops}. "
                    "Explicit operator approval required."
                ),
            }

        return {
            "valid": True,
            "allowed": True,
            "risk_level": risk_level,
            "approval_required": approval_required,
            "requires_confirmation": approval_required != "self",
            "operation_count": len(operations),
            "reason": f"Workflow '{workflow_name}' passed guardrail validation",
        }

    # ------------------------------------------------------------------
    # Fail-closed preservation
    # ------------------------------------------------------------------

    def preserve_fail_closed(self, current_state: str) -> dict[str, Any]:
        """Ensure fail-closed state is preserved.

        Fail-closed means: if governance is uncertain, the system
        defaults to the safest (most restrictive) state.

        Args:
            current_state: The current operational state string.

        Returns:
            Dict with fail-closed assessment.
        """
        # States that are inherently fail-closed
        fail_closed_states = [
            "fail_closed",
            "uninitialized",
            "shutdown",
        ]

        # States that should transition to fail-closed on uncertainty
        safe_states = [
            "standby",
            "governance_check",
            "degraded",
        ]

        is_fail_closed = current_state in fail_closed_states
        is_safe = current_state in safe_states

        if is_fail_closed:
            return {
                "fail_closed_preserved": True,
                "current_state": current_state,
                "recommendation": "maintain",
                "reason": "System is in fail-closed state — governance preserved",
            }

        if is_safe:
            return {
                "fail_closed_preserved": True,
                "current_state": current_state,
                "recommendation": "maintain_or_progress",
                "reason": (
                    "System is in a safe state that can progress "
                    "to operating or revert to fail-closed"
                ),
            }

        # Active states — recommend caution
        return {
            "fail_closed_preserved": True,
            "current_state": current_state,
            "recommendation": "monitor",
            "reason": (
                "System is in active state — maintain governance checks. "
                "Any anomaly should transition to fail-closed."
            ),
        }

    # ------------------------------------------------------------------
    # Guardrail intervention logging
    # ------------------------------------------------------------------

    def log_guardrail_intervention(self, operation: str, reason: str) -> None:
        """Log when a guardrail prevented an operation.

        All interventions are logged for audit purposes.

        Args:
            operation: The operation that was intercepted.
            reason: Human-readable explanation.
        """
        entry = {
            "operation": operation,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "guardrails_enabled": self._guardrails_enabled,
        }
        self._intervention_log.append(entry)
        logger.warning("GUARDRAIL INTERVENTION: %s — %s", operation, reason)

    def get_intervention_log(self) -> list[dict[str, Any]]:
        """Get the guardrail intervention log.

        Returns:
            List of intervention records.
        """
        return list(self._intervention_log)

    def get_intervention_summary(self) -> dict[str, Any]:
        """Get a summary of guardrail interventions.

        Returns:
            Summary dict with counts by operation type.
        """
        by_operation: dict[str, int] = {}
        for entry in self._intervention_log:
            op = entry["operation"]
            by_operation[op] = by_operation.get(op, 0) + 1

        return {
            "total_interventions": len(self._intervention_log),
            "by_operation": by_operation,
            "guardrails_enabled": self._guardrails_enabled,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Guardrail management
    # ------------------------------------------------------------------

    def enable_guardrails(self) -> dict[str, Any]:
        """Enable guardrails.

        Returns:
            Status dict.
        """
        was_enabled = self._guardrails_enabled
        self._guardrails_enabled = True
        logger.info("Guardrails enabled")
        return {
            "action": "enable_guardrails",
            "status": "enabled",
            "was_already_enabled": was_enabled,
        }

    def disable_guardrails(self, operator_id: str, reason: str) -> dict[str, Any]:
        """Disable guardrails — requires confirmation and logs warning.

        Args:
            operator_id: Operator disabling guardrails.
            reason: Reason for disabling.

        Returns:
            Status dict with warning.
        """
        self.log_guardrail_intervention(
            "disable_guardrails",
            f"Guardrails DISABLED by '{operator_id}'. Reason: {reason}",
        )
        return {
            "action": "disable_guardrails",
            "status": "requires_confirmation",
            "warning": (
                "DISABLING GUARDRAILS IS EXTREMELY DANGEROUS. "
                "All safety protections will be removed."
            ),
            "requested_by": operator_id,
            "reason": reason,
            "required_response": "Type 'yes I understand' to confirm",
        }

    def get_status(self) -> dict[str, Any]:
        """Get current guardrail status.

        Returns:
            Status dict.
        """
        return {
            "enabled": self._guardrails_enabled,
            "destructive_patterns_blocked": len(self.DESTRUCTIVE_COMMANDS),
            "confirmation_required_patterns": len(self.CONFIRMATION_REQUIRED),
            "risky_schema_changes_tracked": len(self.RISKY_SCHEMA_CHANGES),
            "total_interventions": len(self._intervention_log),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
