# ADR-0009: Workflow Engine Strategy

- Status: Proposed
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

GARVIS needs to coordinate multi-step, long-running, background, and autonomous work — composing
agents and tools over time, pausing for human approval, surviving restarts, and recovering from
failure. The ratified baseline (ADR-0007) and Accepted decisions define the controls each step must
obey: the Approval Gate authorizes side effects, the Secrets & Permissions Policy demands least
privilege and forbids self-grant, the Memory Authority forbids competing durable stores, the
Observability/Audit spec forbids writing canonical audit directly, the Contracts spec requires
versioned definitions, and the Tool Permission Model gates tool execution. The Agent Orchestration
Model (ADR-0008, Proposed) defines how agents propose. What is missing is the **execution
coordinator** that drives steps through those controls. The Workflow Engine is that coordinator — it
is **not** a tool, agent, scheduler, permission system, the Approval Gate, memory, or observability;
it coordinates them. "Workflow engine strategy" is item #10 of the initial ADR backlog
(`ADR_PROCESS.md` §37). Today there is no workflow engine, no durable workflow state, and no workflow
tests.

## Decision

Adopt
[`docs/architecture/WORKFLOW_ENGINE_STRATEGY.md`](../architecture/WORKFLOW_ENGINE_STRATEGY.md)
as the governing Workflow Engine Strategy for GARVIS, effective before implementing durable
workflows, autonomous execution, background execution, or long-running task orchestration. Core
rules: the Workflow Engine **coordinates** and owns only workflow definitions and state — it owns no
permissions, approvals, durable memory, business logic, tools, agents, contracts, or canonical audit
records, and it never bypasses the Approval Gate, permission checks, contract validation, the Memory
Authority, observability, audit, the Tool Permission Model, or Agent Orchestration; every workflow
step that implies an effect passes the mandatory pipeline **Proposed → Validated → Permission
Checked → Approval Checked → Executed → Observed → Audited → Recovered if necessary**; workflow
execution is resumable, deterministic where possible, checkpoint-based, recoverable, cancellable,
rollback/compensation-capable where possible, supports long-running jobs and human-approval pauses,
and runs autonomously only inside bounded, revocable, auditable permission scopes; background/
autonomous runs bypass nothing; retries are bounded and idempotency-aware and never retry denied or
forbidden steps; permission/approval/contract/audit failures fail closed; and **workflow execution
is disabled until invariant, permission-boundary, approval-invariant, redaction, audit, contract,
recovery/checkpoint, idempotency, and integration tests exist.**

## Options considered

1. **A coordination-only Workflow Engine that owns nothing and bypasses nothing (chosen).** The
   engine drives steps through the mandatory pipeline using the existing authorities. Strongest
   safety and clearest boundaries; conforms to the ratified baseline; persistence/engine technology
   deferred.

2. **Let the Workflow Engine execute side effects directly (rejected).** *Rejected:* removes the
   tool/permission/approval/audit path (Tool Model §8); a directly-executing engine can cause
   never-auto/destructive effects unchecked.

3. **Let the Workflow Engine own permissions and approvals (rejected).** *Rejected:* fragments the
   permission and approval authorities (PRIME §8; Gate Spec §6); the engine must check, not own, them.

4. **Let the Workflow Engine own durable memory or audit (rejected).** *Rejected:* creates competing
   stores against the single Memory Authority and the single Audit Authority (Memory §5; Audit §22);
   the engine persists its own workflow state only and references memory/audit by handle.

5. **Make the engine a business-process/business-logic layer (rejected).** *Rejected:* turns
   orchestration infrastructure into business logic (§53), couples coordination to domain rules, and
   violates separation of concerns; conditions/branches stay declarative and logic stays in the core.

6. **Make the engine an integration layer (rejected).** *Rejected:* integrations are adapters at the
   edge (Overview §17); folding integration into the engine leaks vendor concerns into coordination
   and duplicates the Integration Plane.

7. **Make the engine a scheduler-only system (rejected).** *Rejected:* scheduling is one trigger into
   coordination; a scheduler-only view drops checkpoints, recovery, approval pauses, compensation, and
   the mandatory pipeline — the parts that make long-running work safe (§15, §53).

8. **Implement workflows before the Tool Permission Model and Agent Orchestration Model (rejected).**
   *Rejected:* workflows compose tools and agents; without those models the steps have no safe
   execution/proposal path. (The Tool Model is Accepted, ADR-0006; the Agent Model is Proposed,
   ADR-0008 — this strategy depends on both.)

9. **Implement workflows before Approval Gate and recovery/checkpoint tests (rejected).** *Rejected:*
   contradicts "verification before execution" (PRIME §14–§15); long-running, autonomous,
   side-effecting coordination without proven gating and resumability is unaccountable and unsafe.
   Workflow execution must be disabled until those tests exist (§48).

10. **Allow autonomous/background workflows to bypass correlation, permission, the Gate, or audit for
    convenience (rejected).** *Rejected:* background/autonomous work becomes a loophole; autonomy
    changes the trigger, not the controls (§43–§44).

## Consequences

- **Positive:** GARVIS gains durable, resumable, gated, auditable coordination of multi-step and
  autonomous work without the engine owning or bypassing any authority; long-running jobs and
  human-approval pauses are first-class; recovery/checkpoint/compensation make failures safe.
- **Negative / cost:** up-front strategy, contract, persistence, and test work before any durable/
  autonomous workflow can be enabled; capability gated behind invariant/recovery/permission/approval/
  audit/contract tests, slowing short-term delivery by design.
- **Neutral:** the engine/persistence/scheduler technology, graph representation, and determinism
  guarantees are deferred to later ADRs; this ADR adopts the *strategy*, not an implementation.

## Impact

- **Security:** binds every workflow step to the mandatory pipeline (permission + approval + contract
  + audit), fails closed on failure, forbids raw secrets/tokens/execution-context in persisted state/
  checkpoints/events, and confines autonomous/background runs to bounded, revocable, auditable scopes.
  No secret value appears in this ADR or the strategy.
- **Architecture:** places the engine in the Orchestration Plane as coordination infrastructure that
  owns only workflow definitions/state; tools/agents/memory/audit remain their own authorities.
- **Operational:** defines lifecycle, states, checkpoints, recovery, compensation, rollback,
  cancellation, timeouts, retries, budgets, and human-approval pauses — making long-running work
  observable, recoverable, and resumable across restarts.
- **Performance:** persistence/checkpointing and per-step pipeline add bounded overhead; gated-step
  checks are on the critical path and not skipped; long-running work uses checkpoints + waits rather
  than blocking; measured where budgets exist (PRIME §12).
- **Maintainability:** coordination-only scope and one authority per capability prevent the engine
  from becoming a business-logic/integration monolith; versioned definitions let workflows evolve
  without breaking running instances.
- **Testing:** mandates required, blocking suites — invariant, permission-boundary, approval-
  invariant, redaction, audit, contract, recovery/checkpoint, idempotency, and integration — and
  disables workflow execution until they exist (Strategy §20).

## Rollback strategy

This ADR records a strategy and adds no executable code, engine, persistence, schema, or secret
material, so reversal is low-cost: it is reversed by a superseding ADR that withdraws or replaces the
strategy, with the governing document updated and history preserved (`ADR_PROCESS.md` §16–§17).
Because the decision *adds* coordination constraints rather than enabling capability, reversing it
does not create an unsafe state; any engine/controls implemented under it would be retired
deliberately.

## Validation strategy

- Confirm the strategy conforms to PRIME and the ratified baseline (Architecture Overview, Approval
  Gate, Project Structure, ADR Process) and to the Accepted cross-cutting decisions and the Tool
  Permission Model, and composes the Agent Orchestration Model without contradiction (none found
  during authoring).
- Validate in practice via the strategy's readiness checklist (§54) and the mandatory pipeline (§37):
  the decision is "validated" when the contracts, persistence/checkpoint/recovery, fail-closed
  pipeline, approval-pause, and bounded autonomy controls exist and the required invariant,
  permission-boundary, approval-invariant, redaction, audit, contract, recovery, and integration
  tests pass before the workflow capability they gate is enabled.
- Acceptance is a human review step (`ADR_PROCESS.md` §15); it is not self-approved. No real secret
  is used in any validation.

## Related documents

- `docs/architecture/WORKFLOW_ENGINE_STRATEGY.md` (the adopted strategy)
- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md`
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`
- `docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md`
- `docs/architecture/SECRETS_AND_PERMISSIONS_POLICY.md`
- `docs/architecture/MEMORY_AUTHORITY_SPEC.md`
- `docs/architecture/OBSERVABILITY_AND_AUDIT_SPEC.md`
- `docs/architecture/CONTRACTS_AND_SCHEMA_VERSIONING.md`
- `docs/architecture/TOOL_PERMISSION_MODEL.md`
- `docs/architecture/AGENT_ORCHESTRATION_MODEL.md`
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`
- `docs/adr/ADR-0002-secrets-and-permissions-policy.md`
- `docs/adr/ADR-0003-memory-authority.md`
- `docs/adr/ADR-0004-observability-and-audit.md`
- `docs/adr/ADR-0005-contracts-and-schema-versioning.md`
- `docs/adr/ADR-0006-tool-permission-model.md`
- `docs/adr/ADR-0007-foundational-architecture-ratification.md`
- `docs/adr/ADR-0008-agent-orchestration-model.md`

## Supersedes

None.

## Superseded by

None.
