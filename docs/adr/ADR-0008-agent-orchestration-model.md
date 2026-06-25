# ADR-0008: Agent Orchestration Model

- Status: Proposed
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

Agents are the highest-leverage component in GARVIS: they perceive, reason, plan, and select
actions, and an unbounded agent that can execute, self-authorize, or hold platform authority is the
system's largest risk. GARVIS now has a **ratified** foundational baseline (ADR-0007) and Accepted
cross-cutting decisions (ADR-0001 through ADR-0006) that define the controls an agent must obey: the
Approval Gate authorizes side effects, the Secrets & Permissions Policy forbids self-grant/self-
authorize and demands least privilege, the Memory Authority forbids agent-owned durable memory, the
Observability/Audit spec forbids agents writing canonical audit directly, the Contracts spec
requires versioned agent message/proposal contracts, and the Tool Permission Model requires that
tool calls go through permission + approval + audit. What is missing is the model that binds agents
to those controls — defining agents as orchestrated, propose-only roles. Agent rules are currently
scattered across PRIME §7, Overview §16, Secrets Policy §45, and Tool Model §5 with no single
governing spec. "Agent orchestration model" is item #6 of the initial ADR backlog (`ADR_PROCESS.md`
§37). Today there is no agent registry, no role definitions, and no agent tests.

## Decision

Adopt
[`docs/architecture/AGENT_ORCHESTRATION_MODEL.md`](../architecture/AGENT_ORCHESTRATION_MODEL.md)
as the governing Agent Orchestration Model for GARVIS, effective before implementing durable agents,
multi-agent coordination, agent-selected tool calls, autonomous planning, delegated tasks, agent
memory access, or workflow-driven agent execution. Core rules: agents are orchestrated single-
responsibility roles, not authorities — they own no permission, approval, memory, audit, contract,
or core business logic; agents **propose**, never execute side effects, self-authorize, self-grant,
expand scope, or approve; plans are not approvals, confidence is not authorization, and consensus/
multi-agent agreement never substitutes for human approval; agents never bypass Orchestration, the
Approval Gate, permission checks, contract validation, redaction, observability, or audit; agent-
selected tool calls become Proposed Actions routed through Orchestration → contracts → permissions →
Approval Gate → audited execution (agents never invoke tools directly); agent memory access is
governed, permission-checked, redacted, and auditable, and writes are proposals (never direct);
agents emit events but never write canonical audit directly; agents store no raw secrets/credentials/
tokens/execution-context/audit-payloads; every agent has an owner, purpose, single role, risk class,
permission scope, versioned contracts, and test strategy before enablement; autonomous agents run
only in bounded, revocable, auditable scopes; background agents bypass nothing; denied agent actions
are not auto-retried and forbidden ones are rejected and never queued; permission/approval/contract/
audit failures fail closed; and **agent orchestration is disabled until orchestration-invariant,
permission-boundary, approval-invariant, redaction, audit, contract, memory-boundary, and tool-
boundary tests exist.**

## Options considered

1. **One governed Agent Orchestration Model — orchestrated, propose-only roles (chosen).** Agents
   are owned, classified, permission-scoped, contracted, observable, and incapable of acting except
   by proposing through Orchestration to the Gate. Strongest safety; conforms to the ratified
   baseline; registry/framework deferred.

2. **Let agents execute tools directly (rejected).** *Rejected:* removes the permission + approval +
   audit path the Tool Permission Model requires (Tool Model §8); a directly-executing agent can
   cause never-auto/destructive effects unchecked.

3. **Let agents self-authorize (rejected).** *Rejected:* removes the per-action human authorization
   the Approval Gate exists to provide (Gate Spec §31); a self-authorizing agent is the core safety
   failure.

4. **Let agents own durable memory (rejected).** *Rejected:* creates competing, ungoverned durable
   stores (Memory Spec §47); durable knowledge must be proposed to the single Memory Authority,
   redacted and attributed.

5. **Let agents write canonical audit records directly (rejected).** *Rejected:* breaks the single
   canonical Audit Authority (Audit Spec §22, §39); agents emit, the Authority records.

6. **Let agents define private contracts (rejected).** *Rejected:* fragments the contract authority
   and creates uncontracted boundaries (Contracts §66); agent messages/proposals must use registered
   versioned contracts.

7. **Treat agent consensus as approval (rejected).** *Rejected:* multi-agent agreement is not human
   authorization; consensus could approve never-auto/destructive actions with no human in the loop
   (§113). Only the Gate, under human authority, approves.

8. **Treat agent confidence as authorization (rejected).** *Rejected:* a confidence score is a
   reasoning artifact, not an authorization; high confidence must never bypass classification or
   approval (§113).

9. **Implement agents before the Tool Permission Model (rejected).** *Rejected:* agents select
   tools; without the tool model the selection has no safe execution path. (Moot here — the Tool
   Permission Model is Accepted, ADR-0006 — and this ordering is preserved.)

10. **Implement agents before Approval Gate and permission-boundary tests (rejected).** *Rejected:*
    contradicts "verification before execution" (PRIME §14–§15); agents that propose side effects
    without proven Gate/permission boundaries act unaccountably. Agent orchestration must be disabled
    until those tests exist (§92, §120).

11. **Create many general-purpose agents instead of single-responsibility roles (rejected).**
    *Rejected:* general-purpose agents accrue broad scope, blur ownership, and resist least privilege
    (PRIME §8); GARVIS uses narrow, single-responsibility roles (§29).

12. **Allow peer-to-peer delegation without Orchestration (rejected).** *Rejected:* P2P delegation
    creates ungoverned coordination/authorization channels that bypass routing, permission, and the
    Gate; all coordination must be Orchestration-mediated (§65).

## Consequences

- **Positive:** every agent action is a governed proposal; agents cannot execute, self-authorize, or
  own authority; a single model binds agents to the Gate, permissions, memory, audit, contracts, and
  the tool model; safe foundation for multi-agent coordination and autonomy.
- **Negative / cost:** up-front model, registry, contract, and test work before any agent can be
  enabled; agent delivery is gated behind orchestration/permission/approval/redaction/audit/contract/
  memory/tool tests, slowing short-term delivery by design.
- **Neutral:** the agent registry implementation, framework, role taxonomy granularity, and autonomy
  budget model are deferred to later ADRs; this ADR adopts the *model*, not an implementation.

## Impact

- **Security:** binds agents to least-privilege scopes and single-use approvals; forbids self-
  authorization/scope-expansion/consensus-as-approval; treats prompt/context/tool-output as untrusted
  data (PRIME §7); forbids raw secrets/tokens/execution-context in agents; mandates redaction of
  agent inputs/proposals/results including failure paths. No secret value appears in this ADR or the
  model.
- **Architecture:** places agents at `planes/orchestration/agents/` under Orchestration; agents own
  no authority and reach tools/memory/audit only by proposal through governed paths; multi-agent
  coordination is supervisor-mediated, never peer-to-peer.
- **Operational:** defines lifecycle, registration/enablement/disablement/revocation, timeout/retry/
  rate-limit/concurrency/budget, failure/recovery, and autonomy/background constraints; agent activity
  is observable and auditable by reference.
- **Performance:** proposal validation, permission, and approval binding add bounded overhead on the
  agent critical path; safety checks for gated actions are not skipped; measured where budgets exist
  (PRIME §12).
- **Maintainability:** single-responsibility roles and one authority per capability remove duplicated
  agent/permission/coordination logic; versioned contracts let agent shapes evolve without breaking
  consumers.
- **Testing:** mandates required, blocking suites — orchestration-invariant, permission-boundary,
  approval-invariant, redaction, audit, contract, memory-boundary, tool-boundary, and adversarial —
  and disables agent orchestration until they exist (Strategy §18).

## Rollback strategy

This ADR records a model and adds no executable code, agent, registry, schema, or secret material,
so reversal is low-cost: it is reversed by a superseding ADR that withdraws or replaces the model,
with the governing document updated and history preserved (`ADR_PROCESS.md` §16–§17). Because the
decision *adds* constraints rather than enabling capability, reversing it does not create an unsafe
state; any registry/controls implemented under it would be retired deliberately.

## Validation strategy

- Confirm the model conforms to PRIME and the ratified baseline (Architecture Overview, Approval
  Gate, Project Structure, ADR Process) and to the Accepted cross-cutting decisions (testing,
  secrets/permissions, memory, observability/audit, contracts, tool model) — no critical
  contradiction found during authoring.
- Validate in practice via the model's readiness checklist (§125) and migration phases (§118): the
  decision is "validated" when, at each phase, the registry/contract/permission/approval/redaction/
  audit/memory/tool controls exist and the required orchestration-invariant, permission-boundary,
  approval-invariant, redaction, audit, contract, memory-boundary, tool-boundary, and adversarial
  tests pass before the agent capability they gate is enabled.
- Acceptance is a human review step (`ADR_PROCESS.md` §15); it is not self-approved. No real secret
  is used in any validation.

## Related documents

- `docs/architecture/AGENT_ORCHESTRATION_MODEL.md` (the adopted model)
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
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`
- `docs/adr/ADR-0002-secrets-and-permissions-policy.md`
- `docs/adr/ADR-0003-memory-authority.md`
- `docs/adr/ADR-0004-observability-and-audit.md`
- `docs/adr/ADR-0005-contracts-and-schema-versioning.md`
- `docs/adr/ADR-0006-tool-permission-model.md`
- `docs/adr/ADR-0007-foundational-architecture-ratification.md`

## Supersedes

None.

## Superseded by

None.
