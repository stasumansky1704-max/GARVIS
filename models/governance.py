"""Governance Pydantic models for GARVIS."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class GovernancePolicy(BaseModel):
    """An individual policy rule within a schema."""

    policy_id: str
    description: str
    rule_type: str  # "threshold", "prohibition", "requirement", "constraint"
    condition: str  # Human-readable condition
    evaluation_logic: str  # Python expression or reference to evaluator
    severity: str  # "critical", "warning", "info"
    auto_remediation: bool = False


class GovernanceConstraint(BaseModel):
    """A hard constraint that must always hold."""

    constraint_id: str
    description: str
    scope: str  # "global", "session", "inference", "memory"
    enforcement: str  # "hard_stop", "log_only", "degrade"


class GovernanceViolation(BaseModel):
    """Recorded when a policy or constraint is breached."""

    violation_id: UUID = Field(default_factory=uuid4)
    schema_id: str
    policy_id: str
    severity: str
    description: str
    context: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    resolution: str | None = None


class GovernanceCheckResult(BaseModel):
    """Result of a governance validation check."""

    check_id: UUID = Field(default_factory=uuid4)
    schema_id: str
    policy_id: str
    passed: bool
    violation: GovernanceViolation | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ViolationResponse(BaseModel):
    """How a schema responds to violations."""

    action: str  # "halt", "degrade", "escalate", "log"
    log_level: str  # "critical", "warning", "info"
    notification_target: str  # "admin", "operator", "system"


class GovernanceSchema(BaseModel):
    """A loaded governance schema with validated structure."""

    schema_id: str
    name: str
    version: str
    category: str
    description: str
    policies: list[GovernancePolicy]
    constraints: list[GovernanceConstraint]
    fail_closed: bool = True
    violation_response: ViolationResponse | None = None

    def get_policies_by_severity(self, severity: str) -> list[GovernancePolicy]:
        """Return policies filtered by severity level."""
        return [p for p in self.policies if p.severity == severity]

    def get_constraints_by_scope(self, scope: str) -> list[GovernanceConstraint]:
        """Return constraints filtered by scope."""
        return [c for c in self.constraints if c.scope == scope]
