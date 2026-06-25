# ADR-0006: Tool Permission Model

- Status: Accepted
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

Tools are where GARVIS actually touches the world — reading and writing files, accessing networks,
calling integrations, executing commands, modifying state, and causing external side effects. An
unconstrained tool is an unbounded risk: data loss, network exfiltration, irreversible external
change, or secret leakage. The foundational specifications already define the controls a tool must
obey: the Approval Gate authorizes side effects (Gate Spec §32), the Secrets & Permissions Policy
forbids self-grant/self-authorize and demands least privilege (§39, §46), the Memory Authority
forbids tool-owned durable memory (§48), the Observability/Audit spec forbids tools writing
canonical audit directly (§10, §40), and the Contracts spec requires versioned tool call/result
contracts (§67). What is missing is a single model that binds tools to those controls. ADR-0001
through ADR-0005 are **Proposed, not Accepted**; they are used here as documented architectural
inputs and their status is unchanged. "Tool permission model" is item #7 of the initial ADR backlog
(`ADR_PROCESS.md` §37). Today there is no tool registry, no tool permission scoping, and no tool
tests.

## Decision

Adopt
[`docs/architecture/TOOL_PERMISSION_MODEL.md`](../architecture/TOOL_PERMISSION_MODEL.md)
as the governing Tool Permission Model for GARVIS, effective before implementing tools that read
files, write files, access networks, call integrations, execute commands, modify state, perform
external side effects, or participate in autonomous workflows. Core rules: tools are capability
executors/adapters, not authorities — they own no permission, approval, memory, audit, or business
logic; tools never self-authorize, self-grant, expand scope, or bypass Orchestration, the Approval
Gate, permission checks, contract validation, redaction, observability, or audit; a side-effecting
tool runs only with the required permission scope **and** a single-use approval bound to its exact
action, through the Integration Plane; every tool has an owner, purpose, risk class, permission
scope, versioned call/result/error contract, and test strategy; destructive tools require explicit
permission **and** explicit approval; credential-sensitive tools are forbidden unless explicitly
allowed under strict policy; execution tools require permission, approval where required, audit,
timeout, failure handling, and rollback expectations; tools store no raw secrets/credentials/
tokens/execution-context/audit-payloads; retries are bounded and idempotency-aware and never retry
denied or forbidden actions; permission/approval/contract/audit failures fail closed; and **tool
execution is disabled until permission-boundary, approval-invariant, redaction, audit, and contract
tests exist.**

## Options considered

1. **One governed Tool Permission Model (chosen).** Tools are owned, classified, permission-scoped,
   approval-gated where required, contracted, audited, reversible-aware, and test-gated. Strongest
   safety; conforms to PRIME and the cross-cutting specs; registry/encoding deferred.

2. **Let tools self-authorize (rejected).** *Rejected:* removes the per-action human authorization
   the Approval Gate exists to provide; a self-authorizing tool can perform never-auto/destructive
   actions unchecked (Gate Spec §32; §100).

3. **Let tools own permission logic (rejected).** *Rejected:* fragments the permission authority
   (PRIME §8) and lets a tool widen its own scope; permission must live in core and be enforced at
   the boundary (Secrets Policy §46).

4. **Treat tools as unrestricted helper functions (rejected).** *Rejected:* ignores blast radius and
   reversibility; an unrestricted helper that writes files or hits networks is exactly the unbounded
   risk this model prevents.

5. **Add tools before the Approval Gate and permission contracts exist (rejected).** *Rejected:*
   contradicts "verification before execution" (PRIME §14–§15); side-effecting tools without the
   Gate and permission boundary act unauthorized by construction.

6. **Use vendor-native tool payloads as core contracts (rejected).** *Rejected:* leaks external
   shapes into core (PRIME §8; Contracts §69) and couples the platform to a vendor; integrations
   must translate at the edge.

7. **Allow tools to write directly to memory (rejected).** *Rejected:* creates competing, ungoverned
   durable stores (Memory Spec §48); durable results must be written through the Memory Authority,
   redacted and attributed.

8. **Allow tools to write canonical audit records directly (rejected).** *Rejected:* breaks the
   single canonical Audit Authority (Audit Spec §22, §40); tools emit, the Authority records.

9. **Allow background jobs to call tools without correlation and approval rules (rejected).**
   *Rejected:* background work becomes a bypass loophole; background tool use must carry correlation,
   permission, redaction, and audit and cannot self-grant (Secrets Policy §64; §59).

10. **Allow denied tool actions to be retried automatically (rejected).** *Rejected:* launders a
    denial; denied actions must not be auto-rephrased/retried and forbidden actions must be rejected
    and never queued (Gate Spec §25, §16; §66).

11. **Add execution tools before permission-boundary and approval-invariant tests exist (rejected).**
    *Rejected:* enables side effects with no proof the controls hold; tool execution must be disabled
    until those tests exist (§81, §108).

## Consequences

- **Positive:** every tool action is owned, classified, authorized, contracted, audited, and
  reversible-aware; a single model binds tools to the Gate, permissions, memory, audit, and
  contracts; safe foundation for execution and autonomous tool use.
- **Negative / cost:** up-front model, registry, contract, and test work before any side-effecting
  tool can ship; tool delivery is gated behind permission/approval/redaction/audit/contract tests,
  slowing short-term delivery by design.
- **Neutral:** the tool registry implementation, encoding, sandbox mechanism, and per-class preview
  feasibility are deferred to later ADRs; this ADR adopts the *model*, not an implementation.

## Impact

- **Security:** binds tools to least-privilege permission scopes and single-use approvals; forbids
  self-authorization/scope-expansion; forbids raw secrets/tokens/execution-context in tools;
  mandates redaction of params/results/errors including failure paths; destructive/credential-
  sensitive tools are tightly constrained or forbidden. No secret value appears in this ADR or the
  model.
- **Architecture:** places tools at `planes/integration/tools/` as adapters invoked by Execution
  through Integration; tools own no authority and reach externals only through the permission
  boundary.
- **Operational:** defines lifecycle, registration/enablement/disablement/revocation, timeout/
  retry/rate-limit/concurrency, failure/recovery, and rollback; tool activity is observable and
  auditable by reference.
- **Performance:** validation, permission, and approval binding add bounded overhead on the tool
  critical path; safety checks for gated tools are not skipped; measured where budgets exist (PRIME
  §12).
- **Maintainability:** one model and one authority per capability remove duplicated tool/permission
  logic; versioned contracts let tool shapes evolve without breaking consumers.
- **Testing:** mandates required, blocking suites — permission-boundary, approval-invariant,
  redaction, audit, contract, integration, and adversarial — and disables tool execution until they
  exist (Strategy §17, §19).

## Rollback strategy

This ADR records a model and adds no executable code, registry, tool, schema, or secret material, so
reversal is low-cost: it is reversed by a superseding ADR that withdraws or replaces the model, with
the governing document updated and history preserved (`ADR_PROCESS.md` §16–§17). Because the
decision *adds* constraints rather than enabling capability, reversing it does not create an unsafe
state; any registry/controls implemented under it would be retired deliberately.

## Validation strategy

- Confirm the model conforms to PRIME, the Architecture Overview, the Approval Gate spec, Project
  Structure, the testing strategy, the secrets/permissions policy, the Memory Authority spec, the
  Observability/Audit spec, and the Contracts spec (no critical contradiction found during
  authoring).
- Validate in practice via the model's readiness checklist (§113) and migration phases (§106): the
  decision is "validated" when, at each phase, the registry/contract/permission/approval/redaction/
  audit controls exist and the required permission-boundary, approval-invariant, redaction, audit,
  contract, and adversarial tests pass before the tool capability they gate is enabled.
- Acceptance is a human review step (`ADR_PROCESS.md` §15); it is not self-approved. No real secret
  is used in any validation.

## Related documents

- `docs/architecture/TOOL_PERMISSION_MODEL.md` (the adopted model)
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
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`
- `docs/adr/ADR-0002-secrets-and-permissions-policy.md`
- `docs/adr/ADR-0003-memory-authority.md`
- `docs/adr/ADR-0004-observability-and-audit.md`
- `docs/adr/ADR-0005-contracts-and-schema-versioning.md`

## Supersedes

None.

## Superseded by

None.
