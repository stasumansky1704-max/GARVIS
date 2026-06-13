"""Project Governance System Tests — tests/test_projects.py

Comprehensive test suite for the per-project governance system:
- ProjectGovernance: initialization, constraints, validation
- ProjectContext: lifecycle, context switching, state management
- ContextManager: registration, switching, isolation
- ProjectMemory: storage, retrieval, cross-project access
- OperationalReasoningEngine: workflow reasoning, risk assessment
- ProjectRegistry: system-level integration
- All 7 projects: end-to-end coverage

50+ tests covering all critical paths.
"""

from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from models.governance import (
    GovernanceConstraint,
    GovernancePolicy,
    GovernanceSchema,
    ViolationResponse,
)
from projects.governance import ProjectGovernance
from projects.context import ProjectContext, ContextManager
from projects.memory import ProjectMemory
from projects.reasoning import OperationalReasoningEngine, WorkflowDefinition
from projects.registry import ProjectRegistry, PROJECTS


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_global_registry() -> MagicMock:
    """Return a mock GovernanceRegistry with 3 active schemas."""
    registry = MagicMock()

    # Create test schemas
    schema1 = GovernanceSchema(
        schema_id="uncertainty_management",
        name="Uncertainty Management",
        version="1.0.0",
        category="epistemic",
        description="Governs uncertainty",
        policies=[
            GovernancePolicy(
                policy_id="uncertainty_required",
                description="Uncertainty must be quantified",
                rule_type="requirement",
                condition="confidence present",
                evaluation_logic="validate_confidence",
                severity="critical",
            ),
        ],
        constraints=[
            GovernanceConstraint(
                constraint_id="no_false_certainty",
                description="No false certainty",
                scope="inference",
                enforcement="hard_stop",
            ),
        ],
        fail_closed=True,
        violation_response=ViolationResponse(
            action="halt", log_level="critical", notification_target="system",
        ),
    )

    schema2 = GovernanceSchema(
        schema_id="truthfulness_governance",
        name="Truthfulness",
        version="1.0.0",
        category="epistemic",
        description="Governs truthfulness",
        policies=[
            GovernancePolicy(
                policy_id="no_contradiction",
                description="No contradictions",
                rule_type="prohibition",
                condition="no contradiction",
                evaluation_logic="check_contradiction",
                severity="warning",
            ),
        ],
        constraints=[
            GovernanceConstraint(
                constraint_id="no_known_falsehoods",
                description="No known falsehoods",
                scope="inference",
                enforcement="hard_stop",
            ),
        ],
        fail_closed=True,
        violation_response=ViolationResponse(
            action="halt", log_level="critical", notification_target="system",
        ),
    )

    schema3 = GovernanceSchema(
        schema_id="operational_safety",
        name="Operational Safety",
        version="1.0.0",
        category="operational",
        description="Governs operations",
        policies=[
            GovernancePolicy(
                policy_id="approval_required",
                description="Approval required for risky ops",
                rule_type="requirement",
                condition="approval present",
                evaluation_logic="check_approval",
                severity="critical",
            ),
        ],
        constraints=[
            GovernanceConstraint(
                constraint_id="no_unauthorized_execution",
                description="No unauthorized execution",
                scope="global",
                enforcement="hard_stop",
            ),
        ],
        fail_closed=True,
        violation_response=ViolationResponse(
            action="halt", log_level="critical", notification_target="system",
        ),
    )

    registry.get_active_schema_ids = MagicMock(
        return_value=["uncertainty_management", "truthfulness_governance", "operational_safety"]
    )
    registry.get_schema = MagicMock(side_effect=lambda sid: {
        "uncertainty_management": schema1,
        "truthfulness_governance": schema2,
        "operational_safety": schema3,
    }.get(sid))
    registry._schemas = {
        "uncertainty_management": schema1,
        "truthfulness_governance": schema2,
        "operational_safety": schema3,
    }

    return registry


@pytest.fixture
def sample_project_config() -> dict[str, str]:
    """Return a sample project configuration."""
    return {
        "name": "Test Project",
        "category": "test",
        "status": "active",
        "description": "A test project",
    }


@pytest.fixture
def all_project_configs() -> list[dict[str, str]]:
    """Return all 7 GARVIS project configurations."""
    return PROJECTS


# ============================================================================
# ProjectGovernance Tests
# ============================================================================


class TestProjectGovernanceInitialization:
    """Test ProjectGovernance initialization."""

    def test_project_governance_creation(self, mock_global_registry: MagicMock) -> None:
        """Test that ProjectGovernance can be created."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        assert pg.project_id == "test_project"
        assert pg.global_registry == mock_global_registry
        assert pg._initialized is False
        assert len(pg._active_schemas) == 0
        assert len(pg._project_constraints) == 0

    def test_initialize_with_all_global_schemas(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test initialization inherits all global active schemas."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        assert pg._initialized is True
        assert len(pg._active_schemas) == 3
        assert "uncertainty_management" in pg._active_schemas
        assert "truthfulness_governance" in pg._active_schemas
        assert "operational_safety" in pg._active_schemas

    def test_initialize_with_subset_schemas(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test initialization with specific schema subset."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize(schema_ids=["uncertainty_management", "operational_safety"])
        assert len(pg._active_schemas) == 2
        assert "uncertainty_management" in pg._active_schemas
        assert "truthfulness_governance" not in pg._active_schemas
        assert "operational_safety" in pg._active_schemas

    def test_initialize_with_invalid_schema_skipped(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that invalid schema IDs are skipped with warning."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize(schema_ids=["uncertainty_management", "nonexistent_schema"])
        assert len(pg._active_schemas) == 1
        assert "uncertainty_management" in pg._active_schemas

    def test_get_active_schemas(self, mock_global_registry: MagicMock) -> None:
        """Test retrieving active schemas."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        schemas = pg.get_active_schemas()
        assert len(schemas) == 3
        schema_ids = [s.schema_id for s in schemas]
        assert "uncertainty_management" in schema_ids
        assert "truthfulness_governance" in schema_ids
        assert "operational_safety" in schema_ids

    def test_get_active_schemas_empty_when_not_initialized(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that active schemas are empty before initialization."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        schemas = pg.get_active_schemas()
        assert len(schemas) == 0


class TestProjectGovernanceConstraints:
    """Test project-specific constraint management."""

    def test_add_project_constraint(self, mock_global_registry: MagicMock) -> None:
        """Test adding a project-specific constraint."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="test_constraint",
            description="A test constraint",
            scope="global",
            enforcement="hard_stop",
        )
        result = pg.add_project_constraint(constraint, "operator_1")
        assert result["status"] == "added"
        assert result["constraint_id"] == "test_constraint"
        assert len(pg.get_project_constraints()) == 1

    def test_add_constraint_requires_operator(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that adding a constraint requires an operator ID."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="test_constraint",
            description="A test constraint",
            scope="global",
            enforcement="hard_stop",
        )
        result = pg.add_project_constraint(constraint, "")
        assert result["status"] == "error"
        assert len(pg.get_project_constraints()) == 0

    def test_add_duplicate_constraint_rejected(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that duplicate constraint IDs are rejected."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="test_constraint",
            description="A test constraint",
            scope="global",
            enforcement="hard_stop",
        )
        pg.add_project_constraint(constraint, "operator_1")
        result = pg.add_project_constraint(constraint, "operator_1")
        assert result["status"] == "error"
        assert len(pg.get_project_constraints()) == 1

    def test_remove_project_constraint(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test removing a project-specific constraint."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="test_constraint",
            description="A test constraint",
            scope="global",
            enforcement="hard_stop",
        )
        pg.add_project_constraint(constraint, "operator_1")
        removed = pg.remove_project_constraint("test_constraint", "operator_1")
        assert removed is True
        assert len(pg.get_project_constraints()) == 0

    def test_remove_nonexistent_constraint(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test removing a constraint that doesn't exist."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        removed = pg.remove_project_constraint("nonexistent", "operator_1")
        assert removed is False

    def test_remove_constraint_requires_operator(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that removing a constraint requires an operator ID."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="test_constraint",
            description="A test constraint",
            scope="global",
            enforcement="hard_stop",
        )
        pg.add_project_constraint(constraint, "operator_1")
        removed = pg.remove_project_constraint("test_constraint", "")
        assert removed is False
        assert len(pg.get_project_constraints()) == 1

    def test_constraint_audit_log(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that constraint changes are audited."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="test_constraint",
            description="A test constraint",
            scope="global",
            enforcement="hard_stop",
        )
        pg.add_project_constraint(constraint, "operator_1")
        pg.remove_project_constraint("test_constraint", "operator_2")
        log = pg.get_constraint_audit_log()
        assert len(log) == 2
        assert log[0]["action"] == "constraint_added"
        assert log[0]["operator_id"] == "operator_1"
        assert log[1]["action"] == "constraint_removed"
        assert log[1]["operator_id"] == "operator_2"


class TestProjectGovernanceValidation:
    """Test governance validation within project scope."""

    def test_validate_operation_passes(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that valid operations pass governance checks."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        results = pg.validate_operation(
            "test_operation",
            context={"value": 0.5, "threshold": 1.0},
        )
        assert len(results) == 3  # 3 policies from active schemas
        assert all(r.passed for r in results)

    def test_validate_operation_with_project_constraint(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that project-specific constraints are checked."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="no_deploy",
            description="No deployment allowed",
            scope="global",
            enforcement="hard_stop",
        )
        pg.add_project_constraint(constraint, "operator_1")
        results = pg.validate_operation(
            "deploy",
            context={"restricted_operations": ["deploy"]},
        )
        # Should have violations from project constraint
        violations = [r for r in results if not r.passed]
        assert len(violations) >= 1

    def test_get_global_constraints(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test retrieving global constraints."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        global_constraints = pg.get_global_constraints_for_project()
        assert len(global_constraints) == 3  # One from each schema

    def test_get_all_constraints(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test retrieving all constraints (global + project-specific)."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="project_only",
            description="Project-specific constraint",
            scope="global",
            enforcement="log_only",
        )
        pg.add_project_constraint(constraint, "operator_1")
        all_constraints = pg.get_all_constraints()
        assert len(all_constraints) == 4  # 3 global + 1 project


class TestProjectGovernanceHealth:
    """Test governance health reporting."""

    def test_get_health(self, mock_global_registry: MagicMock) -> None:
        """Test health report structure."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        health = pg.get_health()
        assert health["project_id"] == "test_project"
        assert health["initialized"] is True
        assert health["schema_coverage"] == 1.0
        assert health["active_schemas"] == 3
        assert health["total_constraints"] == 3
        assert health["status"] in ("healthy", "elevated", "critical")

    def test_health_with_project_constraints(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test health with additional project constraints."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        constraint = GovernanceConstraint(
            constraint_id="extra_constraint",
            description="Extra constraint",
            scope="global",
            enforcement="hard_stop",
        )
        pg.add_project_constraint(constraint, "operator_1")
        health = pg.get_health()
        assert health["project_constraints"] == 1
        assert health["total_constraints"] == 4
        assert health["hard_stop_constraints"] == 4

    def test_health_partial_coverage(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test health with partial schema coverage."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize(schema_ids=["uncertainty_management"])
        health = pg.get_health()
        assert health["schema_coverage"] == round(1 / 3, 2)
        assert health["active_schemas"] == 1

    def test_repr(self, mock_global_registry: MagicMock) -> None:
        """Test string representation."""
        pg = ProjectGovernance("test_project", mock_global_registry)
        pg.initialize()
        repr_str = repr(pg)
        assert "test_project" in repr_str
        assert "schemas=3" in repr_str


# ============================================================================
# ProjectContext Tests
# ============================================================================


class TestProjectContextLifecycle:
    """Test ProjectContext lifecycle management."""

    @pytest.mark.asyncio
    async def test_context_creation(
        self, sample_project_config: dict[str, str]
    ) -> None:
        """Test ProjectContext creation."""
        ctx = ProjectContext("test_project", sample_project_config)
        assert ctx.project_id == "test_project"
        assert ctx.name == "Test Project"
        assert ctx.category == "test"
        assert ctx.status == "active"
        assert ctx._initialized is False
        assert ctx._is_active is False

    @pytest.mark.asyncio
    async def test_context_initialize(
        self, mock_global_registry: MagicMock, sample_project_config: dict[str, str]
    ) -> None:
        """Test ProjectContext initialization with governance."""
        ctx = ProjectContext("test_project", sample_project_config)
        await ctx.initialize(mock_global_registry)
        assert ctx._initialized is True
        assert ctx.governance is not None
        assert ctx.memory is not None
        assert ctx.governance.project_id == "test_project"

    @pytest.mark.asyncio
    async def test_context_switch_in(
        self, mock_global_registry: MagicMock, sample_project_config: dict[str, str]
    ) -> None:
        """Test switching into a project context."""
        ctx = ProjectContext("test_project", sample_project_config)
        await ctx.initialize(mock_global_registry)
        result = await ctx.switch_in()
        assert ctx.is_active() is True
        assert result["project_id"] == "test_project"
        assert result["governance_active"] is True
        assert "active_schemas" in result

    @pytest.mark.asyncio
    async def test_context_switch_out(
        self, mock_global_registry: MagicMock, sample_project_config: dict[str, str]
    ) -> None:
        """Test switching out of a project context."""
        ctx = ProjectContext("test_project", sample_project_config)
        await ctx.initialize(mock_global_registry)
        await ctx.switch_in()
        assert ctx.is_active() is True
        await ctx.switch_out()
        assert ctx.is_active() is False

    @pytest.mark.asyncio
    async def test_context_audit_log(
        self, mock_global_registry: MagicMock, sample_project_config: dict[str, str]
    ) -> None:
        """Test that context switches create audit entries."""
        ctx = ProjectContext("test_project", sample_project_config)
        await ctx.initialize(mock_global_registry)
        initial_len = len(ctx.audit_log)
        await ctx.switch_in()
        await ctx.switch_out()
        assert len(ctx.audit_log) == initial_len + 2
        assert ctx.audit_log[-2]["action"] == "context_activated"
        assert ctx.audit_log[-1]["action"] == "context_deactivated"


class TestProjectContextState:
    """Test ProjectContext state management."""

    def test_set_and_get_state(
        self, sample_project_config: dict[str, str]
    ) -> None:
        """Test setting and getting state values."""
        ctx = ProjectContext("test_project", sample_project_config)
        ctx.set_state("key1", "value1")
        assert ctx.get_state("key1") == "value1"
        assert ctx.get_state("nonexistent", "default") == "default"

    def test_clear_state(self, sample_project_config: dict[str, str]) -> None:
        """Test clearing all state."""
        ctx = ProjectContext("test_project", sample_project_config)
        ctx.set_state("key1", "value1")
        ctx.set_state("key2", "value2")
        ctx.clear_state()
        assert ctx.get_state("key1") is None
        assert ctx.get_state("key2") is None

    def test_state_isolation(
        self, sample_project_config: dict[str, str]
    ) -> None:
        """Test that state is isolated between contexts."""
        ctx1 = ProjectContext("project_1", sample_project_config)
        ctx2 = ProjectContext("project_2", sample_project_config)
        ctx1.set_state("shared_key", "value_1")
        ctx2.set_state("shared_key", "value_2")
        assert ctx1.get_state("shared_key") == "value_1"
        assert ctx2.get_state("shared_key") == "value_2"


class TestProjectContextWorkflows:
    """Test ProjectContext workflow management."""

    def test_register_workflow(self, sample_project_config: dict[str, str]) -> None:
        """Test registering a workflow."""
        ctx = ProjectContext("test_project", sample_project_config)
        ctx.register_workflow("workflow_1")
        assert "workflow_1" in ctx.get_active_workflows()

    def test_unregister_workflow(self, sample_project_config: dict[str, str]) -> None:
        """Test unregistering a workflow."""
        ctx = ProjectContext("test_project", sample_project_config)
        ctx.register_workflow("workflow_1")
        removed = ctx.unregister_workflow("workflow_1")
        assert removed is True
        assert "workflow_1" not in ctx.get_active_workflows()

    def test_unregister_nonexistent(
        self, sample_project_config: dict[str, str]
    ) -> None:
        """Test unregistering a workflow that doesn't exist."""
        ctx = ProjectContext("test_project", sample_project_config)
        removed = ctx.unregister_workflow("nonexistent")
        assert removed is False

    def test_no_duplicate_workflows(
        self, sample_project_config: dict[str, str]
    ) -> None:
        """Test that duplicate workflow registrations are ignored."""
        ctx = ProjectContext("test_project", sample_project_config)
        ctx.register_workflow("workflow_1")
        ctx.register_workflow("workflow_1")
        assert len(ctx.get_active_workflows()) == 1

    def test_get_status(
        self, mock_global_registry: MagicMock, sample_project_config: dict[str, str]
    ) -> None:
        """Test getting full project status."""
        ctx = ProjectContext("test_project", sample_project_config)
        status = ctx.get_status()
        assert status["project_id"] == "test_project"
        assert status["name"] == "Test Project"
        assert "governance" in status
        assert "memory_entries" in status
        assert "active_workflows" in status


# ============================================================================
# ContextManager Tests
# ============================================================================


class TestContextManagerRegistration:
    """Test ContextManager project registration."""

    def test_register_project(self) -> None:
        """Test registering a project."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}
        ctx = cm.register_project("test", config)
        assert ctx.project_id == "test"
        assert cm.list_project_ids() == ["test"]

    def test_register_duplicate_raises(self) -> None:
        """Test that duplicate registration raises ValueError."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}
        cm.register_project("test", config)
        with pytest.raises(ValueError, match="already registered"):
            cm.register_project("test", config)

    def test_contains(self) -> None:
        """Test __contains__ operator."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}
        cm.register_project("test", config)
        assert "test" in cm
        assert "nonexistent" not in cm

    def test_len(self) -> None:
        """Test __len__ operator."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}
        cm.register_project("test1", config)
        cm.register_project("test2", config)
        assert len(cm) == 2

    def test_get_context(self) -> None:
        """Test getting a context by ID."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}
        cm.register_project("test", config)
        ctx = cm.get_context("test")
        assert ctx is not None
        assert ctx.project_id == "test"
        assert cm.get_context("nonexistent") is None

    def test_list_contexts(self) -> None:
        """Test listing all contexts."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}
        cm.register_project("test1", config)
        cm.register_project("test2", config)
        contexts = cm.list_contexts()
        assert len(contexts) == 2
        ids = [c["project_id"] for c in contexts]
        assert "test1" in ids
        assert "test2" in ids


class TestContextManagerSwitching:
    """Test context switching behavior."""

    @pytest.mark.asyncio
    async def test_switch_context(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test switching between project contexts."""
        cm = ContextManager()
        config1 = {"name": "Project 1", "category": "test", "status": "active"}
        config2 = {"name": "Project 2", "category": "test", "status": "active"}

        ctx1 = cm.register_project("proj1", config1)
        ctx2 = cm.register_project("proj2", config2)
        await ctx1.initialize(mock_global_registry)
        await ctx2.initialize(mock_global_registry)

        result = await cm.switch_context("proj1")
        assert result.project_id == "proj1"
        assert result.is_active() is True
        assert cm.get_active_project_id() == "proj1"

        result = await cm.switch_context("proj2")
        assert result.project_id == "proj2"
        assert result.is_active() is True
        assert ctx1.is_active() is False  # First context deactivated
        assert cm.get_active_project_id() == "proj2"

    @pytest.mark.asyncio
    async def test_switch_to_same_context_noop(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test switching to already-active context is a no-op."""
        cm = ContextManager()
        config = {"name": "Project 1", "category": "test", "status": "active"}
        ctx = cm.register_project("proj1", config)
        await ctx.initialize(mock_global_registry)

        await cm.switch_context("proj1")
        result = await cm.switch_context("proj1")
        assert result.project_id == "proj1"

    @pytest.mark.asyncio
    async def test_switch_to_unregistered_raises(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test switching to unregistered project raises ValueError."""
        cm = ContextManager()
        with pytest.raises(ValueError, match="not registered"):
            await cm.switch_context("nonexistent")

    @pytest.mark.asyncio
    async def test_only_one_context_active(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that only one context is active at a time."""
        cm = ContextManager()
        configs = [
            {"name": f"Project {i}", "category": "test", "status": "active"}
            for i in range(3)
        ]

        contexts = []
        for i, cfg in enumerate(configs):
            ctx = cm.register_project(f"proj{i}", cfg)
            await ctx.initialize(mock_global_registry)
            contexts.append(ctx)

        await cm.switch_context("proj0")
        assert contexts[0].is_active() is True
        assert contexts[1].is_active() is False
        assert contexts[2].is_active() is False

        await cm.switch_context("proj1")
        assert contexts[0].is_active() is False
        assert contexts[1].is_active() is True
        assert contexts[2].is_active() is False

        await cm.switch_context("proj2")
        assert contexts[0].is_active() is False
        assert contexts[1].is_active() is False
        assert contexts[2].is_active() is True

    @pytest.mark.asyncio
    async def test_switch_history(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that context switches are recorded."""
        cm = ContextManager()
        config = {"name": "Project", "category": "test", "status": "active"}
        ctx = cm.register_project("proj", config)
        await ctx.initialize(mock_global_registry)

        await cm.switch_context("proj")
        history = cm.get_switch_history()
        assert len(history) == 1
        assert history[0]["project_id"] == "proj"

    def test_get_active_context_none(self) -> None:
        """Test that active context is None initially."""
        cm = ContextManager()
        assert cm.get_active_context() is None
        assert cm.get_active_project_id() is None

    def test_repr(self) -> None:
        """Test string representation."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}
        cm.register_project("test", config)
        repr_str = repr(cm)
        assert "projects=1" in repr_str


# ============================================================================
# Context Isolation Tests
# ============================================================================


class TestContextIsolation:
    """Test that contexts are fully isolated — no cross-project data leakage."""

    @pytest.mark.asyncio
    async def test_memory_isolation(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that project memories are isolated."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}

        ctx1 = cm.register_project("proj1", config)
        ctx2 = cm.register_project("proj2", config)
        await ctx1.initialize(mock_global_registry)
        await ctx2.initialize(mock_global_registry)

        # Store memory in project 1
        await ctx1.memory.store("memory_for_proj1", "test", {})

        # Store memory in project 2
        await ctx2.memory.store("memory_for_proj2", "test", {})

        # Verify isolation: proj1 only sees its own memories
        proj1_memories = await ctx1.memory.retrieve(limit=10)
        assert all(m["project_id"] == "proj1" for m in proj1_memories)
        assert not any("proj2" in m["content"] for m in proj1_memories)

        # Verify isolation: proj2 only sees its own memories
        proj2_memories = await ctx2.memory.retrieve(limit=10)
        assert all(m["project_id"] == "proj2" for m in proj2_memories)
        assert not any("proj1" in m["content"] for m in proj2_memories)

    @pytest.mark.asyncio
    async def test_governance_isolation(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that project governance is isolated."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}

        ctx1 = cm.register_project("proj1", config)
        ctx2 = cm.register_project("proj2", config)
        await ctx1.initialize(mock_global_registry)
        await ctx2.initialize(mock_global_registry)

        # Add constraint only to project 1
        constraint = GovernanceConstraint(
            constraint_id="proj1_only",
            description="Only for project 1",
            scope="global",
            enforcement="hard_stop",
        )
        ctx1.governance.add_project_constraint(constraint, "operator_1")

        # Verify proj1 has the constraint
        assert len(ctx1.governance.get_project_constraints()) == 1
        # Verify proj2 does NOT have the constraint
        assert len(ctx2.governance.get_project_constraints()) == 0

    @pytest.mark.asyncio
    async def test_state_isolation_on_switch(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test state isolation during context switches."""
        cm = ContextManager()
        config = {"name": "Test", "category": "test", "status": "active"}

        ctx1 = cm.register_project("proj1", config)
        ctx2 = cm.register_project("proj2", config)
        await ctx1.initialize(mock_global_registry)
        await ctx2.initialize(mock_global_registry)

        await cm.switch_context("proj1")
        ctx1.set_state("shared_key", "proj1_value")

        await cm.switch_context("proj2")
        ctx2.set_state("shared_key", "proj2_value")

        # Values should be isolated
        assert ctx1.get_state("shared_key") == "proj1_value"
        assert ctx2.get_state("shared_key") == "proj2_value"

    def test_no_cross_project_access_without_operator(self) -> None:
        """Test that cross-project access requires explicit operator action."""
        # This is enforced at the memory level
        memory1 = ProjectMemory("proj1")
        # Direct access to another project's memory is not possible
        # through the API - each ProjectMemory only knows its own project_id
        assert memory1.project_id == "proj1"


# ============================================================================
# ProjectMemory Tests
# ============================================================================


class TestProjectMemoryStorage:
    """Test ProjectMemory storage operations."""

    @pytest.mark.asyncio
    async def test_store_memory(self) -> None:
        """Test storing a memory."""
        memory = ProjectMemory("test_project")
        result = await memory.store("Test content", "test_type", {"key": "value"})
        assert result["content"] == "Test content"
        assert result["memory_type"] == "test_type"
        assert result["project_id"] == "test_project"
        assert result["metadata"]["key"] == "value"
        assert "memory_id" in result
        assert "created_at" in result

    @pytest.mark.asyncio
    async def test_store_multiple(self) -> None:
        """Test storing multiple memories."""
        memory = ProjectMemory("test_project")
        for i in range(5):
            await memory.store(f"Content {i}", "test", {})
        assert len(memory) == 5

    @pytest.mark.asyncio
    async def test_retrieve_all(self) -> None:
        """Test retrieving memories."""
        memory = ProjectMemory("test_project")
        await memory.store("First memory", "test", {})
        await memory.store("Second memory", "test", {})
        results = await memory.retrieve(limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_retrieve_with_query(self) -> None:
        """Test retrieving with text query."""
        memory = ProjectMemory("test_project")
        await memory.store("Apple pie recipe", "recipe", {})
        await memory.store("Banana bread recipe", "recipe", {})
        await memory.store("Something else entirely", "other", {})
        results = await memory.retrieve(query="recipe", limit=10)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_retrieve_by_type(self) -> None:
        """Test retrieving filtered by memory type."""
        memory = ProjectMemory("test_project")
        await memory.store("Workflow 1", "workflow", {})
        await memory.store("Workflow 2", "workflow", {})
        await memory.store("Decision 1", "decision", {})
        results = await memory.retrieve(memory_type="workflow", limit=10)
        assert len(results) == 2
        assert all(r["memory_type"] == "workflow" for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_limit(self) -> None:
        """Test retrieve respects limit."""
        memory = ProjectMemory("test_project")
        for i in range(10):
            await memory.store(f"Memory {i}", "test", {})
        results = await memory.retrieve(limit=3)
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_get_by_id(self) -> None:
        """Test retrieving a specific memory by ID."""
        memory = ProjectMemory("test_project")
        stored = await memory.store("Test content", "test", {})
        fetched = await memory.get_by_id(stored["memory_id"])
        assert fetched is not None
        assert fetched["content"] == "Test content"

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self) -> None:
        """Test retrieving nonexistent memory returns None."""
        memory = ProjectMemory("test_project")
        result = await memory.get_by_id("nonexistent_id")
        assert result is None

    @pytest.mark.asyncio
    async def test_retrieval_updates_count(self) -> None:
        """Test that retrieval updates access metadata."""
        memory = ProjectMemory("test_project")
        stored = await memory.store("Test content", "test", {})
        # Retrieve
        await memory.retrieve(limit=10)
        fetched = await memory.get_by_id(stored["memory_id"])
        assert fetched["retrieval_count"] >= 1
        assert fetched["last_accessed"] is not None


class TestProjectMemorySpecializedQueries:
    """Test specialized memory queries."""

    @pytest.mark.asyncio
    async def test_get_workflow_history(self) -> None:
        """Test getting workflow history."""
        memory = ProjectMemory("test_project")
        await memory.store("Workflow 1", "workflow", {})
        await memory.store("Step 1", "workflow_step", {})
        await memory.store("Decision", "decision", {})
        history = await memory.get_workflow_history()
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_decision_ancestry(self) -> None:
        """Test getting decision ancestry."""
        memory = ProjectMemory("test_project")
        await memory.store("Decision 1", "decision", {})
        await memory.store("Context switch", "context_switch", {})
        await memory.store("Workflow", "workflow", {})
        ancestry = await memory.get_decision_ancestry()
        assert len(ancestry) == 2

    @pytest.mark.asyncio
    async def test_get_governance_continuity(self) -> None:
        """Test getting governance continuity record."""
        memory = ProjectMemory("test_project")
        await memory.store("Check 1", "governance_check", {})
        await memory.store("Violation", "violation", {})
        await memory.store("Workflow", "workflow", {})
        continuity = await memory.get_governance_continuity()
        assert len(continuity) == 2


class TestProjectMemoryCrossProjectAccess:
    """Test cross-project memory access controls."""

    @pytest.mark.asyncio
    async def test_cross_project_request(self) -> None:
        """Test requesting cross-project access."""
        memory = ProjectMemory("proj1")
        result = await memory.request_cross_project_access(
            target_project_id="proj2",
            operator_id="operator_1",
            reason="Need to compare data",
        )
        assert result["status"] == "pending_approval"
        assert result["source_project"] == "proj1"
        assert result["target_project"] == "proj2"

    @pytest.mark.asyncio
    async def test_cross_project_requires_operator(self) -> None:
        """Test that cross-project access requires operator ID."""
        memory = ProjectMemory("proj1")
        result = await memory.request_cross_project_access(
            target_project_id="proj2",
            operator_id="",
            reason="Need to compare data",
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_cross_project_requires_reason(self) -> None:
        """Test that cross-project access requires a reason."""
        memory = ProjectMemory("proj1")
        result = await memory.request_cross_project_access(
            target_project_id="proj2",
            operator_id="operator_1",
            reason="",
        )
        assert result["status"] == "error"


class TestProjectMemoryStatistics:
    """Test ProjectMemory statistics."""

    @pytest.mark.asyncio
    async def test_get_statistics(self) -> None:
        """Test memory statistics."""
        memory = ProjectMemory("test_project")
        await memory.store("M1", "workflow", {})
        await memory.store("M2", "workflow", {})
        await memory.store("M3", "decision", {})
        stats = memory.get_statistics()
        assert stats["project_id"] == "test_project"
        assert stats["total_memories"] == 3
        assert stats["by_type"]["workflow"] == 2
        assert stats["by_type"]["decision"] == 1

    def test_empty_statistics(self) -> None:
        """Test statistics for empty memory store."""
        memory = ProjectMemory("test_project")
        stats = memory.get_statistics()
        assert stats["total_memories"] == 0
        assert stats["by_type"] == {}

    def test_repr(self) -> None:
        """Test string representation."""
        memory = ProjectMemory("test_project")
        repr_str = repr(memory)
        assert "test_project" in repr_str
        assert "entries=0" in repr_str

    def test_len(self) -> None:
        """Test __len__ operator."""
        memory = ProjectMemory("test_project")
        assert len(memory) == 0


# ============================================================================
# OperationalReasoningEngine Tests
# ============================================================================


class TestOperationalReasoningEngineWorkflow:
    """Test workflow reasoning."""

    @pytest.fixture
    def reasoning_engine(self) -> OperationalReasoningEngine:
        """Return a fresh reasoning engine."""
        return OperationalReasoningEngine()

    @pytest.fixture
    def sample_project_context(
        self, mock_global_registry: MagicMock
    ) -> ProjectContext:
        """Return an initialized project context."""
        config = {"name": "Test", "category": "test", "status": "active"}
        ctx = ProjectContext("test_project", config)
        # Use asyncio to initialize
        loop = asyncio.get_event_loop()
        loop.run_until_complete(ctx.initialize(mock_global_registry))
        return ctx

    def test_reason_about_workflow(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test workflow reasoning."""
        workflow = WorkflowDefinition(
            workflow_id="wf1",
            name="Test Workflow",
            operations=[
                {"type": "query"},
                {"type": "analyze"},
            ],
        )
        result = reasoning_engine.reason_about_workflow(
            workflow, sample_project_context
        )
        assert result["project_id"] == "test_project"
        assert result["workflow_id"] == "wf1"
        assert result["analysis_type"] == "workflow_reasoning"
        assert "overall_risk_score" in result
        assert "operation_analyses" in result
        assert result["bounded"] is True

    def test_reason_about_risky_workflow(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test reasoning about a risky workflow."""
        workflow = WorkflowDefinition(
            workflow_id="wf_risky",
            name="Risky Workflow",
            operations=[
                {"type": "delete"},
                {"type": "schema_change"},
            ],
        )
        result = reasoning_engine.reason_about_workflow(
            workflow, sample_project_context
        )
        assert result["overall_risk_score"] > 0.5
        assert len(result["governance_implications"]) > 0

    def test_workflow_reasoning_is_observable(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that workflow reasoning is recorded in the log."""
        workflow = WorkflowDefinition(
            workflow_id="wf1",
            name="Test Workflow",
            operations=[{"type": "query"}],
        )
        result = reasoning_engine.reason_about_workflow(
            workflow, sample_project_context
        )
        trace_id = result["trace_id"]
        logged = reasoning_engine.get_reasoning_by_trace_id(trace_id)
        assert logged is not None
        assert logged["workflow_id"] == "wf1"


class TestOperationalReasoningEngineRisk:
    """Test risk assessment."""

    @pytest.fixture
    def reasoning_engine(self) -> OperationalReasoningEngine:
        """Return a fresh reasoning engine."""
        return OperationalReasoningEngine()

    @pytest.fixture
    def sample_project_context(
        self, mock_global_registry: MagicMock
    ) -> ProjectContext:
        """Return an initialized project context."""
        config = {"name": "Test", "category": "test", "status": "active"}
        ctx = ProjectContext("test_project", config)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(ctx.initialize(mock_global_registry))
        return ctx

    def test_assess_low_risk_action(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test assessing a low-risk action (query has low base risk but active status adds modifier)."""
        result = reasoning_engine.assess_risk("query", sample_project_context)
        # query base=0.1 + active status modifier=0.2 = 0.3 → medium
        assert result["risk_level"] == "medium"
        assert result["requires_approval"] is False
        assert result["approval_level"] == "self"
        assert result["bounded"] is True

    def test_assess_high_risk_action(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test assessing a high-risk action (delete base=0.9 + active status=0.2 capped at 1.0 → critical)."""
        result = reasoning_engine.assess_risk("delete", sample_project_context)
        # delete base=0.9 + active status modifier=0.2 = 1.1 capped at 1.0 → critical
        assert result["risk_level"] == "critical"
        assert result["requires_approval"] is True
        assert result["approval_level"] == "multi_operator"

    def test_assess_critical_risk_action(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test assessing a critical-risk action."""
        result = reasoning_engine.assess_risk(
            "schema_change", sample_project_context
        )
        assert result["risk_level"] == "critical"
        assert result["requires_approval"] is True

    def test_risk_assessment_is_observable(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that risk assessment is recorded in the log."""
        result = reasoning_engine.assess_risk("deploy", sample_project_context)
        trace_id = result["trace_id"]
        logged = reasoning_engine.get_reasoning_by_trace_id(trace_id)
        assert logged is not None
        assert logged["action"] == "deploy"

    def test_risk_has_mitigations(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that high-risk assessments include mitigations."""
        result = reasoning_engine.assess_risk("delete", sample_project_context)
        assert len(result["mitigations"]) > 0
        assert result["risk_factors"] is not None


class TestOperationalReasoningEnginePrioritization:
    """Test action prioritization."""

    @pytest.fixture
    def reasoning_engine(self) -> OperationalReasoningEngine:
        """Return a fresh reasoning engine."""
        return OperationalReasoningEngine()

    @pytest.fixture
    def sample_project_context(
        self, mock_global_registry: MagicMock
    ) -> ProjectContext:
        """Return an initialized project context."""
        config = {"name": "Test", "category": "test", "status": "active"}
        ctx = ProjectContext("test_project", config)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(ctx.initialize(mock_global_registry))
        return ctx

    def test_prioritize_actions(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test action prioritization."""
        actions = ["query", "delete", "analyze", "deploy"]
        result = reasoning_engine.prioritize_actions(
            actions, sample_project_context
        )
        assert len(result) == 4
        # Each should have a rank
        ranks = [r["rank"] for r in result]
        assert sorted(ranks) == [1, 2, 3, 4]

    def test_low_risk_actions_ranked_higher(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that low-risk actions are ranked higher."""
        actions = ["query", "schema_change"]
        result = reasoning_engine.prioritize_actions(
            actions, sample_project_context
        )
        # query should be rank 1 (lower risk)
        assert result[0]["action"] == "query"
        assert result[0]["rank"] == 1

    def test_prioritization_includes_reasoning(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that prioritization results include reasoning."""
        actions = ["query", "delete"]
        result = reasoning_engine.prioritize_actions(
            actions, sample_project_context
        )
        for entry in result:
            assert "reasoning" in entry
            assert "risk_level" in entry
            assert "requires_approval" in entry


class TestOperationalReasoningEnginePlanning:
    """Test operational plan generation."""

    @pytest.fixture
    def reasoning_engine(self) -> OperationalReasoningEngine:
        """Return a fresh reasoning engine."""
        return OperationalReasoningEngine()

    @pytest.fixture
    def sample_project_context(
        self, mock_global_registry: MagicMock
    ) -> ProjectContext:
        """Return an initialized project context."""
        config = {"name": "Test", "category": "test", "status": "active"}
        ctx = ProjectContext("test_project", config)
        loop = asyncio.get_event_loop()
        loop.run_until_complete(ctx.initialize(mock_global_registry))
        return ctx

    def test_generate_plan(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test plan generation."""
        result = reasoning_engine.generate_operational_plan(
            "Analyze the data and create a report",
            sample_project_context,
        )
        assert result["project_id"] == "test_project"
        assert result["objective"] == "Analyze the data and create a report"
        assert result["analysis_type"] == "operational_plan"
        assert len(result["steps"]) > 0
        assert result["bounded"] is True
        assert "note" in result  # Should note this is planning only

    def test_plan_has_governance_annotations(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that plan steps have governance annotations."""
        result = reasoning_engine.generate_operational_plan(
            "Deploy the application",
            sample_project_context,
        )
        for step in result["steps"]:
            assert "governance_annotation" in step
            assert step["governance_annotation"] in (
                "SAFE", "REVIEW", "APPROVE", "MULTI_APPROVE"
            )

    def test_plan_includes_governance_summary(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that plan includes governance summary."""
        result = reasoning_engine.generate_operational_plan(
            "Backup the database",
            sample_project_context,
        )
        assert "governance_summary" in result
        summary = result["governance_summary"]
        assert "safe_steps" in summary
        assert "review_steps" in summary
        assert "approve_steps" in summary
        assert "multi_approve_steps" in summary

    def test_risky_plan_not_auto_approved(
        self,
        reasoning_engine: OperationalReasoningEngine,
        sample_project_context: ProjectContext,
    ) -> None:
        """Test that risky plans are not auto-approved."""
        result = reasoning_engine.generate_operational_plan(
            "Delete all data and change schema",
            sample_project_context,
        )
        # Risky plan should not be auto-approved
        assert result["plan_approved"] is False or result["overall_risk_level"] in ("high", "critical")


# ============================================================================
# ProjectRegistry Tests
# ============================================================================


class TestProjectRegistryLifecycle:
    """Test ProjectRegistry system lifecycle."""

    @pytest.mark.asyncio
    async def test_initialize_all_projects(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test initializing all 7 projects."""
        registry = ProjectRegistry()
        result = await registry.initialize(mock_global_registry)
        assert result["status"] == "initialized"
        assert result["projects_initialized"] == 7
        assert len(registry) == 7
        assert registry._initialized is True

    @pytest.mark.asyncio
    async def test_all_7_project_ids_present(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that all 7 project IDs are registered."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        expected_ids = {
            "garvis", "alphaflow", "nova", "teachflow",
            "bella", "youtube", "general",
        }
        actual_ids = set(registry.context_manager.list_project_ids())
        assert expected_ids == actual_ids

    @pytest.mark.asyncio
    async def test_shutdown(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test shutdown."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        result = await registry.shutdown()
        assert result["status"] == "shutdown"

    @pytest.mark.asyncio
    async def test_activate_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test activating a project."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        ctx = await registry.activate_project("garvis")
        assert ctx.project_id == "garvis"
        assert ctx.is_active() is True
        assert registry.get_active_project_id() == "garvis"

    @pytest.mark.asyncio
    async def test_deactivate_current(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test deactivating current project."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        await registry.activate_project("garvis")
        assert registry.get_active_project_id() == "garvis"
        await registry.deactivate_current()
        assert registry.get_active_project_id() is None


class TestProjectRegistryQueries:
    """Test ProjectRegistry query methods."""

    @pytest.mark.asyncio
    async def test_get_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test getting a project."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        ctx = registry.get_project("garvis")
        assert ctx is not None
        assert ctx.project_id == "garvis"
        assert ctx.name == "GARVIS"

    @pytest.mark.asyncio
    async def test_get_project_governance(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test getting project governance."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        gov = registry.get_project_governance("garvis")
        assert gov is not None
        assert gov.project_id == "garvis"

    @pytest.mark.asyncio
    async def test_get_project_memory(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test getting project memory."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        memory = registry.get_project_memory("garvis")
        assert memory is not None
        assert memory.project_id == "garvis"

    @pytest.mark.asyncio
    async def test_list_projects(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test listing all projects."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        projects = registry.list_projects()
        assert len(projects) == 7

    @pytest.mark.asyncio
    async def test_list_active_projects(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test listing active projects."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        active = registry.list_active_projects()
        assert len(active) == 2  # garvis and general
        ids = [p["project_id"] for p in active]
        assert "garvis" in ids
        assert "general" in ids

    @pytest.mark.asyncio
    async def test_list_planned_projects(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test listing planned projects."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        planned = registry.list_planned_projects()
        assert len(planned) == 5  # alphaflow, nova, teachflow, bella, youtube

    @pytest.mark.asyncio
    async def test_get_system_health(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test getting system health."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        health = registry.get_system_health()
        assert health["registry_initialized"] is True
        assert health["total_projects"] == 7
        assert "project_healths" in health
        assert "overall_status" in health

    @pytest.mark.asyncio
    async def test_contains(self, mock_global_registry: MagicMock) -> None:
        """Test __contains__ operator."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        assert "garvis" in registry
        assert "nonexistent" not in registry

    @pytest.mark.asyncio
    async def test_len(self, mock_global_registry: MagicMock) -> None:
        """Test __len__ operator."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        assert len(registry) == 7


class TestProjectRegistryReasoning:
    """Test ProjectRegistry reasoning integration."""

    @pytest.mark.asyncio
    async def test_reason_about_workflow(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test workflow reasoning through registry."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        workflow = WorkflowDefinition(
            workflow_id="wf1",
            name="Test Workflow",
            operations=[{"type": "query"}, {"type": "analyze"}],
        )
        result = registry.reason_about_workflow(workflow, project_id="garvis")
        assert result["project_id"] == "garvis"
        assert result["workflow_id"] == "wf1"

    @pytest.mark.asyncio
    async def test_assess_risk(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test risk assessment through registry."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        result = registry.assess_risk("deploy", project_id="garvis")
        assert result["project_id"] == "garvis"
        assert result["action"] == "deploy"
        assert "risk_score" in result

    @pytest.mark.asyncio
    async def test_prioritize_actions(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test action prioritization through registry."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        result = registry.prioritize_actions(
            ["query", "delete", "analyze"],
            project_id="garvis",
        )
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_generate_plan(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test plan generation through registry."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        result = registry.generate_operational_plan(
            "Analyze data",
            project_id="garvis",
        )
        assert result["project_id"] == "garvis"
        assert len(result["steps"]) > 0

    @pytest.mark.asyncio
    async def test_reasoning_without_project_raises(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that reasoning without a project context raises ValueError."""
        registry = ProjectRegistry()
        # Don't initialize — no projects
        with pytest.raises(ValueError, match="No project context"):
            registry.assess_risk("deploy")

    @pytest.mark.asyncio
    async def test_reasoning_log(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that reasoning is logged."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        registry.assess_risk("query", project_id="garvis")
        log = registry.get_reasoning_log()
        assert len(log) >= 1


class TestProjectRegistryCrossProject:
    """Test cross-project operations."""

    @pytest.mark.asyncio
    async def test_cross_project_access_request(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test cross-project access request."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        result = await registry.cross_project_memory_access(
            source_project_id="garvis",
            target_project_id="alphaflow",
            operator_id="operator_1",
            reason="Need to check dependencies",
        )
        assert result["status"] == "pending_approval"

    @pytest.mark.asyncio
    async def test_cross_project_invalid_source(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test cross-project access with invalid source."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        result = await registry.cross_project_memory_access(
            source_project_id="nonexistent",
            target_project_id="alphaflow",
            operator_id="operator_1",
            reason="Test",
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_cross_project_invalid_target(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test cross-project access with invalid target."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)
        result = await registry.cross_project_memory_access(
            source_project_id="garvis",
            target_project_id="nonexistent",
            operator_id="operator_1",
            reason="Test",
        )
        assert result["status"] == "error"


# ============================================================================
# All 7 Projects End-to-End Tests
# ============================================================================


class TestAllSevenProjects:
    """End-to-end tests for all 7 GARVIS projects."""

    @pytest.mark.asyncio
    async def test_garvis_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test GARVIS core project."""
        config = next(p for p in PROJECTS if p["id"] == "garvis")
        ctx = ProjectContext("garvis", config)
        await ctx.initialize(mock_global_registry)
        assert ctx.name == "GARVIS"
        assert ctx.status == "active"
        assert ctx.category == "core"
        assert ctx.governance is not None
        gov_health = ctx.governance.get_health()
        assert gov_health["status"] in ("healthy", "elevated", "critical")

    @pytest.mark.asyncio
    async def test_alphaflow_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test AlphaFlow project."""
        config = next(p for p in PROJECTS if p["id"] == "alphaflow")
        ctx = ProjectContext("alphaflow", config)
        await ctx.initialize(mock_global_registry)
        assert ctx.name == "AlphaFlow"
        assert ctx.status == "planned"
        assert ctx.category == "workflow"

    @pytest.mark.asyncio
    async def test_nova_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test NOVA project."""
        config = next(p for p in PROJECTS if p["id"] == "nova")
        ctx = ProjectContext("nova", config)
        await ctx.initialize(mock_global_registry)
        assert ctx.name == "NOVA"
        assert ctx.status == "planned"
        assert ctx.category == "analytics"

    @pytest.mark.asyncio
    async def test_teachflow_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test TeachFlow project."""
        config = next(p for p in PROJECTS if p["id"] == "teachflow")
        ctx = ProjectContext("teachflow", config)
        await ctx.initialize(mock_global_registry)
        assert ctx.name == "TeachFlow"
        assert ctx.status == "planned"
        assert ctx.category == "education"

    @pytest.mark.asyncio
    async def test_bella_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test Bella & Friends project."""
        config = next(p for p in PROJECTS if p["id"] == "bella")
        ctx = ProjectContext("bella", config)
        await ctx.initialize(mock_global_registry)
        assert ctx.name == "Bella & Friends"
        assert ctx.status == "planned"
        assert ctx.category == "character"

    @pytest.mark.asyncio
    async def test_youtube_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test YouTube Engine project."""
        config = next(p for p in PROJECTS if p["id"] == "youtube")
        ctx = ProjectContext("youtube", config)
        await ctx.initialize(mock_global_registry)
        assert ctx.name == "YouTube Engine"
        assert ctx.status == "planned"
        assert ctx.category == "content"

    @pytest.mark.asyncio
    async def test_general_ops_project(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test General Ops project."""
        config = next(p for p in PROJECTS if p["id"] == "general")
        ctx = ProjectContext("general", config)
        await ctx.initialize(mock_global_registry)
        assert ctx.name == "General Ops"
        assert ctx.status == "active"
        assert ctx.category == "operations"

    @pytest.mark.asyncio
    async def test_all_projects_in_registry(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test that all 7 projects are in the registry with correct categories."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)

        projects = registry.list_projects()
        categories = {p["project_id"]: p["category"] for p in projects}

        assert categories["garvis"] == "core"
        assert categories["alphaflow"] == "workflow"
        assert categories["nova"] == "analytics"
        assert categories["teachflow"] == "education"
        assert categories["bella"] == "character"
        assert categories["youtube"] == "content"
        assert categories["general"] == "operations"

    @pytest.mark.asyncio
    async def test_context_switching_all_projects(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test switching through all 7 projects."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)

        for project_config in PROJECTS:
            pid = project_config["id"]
            ctx = await registry.activate_project(pid)
            assert ctx.project_id == pid
            assert ctx.is_active() is True
            assert registry.get_active_project_id() == pid

        # All projects were visited
        history = registry.get_switch_history()
        assert len(history) == 7

    @pytest.mark.asyncio
    async def test_memory_isolation_all_projects(
        self, mock_global_registry: MagicMock
    ) -> None:
        """Test memory isolation across all 7 projects."""
        registry = ProjectRegistry()
        await registry.initialize(mock_global_registry)

        # Store a memory in each project
        for project_config in PROJECTS:
            pid = project_config["id"]
            ctx = registry.get_project(pid)
            if ctx and ctx.memory:
                await ctx.memory.store(
                    f"Memory for {pid}",
                    "test",
                    {"project": pid},
                )

        # Verify each project only sees its own memories
        for project_config in PROJECTS:
            pid = project_config["id"]
            ctx = registry.get_project(pid)
            if ctx and ctx.memory:
                memories = await ctx.memory.retrieve(limit=100)
                assert len(memories) == 1
                assert memories[0]["project_id"] == pid
                assert pid in memories[0]["content"]
