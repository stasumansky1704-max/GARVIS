"""Operational Reasoning — projects/reasoning.py

Bounded operational reasoning for projects. All reasoning is:
- Observable: every step is recorded
- Traceable: full audit trail of reasoning
- Bounded: constrained to project scope
- Governance-aware: respects project governance constraints
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from projects.context import ProjectContext

logger = logging.getLogger("garvis.projects.reasoning")


# ---------------------------------------------------------------------------
# WorkflowDefinition — lightweight workflow descriptor for reasoning
# ---------------------------------------------------------------------------


class WorkflowDefinition:
    """Lightweight workflow descriptor for reasoning analysis.

    Not a full workflow executor — this is for analysis only.
    """

    def __init__(
        self,
        workflow_id: str,
        name: str,
        operations: list[dict[str, Any]],
        description: str = "",
        risk_level: str = "low",
    ) -> None:
        self.workflow_id = workflow_id
        self.name = name
        self.operations = operations
        self.description = description
        self.risk_level = risk_level

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict representation."""
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "operations_count": len(self.operations),
            "risk_level": self.risk_level,
            "operations": self.operations,
        }


# ---------------------------------------------------------------------------
# OperationalReasoningEngine — bounded reasoning for projects
# ---------------------------------------------------------------------------


class OperationalReasoningEngine:
    """Bounded operational reasoning for projects.

    Provides:
    - Workflow reasoning (analyze workflow proposals)
    - Risk-aware planning (assess risks of proposed actions)
    - Governance-aware prioritization (rank actions by governance compliance)
    - Bounded operational cognition (constrained reasoning)

    All reasoning is observable and traceable.
    """

    # Risk scoring weights
    RISK_WEIGHTS: dict[str, float] = {
        "low": 0.25,
        "medium": 0.5,
        "high": 0.75,
        "critical": 1.0,
    }

    # Operation type risk multipliers
    OP_RISK_MULTIPLIERS: dict[str, float] = {
        "read": 0.1,
        "query": 0.1,
        "analyze": 0.2,
        "transform": 0.4,
        "process": 0.4,
        "backup": 0.3,
        "write": 0.6,
        "modify": 0.7,
        "delete": 0.9,
        "api_call": 0.7,
        "external_request": 0.8,
        "execute": 0.8,
        "deploy": 0.9,
        "schema_change": 1.0,
        "disable_guardrail": 1.0,
    }

    def __init__(self) -> None:
        self._reasoning_log: list[dict[str, Any]] = []

    # ── Workflow Reasoning ────────────────────────────────────────

    def reason_about_workflow(
        self, workflow: WorkflowDefinition, project_context: ProjectContext
    ) -> dict[str, Any]:
        """Analyze a workflow within project context.

        Returns reasoning with governance implications. This is analysis
        only — it does NOT execute the workflow.

        Args:
            workflow: The workflow to analyze.
            project_context: The project context to analyze within.

        Returns:
            Dict with reasoning results and governance implications.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Analyze each operation
        operation_analyses: list[dict[str, Any]] = []
        total_risk_score = 0.0
        governance_implications: list[str] = []

        for op in workflow.operations:
            op_type = op.get("type", "unknown")
            op_risk = self._assess_operation_risk(op, project_context)
            total_risk_score += op_risk["score"]

            # Check governance implications
            if op_risk["score"] >= 0.75:
                governance_implications.append(
                    f"High-risk operation '{op_type}' requires explicit approval"
                )

            operation_analyses.append({
                "operation_type": op_type,
                "risk_score": op_risk["score"],
                "risk_factors": op_risk["factors"],
                "governance_compliant": op_risk["score"] < 0.8,
            })

        # Calculate overall risk
        avg_risk = (
            total_risk_score / len(workflow.operations)
            if workflow.operations else 0.0
        )
        overall_risk_level = self._score_to_level(min(avg_risk, 1.0))

        # Check against project governance
        governance = project_context.governance
        if governance is not None:
            validation_results = governance.validate_operation(
                operation=f"workflow:{workflow.workflow_id}",
                context={
                    "workflow_name": workflow.name,
                    "operations": [op.get("type") for op in workflow.operations],
                    "risk_level": overall_risk_level,
                },
            )
            governance_passed = all(r.passed for r in validation_results)
        else:
            governance_passed = True
            validation_results = []

        # Build reasoning result
        reasoning = {
            "timestamp": timestamp,
            "project_id": project_context.project_id,
            "workflow_id": workflow.workflow_id,
            "workflow_name": workflow.name,
            "analysis_type": "workflow_reasoning",
            "overall_risk_score": round(min(avg_risk, 1.0), 2),
            "overall_risk_level": overall_risk_level,
            "operation_count": len(workflow.operations),
            "operation_analyses": operation_analyses,
            "governance_implications": governance_implications,
            "governance_passed": governance_passed,
            "governance_checks": [
                {
                    "schema_id": r.schema_id,
                    "policy_id": r.policy_id,
                    "passed": r.passed,
                }
                for r in validation_results
            ],
            "recommendation": self._generate_workflow_recommendation(
                avg_risk, governance_passed, len(workflow.operations)
            ),
            "bounded": True,
            "trace_id": f"reasoning_{timestamp}",
        }

        # Record in reasoning log
        self._reasoning_log.append(reasoning)

        logger.info(
            "Workflow reasoning: workflow=%s, project=%s, risk=%s, governance_passed=%s",
            workflow.name,
            project_context.project_id,
            overall_risk_level,
            governance_passed,
        )

        return reasoning

    # ── Risk Assessment ───────────────────────────────────────────

    def assess_risk(
        self, action: str, project_context: ProjectContext
    ) -> dict[str, Any]:
        """Assess risk of a proposed action.

        Returns risk score, factors, mitigation suggestions.

        Args:
            action: The action to assess (e.g., 'deploy', 'api_call', 'delete').
            project_context: The project context.

        Returns:
            Dict with risk assessment.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Base risk from action type
        base_risk = self.OP_RISK_MULTIPLIERS.get(action, 0.5)

        # Project status modifier
        project_status = project_context.status
        status_modifier = (
            0.2 if project_status == "active"
            else 0.1 if project_status == "planned"
            else 0.3
        )

        # Category modifier
        category_modifier = (
            0.1 if project_context.category == "operations"
            else 0.0
        )

        # Calculate final risk score
        risk_score = min(base_risk + status_modifier + category_modifier, 1.0)
        risk_level = self._score_to_level(risk_score)

        # Identify risk factors
        risk_factors: list[str] = []
        if base_risk >= 0.7:
            risk_factors.append(f"Action type '{action}' is inherently high-risk")
        if project_status != "active":
            risk_factors.append(f"Project status '{project_status}' adds uncertainty")
        if risk_score >= 0.75:
            risk_factors.append("Risk score exceeds threshold for automatic approval")

        # Generate mitigations
        mitigations: list[str] = []
        if risk_score >= 0.5:
            mitigations.append("Requires operator approval before execution")
        if risk_score >= 0.75:
            mitigations.append("Requires multi-operator approval")
            mitigations.append("Audit trail mandatory")
        if base_risk >= 0.8:
            mitigations.append("Consider sandboxed execution")
            mitigations.append("Have rollback plan ready")

        result = {
            "timestamp": timestamp,
            "project_id": project_context.project_id,
            "action": action,
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "base_risk": base_risk,
            "modifiers": {
                "status": status_modifier,
                "category": category_modifier,
            },
            "risk_factors": risk_factors,
            "mitigations": mitigations,
            "requires_approval": risk_score >= 0.5,
            "approval_level": (
                "multi_operator" if risk_score >= 0.75
                else "single_operator" if risk_score >= 0.5
                else "self"
            ),
            "bounded": True,
            "trace_id": f"risk_{timestamp}",
        }

        self._reasoning_log.append(result)

        logger.info(
            "Risk assessment: action=%s, project=%s, score=%.2f, level=%s",
            action,
            project_context.project_id,
            risk_score,
            risk_level,
        )

        return result

    # ── Action Prioritization ─────────────────────────────────────

    def prioritize_actions(
        self, actions: list[str], project_context: ProjectContext
    ) -> list[dict[str, Any]]:
        """Prioritize actions by governance compliance and risk.

        Returns ranked list with reasoning. Lower risk actions that
        are governance-compliant are ranked higher.

        Args:
            actions: List of action strings to prioritize.
            project_context: The project context.

        Returns:
            Ranked list of actions with scores and reasoning.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        scored_actions: list[dict[str, Any]] = []

        for action in actions:
            # Get risk score
            risk_result = self.assess_risk(action, project_context)
            risk_score = risk_result["risk_score"]

            # Governance compliance score (inverse of risk)
            compliance_score = 1.0 - risk_score

            # Priority score combines compliance and inverse risk
            priority_score = (compliance_score * 0.6) + ((1.0 - risk_score) * 0.4)

            scored_actions.append({
                "action": action,
                "priority_score": round(priority_score, 2),
                "risk_score": risk_score,
                "risk_level": risk_result["risk_level"],
                "compliance_score": round(compliance_score, 2),
                "requires_approval": risk_result["requires_approval"],
                "reasoning": (
                    f"Risk: {risk_result['risk_level']} | "
                    f"Approval: {risk_result['approval_level']}"
                ),
            })

        # Sort by priority score (highest first)
        scored_actions.sort(key=lambda x: x["priority_score"], reverse=True)

        # Add rank
        for i, entry in enumerate(scored_actions):
            entry["rank"] = i + 1

        result = {
            "timestamp": timestamp,
            "project_id": project_context.project_id,
            "analysis_type": "action_prioritization",
            "action_count": len(actions),
            "ranked_actions": scored_actions,
            "bounded": True,
            "trace_id": f"prioritize_{timestamp}",
        }

        self._reasoning_log.append(result)

        logger.info(
            "Action prioritization: project=%s, actions=%d",
            project_context.project_id,
            len(actions),
        )

        return scored_actions

    # ── Operational Plan Generation ───────────────────────────────

    def generate_operational_plan(
        self, objective: str, project_context: ProjectContext
    ) -> dict[str, Any]:
        """Generate a bounded operational plan.

        Returns plan with governance annotations. This is planning only —
        it does NOT execute anything.

        Args:
            objective: The objective to plan for.
            project_context: The project context.

        Returns:
            Dict with operational plan and governance annotations.
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        # Generate plan steps based on objective keywords
        steps = self._derive_plan_steps(objective)

        # Analyze each step through governance lens
        governed_steps: list[dict[str, Any]] = []
        total_risk = 0.0

        for i, step in enumerate(steps):
            risk_result = self.assess_risk(step["action"], project_context)
            total_risk += risk_result["risk_score"]

            governed_steps.append({
                "step_number": i + 1,
                "action": step["action"],
                "description": step["description"],
                "risk_score": risk_result["risk_score"],
                "risk_level": risk_result["risk_level"],
                "requires_approval": risk_result["requires_approval"],
                "approval_level": risk_result["approval_level"],
                "governance_annotation": (
                    "SAFE" if risk_result["risk_score"] < 0.25
                    else "REVIEW" if risk_result["risk_score"] < 0.5
                    else "APPROVE" if risk_result["risk_score"] < 0.75
                    else "MULTI_APPROVE"
                ),
            })

        avg_risk = total_risk / len(steps) if steps else 0.0

        # Overall plan assessment
        plan_approved = all(
            step["risk_score"] < 0.75 for step in governed_steps
        )

        result = {
            "timestamp": timestamp,
            "project_id": project_context.project_id,
            "objective": objective,
            "analysis_type": "operational_plan",
            "step_count": len(steps),
            "average_risk_score": round(avg_risk, 2),
            "overall_risk_level": self._score_to_level(avg_risk),
            "plan_approved": plan_approved,
            "steps": governed_steps,
            "governance_summary": {
                "safe_steps": sum(1 for s in governed_steps if s["governance_annotation"] == "SAFE"),
                "review_steps": sum(1 for s in governed_steps if s["governance_annotation"] == "REVIEW"),
                "approve_steps": sum(1 for s in governed_steps if s["governance_annotation"] == "APPROVE"),
                "multi_approve_steps": sum(1 for s in governed_steps if s["governance_annotation"] == "MULTI_APPROVE"),
            },
            "note": (
                "This is a PLAN only. No actions are executed. "
                "Each step marked APPROVE or MULTI_APPROVE requires "
                "explicit operator approval before execution."
            ),
            "bounded": True,
            "trace_id": f"plan_{timestamp}",
        }

        self._reasoning_log.append(result)

        logger.info(
            "Operational plan: project=%s, objective=%s, steps=%d, risk=%s",
            project_context.project_id,
            objective,
            len(steps),
            result["overall_risk_level"],
        )

        return result

    # ── Reasoning Log ─────────────────────────────────────────────

    def get_reasoning_log(self) -> list[dict[str, Any]]:
        """Get the full reasoning log.

        Returns:
            List of all reasoning records.
        """
        return list(self._reasoning_log)

    def get_reasoning_by_trace_id(self, trace_id: str) -> dict[str, Any] | None:
        """Get a specific reasoning record by trace ID.

        Args:
            trace_id: The trace ID to look up.

        Returns:
            Reasoning record dict or None.
        """
        for entry in self._reasoning_log:
            if entry.get("trace_id") == trace_id:
                return dict(entry)
        return None

    # ── Internal Helpers ──────────────────────────────────────────

    def _assess_operation_risk(
        self, operation: dict[str, Any], project_context: ProjectContext
    ) -> dict[str, Any]:
        """Assess risk of a single operation.

        Args:
            operation: Operation dict with 'type' and optional metadata.
            project_context: The project context.

        Returns:
            Dict with risk score and factors.
        """
        op_type = operation.get("type", "unknown")
        base_risk = self.OP_RISK_MULTIPLIERS.get(op_type, 0.5)

        factors: list[str] = []
        if base_risk >= 0.7:
            factors.append(f"Operation '{op_type}' is high-risk")
        if project_context.status != "active":
            factors.append("Project is not fully active")

        return {
            "score": min(base_risk, 1.0),
            "factors": factors,
        }

    def _score_to_level(self, score: float) -> str:
        """Convert a risk score to a risk level string.

        Args:
            score: Risk score between 0.0 and 1.0.

        Returns:
            Risk level string: 'low', 'medium', 'high', or 'critical'.
        """
        if score < 0.25:
            return "low"
        elif score < 0.5:
            return "medium"
        elif score < 0.75:
            return "high"
        else:
            return "critical"

    def _generate_workflow_recommendation(
        self, avg_risk: float, governance_passed: bool, op_count: int
    ) -> str:
        """Generate a workflow recommendation string.

        Args:
            avg_risk: Average risk score.
            governance_passed: Whether governance checks passed.
            op_count: Number of operations.

        Returns:
            Recommendation string.
        """
        if not governance_passed:
            return "REJECTED: Workflow violates governance constraints. Cannot proceed."

        if avg_risk < 0.25:
            return "APPROVED: Low risk. Can proceed with standard monitoring."
        elif avg_risk < 0.5:
            return "APPROVED_WITH_REVIEW: Medium risk. Review recommended before execution."
        elif avg_risk < 0.75:
            return "REQUIRES_APPROVAL: High risk. Explicit operator approval required."
        else:
            return "REQUIRES_MULTI_APPROVAL: Critical risk. Multiple operators must approve."

    def _derive_plan_steps(self, objective: str) -> list[dict[str, str]]:
        """Derive plan steps from an objective string.

        Simple keyword-based plan derivation for demonstration.
        In production, this would use a more sophisticated planner.

        Args:
            objective: The objective string.

        Returns:
            List of step dicts with 'action' and 'description'.
        """
        objective_lower = objective.lower()
        steps: list[dict[str, str]] = []

        # Default plan
        steps.append({
            "action": "analyze",
            "description": f"Analyze the objective: {objective}",
        })

        # Keyword-based step derivation
        if any(word in objective_lower for word in ("deploy", "release", "ship")):
            steps.append({"action": "backup", "description": "Create backup before deployment"})
            steps.append({"action": "schema_change", "description": "Apply schema changes"})
            steps.append({"action": "deploy", "description": "Deploy to production"})
            steps.append({"action": "query", "description": "Verify deployment"})

        elif any(word in objective_lower for word in ("analyze", "report", "study")):
            steps.append({"action": "query", "description": "Gather data"})
            steps.append({"action": "analyze", "description": "Perform analysis"})
            steps.append({"action": "transform", "description": "Transform results"})

        elif any(word in objective_lower for word in ("backup", "save", "snapshot")):
            steps.append({"action": "query", "description": "Identify data to backup"})
            steps.append({"action": "backup", "description": "Create backup"})
            steps.append({"action": "analyze", "description": "Verify backup integrity"})

        elif any(word in objective_lower for word in ("update", "modify", "change")):
            steps.append({"action": "query", "description": "Assess current state"})
            steps.append({"action": "backup", "description": "Backup before changes"})
            steps.append({"action": "modify", "description": "Apply modifications"})
            steps.append({"action": "query", "description": "Verify changes"})

        elif any(word in objective_lower for word in ("delete", "remove", "clean")):
            steps.append({"action": "query", "description": "Identify targets"})
            steps.append({"action": "backup", "description": "Backup before deletion"})
            steps.append({"action": "delete", "description": "Execute deletion"})

        elif any(word in objective_lower for word in ("api", "call", "fetch")):
            steps.append({"action": "api_call", "description": "Make API request"})
            steps.append({"action": "process", "description": "Process response"})

        else:
            # Generic plan
            steps.append({"action": "query", "description": "Gather information"})
            steps.append({"action": "process", "description": "Process data"})
            steps.append({"action": "analyze", "description": "Analyze results"})

        return steps

    def __repr__(self) -> str:
        return (
            f"OperationalReasoningEngine("
            f"reasoning_records={len(self._reasoning_log)})"
        )
