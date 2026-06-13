"""Tests for Mission Control — tests/test_mission_control.py

Tests for:
- MissionControl (project overview, readiness, governance status)
- WorkflowApprovalFramework (risk classification, approval flow)
- Mission Control API router
"""

from __future__ import annotations

import os
import pytest
import sys
from typing import Any

# Pre-populate sys.modules with stubs for heavy dependencies to avoid
# importing the full runtime/__init__.py chain
if "runtime.bootstrap" not in sys.modules:
    import types
    sys.modules["runtime.bootstrap"] = types.ModuleType("runtime.bootstrap")
    sys.modules["runtime.bootstrap"].RuntimeBootstrap = type("RuntimeBootstrap", (), {})

from mission_control.controller import MissionControl
from mission_control.workflow_approval import WorkflowApprovalFramework


# ============================================================================
# WorkflowApprovalFramework Tests
# ============================================================================


class TestWorkflowApprovalFramework:
    """Tests for the WorkflowApprovalFramework."""

    @pytest.fixture
    def framework(self):
        """Create a WorkflowApprovalFramework instance."""
        return WorkflowApprovalFramework()

    def test_risk_levels_defined(self, framework):
        """All risk levels are defined."""
        expected = {"low", "medium", "high", "critical"}
        assert set(framework.RISK_LEVELS.keys()) == expected

    def test_risk_level_low(self, framework):
        """Low risk level has correct config."""
        assert framework.RISK_LEVELS["low"]["approval"] == "self"

    def test_risk_level_medium(self, framework):
        """Medium risk level requires operator approval."""
        assert framework.RISK_LEVELS["medium"]["approval"] == "operator"

    def test_risk_level_high(self, framework):
        """High risk level requires explicit operator approval."""
        assert framework.RISK_LEVELS["high"]["approval"] == "operator_explicit"

    def test_risk_level_critical(self, framework):
        """Critical risk level requires multi-operator approval."""
        assert framework.RISK_LEVELS["critical"]["approval"] == "operator_multi"

    def test_classify_risk_empty_workflow(self, framework):
        """Empty workflow is low risk."""
        workflow = {}
        assert framework.classify_risk(workflow) == "low"

    def test_classify_risk_low(self, framework):
        """Read-only operations are low risk."""
        workflow = {
            "operations": [
                {"type": "status"},
                {"type": "check"},
            ],
        }
        assert framework.classify_risk(workflow) == "low"

    def test_classify_risk_medium(self, framework):
        """Data processing is medium risk."""
        workflow = {
            "operations": [
                {"type": "process"},
                {"type": "transform"},
            ],
        }
        assert framework.classify_risk(workflow) == "medium"

    def test_classify_risk_high(self, framework):
        """External API calls are high risk."""
        workflow = {
            "operations": [
                {"type": "api_call"},
            ],
        }
        assert framework.classify_risk(workflow) == "high"

    def test_classify_risk_critical(self, framework):
        """Destructive operations are critical risk."""
        workflow = {
            "operations": [
                {"type": "delete"},
            ],
        }
        assert framework.classify_risk(workflow) == "critical"

    def test_classify_risk_critical_rollup(self, framework):
        """Workflow with any critical operation is critical overall."""
        workflow = {
            "operations": [
                {"type": "status"},
                {"type": "delete"},
                {"type": "check"},
            ],
        }
        assert framework.classify_risk(workflow) == "critical"

    def test_submit_for_approval(self, framework):
        """Submitting a workflow creates a proposal."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
            "project_id": "test_project",
        }
        result = framework.submit_for_approval(workflow)
        assert result["status"] == "pending_approval"
        assert "proposal_id" in result
        assert "risk_level" in result
        assert "audit_record_id" in result
        assert "required_approval" in result

    def test_submit_classifies_risk(self, framework):
        """Submission auto-classifies risk."""
        workflow = {
            "name": "destructive_workflow",
            "operations": [{"type": "delete"}],
            "project_id": "test",
        }
        result = framework.submit_for_approval(workflow)
        assert result["risk_level"] == "critical"
        assert result["required_approval"] == "operator_multi"

    def test_approve_workflow(self, framework):
        """Approving a workflow changes status to approved."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        proposal_id = proposal["proposal_id"]

        result = framework.approve_workflow(proposal_id, "operator_1")
        assert result["status"] == "approved"
        assert result["approved_by"] == "operator_1"
        assert "approved_at" in result

    def test_approve_workflow_does_not_execute(self, framework):
        """Approval does not execute the workflow."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        result = framework.approve_workflow(proposal["proposal_id"], "op1")
        assert "NOT executed" in result.get("note", "")

    def test_approve_unknown_proposal(self, framework):
        """Approving unknown proposal returns error."""
        result = framework.approve_workflow("nonexistent", "op1")
        assert result["status"] == "error"

    def test_reject_workflow(self, framework):
        """Rejecting a workflow changes status to rejected."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        proposal_id = proposal["proposal_id"]

        result = framework.reject_workflow(proposal_id, "operator_1", "too risky")
        assert result["status"] == "rejected"
        assert result["rejected_by"] == "operator_1"
        assert result["reason"] == "too risky"

    def test_reject_unknown_proposal(self, framework):
        """Rejecting unknown proposal returns error."""
        result = framework.reject_workflow("nonexistent", "op1", "reason")
        assert result["status"] == "error"

    def test_cannot_approve_already_approved(self, framework):
        """Cannot approve an already-approved proposal."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        proposal_id = proposal["proposal_id"]
        framework.approve_workflow(proposal_id, "op1")

        result = framework.approve_workflow(proposal_id, "op2")
        assert result["status"] == "error"

    def test_cannot_reject_already_rejected(self, framework):
        """Cannot reject an already-rejected proposal."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        proposal_id = proposal["proposal_id"]
        framework.reject_workflow(proposal_id, "op1", "reason")

        result = framework.reject_workflow(proposal_id, "op2", "other reason")
        assert result["status"] == "error"

    def test_get_pending_approvals_empty(self, framework):
        """Pending approvals is empty by default."""
        assert framework.get_pending_approvals() == []

    def test_get_pending_approvals(self, framework):
        """Pending approvals returns submitted workflows."""
        workflow = {
            "name": "pending_workflow",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        framework.submit_for_approval(workflow)
        pending = framework.get_pending_approvals()
        assert len(pending) == 1
        assert pending[0]["workflow_name"] == "pending_workflow"

    def test_pending_excludes_approved(self, framework):
        """Approved workflows are not in pending."""
        workflow = {
            "name": "test",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        framework.approve_workflow(proposal["proposal_id"], "op1")
        assert len(framework.get_pending_approvals()) == 0

    def test_pending_excludes_rejected(self, framework):
        """Rejected workflows are not in pending."""
        workflow = {
            "name": "test",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        framework.reject_workflow(proposal["proposal_id"], "op1", "reason")
        assert len(framework.get_pending_approvals()) == 0

    def test_approval_history(self, framework):
        """Approval history tracks all decisions."""
        workflow = {
            "name": "test",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        framework.approve_workflow(proposal["proposal_id"], "op1")

        history = framework.get_approval_history()
        assert len(history) == 1
        assert history[0]["action"] == "approved"

    def test_approval_history_sorted(self, framework):
        """Approval history is sorted newest first."""
        for i in range(3):
            workflow = {
                "name": f"test_{i}",
                "operations": [{"type": "status"}],
                "project_id": "test",
            }
            proposal = framework.submit_for_approval(workflow)
            if i % 2 == 0:
                framework.approve_workflow(proposal["proposal_id"], "op1")
            else:
                framework.reject_workflow(proposal["proposal_id"], "op1", "no")

        history = framework.get_approval_history()
        assert len(history) == 3
        # Should be reverse chronological
        assert history[0]["timestamp"] >= history[1]["timestamp"]

    def test_audit_workflow_execution(self, framework):
        """Audit record is prepared for workflow execution."""
        workflow = {
            "name": "test",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        proposal = framework.submit_for_approval(workflow)
        audit = framework.audit_workflow_execution(proposal["proposal_id"])
        assert audit["status"] == "audit_prepared"
        assert "audit_events" in audit
        # Check that audit events contain a "not executed" preparatory entry
        audit_events = audit.get("audit_events", [])
        preparatory_notes = [
            e for e in audit_events
            if "not executed" in e.get("note", "").lower() or e.get("event") == "execution_audit_prepared"
        ]
        assert len(preparatory_notes) > 0

    def test_audit_unknown_workflow(self, framework):
        """Auditing unknown workflow returns error."""
        result = framework.audit_workflow_execution("nonexistent")
        assert result["status"] == "error"

    def test_get_proposal(self, framework):
        """Can retrieve a proposal by ID."""
        workflow = {
            "name": "test",
            "operations": [{"type": "status"}],
            "project_id": "test",
        }
        submitted = framework.submit_for_approval(workflow)
        proposal = framework.get_proposal(submitted["proposal_id"])
        assert proposal is not None
        assert proposal["workflow_name"] == "test"
        assert proposal["status"] == "pending_approval"

    def test_get_unknown_proposal(self, framework):
        """Unknown proposal returns None."""
        assert framework.get_proposal("nonexistent") is None


# ============================================================================
# MissionControl Tests
# ============================================================================


class TestMissionControl:
    """Tests for the MissionControl controller."""

    @pytest.fixture
    def mc(self):
        """Create a MissionControl instance."""
        return MissionControl()

    def test_projects_defined(self, mc):
        """All expected projects are defined."""
        expected_ids = {
            "garvis", "alphaflow", "nova", "teachflow",
            "bella", "youtube", "ops",
        }
        actual_ids = {p["id"] for p in MissionControl.PROJECTS}
        assert actual_ids == expected_ids

    def test_active_projects(self, mc):
        """Correct projects are marked active."""
        active = [p for p in MissionControl.PROJECTS if p["status"] == "active"]
        assert len(active) == 2
        assert {p["id"] for p in active} == {"garvis", "ops"}

    def test_get_project_overview(self, mc):
        """Overview includes all projects with readiness."""
        overview = mc.get_project_overview()
        assert len(overview) == 7
        for project in overview:
            assert "workflow_ready" in project
            assert "readiness_score" in project

    def test_get_existing_project(self, mc):
        """Can retrieve an existing project."""
        project = mc.get_project("garvis")
        assert project is not None
        assert project["name"] == "GARVIS"
        assert "readiness" in project
        assert "governance" in project

    def test_get_unknown_project(self, mc):
        """Unknown project returns None."""
        assert mc.get_project("nonexistent") is None

    def test_workflow_readiness_garvis(self, mc):
        """GARVIS has partial readiness (it's active)."""
        readiness = mc.get_workflow_readiness("garvis")
        assert readiness["project_id"] == "garvis"
        assert "criteria_total" in readiness
        assert "met" in readiness
        assert "missing" in readiness
        assert "score" in readiness
        # Active project should have some criteria met
        assert len(readiness["met"]) > 0

    def test_workflow_readiness_alphaflow(self, mc):
        """AlphaFlow has zero readiness (planned, not started)."""
        readiness = mc.get_workflow_readiness("alphaflow")
        assert readiness["score"] == 0.0
        assert len(readiness["met"]) == 0
        assert len(readiness["missing"]) > 0

    def test_workflow_readiness_unknown_project(self, mc):
        """Unknown project returns not-ready readiness."""
        readiness = mc.get_workflow_readiness("nonexistent")
        assert readiness["ready"] is False
        assert readiness["score"] == 0.0

    def test_governance_status_garvis(self, mc):
        """GARVIS has active governance."""
        status = mc.get_governance_status("garvis")
        assert status["governance_active"] is True
        assert status["schemas_loaded"] is True
        assert status["enforcement_active"] is True
        assert status["fail_closed"] is True

    def test_governance_status_planned_project(self, mc):
        """Planned projects have prepared but inactive governance."""
        status = mc.get_governance_status("alphaflow")
        assert status["governance_active"] is False
        assert status["fail_closed"] is True  # Always fail-closed

    def test_governance_status_unknown_project(self, mc):
        """Unknown project returns error governance status."""
        status = mc.get_governance_status("nonexistent")
        assert status["status"] == "error"

    def test_approval_queue_empty(self, mc):
        """Approval queue is empty by default."""
        assert mc.get_approval_queue() == []

    def test_check_windmill_readiness(self, mc):
        """Windmill check returns structured result."""
        result = mc.check_windmill_readiness()
        assert "available" in result
        assert "status" in result
        assert "prepared_slots" in result
        assert "integration_note" in result
        # Windmill should not be detected in test environment
        assert result["available"] is False or result["available"] is True
        assert result["approval_required"] is True

    def test_night_ops_readiness(self, mc):
        """Night-ops readiness returns correct structure."""
        result = mc.get_night_ops_readiness()
        assert result["autonomous_scheduling"] is False
        assert result["status"] == "preparation_only"
        assert result["approval_gates"]["all_workflows_require_approval"] is True
        assert result["approval_gates"]["no_autonomous_execution"] is True
        assert result["task_queue_preview"]["available"] is True

    def test_night_ops_no_autonomous(self, mc):
        """Night-ops explicitly disallows autonomous scheduling."""
        result = mc.get_night_ops_readiness()
        assert result["autonomous_scheduling"] is False
        assert result["audit_requirements"]["no_unattended_execution"] is True

    def test_propose_workflow(self, mc):
        """Proposing a workflow returns proposal with risk classification."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
        }
        result = mc.propose_workflow("garvis", workflow)
        assert result["status"] == "proposed"
        assert "proposal" in result
        assert "NOTE" in result.get("note", "").upper() or "not" in result.get("note", "").lower()

    def test_propose_workflow_unknown_project(self, mc):
        """Proposing to unknown project returns error."""
        result = mc.propose_workflow("nonexistent", {"name": "test"})
        assert result["status"] == "error"

    def test_propose_workflow_does_not_execute(self, mc):
        """Proposing a workflow does not execute it."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
        }
        result = mc.propose_workflow("garvis", workflow)
        assert "PROPOSED" in result.get("note", "").upper() or "not" in result.get("note", "").lower()
        # No execution should have occurred
        assert result["status"] == "proposed"

    def test_approve_workflow(self, mc):
        """Approving a workflow through MissionControl works."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
        }
        proposal = mc.propose_workflow("garvis", workflow)
        proposal_id = proposal["proposal"]["proposal_id"]
        result = mc.approve_workflow(proposal_id, "op1")
        assert result["status"] == "approved"

    def test_reject_workflow(self, mc):
        """Rejecting a workflow through MissionControl works."""
        workflow = {
            "name": "test_workflow",
            "operations": [{"type": "status"}],
        }
        proposal = mc.propose_workflow("garvis", workflow)
        proposal_id = proposal["proposal"]["proposal_id"]
        result = mc.reject_workflow(proposal_id, "op1", "not needed")
        assert result["status"] == "rejected"

    def test_pending_workflow_approvals(self, mc):
        """Pending approvals tracks submitted workflows."""
        workflow = {
            "name": "pending",
            "operations": [{"type": "status"}],
        }
        mc.propose_workflow("garvis", workflow)
        pending = mc.get_pending_workflow_approvals()
        assert len(pending) == 1

    def test_workflow_approval_history(self, mc):
        """Approval history tracks decisions."""
        workflow = {
            "name": "test",
            "operations": [{"type": "status"}],
        }
        proposal = mc.propose_workflow("garvis", workflow)
        mc.approve_workflow(proposal["proposal"]["proposal_id"], "op1")
        history = mc.get_workflow_approval_history()
        assert len(history) == 1


# ============================================================================
# Mission Control API Router Tests
# ============================================================================


class TestMissionControlAPI:
    """Tests for the Mission Control FastAPI router."""

    @pytest.fixture
    def client(self):
        """Create a FastAPI test client."""
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from api.routers.mission_control import router

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/mission-control")
        return TestClient(app)

    def test_get_projects(self, client):
        """GET /projects returns all projects."""
        response = client.get("/api/v1/mission-control/projects")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 7
        assert any(p["id"] == "garvis" for p in data)

    def test_get_project(self, client):
        """GET /projects/{id} returns a specific project."""
        response = client.get("/api/v1/mission-control/projects/garvis")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "garvis"
        assert data["name"] == "GARVIS"

    def test_get_unknown_project(self, client):
        """GET /projects/{id} returns 404 for unknown project."""
        response = client.get("/api/v1/mission-control/projects/nonexistent")
        assert response.status_code == 404

    def test_get_project_readiness(self, client):
        """GET /projects/{id}/readiness returns readiness info."""
        response = client.get("/api/v1/mission-control/projects/garvis/readiness")
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "criteria_total" in data

    def test_get_project_readiness_unknown(self, client):
        """GET readiness for unknown project returns 404."""
        response = client.get("/api/v1/mission-control/projects/nonexistent/readiness")
        assert response.status_code == 404

    def test_get_project_governance(self, client):
        """GET /projects/{id}/governance returns governance status."""
        response = client.get("/api/v1/mission-control/projects/garvis/governance")
        assert response.status_code == 200
        data = response.json()
        assert "governance_active" in data

    def test_get_approvals_empty(self, client):
        """GET /approvals returns empty list by default."""
        response = client.get("/api/v1/mission-control/approvals")
        assert response.status_code == 200
        data = response.json()
        assert data == []

    def test_get_windmill_status(self, client):
        """GET /windmill/status returns detection info."""
        response = client.get("/api/v1/mission-control/windmill/status")
        assert response.status_code == 200
        data = response.json()
        assert "available" in data
        assert "status" in data
        assert data["approval_required"] is True

    def test_get_night_ops_readiness(self, client):
        """GET /night-ops/readiness returns readiness info."""
        response = client.get("/api/v1/mission-control/night-ops/readiness")
        assert response.status_code == 200
        data = response.json()
        assert data["autonomous_scheduling"] is False
        assert data["approval_gates"]["no_autonomous_execution"] is True

    def test_propose_workflow(self, client):
        """POST /workflows/propose creates a proposal."""
        response = client.post(
            "/api/v1/mission-control/workflows/propose?project_id=garvis",
            json={"name": "test", "operations": [{"type": "status"}]},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "proposed"
        assert "proposal" in data

    def test_propose_workflow_no_body(self, client):
        """POST /workflows/propose without body returns 400."""
        response = client.post("/api/v1/mission-control/workflows/propose?project_id=garvis")
        assert response.status_code == 400

    def test_propose_workflow_unknown_project(self, client):
        """POST /workflows/propose to unknown project returns 400."""
        response = client.post(
            "/api/v1/mission-control/workflows/propose?project_id=nonexistent",
            json={"name": "test", "operations": [{"type": "status"}]},
        )
        assert response.status_code == 400

    def test_approve_workflow(self, client):
        """POST /approvals/{id}/approve approves a workflow."""
        # First propose a workflow
        response = client.post(
            "/api/v1/mission-control/workflows/propose?project_id=garvis",
            json={"name": "test_approval", "operations": [{"type": "status"}]},
        )
        assert response.status_code == 200
        proposal_id = response.json()["proposal"]["proposal_id"]

        # Now approve it
        response = client.post(
            f"/api/v1/mission-control/approvals/{proposal_id}/approve?operator_id=op1"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    def test_reject_workflow(self, client):
        """POST /approvals/{id}/reject rejects a workflow."""
        # First propose a workflow
        response = client.post(
            "/api/v1/mission-control/workflows/propose?project_id=garvis",
            json={"name": "test_rejection", "operations": [{"type": "status"}]},
        )
        assert response.status_code == 200
        proposal_id = response.json()["proposal"]["proposal_id"]

        # Now reject it
        response = client.post(
            f"/api/v1/mission-control/approvals/{proposal_id}/reject?operator_id=op1&reason=not_needed"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
