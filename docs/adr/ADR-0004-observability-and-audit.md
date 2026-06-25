# ADR-0004: Observability and Audit

- Status: Accepted
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

GARVIS performs real, gated actions and must be accountable for every consequential one. Without
canonical, correlated, redaction-safe, tamper-evident evidence, there is no way to prove the
Approval Gate held, reconstruct an incident, or hold autonomous behavior accountable. The
constitution requires that nothing act silently and that side-effecting actions be auditable and
attributable, with no secrets in telemetry (PRIME §18); the Approval Gate spec requires a complete
audit trail for every decision (§33) and treats absent audit as a failure (§44); the Memory
Authority deliberately keeps canonical audit out of memory and references it only by safe handle/
redacted metadata (Memory Spec §5, §82); the testing strategy mandates observability/audit and
non-leakage tests (§22, §24); and the secrets policy forbids secrets in logs/audit/diagnostics
(§28, §31, §67). A critical distinction must be enforced: **Observability and Audit are not
Memory** — canonical audit records belong to the Observability Plane's Audit Authority, and
Observability must not become a hidden memory, permission, workflow, business-logic, or execution
system. "Observability and audit storage" is item #8 of the initial ADR backlog (`ADR_PROCESS.md`
§37). Today there is no governed observability or audit; the surface emits only ad-hoc console
output and history was verified manually.

## Decision

Adopt
[`docs/architecture/OBSERVABILITY_AND_AUDIT_SPEC.md`](../architecture/OBSERVABILITY_AND_AUDIT_SPEC.md)
as the governing Observability and Audit specification for GARVIS, effective before execution,
integrations, agents, tools, memory-backed workflows, autonomous workflows, or production operation
proceed. Core rules: one canonical Audit Authority that solely creates canonical audit records from
governed ingestion; planes/agents/tools/workflows **emit** but never write canonical audit directly;
audit is **separate from memory** and references it only by safe handle/redacted metadata; no
secrets/credentials/approval-tokens/execution-context as raw values in logs, audit, traces, metrics,
diagnostics, exports, or failure reports; redaction before every emission boundary; end-to-end
correlation and dependency-chain causality; mandatory, **fail-closed** audit for gated and
security-relevant actions; append-only, retained, tamper-evident-in-principle records;
observability failure must not authorize execution; observability must not become a hidden memory,
permission, or workflow-state system; diagnostics must not become a secret-exfiltration path.

## Options considered

1. **One governed Observability system with a single canonical Audit Authority, contracts-over-
   storage (chosen).** Mandatory, fail-closed, correlated, redacted, tamper-evident audit separate
   from memory. Strongest accountability and safety; conforms to PRIME and the Gate spec; storage
   deferred.

2. **Treat normal logs as the canonical audit trail (rejected).** *Rejected:* ad-hoc logs are
   unstructured, mutable, uncorrelated, and prone to carrying secrets; they cannot serve as a
   tamper-evident system of record and would make audit best-effort.

3. **Let each plane manage audit independently (rejected).** *Rejected:* multiple "logs of record"
   fragment accountability (PRIME §8), produce inconsistent redaction, and create gaps at
   boundaries; conflicts with the single-authority rule.

4. **Store canonical audit records in the Memory Authority (rejected).** *Rejected:* conflates two
   authorities; audit is the canonical record of activity, memory is durable knowledge. Putting raw
   audit/execution context into memory would create an unredacted, secret-bearing store and violate
   Memory Spec §5/§66.

5. **Use UI-visible history as the canonical audit source (rejected).** *Rejected:* a surface view
   is permission-scoped, redacted, and derived; it is not authoritative, complete, or tamper-
   evident. The Interface owns no canonical store (Overview §5).

6. **Log raw execution context for easier debugging (rejected).** *Rejected:* the most direct leak
   path; raw context routinely carries secrets and sensitive data; violates the no-secret and
   redaction rules (§62, §66) — convenience does not justify exposure.

7. **Add audit only after execution features exist (rejected).** *Rejected:* contradicts
   "verification before execution" (PRIME §14–§15) and the Gate's readiness requirement (§44);
   execution without canonical audit is unaccountable by construction.

8. **Make observability vendor-specific at the architecture level (rejected).** *Rejected:* binds
   the architecture to a tool prematurely (PRIME §8 — contracts over implementations); contracts
   must be stable so storage/tooling can change beneath them.

9. **Treat audit as best-effort instead of mandatory for gated actions (rejected).** *Rejected:* if
   gated-action audit can be skipped or silently dropped, the Gate's accountability collapses; audit
   for gated/security-relevant actions must be on the critical path and fail closed (§85).

## Consequences

- **Positive:** every consequential action becomes accountable through one canonical, correlated,
  redacted, tamper-evident trail; a hard audit↔memory boundary; secret-safe observability; a
  testable foundation for execution, autonomy, and production operation.
- **Negative / cost:** up-front contract, redaction, correlation, and canonical-audit work before
  execution/integration features can proceed; mandatory audit adds critical-path overhead for gated
  actions (accepted, fail-closed by design); capability gated behind these controls, slowing
  short-term delivery.
- **Neutral:** storage technology, integrity mechanism, and concrete data model are deferred to
  later ADRs; this ADR adopts the *specification*, not a platform.

## Impact

- **Security:** forbids secrets/credentials/tokens/execution-context as raw values across all
  signals and audit; mandates redaction before every boundary including failure paths; makes
  security events and gated-action audit mandatory and fail-closed; diagnostics cannot become an
  exfiltration path. No secret value appears in this ADR or the spec.
- **Architecture:** establishes the single canonical Audit Authority in `core/observability/` and
  the explicit separation from Memory; planes emit, the Authority owns ingestion and record
  creation.
- **Operational:** defines correlation/causality, retention, immutability, integrity/tamper-
  evidence, incident handling, alerting, dashboards, and user/admin history; the system can report
  its own status and reconstruct incidents.
- **Performance:** general observability may be asynchronous/sampled; mandatory audit for gated
  actions is on the critical path and fail-closed; redaction/correlation overhead is bounded and
  measured where budgets exist (PRIME §12). No budget is asserted without measurement.
- **Maintainability:** contracts-over-storage lets tooling evolve without breaking consumers; one
  authority removes duplicated, divergent logging/audit logic.
- **Testing:** mandates required, blocking suites — completeness of gated-action audit, non-leakage
  across logs/audit/traces/metrics/diagnostics/failure paths, correlation reconstructability,
  immutability/integrity, audit↔memory separation, and fail-closed behavior (Strategy §22, §24).

## Rollback strategy

This ADR records a specification and adds no executable code, storage, schema, log file, or secret
material, so reversal is low-cost: it is reversed by a superseding ADR that withdraws or replaces
the spec, with the governing document updated and history preserved (`ADR_PROCESS.md` §16–§17).
Because the decision *adds* accountability controls rather than enabling capability, reversing it
does not create an unsafe state; any controls already implemented under it would be retired
deliberately.

## Validation strategy

- Confirm the spec conforms to PRIME, the Architecture Overview, the Approval Gate spec, Project
  Structure, the testing strategy, the secrets/permissions policy, and the Memory Authority spec,
  and that the Audit↔Memory separation is preserved (no critical contradiction found during
  authoring).
- Validate in practice via the spec's readiness checklist (§98) and migration phases (§95): the
  decision is "validated" when, at each phase, the corresponding contract, redaction, correlation,
  canonical-audit, fail-closed, and dependency-chain controls exist and their required tests pass
  before the capability they gate is enabled.
- Acceptance is a human review step (`ADR_PROCESS.md` §15); it is not self-approved. No real secret
  is used in any validation.

## Related documents

- `docs/architecture/OBSERVABILITY_AND_AUDIT_SPEC.md` (the adopted specification)
- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md`
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`
- `docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md`
- `docs/architecture/SECRETS_AND_PERMISSIONS_POLICY.md`
- `docs/architecture/MEMORY_AUTHORITY_SPEC.md`
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`
- `docs/adr/ADR-0002-secrets-and-permissions-policy.md`
- `docs/adr/ADR-0003-memory-authority.md`

## Supersedes

None.

## Superseded by

None.
