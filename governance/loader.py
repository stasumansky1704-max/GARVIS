"""Schema Loader — governance/loader.py

Loads and validates all governance schemas from YAML files.
Per the SPEC section 5.1.

Usage:
    loader = SchemaLoader("governance/schemas/")
    schemas = loader.load_all()
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from models.governance import (
    GovernanceSchema,
    GovernancePolicy,
    GovernanceConstraint,
    ViolationResponse,
)

logger = logging.getLogger("garvis.governance.loader")


class GovernanceLoadError(Exception):
    """Raised when a governance schema fails to load or validate."""

    pass


class SchemaLoader:
    """Loads and validates all governance schemas from YAML files.

    Each schema is parsed from YAML, structurally validated, and
    converted into a typed GovernanceSchema Pydantic model.
    """

    REQUIRED_TOP_LEVEL_KEYS = [
        "schema_id",
        "name",
        "version",
        "category",
        "description",
        "fail_closed",
        "policies",
        "constraints",
        "violation_response",
    ]

    REQUIRED_POLICY_KEYS = [
        "policy_id",
        "description",
        "rule_type",
        "condition",
        "evaluation_logic",
        "severity",
    ]

    REQUIRED_CONSTRAINT_KEYS = [
        "constraint_id",
        "description",
        "scope",
        "enforcement",
    ]

    REQUIRED_VIOLATION_RESPONSE_KEYS = [
        "action",
        "log_level",
        "notification_target",
    ]

    VALID_CATEGORIES = {"epistemic", "operational", "boundary", "reflective", "session", "ethical"}
    VALID_RULE_TYPES = {"threshold", "prohibition", "requirement", "constraint"}
    VALID_SEVERITIES = {"critical", "warning", "info"}
    VALID_SCOPES = {"global", "session", "inference", "memory"}
    VALID_ENFORCEMENTS = {"hard_stop", "log_only", "degrade"}
    VALID_VIOLATION_ACTIONS = {"halt", "degrade", "escalate", "log"}
    VALID_LOG_LEVELS = {"critical", "warning", "info"}
    VALID_NOTIFICATION_TARGETS = {"admin", "operator", "system"}

    def __init__(self, schemas_dir: str) -> None:
        self.schemas_dir = Path(schemas_dir)
        self._schemas: dict[str, GovernanceSchema] = {}
        self._loaded = False

    # ── Public API ────────────────────────────────────────────────

    def load_all(self) -> dict[str, GovernanceSchema]:
        """Load all YAML schemas from the schemas directory.

        Returns a mapping of schema_id -> GovernanceSchema.
        Raises GovernanceLoadError if any schema is invalid.
        """
        if not self.schemas_dir.exists():
            raise GovernanceLoadError(
                f"Schemas directory does not exist: {self.schemas_dir}"
            )

        self._schemas = {}
        errors: list[str] = []

        yaml_files = sorted(self.schemas_dir.glob("*.yml"))
        if not yaml_files:
            raise GovernanceLoadError(
                f"No YAML schema files found in {self.schemas_dir}"
            )

        for filepath in yaml_files:
            try:
                raw = self._read_yaml(filepath)
                structure_errors = self.validate_schema_structure(raw)
                if structure_errors:
                    errors.extend(
                        [f"{filepath.name}: {e}" for e in structure_errors]
                    )
                    continue

                schema = self._parse_schema(raw)
                if schema.schema_id in self._schemas:
                    errors.append(
                        f"{filepath.name}: Duplicate schema_id '{schema.schema_id}'"
                    )
                    continue

                self._schemas[schema.schema_id] = schema
                logger.info(
                    "Loaded governance schema: %s (v%s, %s)",
                    schema.schema_id,
                    schema.version,
                    schema.category,
                )

            except GovernanceLoadError as e:
                errors.append(f"{filepath.name}: {e}")
            except Exception as e:
                errors.append(f"{filepath.name}: Unexpected error: {e}")

        if errors:
            raise GovernanceLoadError(
                f"Failed to load {len(errors)} schema(s):\n" + "\n".join(errors)
            )

        self._loaded = True
        logger.info(
            "SchemaLoader: Successfully loaded %d governance schemas",
            len(self._schemas),
        )
        return dict(self._schemas)

    def load_single(self, schema_id: str) -> GovernanceSchema:
        """Load a single schema by ID.

        If schemas have already been loaded, returns from cache.
        Otherwise, loads from the individual YAML file.
        """
        if schema_id in self._schemas:
            return self._schemas[schema_id]

        filepath = self.schemas_dir / f"{schema_id}.yml"
        if not filepath.exists():
            raise GovernanceLoadError(f"Schema file not found: {filepath}")

        raw = self._read_yaml(filepath)
        errors = self.validate_schema_structure(raw)
        if errors:
            raise GovernanceLoadError(
                f"Schema '{schema_id}' validation failed: " + "; ".join(errors)
            )

        schema = self._parse_schema(raw)
        self._schemas[schema_id] = schema
        return schema

    def validate_schema_structure(self, raw: dict[str, Any]) -> list[str]:
        """Validate raw YAML dict has all required fields.

        Returns list of validation errors (empty = valid).
        """
        errors: list[str] = []

        # Top-level keys
        for key in self.REQUIRED_TOP_LEVEL_KEYS:
            if key not in raw:
                errors.append(f"Missing required top-level key: '{key}'")

        if errors:
            return errors  # Cannot validate deeper without top-level structure

        # Category validation
        if raw.get("category") not in self.VALID_CATEGORIES:
            errors.append(
                f"Invalid category '{raw.get('category')}'. "
                f"Must be one of: {self.VALID_CATEGORIES}"
            )

        # Policies validation
        policies = raw.get("policies", [])
        if not policies:
            errors.append("At least one policy is required")
        elif not isinstance(policies, list):
            errors.append("'policies' must be a list")
        else:
            for i, policy in enumerate(policies):
                policy_errors = self._validate_policy(policy, i)
                errors.extend(policy_errors)

        # Constraints validation
        constraints = raw.get("constraints", [])
        if not constraints:
            errors.append("At least one constraint is required")
        elif not isinstance(constraints, list):
            errors.append("'constraints' must be a list")
        else:
            for i, constraint in enumerate(constraints):
                constraint_errors = self._validate_constraint(constraint, i)
                errors.extend(constraint_errors)

        # Violation response validation
        vresp = raw.get("violation_response", {})
        if not isinstance(vresp, dict):
            errors.append("'violation_response' must be a dict")
        else:
            for key in self.REQUIRED_VIOLATION_RESPONSE_KEYS:
                if key not in vresp:
                    errors.append(f"Missing violation_response key: '{key}'")
            if vresp.get("action") not in self.VALID_VIOLATION_ACTIONS:
                errors.append(
                    f"Invalid violation_response.action: '{vresp.get('action')}'"
                )
            if vresp.get("log_level") not in self.VALID_LOG_LEVELS:
                errors.append(
                    f"Invalid violation_response.log_level: '{vresp.get('log_level')}'"
                )
            if vresp.get("notification_target") not in self.VALID_NOTIFICATION_TARGETS:
                errors.append(
                    f"Invalid violation_response.notification_target: "
                    f"'{vresp.get('notification_target')}'"
                )

        return errors

    def get_schemas_by_category(self, category: str) -> list[GovernanceSchema]:
        """Get all schemas in a category."""
        return [
            s for s in self._schemas.values() if s.category == category
        ]

    def reload(self) -> dict[str, GovernanceSchema]:
        """Hot-reload all schemas. Used only at explicit operator request.

        Never auto-reload. No silent evolution.
        Clears the cache and re-loads from disk.
        """
        logger.warning("SchemaLoader.reload() called — hot-reloading all schemas")
        self._schemas = {}
        self._loaded = False
        return self.load_all()

    # ── Internal helpers ──────────────────────────────────────────

    def _read_yaml(self, filepath: Path) -> dict[str, Any]:
        """Read and parse a YAML file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise GovernanceLoadError(f"Invalid YAML in {filepath}: {e}")
        except OSError as e:
            raise GovernanceLoadError(f"Cannot read {filepath}: {e}")

        if not isinstance(data, dict):
            raise GovernanceLoadError(
                f"YAML root must be a dict, got {type(data).__name__}"
            )
        return data

    def _validate_policy(self, policy: Any, index: int) -> list[str]:
        """Validate a single policy dict."""
        errors: list[str] = []
        if not isinstance(policy, dict):
            errors.append(f"Policy {index} must be a dict")
            return errors

        for key in self.REQUIRED_POLICY_KEYS:
            if key not in policy:
                errors.append(f"Policy {index}: missing '{key}'")

        if policy.get("rule_type") not in self.VALID_RULE_TYPES:
            errors.append(
                f"Policy {index}: invalid rule_type '{policy.get('rule_type')}'"
            )
        if policy.get("severity") not in self.VALID_SEVERITIES:
            errors.append(
                f"Policy {index}: invalid severity '{policy.get('severity')}'"
            )
        return errors

    def _validate_constraint(self, constraint: Any, index: int) -> list[str]:
        """Validate a single constraint dict."""
        errors: list[str] = []
        if not isinstance(constraint, dict):
            errors.append(f"Constraint {index} must be a dict")
            return errors

        for key in self.REQUIRED_CONSTRAINT_KEYS:
            if key not in constraint:
                errors.append(f"Constraint {index}: missing '{key}'")

        if constraint.get("scope") not in self.VALID_SCOPES:
            errors.append(
                f"Constraint {index}: invalid scope '{constraint.get('scope')}'"
            )
        if constraint.get("enforcement") not in self.VALID_ENFORCEMENTS:
            errors.append(
                f"Constraint {index}: invalid enforcement '{constraint.get('enforcement')}'"
            )
        return errors

    def _parse_schema(self, raw: dict[str, Any]) -> GovernanceSchema:
        """Convert validated raw dict into a GovernanceSchema model."""
        policies = [
            GovernancePolicy(
                policy_id=p["policy_id"],
                description=p["description"],
                rule_type=p["rule_type"],
                condition=p["condition"],
                evaluation_logic=p["evaluation_logic"],
                severity=p["severity"],
                auto_remediation=p.get("auto_remediation", False),
            )
            for p in raw["policies"]
        ]

        constraints = [
            GovernanceConstraint(
                constraint_id=c["constraint_id"],
                description=c["description"],
                scope=c["scope"],
                enforcement=c["enforcement"],
            )
            for c in raw["constraints"]
        ]

        vresp = raw.get("violation_response", {})
        violation_response = ViolationResponse(
            action=vresp.get("action", "halt"),
            log_level=vresp.get("log_level", "critical"),
            notification_target=vresp.get("notification_target", "system"),
        )

        return GovernanceSchema(
            schema_id=raw["schema_id"],
            name=raw["name"],
            version=raw["version"],
            category=raw["category"],
            description=raw["description"],
            policies=policies,
            constraints=constraints,
            fail_closed=raw.get("fail_closed", True),
            violation_response=violation_response,
        )
