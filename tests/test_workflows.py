"""Comprehensive tests for the Governed Workflow Runtime.

Tests cover:
- Workflow registration and validation
- Approval flow (propose -> classify -> approve -> execute)
- Step execution with governance mediation
- Rollback
- Unapproved workflows cannot execute
- Governance violations stop workflow
- Audit trail completeness
- Workflow statistics
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from models.governance import GovernanceCheckResult, GovernanceViolation
from monitoring.alerts import AlertEngine
from workflows.audit import WorkflowAudit
from workflows.engine import WorkflowEngine
from workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStepResult,
)
from workflows.registry import WorkflowRegistry

# Suppress noisy logging during tests
logging.getLogger("garvis.workflows").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry() -> WorkflowRegistry:
    """Return a fresh WorkflowRegistry."""
    return WorkflowRegistry()


@pytest.fixture
def approval_framework() -> MagicMock:
    """Return a mock WorkflowApprovalFramework."""
    framework = MagicMock()
    framework.submit_for_approval = MagicMock(return_value={
        "proposal_id": str(uuid4()),
        "risk_level": "medium",
        "risk_description": "Data processing, internal changes",
        "required_approval": "operator",
        "audit_record_id": str(uuid4()),
        "status": "pending_approval",
    })
    framework.approve_workflow = MagicMock(return_value={
        "status": "approved",
        "approved_by": "operator_1",
    })
    framework.get_proposal = MagicMock(return_value={
        "status": "approved",
        "approved_by": "operator_1",
    })
    framework.RISK_LEVELS = {
        "low": {"description": "Read-only, no side effects", "approval": "self"},
        "medium": {"description": "Data processing, internal changes", "approval": "operator"},
        "high": {"description": "External calls, file modifications", "approval": "operator_explicit"},
        "critical": {"description": "Destructive, schema changes", "approval": "operator_multi"},
    }
    return framework


@pytest.fixture
def mock_audit_pipeline() -> MagicMock:
    """Return a mock AuditPipeline with async methods."""
    audit = MagicMock()
    audit.log_event = AsyncMock()
    audit.get_events = AsyncMock(return_value=[])
    audit.flush = AsyncMock()
    audit.start = AsyncMock()
    audit.stop = AsyncMock()
    return audit


@pytest.fixture
def mock_lineage_tracker() -> MagicMock:
    """Return a mock LineageTracker with async methods."""
    lineage = MagicMock()
    lineage.start_trace = AsyncMock(return_value=uuid4())
    lineage.record_inference = AsyncMock()
    lineage.record_governance_influence = AsyncMock()
    lineage.record_memory_influence = AsyncMock()
    lineage.get_trace = AsyncMock(return_value=None)
    lineage.get_lineage_graph = AsyncMock(return_value={
        "nodes": {}, "edges": [], "trace_id": str(uuid4()),
    })
    return lineage


@pytest.fixture
def alert_engine() -> AlertEngine:
    """Return a fresh AlertEngine."""
    return AlertEngine()


@pytest.fixture
def workflow_audit(mock_audit_pipeline: MagicMock) -> WorkflowAudit:
    """Return a WorkflowAudit with mock pipeline."""
    return WorkflowAudit(mock_audit_pipeline)


@pytest.fixture
def engine(
    registry: WorkflowRegistry,
    approval_framework: MagicMock,
    mock_audit_pipeline: MagicMock,
    mock_lineage_tracker: MagicMock,
    alert_engine: AlertEngine,
) -> WorkflowEngine:
    """Return a WorkflowEngine with all dependencies."""
    return WorkflowEngine(
        registry=registry,
        approval_framework=approval_framework,
        audit_pipeline=mock_audit_pipeline,
        lineage_tracker=mock_lineage_tracker,
        alert_engine=alert_engine,
    )


@pytest.fixture
def sample_workflow_low_risk() -> WorkflowDefinition:
    """Return a low-risk workflow definition."""
    return WorkflowDefinition(
        workflow_id="wf_low_001",
        name="Health Check",
        description="A simple read-only health check workflow",
        project_id="ops",
        risk_level="low",
        required_approval="self",
        steps=[
            WorkflowStep(
                step_id="check_status",
                name="Check System Status",
                description="Verify system is healthy",
                action_type="audit_log",
                parameters={"event_type": "health_check", "message": "System OK"},
                governance_checks=["system_health"],
            ),
        ],
        governance_schemas=["system_health"],
        created_by="operator_1",
    )


@pytest.fixture
def sample_workflow_medium_risk() -> WorkflowDefinition:
    """Return a medium-risk workflow definition with multiple steps."""
    return WorkflowDefinition(
        workflow_id="wf_medium_001",
        name="Data Analysis",
        description="Process and analyze collected data",
        project_id="nova",
        risk_level="medium",
        required_approval="operator",
        steps=[
            WorkflowStep(
                step_id="fetch_data",
                name="Fetch Data",
                description="Retrieve data from storage",
                action_type="memory_retrieve",
                parameters={"query": "recent_metrics", "limit": 100},
                governance_checks=["data_access"],
            ),
            WorkflowStep(
                step_id="process_data",
                name="Process Data",
                description="Transform and aggregate data",
                action_type="governance_check",
                parameters={"schema_id": "data_integrity", "check_type": "validation"},
                governance_checks=["data_integrity", "privacy_protection"],
                depends_on=["fetch_data"],
            ),
            WorkflowStep(
                step_id="log_results",
                name="Log Results",
                description="Write analysis results to audit log",
                action_type="audit_log",
                parameters={"event_type": "analysis_complete", "message": "Data processed"},
                governance_checks=["audit_compliance"],
                depends_on=["process_data"],
            ),
        ],
        governance_schemas=["data_access", "data_integrity", "privacy_protection", "audit_compliance"],
        created_by="operator_1",
    )


@pytest.fixture
def sample_workflow_high_risk() -> WorkflowDefinition:
    """Return a high-risk workflow definition with external calls."""
    return WorkflowDefinition(
        workflow_id="wf_high_001",
        name="External API Sync",
        description="Synchronize data with external API",
        project_id="ops",
        risk_level="high",
        required_approval="operator_explicit",
        steps=[
            WorkflowStep(
                step_id="api_call",
                name="Call External API",
                description="Send data to external service",
                action_type="external_call",
                parameters={"endpoint": "https://api.example.com/sync", "method": "POST"},
                governance_checks=["external_api_policy", "data_exposure"],
            ),
        ],
        governance_schemas=["external_api_policy", "data_exposure"],
        created_by="operator_1",
    )


@pytest.fixture
def sample_workflow_critical() -> WorkflowDefinition:
    """Return a critical-risk workflow definition."""
    return WorkflowDefinition(
        workflow_id="wf_crit_001",
        name="Database Migration",
        description="Destructive database schema migration",
        project_id="garvis",
        risk_level="critical",
        required_approval="operator_multi",
        steps=[
            WorkflowStep(
                step_id="backup",
                name="Create Backup",
                description="Backup database before migration",
                action_type="governance_check",
                parameters={"schema_id": "backup_policy", "check_type": "verify"},
                governance_checks=["backup_policy"],
            ),
            WorkflowStep(
                step_id="migrate",
                name="Run Migration",
                description="Apply schema changes",
                action_type="external_call",
                parameters={"endpoint": "/db/migrate", "method": "POST"},
                governance_checks=["schema_change_policy", "backup_verified"],
                depends_on=["backup"],
            ),
        ],
        governance_schemas=["backup_policy", "schema_change_policy"],
        created_by="operator_1",
    )


# ---------------------------------------------------------------------------
# 1. Workflow Model Tests
# ---------------------------------------------------------------------------


class TestWorkflowModels:
    """Test the Pydantic workflow models."""

    def test_workflow_step_creation(self) -> None:
        """Test that a WorkflowStep can be created."""
        step = WorkflowStep(
            step_id="test_step",
            name="Test Step",
            description="A test step",
            action_type="audit_log",
            parameters={"key": "value"},
        )
        assert step.step_id == "test_step"
        assert step.name == "Test Step"
        assert step.action_type == "audit_log"
        assert step.parameters == {"key": "value"}
        assert step.timeout_seconds == 30
        assert step.retry_count == 0
        assert step.depends_on == []

    def test_workflow_step_default_values(self) -> None:
        """Test WorkflowStep default values."""
        step = WorkflowStep(
            step_id="step1",
            name="Step One",
            description="First step",
            action_type="audit_log",
        )
        assert step.parameters == {}
        assert step.governance_checks == []
        assert step.timeout_seconds == 30
        assert step.retry_count == 0
        assert step.depends_on == []

    def test_workflow_definition_creation(self, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test that a WorkflowDefinition can be created."""
        wf = sample_workflow_low_risk
        assert wf.workflow_id == "wf_low_001"
        assert wf.name == "Health Check"
        assert wf.risk_level == "low"
        assert len(wf.steps) == 1
        assert wf.active is False

    def test_workflow_definition_get_step(self, sample_workflow_medium_risk: WorkflowDefinition) -> None:
        """Test retrieving a step by ID."""
        wf = sample_workflow_medium_risk
        step = wf.get_step("process_data")
        assert step is not None
        assert step.name == "Process Data"

    def test_workflow_definition_get_step_not_found(self, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test retrieving a nonexistent step."""
        assert sample_workflow_low_risk.get_step("nonexistent") is None

    def test_workflow_definition_ordered_steps(self, sample_workflow_medium_risk: WorkflowDefinition) -> None:
        """Test dependency-ordered step retrieval."""
        ordered = sample_workflow_medium_risk.get_ordered_steps()
        step_ids = [s.step_id for s in ordered]
        # fetch_data has no deps, comes first
        assert step_ids.index("fetch_data") < step_ids.index("process_data")
        # process_data depends on fetch_data
        assert step_ids.index("process_data") < step_ids.index("log_results")

    def test_workflow_definition_validate_dependencies_ok(self, sample_workflow_medium_risk: WorkflowDefinition) -> None:
        """Test dependency validation with valid deps."""
        errors = sample_workflow_medium_risk.validate_dependencies()
        assert errors == []

    def test_workflow_definition_validate_dependencies_missing(self) -> None:
        """Test dependency validation with missing dependency."""
        wf = WorkflowDefinition(
            workflow_id="wf_bad",
            name="Bad Workflow",
            description="Has missing dependency",
            project_id="test",
            risk_level="low",
            required_approval="self",
            steps=[
                WorkflowStep(
                    step_id="step1",
                    name="Step 1",
                    description="Depends on missing step",
                    action_type="audit_log",
                    depends_on=["missing_step"],
                ),
            ],
        )
        errors = wf.validate_dependencies()
        assert len(errors) == 1
        assert "missing_step" in errors[0]

    def test_workflow_instance_creation(self) -> None:
        """Test WorkflowInstance creation."""
        instance = WorkflowInstance(
            workflow_id="wf_001",
            project_id="test",
            operator_id="op_1",
            approval_id="prop_1",
        )
        assert instance.workflow_id == "wf_001"
        assert instance.status == "pending"
        assert isinstance(instance.instance_id, UUID)
        assert isinstance(instance.trace_id, UUID)

    def test_workflow_instance_get_step_result(self) -> None:
        """Test retrieving a step result."""
        result = WorkflowStepResult(step_id="s1", status="completed")
        instance = WorkflowInstance(
            workflow_id="wf_001",
            project_id="test",
            operator_id="op_1",
            approval_id="prop_1",
            steps_executed=[result],
        )
        found = instance.get_step_result("s1")
        assert found is not None
        assert found.status == "completed"

    def test_workflow_instance_is_step_completed(self) -> None:
        """Test checking step completion."""
        result = WorkflowStepResult(step_id="s1", status="completed")
        instance = WorkflowInstance(
            workflow_id="wf_001",
            project_id="test",
            operator_id="op_1",
            approval_id="prop_1",
            steps_executed=[result],
        )
        assert instance.is_step_completed("s1") is True
        assert instance.is_step_completed("s2") is False

    def test_workflow_instance_all_steps_succeeded(self) -> None:
        """Test checking all steps succeeded."""
        instance = WorkflowInstance(
            workflow_id="wf_001",
            project_id="test",
            operator_id="op_1",
            approval_id="prop_1",
            steps_executed=[
                WorkflowStepResult(step_id="s1", status="completed"),
                WorkflowStepResult(step_id="s2", status="completed"),
            ],
        )
        assert instance.all_steps_succeeded() is True

    def test_workflow_instance_has_failed_steps(self) -> None:
        """Test detecting failed steps."""
        instance = WorkflowInstance(
            workflow_id="wf_001",
            project_id="test",
            operator_id="op_1",
            approval_id="prop_1",
            steps_executed=[
                WorkflowStepResult(step_id="s1", status="completed"),
                WorkflowStepResult(step_id="s2", status="failed"),
            ],
        )
        assert instance.has_failed_steps() is True

    def test_workflow_instance_step_counts(self) -> None:
        """Test step counting methods."""
        instance = WorkflowInstance(
            workflow_id="wf_001",
            project_id="test",
            operator_id="op_1",
            approval_id="prop_1",
            steps_executed=[
                WorkflowStepResult(step_id="s1", status="completed"),
                WorkflowStepResult(step_id="s2", status="completed"),
                WorkflowStepResult(step_id="s3", status="failed"),
                WorkflowStepResult(step_id="s4", status="pending"),
            ],
        )
        assert instance.steps_completed_count() == 2
        assert instance.steps_failed_count() == 1

    def test_workflow_step_result_defaults(self) -> None:
        """Test WorkflowStepResult default values."""
        result = WorkflowStepResult(step_id="s1")
        assert result.status == "pending"
        assert result.result == {}
        assert result.governance_checks == []
        assert result.error is None

    def test_workflow_step_result_with_governance_checks(self) -> None:
        """Test WorkflowStepResult with governance check results."""
        check = GovernanceCheckResult(
            schema_id="test_schema",
            policy_id="test_policy",
            passed=True,
        )
        result = WorkflowStepResult(
            step_id="s1",
            status="completed",
            governance_checks=[check],
        )
        assert len(result.governance_checks) == 1
        assert result.governance_checks[0].passed is True


# ---------------------------------------------------------------------------
# 2. Workflow Registry Tests
# ---------------------------------------------------------------------------


class TestWorkflowRegistry:
    """Test the WorkflowRegistry."""

    def test_register_workflow(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test registering a workflow."""
        result = registry.register(sample_workflow_low_risk, "operator_1")
        assert result.workflow_id == "wf_low_001"
        assert result.created_by == "operator_1"
        assert result.active is False

    def test_register_duplicate_id_overwrites(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test that registering with same ID updates the workflow."""
        registry.register(sample_workflow_low_risk, "operator_1")
        modified = sample_workflow_low_risk.model_copy(update={"name": "Updated"})
        result = registry.register(modified, "operator_2")
        assert result.name == "Updated"

    def test_register_invalid_risk_level(self, registry: WorkflowRegistry) -> None:
        """Test registering a workflow with invalid risk level."""
        wf = WorkflowDefinition(
            workflow_id="wf_bad",
            name="Bad",
            description="Invalid risk",
            project_id="test",
            risk_level="invalid",
            required_approval="self",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    name="Step 1",
                    description="A step",
                    action_type="audit_log",
                ),
            ],
        )
        with pytest.raises(ValueError, match="risk"):
            registry.register(wf, "operator_1")

    def test_register_no_steps(self, registry: WorkflowRegistry) -> None:
        """Test registering a workflow with no steps."""
        wf = WorkflowDefinition(
            workflow_id="wf_empty",
            name="Empty",
            description="No steps",
            project_id="test",
            risk_level="low",
            required_approval="self",
            steps=[],
        )
        with pytest.raises(ValueError, match="step"):
            registry.register(wf, "operator_1")

    def test_register_invalid_action_type(self, registry: WorkflowRegistry) -> None:
        """Test registering a workflow with invalid action type."""
        wf = WorkflowDefinition(
            workflow_id="wf_bad_action",
            name="Bad Action",
            description="Invalid action type",
            project_id="test",
            risk_level="low",
            required_approval="self",
            steps=[
                WorkflowStep(
                    step_id="s1",
                    name="Step 1",
                    description="Bad action",
                    action_type="invalid_action",
                ),
            ],
        )
        with pytest.raises(ValueError, match="action"):
            registry.register(wf, "operator_1")

    def test_get_workflow(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test retrieving a workflow."""
        registry.register(sample_workflow_low_risk, "operator_1")
        found = registry.get("wf_low_001")
        assert found is not None
        assert found.name == "Health Check"

    def test_get_workflow_not_found(self, registry: WorkflowRegistry) -> None:
        """Test retrieving a nonexistent workflow."""
        assert registry.get("nonexistent") is None

    def test_list_workflows_active_only(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test listing only active workflows."""
        registry.register(sample_workflow_low_risk, "operator_1")
        # Workflow is inactive by default
        active = registry.list(active_only=True)
        assert len(active) == 0
        inactive = registry.list(active_only=False)
        assert len(inactive) == 1

    def test_list_workflows_by_project(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition, sample_workflow_medium_risk: WorkflowDefinition) -> None:
        """Test filtering workflows by project."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.register(sample_workflow_medium_risk, "op_1")
        ops_workflows = registry.list(project_id="ops", active_only=False)
        assert len(ops_workflows) == 1
        assert ops_workflows[0].project_id == "ops"

    def test_activate_workflow(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test activating a workflow."""
        registry.register(sample_workflow_low_risk, "op_1")
        # Validation should pass for a valid workflow
        result = registry.activate("wf_low_001", "op_1")
        assert result is True
        wf = registry.get("wf_low_001")
        assert wf is not None
        assert wf.active is True

    def test_activate_nonexistent_workflow(self, registry: WorkflowRegistry) -> None:
        """Test activating a nonexistent workflow."""
        result = registry.activate("nonexistent", "op_1")
        assert result is False

    def test_deactivate_workflow(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test deactivating a workflow."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")
        result = registry.deactivate("wf_low_001", "op_1")
        assert result is True
        wf = registry.get("wf_low_001")
        assert wf is not None
        assert wf.active is False

    def test_deactivate_nonexistent_workflow(self, registry: WorkflowRegistry) -> None:
        """Test deactivating a nonexistent workflow."""
        result = registry.deactivate("nonexistent", "op_1")
        assert result is False

    def test_validate_valid_workflow(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test validating a valid workflow."""
        registry.register(sample_workflow_low_risk, "op_1")
        results = registry.validate("wf_low_001")
        assert all(r.passed for r in results)

    def test_validate_invalid_risk_level(self, registry: WorkflowRegistry) -> None:
        """Test validation catches invalid risk level."""
        # Use a valid risk level for registration, then patch it
        wf = WorkflowDefinition(
            workflow_id="wf_test",
            name="Test",
            description="Test workflow",
            project_id="test",
            risk_level="low",
            required_approval="self",
            steps=[
                WorkflowStep(
                    step_id="s1", name="S1", description="Test",
                    action_type="audit_log",
                ),
            ],
        )
        registry.register(wf, "op_1")
        # Now manually override the risk level to invalid
        stored = registry.get("wf_test")
        assert stored is not None
        stored.risk_level = "invalid_risk"
        results = registry.validate("wf_test")
        risk_check = [r for r in results if r.policy_id == "valid_risk_level"]
        assert len(risk_check) == 1
        assert risk_check[0].passed is False

    def test_validate_missing_workflow(self, registry: WorkflowRegistry) -> None:
        """Test validating a nonexistent workflow."""
        results = registry.validate("nonexistent")
        assert any(not r.passed for r in results)

    def test_validate_circular_dependencies(self, registry: WorkflowRegistry) -> None:
        """Test that registration rejects workflows with circular dependencies."""
        wf = WorkflowDefinition(
            workflow_id="wf_cycle",
            name="Cyclic",
            description="Has circular deps",
            project_id="test",
            risk_level="low",
            required_approval="self",
            steps=[
                WorkflowStep(
                    step_id="a", name="A", description="Depends on B",
                    action_type="audit_log", depends_on=["b"],
                ),
                WorkflowStep(
                    step_id="b", name="B", description="Depends on A",
                    action_type="audit_log", depends_on=["a"],
                ),
            ],
        )
        # Circular dependencies are caught at registration time
        with pytest.raises(ValueError, match="Circular|circular|cycle"):
            registry.register(wf, "op_1")

    def test_detect_cycle_true(self, registry: WorkflowRegistry) -> None:
        """Test cycle detection with actual cycle."""
        wf = WorkflowDefinition(
            workflow_id="wf_cyc",
            name="Cyclic",
            description="Circular",
            project_id="test",
            risk_level="low",
            required_approval="self",
            steps=[
                WorkflowStep(
                    step_id="a", name="A", description="",
                    action_type="audit_log", depends_on=["b"],
                ),
                WorkflowStep(
                    step_id="b", name="B", description="",
                    action_type="audit_log", depends_on=["a"],
                ),
            ],
        )
        assert WorkflowRegistry._detect_cycle(wf) is True

    def test_detect_cycle_false(self, registry: WorkflowRegistry, sample_workflow_medium_risk: WorkflowDefinition) -> None:
        """Test cycle detection with no cycle."""
        assert WorkflowRegistry._detect_cycle(sample_workflow_medium_risk) is False

    def test_count(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test workflow count."""
        assert registry.count() == 0
        registry.register(sample_workflow_low_risk, "op_1")
        assert registry.count() == 1

    def test_registration_log(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test registration log entries."""
        registry.register(sample_workflow_low_risk, "op_1")
        log = registry.get_registration_log("wf_low_001")
        assert len(log) >= 1
        assert log[0]["action"] == "registered"

    def test_reset(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test registry reset."""
        registry.register(sample_workflow_low_risk, "op_1")
        assert registry.count() == 1
        registry.reset()
        assert registry.count() == 0


# ---------------------------------------------------------------------------
# 3. Workflow Audit Tests
# ---------------------------------------------------------------------------


class TestWorkflowAudit:
    """Test the WorkflowAudit class."""

    @pytest.mark.asyncio
    async def test_log_proposal(self, workflow_audit: WorkflowAudit, mock_audit_pipeline: MagicMock) -> None:
        """Test logging a workflow proposal."""
        proposal = {
            "proposal_id": "prop_1",
            "workflow_id": "wf_1",
            "workflow_name": "Test",
            "project_id": "test",
            "operator_id": "op_1",
            "risk_level": "low",
            "required_approval": "self",
        }
        await workflow_audit.log_proposal(proposal)
        mock_audit_pipeline.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_approval(self, workflow_audit: WorkflowAudit, mock_audit_pipeline: MagicMock) -> None:
        """Test logging an approval decision."""
        approval = {
            "proposal_id": "prop_1",
            "workflow_id": "wf_1",
            "operator_id": "op_1",
            "instance_id": "inst_1",
        }
        await workflow_audit.log_approval(approval)
        mock_audit_pipeline.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_step_start(self, workflow_audit: WorkflowAudit, mock_audit_pipeline: MagicMock) -> None:
        """Test logging step execution start."""
        await workflow_audit.log_step_start("inst_1", "step_1")
        mock_audit_pipeline.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_step_complete(self, workflow_audit: WorkflowAudit, mock_audit_pipeline: MagicMock) -> None:
        """Test logging step completion."""
        result = WorkflowStepResult(
            step_id="step_1",
            status="completed",
            governance_checks=[
                GovernanceCheckResult(
                    schema_id="test", policy_id="p1", passed=True
                ),
            ],
        )
        await workflow_audit.log_step_complete("inst_1", "step_1", result)
        mock_audit_pipeline.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_step_failure(self, workflow_audit: WorkflowAudit, mock_audit_pipeline: MagicMock) -> None:
        """Test logging step failure."""
        await workflow_audit.log_step_failure("inst_1", "step_1", "Something broke")
        mock_audit_pipeline.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_rollback(self, workflow_audit: WorkflowAudit, mock_audit_pipeline: MagicMock) -> None:
        """Test logging rollback."""
        await workflow_audit.log_rollback("inst_1", "op_1")
        mock_audit_pipeline.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_workflow_complete(self, workflow_audit: WorkflowAudit, mock_audit_pipeline: MagicMock) -> None:
        """Test logging workflow completion."""
        instance = WorkflowInstance(
            workflow_id="wf_1",
            project_id="test",
            operator_id="op_1",
            status="completed",
            approval_id="prop_1",
            steps_executed=[
                WorkflowStepResult(step_id="s1", status="completed"),
            ],
        )
        await workflow_audit.log_workflow_complete(instance)
        mock_audit_pipeline.log_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_workflow_audit_trail(self, workflow_audit: WorkflowAudit) -> None:
        """Test retrieving workflow audit trail."""
        # Log some events first
        await workflow_audit.log_step_start("inst_1", "step_1")
        await workflow_audit.log_step_start("inst_1", "step_2")
        trail = await workflow_audit.get_workflow_audit_trail("inst_1")
        assert len(trail) == 2

    @pytest.mark.asyncio
    async def test_get_workflow_audit_trail_empty(self, workflow_audit: WorkflowAudit) -> None:
        """Test retrieving audit trail for unknown instance."""
        trail = await workflow_audit.get_workflow_audit_trail("unknown")
        assert trail == []

    @pytest.mark.asyncio
    async def test_get_workflow_statistics(self, workflow_audit: WorkflowAudit) -> None:
        """Test getting workflow statistics."""
        stats = await workflow_audit.get_workflow_statistics()
        assert "total_executions" in stats
        assert "by_status" in stats
        assert "rollbacks" in stats

    def test_reset(self, workflow_audit: WorkflowAudit) -> None:
        """Test audit reset."""
        workflow_audit.reset()
        assert len(workflow_audit._workflow_events) == 0


# ---------------------------------------------------------------------------
# 4. Approval Flow Tests
# ---------------------------------------------------------------------------


class TestApprovalFlow:
    """Test the approval flow: propose -> classify -> approve -> execute."""

    @pytest.mark.asyncio
    async def test_propose_execution(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test proposing workflow execution."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        result = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        assert result["status"] == "proposed"
        assert "proposal_id" in result
        assert result["workflow_id"] == "wf_low_001"

    @pytest.mark.asyncio
    async def test_propose_inactive_workflow(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that inactive workflows cannot be proposed."""
        registry.register(sample_workflow_low_risk, "op_1")
        # Don't activate
        result = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        assert result["status"] == "error"
        assert "not active" in result["reason"]

    @pytest.mark.asyncio
    async def test_propose_nonexistent_workflow(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test that nonexistent workflows cannot be proposed."""
        result = await engine.propose_execution(
            workflow_id="nonexistent",
            project_id="ops",
            operator_id="op_1",
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_execute_approved_workflow(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test executing an approved workflow."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        proposal_id = proposal["proposal_id"]

        instance = await engine.execute(proposal_id, "op_1")
        assert instance.workflow_id == "wf_low_001"
        assert instance.status in ("completed", "failed")

    @pytest.mark.asyncio
    async def test_execute_without_approval(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that unapproved workflows cannot execute."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        # Create a proposal but don't approve it
        proposal = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        proposal_id = proposal["proposal_id"]

        # Override to not approved
        engine.approval.get_proposal.return_value = {"status": "pending_approval"}

        with pytest.raises(ValueError, match="not approved"):
            await engine.execute(proposal_id, "op_1")

    @pytest.mark.asyncio
    async def test_execute_nonexistent_proposal(self, engine: WorkflowEngine) -> None:
        """Test executing a nonexistent proposal."""
        with pytest.raises(ValueError, match="not found"):
            await engine.execute("nonexistent_proposal", "op_1")

    @pytest.mark.asyncio
    async def test_risk_classification_low(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that low-risk workflows get correct classification."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        approval_framework.submit_for_approval.return_value = {
            "proposal_id": str(uuid4()),
            "risk_level": "low",
            "risk_description": "Read-only, no side effects",
            "required_approval": "self",
            "audit_record_id": str(uuid4()),
            "status": "pending_approval",
        }

        result = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        assert result["status"] == "proposed"
        assert result["risk_level"] == "low"

    @pytest.mark.asyncio
    async def test_risk_classification_critical(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_critical: WorkflowDefinition,
    ) -> None:
        """Test that critical-risk workflows get correct classification."""
        registry.register(sample_workflow_critical, "op_1")
        registry.activate("wf_crit_001", "op_1")

        approval_framework.submit_for_approval.return_value = {
            "proposal_id": str(uuid4()),
            "risk_level": "critical",
            "risk_description": "Destructive, schema changes",
            "required_approval": "operator_multi",
            "audit_record_id": str(uuid4()),
            "status": "pending_approval",
        }

        result = await engine.propose_execution(
            workflow_id="wf_crit_001",
            project_id="garvis",
            operator_id="op_1",
        )
        assert result["status"] == "proposed"
        assert result["risk_level"] == "critical"

    @pytest.mark.asyncio
    async def test_proposal_stores_parameters(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that runtime parameters are stored in proposal."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        params = {"custom_param": "custom_value"}
        result = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
            parameters=params,
        )
        assert result["status"] == "proposed"


# ---------------------------------------------------------------------------
# 5. Step Execution Tests
# ---------------------------------------------------------------------------


class TestStepExecution:
    """Test step execution with governance mediation."""

    @pytest.mark.asyncio
    async def test_execute_single_step_workflow(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test executing a single-step workflow."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")

        assert len(instance.steps_executed) >= 1
        first_step = instance.steps_executed[0]
        assert first_step.step_id == "check_status"

    @pytest.mark.asyncio
    async def test_execute_multi_step_workflow(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_medium_risk: WorkflowDefinition,
    ) -> None:
        """Test executing a multi-step workflow."""
        registry.register(sample_workflow_medium_risk, "op_1")
        registry.activate("wf_medium_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_medium_001",
            project_id="nova",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")

        assert len(instance.steps_executed) == 3
        step_ids = [r.step_id for r in instance.steps_executed]
        assert "fetch_data" in step_ids
        assert "process_data" in step_ids
        assert "log_results" in step_ids

    @pytest.mark.asyncio
    async def test_step_execution_order(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_medium_risk: WorkflowDefinition,
    ) -> None:
        """Test that steps execute in dependency order."""
        registry.register(sample_workflow_medium_risk, "op_1")
        registry.activate("wf_medium_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_medium_001",
            project_id="nova",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")

        step_ids = [r.step_id for r in instance.steps_executed]
        # fetch_data should execute before process_data
        if "fetch_data" in step_ids and "process_data" in step_ids:
            assert step_ids.index("fetch_data") < step_ids.index("process_data")

    @pytest.mark.asyncio
    async def test_step_governance_checks_recorded(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that governance checks are recorded for each step."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")

        for step_result in instance.steps_executed:
            if step_result.status == "completed":
                assert len(step_result.governance_checks) > 0

    @pytest.mark.asyncio
    async def test_execute_step_directly(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test executing a single step directly."""
        registry.register(sample_workflow_low_risk, "op_1")

        instance = WorkflowInstance(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
            status="executing",
            approval_id="prop_1",
            governance_context=["system_health"],
        )
        engine._instances[str(instance.instance_id)] = instance
        engine._proposals["prop_1"] = {
            "workflow_id": "wf_low_001",
            "status": "pending_approval",
        }

        step = sample_workflow_low_risk.steps[0]
        result = await engine.execute_step(instance, step)

        assert result.step_id == "check_status"
        assert result.status in ("completed", "failed")
        assert result.started_at is not None

    @pytest.mark.asyncio
    async def test_execute_step_instance_not_executing(
        self,
        engine: WorkflowEngine,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that steps fail when instance is not in executing status."""
        instance = WorkflowInstance(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
            status="pending",  # Not executing
            approval_id="prop_1",
        )
        step = sample_workflow_low_risk.steps[0]
        result = await engine.execute_step(instance, step)

        assert result.status == "failed"
        assert "not executing" in result.error.lower()

    @pytest.mark.asyncio
    async def test_execute_step_approval_revoked(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that step fails when approval is revoked."""
        approval_framework.get_proposal.return_value = {"status": "rejected"}

        instance = WorkflowInstance(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
            status="executing",
            approval_id="prop_1",
            governance_context=["system_health"],
        )
        engine._proposals["prop_1"] = {"workflow_id": "wf_low_001"}

        step = sample_workflow_low_risk.steps[0]
        result = await engine.execute_step(instance, step)

        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_action_ollama_inference(self, engine: WorkflowEngine) -> None:
        """Test the ollama_inference action handler."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="inf", name="Inference", description="Run inference",
            action_type="ollama_inference",
            parameters={"model": "llama3.1", "prompt": "Hello"},
        )
        result = await engine._action_ollama_inference(instance, step, step.parameters)
        assert result["action"] == "ollama_inference"
        assert result["model"] == "llama3.1"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_action_memory_store(self, engine: WorkflowEngine) -> None:
        """Test the memory_store action handler."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="mem", name="Memory Store", description="Store memory",
            action_type="memory_store",
            parameters={"content": "test data"},
        )
        result = await engine._action_memory_store(instance, step, step.parameters)
        assert result["action"] == "memory_store"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_action_memory_retrieve(self, engine: WorkflowEngine) -> None:
        """Test the memory_retrieve action handler."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="ret", name="Retrieve", description="Retrieve memory",
            action_type="memory_retrieve",
            parameters={"query": "test", "limit": 5},
        )
        result = await engine._action_memory_retrieve(instance, step, step.parameters)
        assert result["action"] == "memory_retrieve"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_action_governance_check(self, engine: WorkflowEngine) -> None:
        """Test the governance_check action handler."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="gov", name="Governance", description="Check governance",
            action_type="governance_check",
            parameters={"schema_id": "test_schema"},
        )
        result = await engine._action_governance_check(instance, step, step.parameters)
        assert result["action"] == "governance_check"
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_action_audit_log(self, engine: WorkflowEngine) -> None:
        """Test the audit_log action handler."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="log", name="Log", description="Write audit log",
            action_type="audit_log",
            parameters={"event_type": "test", "message": "Test message"},
        )
        result = await engine._action_audit_log(instance, step, step.parameters)
        assert result["action"] == "audit_log"
        assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_action_external_call(self, engine: WorkflowEngine) -> None:
        """Test the external_call action handler."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="ext", name="External", description="Call external API",
            action_type="external_call",
            parameters={"endpoint": "https://api.example.com/test", "method": "GET"},
        )
        result = await engine._action_external_call(instance, step, step.parameters)
        assert result["action"] == "external_call"
        assert result["status"] == "success"


# ---------------------------------------------------------------------------
# 6. Governance Mediation Tests
# ---------------------------------------------------------------------------


class TestGovernanceMediation:
    """Test that governance mediation works correctly."""

    @pytest.mark.asyncio
    async def test_governance_checks_run_per_step(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that governance checks run for each step."""
        registry.register(sample_workflow_low_risk, "op_1")

        instance = WorkflowInstance(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
            status="executing",
            approval_id="prop_1",
            governance_context=["system_health"],
        )
        engine._proposals["prop_1"] = {
            "workflow_id": "wf_low_001",
            "status": "pending_approval",
        }

        step = sample_workflow_low_risk.steps[0]
        result = await engine.execute_step(instance, step)

        assert len(result.governance_checks) > 0

    @pytest.mark.asyncio
    async def test_step_fails_when_governance_schema_not_active(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that step fails when required governance schema is not active."""
        registry.register(sample_workflow_low_risk, "op_1")

        instance = WorkflowInstance(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
            status="executing",
            approval_id="prop_1",
            governance_context=[],  # Empty — schema not active
        )
        engine._proposals["prop_1"] = {
            "workflow_id": "wf_low_001",
            "status": "pending_approval",
        }

        step = sample_workflow_low_risk.steps[0]
        result = await engine.execute_step(instance, step)

        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_result_validation_passes(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test that valid results pass governance validation."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="s1", name="Test", description="Test step",
            action_type="audit_log",
        )
        result = {"status": "success", "data": "test"}
        checks = await engine._validate_result(instance, step, result)
        assert all(c.passed for c in checks)

    @pytest.mark.asyncio
    async def test_result_validation_fails_no_status(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test that result without status fails validation."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step = WorkflowStep(
            step_id="s1", name="Test", description="Test step",
            action_type="audit_log",
        )
        result = {"data": "no status field"}
        checks = await engine._validate_result(instance, step, result)
        status_checks = [c for c in checks if "status" in c.policy_id]
        assert any(not c.passed for c in status_checks)

    @pytest.mark.asyncio
    async def test_run_governance_checks_approval_valid(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test governance checks with valid approval."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
            governance_context=["schema_1"],
        )
        engine._proposals["prop_1"] = {"workflow_id": "wf_test"}

        step = WorkflowStep(
            step_id="s1", name="Test", description="Test",
            action_type="audit_log", governance_checks=["schema_1"],
        )
        results = await engine._run_governance_checks(instance, step)
        approval_check = [r for r in results if r.policy_id == "approval_still_valid"]
        assert len(approval_check) > 0
        assert approval_check[0].passed is True

    @pytest.mark.asyncio
    async def test_run_governance_checks_missing_proposal(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test governance checks when proposal is missing."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="missing_prop",
            governance_context=["schema_1"],
        )
        # Don't add proposal to engine._proposals

        step = WorkflowStep(
            step_id="s1", name="Test", description="Test",
            action_type="audit_log",
        )
        results = await engine._run_governance_checks(instance, step)
        assert any(not r.passed for r in results)


# ---------------------------------------------------------------------------
# 7. Rollback Tests
# ---------------------------------------------------------------------------


class TestRollback:
    """Test workflow rollback functionality."""

    @pytest.mark.asyncio
    async def test_rollback_failed_workflow(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test rolling back a failed workflow."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")
        instance_id = str(instance.instance_id)

        # Force the instance to failed status
        instance.status = "failed"
        instance.steps_executed = [
            WorkflowStepResult(step_id="s1", status="completed", result={"data": "test"}),
        ]

        result = await engine.rollback(instance_id, "op_1")
        assert result is True

        updated = engine.get_instance(instance_id)
        assert updated is not None
        assert updated.status == "rolled_back"

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_instance(self, engine: WorkflowEngine) -> None:
        """Test rolling back a nonexistent instance."""
        result = await engine.rollback("nonexistent", "op_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_pending_instance(self, engine: WorkflowEngine) -> None:
        """Test that pending instances cannot be rolled back."""
        instance = WorkflowInstance(
            workflow_id="wf_1", project_id="test",
            operator_id="op_1", approval_id="prop_1",
            status="pending",
        )
        engine._instances[str(instance.instance_id)] = instance
        instance_id = str(instance.instance_id)

        result = await engine.rollback(instance_id, "op_1")
        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_records_audit(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        mock_audit_pipeline: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test that rollback is audited."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")
        instance_id = str(instance.instance_id)

        instance.status = "failed"
        instance.steps_executed = [
            WorkflowStepResult(step_id="s1", status="completed", result={"data": "test"}),
        ]

        mock_audit_pipeline.log_event.reset_mock()
        await engine.rollback(instance_id, "op_1")
        mock_audit_pipeline.log_event.assert_called()

    @pytest.mark.asyncio
    async def test_undo_step(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test undoing a single step."""
        instance = WorkflowInstance(
            workflow_id="wf_1", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        step_result = WorkflowStepResult(
            step_id="s1", status="completed",
            result={"data": "original"},
        )
        await engine._undo_step(instance, step_result)
        assert step_result.result.get("undone") is True
        assert "undone_at" in step_result.result


# ---------------------------------------------------------------------------
# 8. Instance Query Tests
# ---------------------------------------------------------------------------


class TestInstanceQueries:
    """Test workflow instance queries."""

    def test_get_instance(self, engine: WorkflowEngine) -> None:
        """Test retrieving a workflow instance."""
        instance = WorkflowInstance(
            workflow_id="wf_1", project_id="test",
            operator_id="op_1", approval_id="prop_1",
        )
        engine._instances[str(instance.instance_id)] = instance
        found = engine.get_instance(str(instance.instance_id))
        assert found is not None
        assert found.workflow_id == "wf_1"

    def test_get_instance_not_found(self, engine: WorkflowEngine) -> None:
        """Test retrieving a nonexistent instance."""
        assert engine.get_instance("nonexistent") is None

    def test_list_instances_all(self, engine: WorkflowEngine) -> None:
        """Test listing all instances."""
        for i in range(3):
            instance = WorkflowInstance(
                workflow_id=f"wf_{i}", project_id="test",
                operator_id="op_1", approval_id="prop_1",
            )
            engine._instances[str(instance.instance_id)] = instance
        instances = engine.list_instances()
        assert len(instances) == 3

    def test_list_instances_by_project(self, engine: WorkflowEngine) -> None:
        """Test filtering instances by project."""
        instance_a = WorkflowInstance(
            workflow_id="wf_a", project_id="project_a",
            operator_id="op_1", approval_id="prop_1",
        )
        instance_b = WorkflowInstance(
            workflow_id="wf_b", project_id="project_b",
            operator_id="op_1", approval_id="prop_1",
        )
        engine._instances[str(instance_a.instance_id)] = instance_a
        engine._instances[str(instance_b.instance_id)] = instance_b

        result = engine.list_instances(project_id="project_a")
        assert len(result) == 1
        assert result[0].project_id == "project_a"

    def test_list_instances_by_status(self, engine: WorkflowEngine) -> None:
        """Test filtering instances by status."""
        instance_active = WorkflowInstance(
            workflow_id="wf_1", project_id="test",
            operator_id="op_1", approval_id="prop_1",
            status="executing",
        )
        instance_pending = WorkflowInstance(
            workflow_id="wf_2", project_id="test",
            operator_id="op_1", approval_id="prop_1",
            status="pending",
        )
        engine._instances[str(instance_active.instance_id)] = instance_active
        engine._instances[str(instance_pending.instance_id)] = instance_pending

        result = engine.list_instances(status="executing")
        assert len(result) == 1
        assert result[0].status == "executing"

    def test_list_instances_combined_filter(self, engine: WorkflowEngine) -> None:
        """Test filtering instances by both project and status."""
        instance = WorkflowInstance(
            workflow_id="wf_1", project_id="ops",
            operator_id="op_1", approval_id="prop_1",
            status="completed",
        )
        engine._instances[str(instance.instance_id)] = instance

        result = engine.list_instances(project_id="ops", status="completed")
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 9. Integration / End-to-End Tests
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """End-to-end workflow tests."""

    @pytest.mark.asyncio
    async def test_full_workflow_lifecycle_low_risk(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test full lifecycle of a low-risk workflow."""
        # 1. Register
        registry.register(sample_workflow_low_risk, "op_1")

        # 2. Activate
        activated = registry.activate("wf_low_001", "op_1")
        assert activated is True

        # 3. Propose
        proposal = await engine.propose_execution(
            workflow_id="wf_low_001",
            project_id="ops",
            operator_id="op_1",
        )
        assert proposal["status"] == "proposed"

        # 4. Execute (approved)
        instance = await engine.execute(proposal["proposal_id"], "op_1")
        assert instance.workflow_id == "wf_low_001"

        # 5. Verify instance is tracked
        found = engine.get_instance(str(instance.instance_id))
        assert found is not None

    @pytest.mark.asyncio
    async def test_full_workflow_lifecycle_medium_risk(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_medium_risk: WorkflowDefinition,
    ) -> None:
        """Test full lifecycle of a medium-risk workflow."""
        registry.register(sample_workflow_medium_risk, "op_1")
        registry.activate("wf_medium_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_medium_001",
            project_id="nova",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")

        assert instance.workflow_id == "wf_medium_001"
        assert len(instance.steps_executed) == 3

    @pytest.mark.asyncio
    async def test_workflow_with_all_action_types(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
    ) -> None:
        """Test workflow with all supported action types."""
        wf = WorkflowDefinition(
            workflow_id="wf_all_actions",
            name="All Actions",
            description="Tests every action type",
            project_id="test",
            risk_level="medium",
            required_approval="operator",
            steps=[
                WorkflowStep(
                    step_id="inf", name="Inference", description="Run LLM",
                    action_type="ollama_inference",
                    parameters={"model": "llama3.1", "prompt": "Hello"},
                    governance_checks=["test_schema"],
                ),
                WorkflowStep(
                    step_id="mem_s", name="Memory Store", description="Store memory",
                    action_type="memory_store",
                    parameters={"content": "test"},
                    governance_checks=["test_schema"],
                ),
                WorkflowStep(
                    step_id="mem_r", name="Memory Retrieve", description="Get memory",
                    action_type="memory_retrieve",
                    parameters={"query": "test"},
                    governance_checks=["test_schema"],
                ),
                WorkflowStep(
                    step_id="gov", name="Governance", description="Check governance",
                    action_type="governance_check",
                    parameters={"schema_id": "test"},
                    governance_checks=["test_schema"],
                ),
                WorkflowStep(
                    step_id="log", name="Audit Log", description="Write log",
                    action_type="audit_log",
                    parameters={"event_type": "test", "message": "test"},
                    governance_checks=["test_schema"],
                ),
                WorkflowStep(
                    step_id="ext", name="External", description="External call",
                    action_type="external_call",
                    parameters={"endpoint": "/test", "method": "GET"},
                    governance_checks=["test_schema"],
                ),
            ],
            governance_schemas=["test_schema"],
            created_by="op_1",
        )
        registry.register(wf, "op_1")
        registry.activate("wf_all_actions", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_all_actions",
            project_id="test",
            operator_id="op_1",
        )
        instance = await engine.execute(proposal["proposal_id"], "op_1")

        assert instance.workflow_id == "wf_all_actions"
        assert len(instance.steps_executed) == 6

    @pytest.mark.asyncio
    async def test_multiple_workflow_instances(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test running multiple instances of the same workflow."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        instances = []
        for i in range(3):
            proposal = await engine.propose_execution(
                workflow_id="wf_low_001",
                project_id="ops",
                operator_id="op_1",
                parameters={"run_id": i},
            )
            instance = await engine.execute(proposal["proposal_id"], "op_1")
            instances.append(instance)

        assert len(instances) == 3
        all_instances = engine.list_instances()
        assert len(all_instances) == 3


# ---------------------------------------------------------------------------
# 10. Edge Case and Boundary Tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_registry_list(self, registry: WorkflowRegistry) -> None:
        """Test listing an empty registry."""
        workflows = registry.list(active_only=False)
        assert workflows == []

    def test_registry_count_empty(self, registry: WorkflowRegistry) -> None:
        """Test count on empty registry."""
        assert registry.count() == 0

    @pytest.mark.asyncio
    async def test_propose_workflow_not_in_registry(self, engine: WorkflowEngine) -> None:
        """Test proposing a workflow that was never registered."""
        result = await engine.propose_execution(
            workflow_id="never_registered",
            project_id="ops",
            operator_id="op_1",
        )
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_execute_with_revoked_proposal_mid_execution(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_medium_risk: WorkflowDefinition,
    ) -> None:
        """Test that revoked proposal blocks workflow execution entirely."""
        registry.register(sample_workflow_medium_risk, "op_1")
        registry.activate("wf_medium_001", "op_1")

        proposal = await engine.propose_execution(
            workflow_id="wf_medium_001",
            project_id="nova",
            operator_id="op_1",
        )
        proposal_id = proposal["proposal_id"]

        # Revoke approval BEFORE execution
        approval_framework.get_proposal.return_value = {"status": "pending_approval"}

        # Execution should be blocked
        with pytest.raises(ValueError, match="not approved"):
            await engine.execute(proposal_id, "op_1")

    @pytest.mark.asyncio
    async def test_step_with_empty_parameters(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test executing a step with empty parameters."""
        instance = WorkflowInstance(
            workflow_id="wf_test", project_id="test",
            operator_id="op_1", approval_id="prop_1",
            status="executing",
        )
        engine._proposals["prop_1"] = {"workflow_id": "wf_test"}

        step = WorkflowStep(
            step_id="empty_params", name="Empty", description="No params",
            action_type="audit_log", parameters={},
            governance_checks=[],
        )
        result = await engine.execute_step(instance, step)
        # Should either complete or fail gracefully
        assert result.status in ("completed", "failed")

    @pytest.mark.asyncio
    async def test_step_with_long_timeout(
        self,
        engine: WorkflowEngine,
    ) -> None:
        """Test that timeout parameter is accepted."""
        step = WorkflowStep(
            step_id="timeout_step", name="Timeout", description="Long timeout",
            action_type="audit_log", timeout_seconds=300,
        )
        assert step.timeout_seconds == 300

    @pytest.mark.asyncio
    async def test_workflow_with_no_governance_schemas(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
    ) -> None:
        """Test workflow with no governance schemas."""
        wf = WorkflowDefinition(
            workflow_id="wf_no_gov",
            name="No Governance",
            description="No governance schemas",
            project_id="test",
            risk_level="low",
            required_approval="self",
            steps=[
                WorkflowStep(
                    step_id="s1", name="Step 1", description="Simple step",
                    action_type="audit_log", governance_checks=[],
                ),
            ],
            governance_schemas=[],
            created_by="op_1",
        )
        registry.register(wf, "op_1")

    def test_workflow_registry_persists_workflows(self, registry: WorkflowRegistry, sample_workflow_low_risk: WorkflowDefinition) -> None:
        """Test that workflows persist in the registry."""
        registry.register(sample_workflow_low_risk, "op_1")
        wf1 = registry.get("wf_low_001")
        wf2 = registry.get("wf_low_001")
        assert wf1 is not None
        assert wf2 is not None
        assert wf1.workflow_id == wf2.workflow_id

    @pytest.mark.asyncio
    async def test_audit_trail_accumulates(
        self,
        workflow_audit: WorkflowAudit,
    ) -> None:
        """Test that audit trail accumulates multiple events."""
        await workflow_audit.log_step_start("inst_1", "step_1")
        await workflow_audit.log_step_start("inst_1", "step_2")
        await workflow_audit.log_step_start("inst_1", "step_3")
        await workflow_audit.log_rollback("inst_1", "op_1")

        trail = await workflow_audit.get_workflow_audit_trail("inst_1")
        assert len(trail) == 4

    @pytest.mark.asyncio
    async def test_statistics_after_executions(
        self,
        engine: WorkflowEngine,
        registry: WorkflowRegistry,
        approval_framework: MagicMock,
        sample_workflow_low_risk: WorkflowDefinition,
    ) -> None:
        """Test statistics reflect actual executions."""
        registry.register(sample_workflow_low_risk, "op_1")
        registry.activate("wf_low_001", "op_1")

        for _ in range(2):
            proposal = await engine.propose_execution(
                workflow_id="wf_low_001",
                project_id="ops",
                operator_id="op_1",
            )
            await engine.execute(proposal["proposal_id"], "op_1")

        # Engine's internal audit should have recorded events
        assert len(engine.workflow_audit._workflow_events) > 0


# ---------------------------------------------------------------------------
# 11. Import Tests
# ---------------------------------------------------------------------------


class TestImports:
    """Test that all public interfaces are importable."""

    def test_import_workflow_engine(self) -> None:
        """Test importing WorkflowEngine."""
        from workflows import WorkflowEngine
        assert WorkflowEngine is not None

    def test_import_workflow_audit(self) -> None:
        """Test importing WorkflowAudit."""
        from workflows import WorkflowAudit
        assert WorkflowAudit is not None

    def test_import_workflow_registry(self) -> None:
        """Test importing WorkflowRegistry."""
        from workflows import WorkflowRegistry
        assert WorkflowRegistry is not None

    def test_import_workflow_instance(self) -> None:
        """Test importing WorkflowInstance."""
        from workflows import WorkflowInstance
        assert WorkflowInstance is not None

    def test_import_workflow_step(self) -> None:
        """Test importing WorkflowStep."""
        from workflows import WorkflowStep
        assert WorkflowStep is not None

    def test_import_workflow_definition(self) -> None:
        """Test importing WorkflowDefinition."""
        from workflows import WorkflowDefinition
        assert WorkflowDefinition is not None

    def test_import_workflow_step_result(self) -> None:
        """Test importing WorkflowStepResult."""
        from workflows import WorkflowStepResult
        assert WorkflowStepResult is not None

    def test_import_all_from_module(self) -> None:
        """Test that __all__ exports are accessible."""
        from workflows import (
            WorkflowAudit,
            WorkflowDefinition,
            WorkflowEngine,
            WorkflowInstance,
            WorkflowRegistry,
            WorkflowStep,
            WorkflowStepResult,
        )
        assert all(v is not None for v in [
            WorkflowEngine, WorkflowAudit, WorkflowRegistry,
            WorkflowInstance, WorkflowStep,
            WorkflowDefinition, WorkflowStepResult,
        ])

    def test_workflow_engine_has_required_methods(self, engine: WorkflowEngine) -> None:
        """Test that WorkflowEngine has all required methods."""
        assert hasattr(engine, "propose_execution")
        assert hasattr(engine, "execute")
        assert hasattr(engine, "execute_step")
        assert hasattr(engine, "rollback")
        assert hasattr(engine, "get_instance")
        assert hasattr(engine, "list_instances")

    def test_workflow_registry_has_required_methods(self, registry: WorkflowRegistry) -> None:
        """Test that WorkflowRegistry has all required methods."""
        assert hasattr(registry, "register")
        assert hasattr(registry, "activate")
        assert hasattr(registry, "deactivate")
        assert hasattr(registry, "get")
        assert hasattr(registry, "list")
        assert hasattr(registry, "validate")

    def test_workflow_audit_has_required_methods(self, workflow_audit: WorkflowAudit) -> None:
        """Test that WorkflowAudit has all required methods."""
        assert hasattr(workflow_audit, "log_proposal")
        assert hasattr(workflow_audit, "log_approval")
        assert hasattr(workflow_audit, "log_step_start")
        assert hasattr(workflow_audit, "log_step_complete")
        assert hasattr(workflow_audit, "log_step_failure")
        assert hasattr(workflow_audit, "log_rollback")
        assert hasattr(workflow_audit, "log_workflow_complete")
        assert hasattr(workflow_audit, "get_workflow_audit_trail")
        assert hasattr(workflow_audit, "get_workflow_statistics")
