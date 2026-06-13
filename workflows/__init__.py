"""Governed Workflow Runtime for GARVIS.

Phase 11 — The FIRST REAL WORKFLOW SYSTEM.

This module provides a governed workflow execution engine that:
- Registers workflow definitions with governance validation
- Requires explicit operator approval before execution
- Mediates every step through governance checks
- Maintains full audit trails for all operations
- Supports rollback of failed workflows
- Classifies risk and determines approval requirements

Key classes:
- WorkflowEngine: Core execution engine with governance mediation
- WorkflowRegistry: Registration and lifecycle management
- WorkflowAudit: Workflow-specific audit trail tracking
- WorkflowInstance: A running workflow execution
- WorkflowStep: A single step in a workflow definition
"""

from __future__ import annotations

from workflows.audit import WorkflowAudit
from workflows.engine import WorkflowEngine
from workflows.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStepResult,
)
from workflows.registry import WorkflowRegistry

__all__ = [
    "WorkflowEngine",
    "WorkflowAudit",
    "WorkflowRegistry",
    "WorkflowInstance",
    "WorkflowStep",
    "WorkflowDefinition",
    "WorkflowStepResult",
]
