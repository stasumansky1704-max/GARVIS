# ADR-0003: Memory Authority

- Status: Proposed
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

GARVIS needs durable memory and knowledge — project knowledge, user preferences, governed
operational/workflow/execution state, and derived summaries — to operate over a long horizon.
Without one governed authority, each plane, agent, tool, or workflow would grow its own store,
fragmenting truth (PRIME §8, §21), and an ungoverned store would leak secrets or unredacted
content. The constitution requires a single memory authority with no competing layers and no
secrets in memory (PRIME §21); the Architecture Overview places Memory as a cross-cutting,
single-writer plane (§15); the Secrets & Permissions Policy forbids raw secrets in memory and
requires permission-checked, redacted handling (§29, §53, §70); and the Testing & Verification
Strategy mandates memory consistency/ownership/redaction/audit tests (§21). A critical
distinction must be enforced: **the Memory Authority is not the Audit Authority** — canonical
audit trails belong to the Observability Plane, and memory may reference allowed audit metadata
only through governed interfaces, never own raw audit logs, raw execution context, raw approval
records, raw secrets, or security-event logs. "Memory authority design" is item #4 of the initial
ADR backlog (`ADR_PROCESS.md` §37). Today there is no governed memory and no test layer.

## Decision

Adopt
[`docs/architecture/MEMORY_AUTHORITY_SPEC.md`](../architecture/MEMORY_AUTHORITY_SPEC.md)
as the governing Memory Authority specification for GARVIS, effective before durable memory,
knowledge management, agent memory, workflow memory, autonomous memory usage, or memory-backed
execution proceeds. Core rules: one Memory Authority with a single writer and governed read
interface; no plane/agent/tool/workflow/integration owns durable memory; memory is **separate
from audit/observability** and references audit only by safe handle/redacted metadata; no raw
secrets, credentials, approval tokens, audit logs, security events, or (by default) raw execution
context in memory; redaction before write/index/summarize/export/display; mandatory provenance,
with confidence on inferred/summarized content; record kinds distinguished (fact, preference,
inference, plan, task, state, summary); permission-checked writes with approval when sensitive/
durable/user-visible/external/security-relevant; user corrections never silently overwritten;
deletions explicit, auditable, and recoverable when practical; autonomous/background work cannot
expand its own memory access; memory exposes stable contracts, not storage internals.

## Options considered

1. **One governed Memory Authority with contracts-over-storage (chosen).** A single, single-
   writer authority defining contracts, classification, provenance, redaction, permissions, and
   lifecycle, kept separate from audit. Strongest consistency and safety; conforms to PRIME;
   modest documentation cost; storage deliberately deferred.

2. **Let each plane manage its own memory (rejected).** *Rejected:* fragments truth and authority
   (PRIME §8), produces inconsistent redaction/provenance, and creates competing stores — the
   exact failure the single-authority rule prevents.

3. **Give agents durable memory ownership (rejected).** *Rejected:* agents are bounded proposers
   under orchestration (Overview §5; Secrets Policy §45); durable agent-owned memory becomes an
   ungoverned, secret-leaking store outside the single writer.

4. **Use tool-local memory as system memory (rejected).** *Rejected:* tools are adapters with no
   business logic or durable ownership (Overview §17); promoting transient tool state to system
   memory hides truth in adapters and bypasses governance.

5. **Treat logs or audit trails as memory (rejected).** *Rejected:* conflates the Audit Authority
   with the Memory Authority; audit is the canonical record of activity owned by Observability,
   not a knowledge store. Merging them would put raw, unredacted, secret-bearing records into
   memory — directly unsafe (§5, §66).

6. **Store raw execution context by default (rejected).** *Rejected:* raw context routinely
   contains secrets and sensitive data; default-storing it makes memory a hidden, unredacted log
   (§67) and violates the redaction and no-secret rules.

7. **Implement memory before defining permissions and redaction (rejected).** *Rejected:*
   contradicts "verification before execution" (PRIME §14–§15) and would persist data before the
   controls that keep it safe exist; permissions and redaction (ADR-0002) must precede memory.

8. **Choose storage technology before defining contracts (rejected).** *Rejected:* binds the
   design to a vendor/store prematurely (PRIME §8 — contracts over implementations); contracts
   must be stable first so storage can change beneath them without breaking consumers.

## Consequences

- **Positive:** one governed home for durable knowledge with consistent provenance, redaction,
  and permissions; a hard memory↔audit boundary; no competing stores; safe foundation for agent/
  workflow/autonomous memory and memory-backed execution.
- **Negative / cost:** up-front contract, redaction, and single-writer work before durable memory
  features can proceed; capability gated behind these controls, slowing short-term delivery by
  design.
- **Neutral:** storage technology and concrete data model are deferred to later ADRs; this ADR
  adopts the *specification*, not a database.

## Impact

- **Security:** forbids raw secrets/credentials/approval-tokens/audit/security-events and (by
  default) raw execution context in memory; mandates redaction before write/index/summarize/
  export/display including failure paths; permission-checked, deny-by-default access. No secret
  value appears in this ADR or the spec.
- **Architecture:** establishes the single-writer Memory/Knowledge plane at `core/memory/` and the
  explicit separation from the Observability/Audit authority; references audit only by safe
  handle/redacted metadata.
- **Operational:** defines lifecycle, versioning, conflict resolution, user-correction priority,
  deletion/archival/expiration, fail-closed and recovery behavior; memory operations are
  observable through Observability, not a memory-owned log.
- **Performance:** redaction, provenance, and single-writer serialization add bounded overhead at
  write/read boundaries; acceptable and measured where budgets exist (PRIME §12). No budget is
  asserted without measurement.
- **Maintainability:** contracts-over-storage lets storage evolve without breaking consumers; one
  authority removes duplicated, divergent memory logic.
- **Testing:** mandates required, blocking suites — single-writer, consistency, redaction,
  provenance/confidence, permissions, memory≠audit, and user-correction preservation (Strategy
  §21).

## Rollback strategy

This ADR records a specification and adds no executable code, database, schema, or secret
material, so reversal is low-cost: it is reversed by a superseding ADR that withdraws or replaces
the spec, with the governing document updated and history preserved (`ADR_PROCESS.md` §16–§17).
Because the decision *adds* governance rather than enabling capability, reversing it does not
create an unsafe state; any controls already implemented under it would be retired deliberately.

## Validation strategy

- Confirm the spec conforms to PRIME, the Architecture Overview, the Approval Gate spec, Project
  Structure, the testing strategy, and the secrets/permissions policy, and that the Memory↔Audit
  separation is preserved (no critical contradiction found during authoring).
- Validate in practice via the spec's readiness checklist (§92) and migration phases (§89): the
  decision is "validated" when, at each phase, the corresponding contract, redaction, single-
  writer, permission, and lifecycle controls exist and their required tests pass before the
  capability they gate is enabled.
- Acceptance is a human review step (`ADR_PROCESS.md` §15); it is not self-approved. No real
  secret is used in any validation.

## Related documents

- `docs/architecture/MEMORY_AUTHORITY_SPEC.md` (the adopted specification)
- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md`
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`
- `docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md`
- `docs/architecture/SECRETS_AND_PERMISSIONS_POLICY.md`
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`
- `docs/adr/ADR-0002-secrets-and-permissions-policy.md`

## Supersedes

None.

## Superseded by

None.
