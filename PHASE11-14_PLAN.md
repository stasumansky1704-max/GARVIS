# GARVIS Phase 11-14 — Governed Real Operation Transition

## Phase 11: Governed Real Workflow Pilot
- `workflows/` — Workflow execution engine (approval-gated)
- `workflows/engine.py` — Execute workflows only after operator approval
- `workflows/audit.py` — Full workflow lifecycle audit
- `workflows/registry.py` — Workflow registry with governance binding

## Phase 12: Governed Operational Intelligence
- `projects/` — Per-project governance system
- `projects/governance.py` — Project-level governance
- `projects/context.py` — Context isolation between projects
- `projects/memory.py` — Per-project operational memory

## Phase 13: Governed Collaborative Cognition
- `cognition/collaboration.py` — Operator-cognition interaction model
- `cognition/negotiation.py` — Governance negotiation view
- `cognition/strategy.py` — Bounded strategic reasoning

## Phase 14: Constitutional Operational Ecosystem
- Full Mission Control API expansion
- Ecosystem-wide observability
- Cross-system analytics
- Complete dashboard integration

## Test Coverage
- `tests/test_workflows.py` — Workflow engine validation
- `tests/test_projects.py` — Project governance validation
- `tests/test_collaboration.py` — Collaboration layer validation
- `tests/test_ecosystem_integration.py` — Full ecosystem validation
