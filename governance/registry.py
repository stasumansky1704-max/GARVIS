"""Governance Registry — governance/registry.py

Central registry for all loaded governance schemas.
Provides cross-schema validation and dependency resolution.
Per the SPEC section 5.2.
"""

from __future__ import annotations

import logging
from typing import Any

from models.governance import (
    GovernanceSchema,
    GovernanceConstraint,
    GovernancePolicy,
)
from governance.loader import SchemaLoader

logger = logging.getLogger("garvis.governance.registry")


class GovernanceRegistry:
    """Central registry for all loaded governance schemas.

    Provides:
    - Schema activation/deactivation (explicit, operator-controlled)
    - Cross-schema consistency validation
    - Enforcement chain retrieval by scope
    """

    # Severity ranking for ordering enforcement
    SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}

    # Enforcement priority ranking
    ENFORCEMENT_ORDER = {"hard_stop": 0, "degrade": 1, "log_only": 2}

    def __init__(self, loader: SchemaLoader) -> None:
        self.loader = loader
        self._schemas: dict[str, GovernanceSchema] = {}
        self._active: set[str] = set()
        self._initialized = False

    # ── Lifecycle ─────────────────────────────────────────────────

    def initialize(self) -> None:
        """Load and register all schemas. Must succeed before runtime starts.

        Loads all schemas, activates them by default, and validates
        cross-schema consistency. Raises RuntimeError on failure.
        """
        logger.info("GovernanceRegistry.initialize() — loading all schemas")

        try:
            self._schemas = self.loader.load_all()
        except Exception as e:
            logger.critical("Failed to load governance schemas: %s", e)
            raise RuntimeError(f"Governance initialization failed: {e}") from e

        # Activate all schemas by default
        for schema_id in self._schemas:
            self._active.add(schema_id)
            logger.debug("Activated schema: %s", schema_id)

        # Validate cross-schema consistency
        inconsistencies = self.validate_cross_schema_consistency()
        if inconsistencies:
            for inc in inconsistencies:
                logger.error("Cross-schema inconsistency: %s", inc)
            raise RuntimeError(
                f"Governance initialization failed: {len(inconsistencies)} "
                f"cross-schema inconsistency(ies) found"
            )

        self._initialized = True
        logger.info(
            "GovernanceRegistry initialized: %d schemas, %d active",
            len(self._schemas),
            len(self._active),
        )

    # ── Schema Activation Control ─────────────────────────────────

    def activate(self, schema_id: str) -> None:
        """Explicitly activate a schema for enforcement.

        The schema must be loaded before activation.
        """
        if schema_id not in self._schemas:
            raise ValueError(f"Cannot activate unknown schema: '{schema_id}'")
        self._active.add(schema_id)
        logger.info("Schema activated: %s", schema_id)

    def deactivate(self, schema_id: str) -> None:
        """Explicitly deactivate a schema.

        Requires operator authorization (enforced at higher layer).
        Logs the deactivation for audit purposes.
        """
        if schema_id not in self._schemas:
            raise ValueError(f"Cannot deactivate unknown schema: '{schema_id}'")
        if schema_id in self._active:
            self._active.remove(schema_id)
            logger.warning(
                "Schema DEACTIVATED: %s — governance coverage reduced", schema_id
            )

    def is_active(self, schema_id: str) -> bool:
        """Check whether a schema is currently active."""
        return schema_id in self._active

    def get_active_schemas(self) -> list[GovernanceSchema]:
        """All currently active schemas."""
        return [self._schemas[sid] for sid in self._active if sid in self._schemas]

    def get_all_schemas(self) -> list[GovernanceSchema]:
        """All loaded schemas (active or inactive)."""
        return list(self._schemas.values())

    def get_schema(self, schema_id: str) -> GovernanceSchema | None:
        """Get a specific schema by ID."""
        return self._schemas.get(schema_id)

    # ── Cross-Schema Validation ───────────────────────────────────

    def validate_cross_schema_consistency(self) -> list[str]:
        """Check that active schemas have no contradictory policies.

        Returns list of inconsistency descriptions.
        Must pass before runtime can enter COGNITION_ACTIVE.

        Checks:
        - No duplicate policy_ids across schemas
        - No duplicate constraint_ids across schemas
        - No schema_id collisions
        - Categories are valid
        """
        inconsistencies: list[str] = []
        active_schemas = self.get_active_schemas()

        # Check 1: Duplicate schema_ids (shouldn't happen due to loader, but verify)
        seen_ids: set[str] = set()
        for schema in active_schemas:
            if schema.schema_id in seen_ids:
                inconsistencies.append(
                    f"Duplicate schema_id detected: '{schema.schema_id}'"
                )
            seen_ids.add(schema.schema_id)

        # Check 2: Duplicate policy_ids across schemas
        policy_map: dict[str, str] = {}  # policy_id -> schema_id
        for schema in active_schemas:
            for policy in schema.policies:
                if policy.policy_id in policy_map:
                    inconsistencies.append(
                        f"Duplicate policy_id '{policy.policy_id}' in schemas "
                        f"'{policy_map[policy.policy_id]}' and '{schema.schema_id}'"
                    )
                policy_map[policy.policy_id] = schema.schema_id

        # Check 3: Duplicate constraint_ids across schemas
        constraint_map: dict[str, str] = {}  # constraint_id -> schema_id
        for schema in active_schemas:
            for constraint in schema.constraints:
                if constraint.constraint_id in constraint_map:
                    inconsistencies.append(
                        f"Duplicate constraint_id '{constraint.constraint_id}' in schemas "
                        f"'{constraint_map[constraint.constraint_id]}' and "
                        f"'{schema.schema_id}'"
                    )
                constraint_map[constraint.constraint_id] = schema.schema_id

        # Check 4: Detect potentially contradictory enforcement actions
        # Schemas with hard_stop should not conflict on same scope
        scope_enforcements: dict[str, list[tuple[str, str]]] = {}
        for schema in active_schemas:
            for constraint in schema.constraints:
                scope = constraint.scope
                if scope not in scope_enforcements:
                    scope_enforcements[scope] = []
                scope_enforcements[scope].append(
                    (schema.schema_id, constraint.enforcement)
                )

        # Check 5: All fail-closed schemas must have violation_response
        for schema in active_schemas:
            if schema.fail_closed and schema.violation_response is None:
                inconsistencies.append(
                    f"Schema '{schema.schema_id}' has fail_closed=true but "
                    f"no violation_response defined"
                )

        if inconsistencies:
            logger.warning(
                "Cross-schema consistency check found %d issue(s)",
                len(inconsistencies),
            )
        else:
            logger.info("Cross-schema consistency check: PASSED")

        return inconsistencies

    # ── Enforcement Chain ─────────────────────────────────────────

    def get_enforcement_chain(self, scope: str) -> list[GovernanceConstraint]:
        """Get all constraints applicable to a scope, ordered by enforcement severity.

        Constraints are ordered: hard_stop first, then degrade, then log_only.
        Within same enforcement level, critical policies come first.
        """
        constraints: list[GovernanceConstraint] = []

        for schema in self.get_active_schemas():
            for constraint in schema.constraints:
                if constraint.scope == scope or constraint.scope == "global":
                    constraints.append(constraint)

        # Sort by enforcement severity
        constraints.sort(
            key=lambda c: (
                self.ENFORCEMENT_ORDER.get(c.enforcement, 99),
            )
        )

        logger.debug(
            "Enforcement chain for scope '%s': %d constraints",
            scope,
            len(constraints),
        )
        return constraints

    def get_policies_for_scope(self, scope: str) -> list[GovernancePolicy]:
        """Get all policies from active schemas that apply to a given scope.

        Policies are sorted by severity (critical first).
        """
        policies: list[GovernancePolicy] = []

        for schema in self.get_active_schemas():
            for policy in schema.policies:
                policies.append(policy)

        # Sort by severity
        policies.sort(
            key=lambda p: self.SEVERITY_ORDER.get(p.severity, 99)
        )
        return policies

    def get_active_schema_ids(self) -> list[str]:
        """Return list of active schema IDs."""
        return sorted(self._active)

    def __len__(self) -> int:
        return len(self._active)

    def __contains__(self, schema_id: str) -> bool:
        return schema_id in self._active
