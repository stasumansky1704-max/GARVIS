"""GARVIS — Governance Layer

The governance layer is the FIRST and MOST CRITICAL layer of GARVIS.
All cognition passes through governance validation before execution.
Fail-closed by design: any critical failure blocks the operation.

Exports:
    SchemaLoader: Loads and validates governance schemas from YAML
    GovernanceRegistry: Central registry for active governance schemas
    RuntimeValidator: Core fail-closed validation engine
    GovernanceMiddleware: Governance firewall wrapping all cognition
    EnforcementEngine: Fail-closed enforcement actions
"""

from governance.loader import SchemaLoader, GovernanceLoadError
from governance.registry import GovernanceRegistry
from governance.validator import RuntimeValidator
from governance.middleware import GovernanceMiddleware
from governance.enforcer import EnforcementEngine

__all__ = [
    "SchemaLoader",
    "GovernanceLoadError",
    "GovernanceRegistry",
    "RuntimeValidator",
    "GovernanceMiddleware",
    "EnforcementEngine",
]
