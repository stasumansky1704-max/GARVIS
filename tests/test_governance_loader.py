"""Tests for the governance schema loader.

Tests cover loading all 28 YAML schemas, loading individual schemas,
validation of required fields, filtering by category, and hot reload.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from governance.loader import GovernanceLoadError, SchemaLoader
from models.governance import GovernanceSchema


class TestSchemaLoader:
    """Tests for SchemaLoader loading functionality."""

    def test_load_all_schemas(self) -> None:
        """load_all() loads all 28 YAML schema files from the schemas directory."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)
        schemas = loader.load_all()

        assert len(schemas) == 28, f"Expected 28 schemas, got {len(schemas)}"

        # Verify all expected schema IDs are loaded
        expected_ids = {
            "adaptation_pressure",
            "boundary_conflicts",
            "boundary_preservation",
            "cognitive_consistency",
            "cognitive_humility",
            "cognitive_traceability",
            "decision_boundaries",
            "degradation_awareness",
            "dependency_awareness",
            "equilibrium_awareness",
            "escalation_awareness",
            "evidence_coherence",
            "integrity_verification",
            "interception_manifest",
            "operational_state_model",
            "planning_cognition",
            "priority_resolution",
            "provenance_awareness",
            "recovery_awareness",
            "resilience_awareness",
            "retrieval_scoring",
            "runtime_boundary",
            "runtime_mediation",
            "self_limitation_awareness",
            "session_continuity",
            "truthfulness_governance",
            "uncertainty_management",
            "workload_awareness",
        }
        assert set(schemas.keys()) == expected_ids

        # Verify all loaded objects are GovernanceSchema instances
        for schema in schemas.values():
            assert isinstance(schema, GovernanceSchema)
            assert schema.schema_id
            assert schema.name
            assert schema.version
            assert schema.category in {
                "epistemic", "operational", "boundary", "reflective", "session", "ethical"
            }
            assert len(schema.policies) > 0, f"{schema.schema_id} has no policies"
            assert len(schema.constraints) > 0, f"{schema.schema_id} has no constraints"

    def test_load_all_caches_results(self) -> None:
        """load_all() caches schemas internally for subsequent lookups."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)
        schemas1 = loader.load_all()
        schemas2 = loader.load_all()
        # Both loads return the same cached data
        assert schemas1 == schemas2
        assert len(schemas1) == 28

    def test_load_all_missing_directory(self) -> None:
        """load_all() raises GovernanceLoadError for non-existent directory."""
        loader = SchemaLoader("/nonexistent/path")
        with pytest.raises(GovernanceLoadError, match="does not exist"):
            loader.load_all()

    def test_load_single_schema(self) -> None:
        """load_single() loads a specific schema by ID."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)

        schema = loader.load_single("uncertainty_management")

        assert isinstance(schema, GovernanceSchema)
        assert schema.schema_id == "uncertainty_management"
        assert schema.name == "Uncertainty Management"
        assert schema.version == "1.0.0"
        assert schema.category == "epistemic"
        assert schema.fail_closed is True
        assert len(schema.policies) >= 1
        assert len(schema.constraints) >= 1
        assert schema.violation_response is not None

    def test_load_single_missing_schema(self) -> None:
        """load_single() raises GovernanceLoadError for missing schema ID."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)

        with pytest.raises(GovernanceLoadError, match="not found"):
            loader.load_single("nonexistent_schema")

    def test_load_single_returns_from_cache(self) -> None:
        """load_single() returns cached schema if already loaded."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)

        schema1 = loader.load_single("uncertainty_management")
        schema2 = loader.load_single("uncertainty_management")

        assert schema1 is schema2  # same cached object

    def test_invalid_schema_rejected_missing_required_key(self, tmp_path: Path) -> None:
        """Schema missing required top-level keys is rejected."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()

        invalid_schema = {
            "schema_id": "bad_schema",
            "name": "Bad Schema",
            # Missing version, category, description, fail_closed, policies, constraints
            "violation_response": {"action": "halt", "log_level": "critical", "notification_target": "system"},
        }
        schema_file = schemas_dir / "bad_schema.yml"
        schema_file.write_text(yaml.safe_dump(invalid_schema))

        loader = SchemaLoader(str(schemas_dir))
        with pytest.raises(GovernanceLoadError, match="Missing required top-level key"):
            loader.load_all()

    def test_invalid_schema_rejected_empty_policies(self, tmp_path: Path) -> None:
        """Schema with empty policies list is rejected."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()

        invalid_schema = {
            "schema_id": "bad_schema",
            "name": "Bad Schema",
            "version": "1.0.0",
            "category": "epistemic",
            "description": "A bad schema",
            "fail_closed": True,
            "policies": [],
            "constraints": [{"constraint_id": "c1", "description": "d", "scope": "global", "enforcement": "hard_stop"}],
            "violation_response": {"action": "halt", "log_level": "critical", "notification_target": "system"},
        }
        schema_file = schemas_dir / "bad_schema.yml"
        schema_file.write_text(yaml.safe_dump(invalid_schema))

        loader = SchemaLoader(str(schemas_dir))
        with pytest.raises(GovernanceLoadError, match="At least one policy is required"):
            loader.load_all()

    def test_invalid_schema_rejected_bad_category(self, tmp_path: Path) -> None:
        """Schema with invalid category is rejected."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()

        invalid_schema = {
            "schema_id": "bad_schema",
            "name": "Bad Schema",
            "version": "1.0.0",
            "category": "invalid_category",
            "description": "desc",
            "fail_closed": True,
            "policies": [{"policy_id": "p1", "description": "d", "rule_type": "requirement", "condition": "c", "evaluation_logic": "e", "severity": "info"}],
            "constraints": [{"constraint_id": "c1", "description": "d", "scope": "global", "enforcement": "hard_stop"}],
            "violation_response": {"action": "halt", "log_level": "critical", "notification_target": "system"},
        }
        schema_file = schemas_dir / "bad_schema.yml"
        schema_file.write_text(yaml.safe_dump(invalid_schema))

        loader = SchemaLoader(str(schemas_dir))
        with pytest.raises(GovernanceLoadError, match="Invalid category"):
            loader.load_all()

    def test_invalid_schema_rejected_duplicate_id(self, tmp_path: Path) -> None:
        """Schema with duplicate schema_id is rejected."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()

        schema_def = {
            "schema_id": "duplicate_id",
            "name": "Schema One",
            "version": "1.0.0",
            "category": "epistemic",
            "description": "desc",
            "fail_closed": True,
            "policies": [{"policy_id": "p1", "description": "d", "rule_type": "requirement", "condition": "c", "evaluation_logic": "e", "severity": "info"}],
            "constraints": [{"constraint_id": "c1", "description": "d", "scope": "global", "enforcement": "hard_stop"}],
            "violation_response": {"action": "halt", "log_level": "critical", "notification_target": "system"},
        }
        (schemas_dir / "file1.yml").write_text(yaml.safe_dump(schema_def))
        (schemas_dir / "file2.yml").write_text(yaml.safe_dump(schema_def))

        loader = SchemaLoader(str(schemas_dir))
        with pytest.raises(GovernanceLoadError, match="Duplicate schema_id"):
            loader.load_all()

    def test_get_by_category(self) -> None:
        """get_schemas_by_category() returns only schemas in that category."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)
        loader.load_all()

        epistemic = loader.get_schemas_by_category("epistemic")
        assert len(epistemic) > 0
        for schema in epistemic:
            assert schema.category == "epistemic"

        operational = loader.get_schemas_by_category("operational")
        assert len(operational) > 0
        for schema in operational:
            assert schema.category == "operational"

        boundary = loader.get_schemas_by_category("boundary")
        assert len(boundary) > 0
        for schema in boundary:
            assert schema.category == "boundary"

    def test_reload(self) -> None:
        """reload() clears cache and re-loads all schemas."""
        schemas_dir = str(Path(__file__).parent.parent / "governance" / "schemas")
        loader = SchemaLoader(schemas_dir)

        schemas1 = loader.load_all()
        schemas2 = loader.reload()

        assert len(schemas2) == 28
        # Not the same dict object (cache was cleared)
        assert schemas1 is not schemas2

    def test_reload_on_empty_loader(self, tmp_path: Path) -> None:
        """reload() works even on a fresh loader."""
        schemas_dir = tmp_path / "schemas"
        schemas_dir.mkdir()

        schema_def = {
            "schema_id": "reload_test",
            "name": "Reload Test",
            "version": "1.0.0",
            "category": "epistemic",
            "description": "desc",
            "fail_closed": True,
            "policies": [{"policy_id": "p1", "description": "d", "rule_type": "requirement", "condition": "c", "evaluation_logic": "e", "severity": "info"}],
            "constraints": [{"constraint_id": "c1", "description": "d", "scope": "global", "enforcement": "hard_stop"}],
            "violation_response": {"action": "halt", "log_level": "critical", "notification_target": "system"},
        }
        (schemas_dir / "reload_test.yml").write_text(yaml.safe_dump(schema_def))

        loader = SchemaLoader(str(schemas_dir))
        schemas = loader.reload()
        assert "reload_test" in schemas
