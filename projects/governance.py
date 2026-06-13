"""Project Governance — projects/governance.py

Per-project governance system that inherits from global governance
and adds project-specific constraints. All operations are scoped
to the active project context.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from models.governance import (
    GovernanceCheckResult,
    GovernanceConstraint,
    GovernanceSchema,
    GovernanceViolation,
)

logger = logging.getLogger("garvis.projects.governance")


# ---------------------------------------------------------------------------
# ProjectGovernance — governance scoped to a single project
# ---------------------------------------------------------------------------


class ProjectGovernance:
    """Governance system scoped to a specific project.

    Each project has:
    - Its own active governance schemas (subset of global)
    - Its own governance constraints
    - Its own operational boundaries
    - Its own audit trail

    Projects inherit global governance but can have additional
    project-specific constraints.
    """

    # Severity ranking for ordering enforcement
    SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

    # Enforcement priority ranking
    ENFORCEMENT_ORDER = {"hard_stop": 0, "degrade": 1, "log_only": 2}

    def __init__(self, project_id: str, global_registry: Any) -> None:
        self.project_id = project_id
        self.global_registry = global_registry
        self._active_schemas: set[str] = set()
        self._project_constraints: list[GovernanceConstraint] = []
        self._constraint_audit_log: list[dict[str, Any]] = []
        self._initialized = False

    # ── Lifecycle ─────────────────────────────────────────────────

    def initialize(self, schema_ids: list[str] | None = None) -> None:
        """Initialize project governance with specified schemas.

        If no schemas specified, uses all global active schemas.

        Args:
            schema_ids: Optional list of schema IDs to activate for this project.
                       If None, all globally active schemas are inherited.
        """
        logger.info(
            "ProjectGovernance.initialize() — project=%s, schemas=%s",
            self.project_id,
            schema_ids or "(all global active)",
        )

        # Get schemas from global registry
        global_active = self.global_registry.get_active_schema_ids()

        if schema_ids is not None:
            # Validate requested schemas exist globally
            for sid in schema_ids:
                if sid not in global_active:
                    logger.warning(
                        "Schema '%s' not globally active, skipping for project '%s'",
                        sid,
                        self.project_id,
                    )
                    continue
                self._active_schemas.add(sid)
        else:
            # Inherit all globally active schemas
            self._active_schemas = set(global_active)

        self._initialized = True
        logger.info(
            "ProjectGovernance initialized: project=%s, schemas=%d, constraints=%d",
            self.project_id,
            len(self._active_schemas),
            len(self._project_constraints),
        )

    # ── Project-Specific Constraints ──────────────────────────────

    def add_project_constraint(
        self, constraint: GovernanceConstraint, operator_id: str
    ) -> dict[str, Any]:
        """Add a project-specific governance constraint.

        Requires operator approval. The constraint is recorded in the
        audit trail and applied in addition to global constraints.

        Args:
            constraint: The governance constraint to add.
            operator_id: ID of the operator adding the constraint.

        Returns:
            Result dict with operation status.
        """
        if not operator_id:
            return {
                "status": "error",
                "reason": "operator_id required to add project constraint",
            }

        # Check for duplicate constraint ID
        existing = [
            c for c in self._project_constraints
            if c.constraint_id == constraint.constraint_id
        ]
        if existing:
            return {
                "status": "error",
                "reason": (
                    f"Constraint '{constraint.constraint_id}' "
                    f"already exists for project '{self.project_id}'"
                ),
            }

        self._project_constraints.append(constraint)

        # Audit log entry
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "constraint_added",
            "operator_id": operator_id,
            "project_id": self.project_id,
            "constraint_id": constraint.constraint_id,
            "constraint_scope": constraint.scope,
            "constraint_enforcement": constraint.enforcement,
        }
        self._constraint_audit_log.append(audit_entry)

        logger.info(
            "Project constraint added: project=%s, constraint=%s, operator=%s",
            self.project_id,
            constraint.constraint_id,
            operator_id,
        )

        return {
            "status": "added",
            "project_id": self.project_id,
            "constraint_id": constraint.constraint_id,
            "operator_id": operator_id,
        }

    def remove_project_constraint(
        self, constraint_id: str, operator_id: str
    ) -> bool:
        """Remove a project-specific constraint.

        Requires operator approval. Global constraints cannot be removed
        at the project level — only project-specific ones.

        Args:
            constraint_id: ID of the constraint to remove.
            operator_id: ID of the operator removing the constraint.

        Returns:
            True if constraint was removed, False if not found.
        """
        if not operator_id:
            return False

        for i, constraint in enumerate(self._project_constraints):
            if constraint.constraint_id == constraint_id:
                removed = self._project_constraints.pop(i)

                # Audit log entry
                audit_entry = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "action": "constraint_removed",
                    "operator_id": operator_id,
                    "project_id": self.project_id,
                    "constraint_id": removed.constraint_id,
                }
                self._constraint_audit_log.append(audit_entry)

                logger.info(
                    "Project constraint removed: project=%s, constraint=%s, operator=%s",
                    self.project_id,
                    removed.constraint_id,
                    operator_id,
                )
                return True

        logger.warning(
            "Project constraint not found: project=%s, constraint=%s",
            self.project_id,
            constraint_id,
        )
        return False

    # ── Validation ────────────────────────────────────────────────

    def validate_operation(
        self, operation: str, context: dict[str, Any]
    ) -> list[GovernanceCheckResult]:
        """Validate an operation within this project's governance scope.

        Checks against both global schemas (filtered to active) and
        project-specific constraints.

        Args:
            operation: The operation being validated.
            context: Additional context for validation.

        Returns:
            List of governance check results.
        """
        results: list[GovernanceCheckResult] = []

        # Get active schemas for this project
        active_schemas = self.get_active_schemas()

        for schema in active_schemas:
            for policy in schema.policies:
                # Evaluate policy against operation and context
                passed = self._evaluate_policy(policy, operation, context)
                violation = None
                if not passed:
                    violation = GovernanceViolation(
                        schema_id=schema.schema_id,
                        policy_id=policy.policy_id,
                        severity=policy.severity,
                        description=f"Policy '{policy.policy_id}' violated for operation '{operation}'",
                        context={"project_id": self.project_id, "operation": operation},
                    )

                results.append(
                    GovernanceCheckResult(
                        schema_id=schema.schema_id,
                        policy_id=policy.policy_id,
                        passed=passed,
                        violation=violation,
                    )
                )

        # Check project-specific constraints
        for constraint in self._project_constraints:
            passed = self._evaluate_constraint(constraint, operation, context)
            if not passed:
                results.append(
                    GovernanceCheckResult(
                        schema_id=f"project:{self.project_id}",
                        policy_id=constraint.constraint_id,
                        passed=False,
                        violation=GovernanceViolation(
                            schema_id=f"project:{self.project_id}",
                            policy_id=constraint.constraint_id,
                            severity="critical",
                            description=f"Project constraint '{constraint.constraint_id}' violated",
                            context={"project_id": self.project_id, "operation": operation},
                        ),
                    )
                )

        logger.debug(
            "Operation validated: project=%s, operation=%s, checks=%d, passed=%d",
            self.project_id,
            operation,
            len(results),
            sum(1 for r in results if r.passed),
        )

        return results

    def _evaluate_policy(
        self, policy: Any, operation: str, context: dict[str, Any]
    ) -> bool:
        """Evaluate a single policy against an operation.

        Simplified evaluation — in production this would use the
        full evaluation_logic referenced by the policy.

        Args:
            policy: The policy to evaluate.
            operation: The operation being checked.
            context: Validation context.

        Returns:
            True if policy passes, False if violated.
        """
        # Check for prohibitions
        if policy.rule_type == "prohibition":
            prohibited_ops = context.get("prohibited_operations", [])
            if operation in prohibited_ops:
                return False

        # Check for required operations
        if policy.rule_type == "requirement":
            required_ops = context.get("required_operations", [])
            if required_ops and operation not in required_ops:
                return True  # Requirement only applies to required ops

        # Check for threshold violations
        if policy.rule_type == "threshold":
            threshold = context.get("threshold")
            value = context.get("value")
            if threshold is not None and value is not None:
                if policy.severity == "critical" and value > threshold:
                    return False

        # Default: pass
        return True

    def _evaluate_constraint(
        self, constraint: GovernanceConstraint, operation: str, context: dict[str, Any]
    ) -> bool:
        """Evaluate a project-specific constraint.

        Args:
            constraint: The constraint to evaluate.
            operation: The operation being checked.
            context: Validation context.

        Returns:
            True if constraint is satisfied, False if violated.
        """
        # Hard constraints on specific operations
        restricted_ops = context.get("restricted_operations", [])
        if constraint.enforcement == "hard_stop" and operation in restricted_ops:
            return False
        return True

    # ── Queries ───────────────────────────────────────────────────

    def get_active_schemas(self) -> list[GovernanceSchema]:
        """Get all active schemas for this project.

        Returns schemas from the global registry that are active
        for this project.

        Returns:
            List of active GovernanceSchema objects.
        """
        schemas = []
        for sid in self._active_schemas:
            schema = self.global_registry.get_schema(sid)
            if schema is not None:
                schemas.append(schema)
        return schemas

    def get_project_constraints(self) -> list[GovernanceConstraint]:
        """Get project-specific constraints.

        Returns:
            List of GovernanceConstraint objects added at project level.
        """
        return list(self._project_constraints)

    def get_global_constraints_for_project(self) -> list[GovernanceConstraint]:
        """Get global constraints from active schemas.

        Returns:
            List of GovernanceConstraint objects from global schemas.
        """
        constraints: list[GovernanceConstraint] = []
        for schema in self.get_active_schemas():
            constraints.extend(schema.constraints)
        return constraints

    def get_all_constraints(self) -> list[GovernanceConstraint]:
        """Get all constraints applicable to this project.

        Combines global constraints from active schemas with
        project-specific constraints.

        Returns:
            Combined list of GovernanceConstraint objects.
        """
        global_constraints = self.get_global_constraints_for_project()
        return global_constraints + self._project_constraints

    def get_health(self) -> dict[str, Any]:
        """Get project governance health: coverage, pressure, violations.

        Returns:
            Dict with governance health metrics.
        """
        active_schemas = self.get_active_schemas()
        project_constraints = self.get_project_constraints()
        global_constraints = self.get_global_constraints_for_project()

        # Calculate coverage score
        total_global = len(self.global_registry.get_active_schema_ids())
        coverage = (
            len(self._active_schemas) / total_global
            if total_global > 0 else 1.0
        )

        # Calculate constraint pressure
        total_constraints = len(global_constraints) + len(project_constraints)
        hard_stop_count = sum(
            1 for c in global_constraints + project_constraints
            if c.enforcement == "hard_stop"
        )
        pressure = hard_stop_count / total_constraints if total_constraints > 0 else 0.0

        return {
            "project_id": self.project_id,
            "initialized": self._initialized,
            "schema_coverage": round(coverage, 2),
            "active_schemas": len(self._active_schemas),
            "global_schemas_available": total_global,
            "project_constraints": len(project_constraints),
            "global_constraints_inherited": len(global_constraints),
            "total_constraints": total_constraints,
            "hard_stop_constraints": hard_stop_count,
            "constraint_pressure": round(pressure, 2),
            "status": (
                "healthy" if coverage >= 0.8 and pressure <= 0.5
                else "elevated" if coverage >= 0.5
                else "critical"
            ),
        }

    def get_constraint_audit_log(self) -> list[dict[str, Any]]:
        """Get audit log of constraint changes.

        Returns:
            List of audit entries for constraint additions/removals.
        """
        return list(self._constraint_audit_log)

    def __repr__(self) -> str:
        return (
            f"ProjectGovernance("
            f"project_id='{self.project_id}', "
            f"schemas={len(self._active_schemas)}, "
            f"constraints={len(self._project_constraints)})"
        )
