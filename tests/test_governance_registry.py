"""Tests for the governance registry.

Tests cover initialization, activation/deactivation, active schema filtering,
cross-schema consistency detection, and enforcement chain retrieval.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from governance.loader import SchemaLoader
from governance.registry import GovernanceRegistry
from models.governance import GovernanceConstraint, GovernanceSchema


class TestGovernanceRegistry:
    """Tests for GovernanceRegistry operations."""

    @pytest.fixture
    def registry(self) -> GovernanceRegistry:
        """Return an initialized GovernanceRegistry with all 28 schemas."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)
        registry = GovernanceRegistry(loader)
        registry.initialize()
        return registry

    def test_initialize_registry(self, registry: GovernanceRegistry) -> None:
        """initialize() loads and registers all 28 schemas."""
        all_schemas = registry.get_all_schemas()
        assert len(all_schemas) == 28

        active = registry.get_active_schemas()
        assert len(active) == 28

    def test_initialize_registry_fails_on_inconsistency(self) -> None:
        """initialize() raises RuntimeError when schemas have contradictions."""
        # Create a loader that returns schemas with duplicate policy IDs
        loader = MagicMock()
        policy = MagicMock()
        policy.policy_id = "duplicate_policy"
        policy.severity = "critical"

        constraint = MagicMock()
        constraint.constraint_id = "c1"
        constraint.scope = "global"
        constraint.enforcement = "hard_stop"

        schema1 = MagicMock()
        schema1.schema_id = "schema_a"
        schema1.category = "epistemic"
        schema1.fail_closed = True
        schema1.violation_response = MagicMock()
        schema1.policies = [policy]
        schema1.constraints = [constraint]

        schema2 = MagicMock()
        schema2.schema_id = "schema_b"
        schema2.category = "epistemic"
        schema2.fail_closed = True
        schema2.violation_response = MagicMock()
        schema2.policies = [policy]  # same policy_id — duplicate
        schema2.constraints = [constraint]

        loader.load_all.return_value = {"schema_a": schema1, "schema_b": schema2}

        registry = GovernanceRegistry(loader)

        # The initialize() method calls validate_cross_schema_consistency() internally
        # and should raise RuntimeError if inconsistencies are found
        with pytest.raises(RuntimeError):
            registry.initialize()

    def test_activate_deactivate_schema(self, registry: GovernanceRegistry) -> None:
        """activate() and deactivate() toggle schema enforcement."""
        schema_id = "uncertainty_management"

        # Initially active (all are activated by default)
        assert registry.is_active(schema_id)

        # Deactivate
        registry.deactivate(schema_id)
        assert not registry.is_active(schema_id)

        active = registry.get_active_schemas()
        assert len(active) == 27

        # Re-activate
        registry.activate(schema_id)
        assert registry.is_active(schema_id)

        active = registry.get_active_schemas()
        assert len(active) == 28

    def test_activate_unknown_schema(self, registry: GovernanceRegistry) -> None:
        """activate() raises ValueError for unknown schema."""
        with pytest.raises(ValueError, match="unknown schema"):
            registry.activate("nonexistent")

    def test_deactivate_unknown_schema(self, registry: GovernanceRegistry) -> None:
        """deactivate() raises ValueError for unknown schema."""
        with pytest.raises(ValueError, match="unknown schema"):
            registry.deactivate("nonexistent")

    def test_get_active_schemas_only_active(self, registry: GovernanceRegistry) -> None:
        """get_active_schemas() returns only currently active schemas."""
        # Deactivate several schemas
        registry.deactivate("uncertainty_management")
        registry.deactivate("truthfulness_governance")

        active = registry.get_active_schemas()
        active_ids = {s.schema_id for s in active}

        assert "uncertainty_management" not in active_ids
        assert "truthfulness_governance" not in active_ids
        assert len(active) == 26

        for schema in active:
            assert isinstance(schema, GovernanceSchema)

    def test_get_all_schemas(self, registry: GovernanceRegistry) -> None:
        """get_all_schemas() returns all loaded schemas regardless of activation."""
        registry.deactivate("uncertainty_management")

        all_schemas = registry.get_all_schemas()
        assert len(all_schemas) == 28

    def test_get_schema(self, registry: GovernanceRegistry) -> None:
        """get_schema() retrieves a specific schema by ID."""
        schema = registry.get_schema("uncertainty_management")
        assert schema is not None
        assert schema.schema_id == "uncertainty_management"

    def test_get_schema_unknown(self, registry: GovernanceRegistry) -> None:
        """get_schema() returns None for unknown schema ID."""
        assert registry.get_schema("nonexistent") is None

    def test_cross_schema_consistency(self, registry: GovernanceRegistry) -> None:
        """validate_cross_schema_consistency() returns empty list for valid schemas."""
        inconsistencies = registry.validate_cross_schema_consistency()
        assert isinstance(inconsistencies, list)
        assert len(inconsistencies) == 0, f"Unexpected inconsistencies: {inconsistencies}"

    def test_cross_schema_consistency_detects_duplicates(self) -> None:
        """validate_cross_schema_consistency() detects duplicate policy IDs."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)
        registry = GovernanceRegistry(loader)
        registry.initialize()

        # Manually introduce a duplicate by modifying internal state
        from models.governance import GovernancePolicy
        schema = registry.get_schema("uncertainty_management")
        if schema:
            # Add a policy with the same ID as one from another schema
            another_schema = registry.get_schema("truthfulness_governance")
            if another_schema and another_schema.policies:
                dup_policy = GovernancePolicy(
                    policy_id=another_schema.policies[0].policy_id,
                    description="duplicate",
                    rule_type="requirement",
                    condition="c",
                    evaluation_logic="e",
                    severity="info",
                )
                schema.policies.append(dup_policy)

        inconsistencies = registry.validate_cross_schema_consistency()
        assert len(inconsistencies) > 0

    def test_enforcement_chain(self, registry: GovernanceRegistry) -> None:
        """get_enforcement_chain() returns constraints ordered by enforcement severity."""
        # Test for inference scope
        chain = registry.get_enforcement_chain("inference")
        assert isinstance(chain, list)
        assert len(chain) > 0

        # hard_stop constraints should come first
        for i in range(len(chain) - 1):
            curr = chain[i].enforcement
            nxt = chain[i + 1].enforcement
            order = {"hard_stop": 0, "degrade": 1, "log_only": 2}
            assert order.get(curr, 99) <= order.get(nxt, 99), \
                f"Constraint ordering violated: {curr} before {nxt}"

    def test_enforcement_chain_includes_global(self, registry: GovernanceRegistry) -> None:
        """get_enforcement_chain() includes global-scope constraints."""
        chain = registry.get_enforcement_chain("inference")

        # Global constraints should be in the chain
        global_constraints = [c for c in chain if c.scope == "global"]
        assert len(global_constraints) > 0

    def test_get_policies_for_scope(self, registry: GovernanceRegistry) -> None:
        """get_policies_for_scope() returns policies sorted by severity."""
        policies = registry.get_policies_for_scope("inference")
        assert len(policies) > 0

        # Critical policies should come first
        for i in range(len(policies) - 1):
            order = {"critical": 0, "warning": 1, "info": 2}
            curr = order.get(policies[i].severity, 99)
            nxt = order.get(policies[i + 1].severity, 99)
            assert curr <= nxt, "Policies not sorted by severity"

    def test_get_active_schema_ids(self, registry: GovernanceRegistry) -> None:
        """get_active_schema_ids() returns sorted list of active IDs."""
        ids = registry.get_active_schema_ids()
        assert len(ids) == 28
        assert ids == sorted(ids)

    def test_len(self, registry: GovernanceRegistry) -> None:
        """__len__ returns count of active schemas."""
        assert len(registry) == 28
        registry.deactivate("uncertainty_management")
        assert len(registry) == 27

    def test_contains(self, registry: GovernanceRegistry) -> None:
        """__contains__ checks if schema is active."""
        assert "uncertainty_management" in registry
        registry.deactivate("uncertainty_management")
        assert "uncertainty_management" not in registry

    def test_fail_closed_schema_must_have_violation_response(self) -> None:
        """Cross-schema consistency checks fail_closed schemas have violation_response."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)
        registry = GovernanceRegistry(loader)
        registry.initialize()

        # All fail-closed schemas in the real set have violation_response
        # Let's verify
        for schema in registry.get_active_schemas():
            if schema.fail_closed:
                assert schema.violation_response is not None, \
                    f"Schema {schema.schema_id} has fail_closed=True but no violation_response"
