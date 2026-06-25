# GARVIS — Observability & Audit Specification

**Status:** Binding subsystem specification (governed by ADR-0004) · **Scope:** All evidence,
diagnostics, signals, and canonical audit in GARVIS · **Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md),
[`ADR_PROCESS.md`](./ADR_PROCESS.md),
[`TESTING_AND_VERIFICATION_STRATEGY.md`](./TESTING_AND_VERIFICATION_STRATEGY.md),
[`SECRETS_AND_PERMISSIONS_POLICY.md`](./SECRETS_AND_PERMISSIONS_POLICY.md),
[`MEMORY_AUTHORITY_SPEC.md`](./MEMORY_AUTHORITY_SPEC.md). Where this and those conflict, the
constitution prevails; the conflict is reported, not silently resolved.

Vendor-neutral: no products, log platforms, tracing/monitoring providers, databases, models,
APIs, or temporary implementation detail, and **no implementation code, schemas-as-code, or log
files**. It defines *what must be true* about observability and audit, not *how it is stored*. It
contains and references **no secret values**.

---

## 1. Purpose

- Define the single canonical authority for GARVIS audit and the governed system for
  observability (logs, metrics, traces, health, diagnostics, failure evidence) so that every
  consequential action is accountable, correlated, and redaction-safe.
- Make audit mandatory for gated and security-relevant actions, and keep it cleanly separate from
  memory.

## 2. Scope

- **In scope:** ownership, event emission/ingestion, classification, the canonical audit record,
  observability signals, redaction, retention/immutability/integrity, per-plane observability,
  correlation/causality, and the tests that prove it safe.
- **Out of scope:** storage technology, log/trace/monitoring tooling, and any concrete data model
  (deliberately unspecified); durable knowledge (owned by Memory, §6).

## 3. Non-goals

- Not a tooling selection, dashboard build, or schema-as-code. Not a memory system, a permission
  system, a workflow engine, business logic, or an execution system.
- Not a guarantee by documentation alone — the rules are enforced by mechanism and proven by
  tests (§84–§85).

## 4. Why GARVIS needs Observability and Audit

- GARVIS performs real, gated actions; without canonical, correlated, tamper-evident evidence,
  there is no accountability, no incident reconstruction, and no proof the Approval Gate held.
- One canonical Audit Authority gives every consequential action a single, trustworthy record;
  observability gives operators and tests the signals to see system state without leaking
  secrets.

## 5. Observability Authority vs Audit Authority

- **Observability** owns evidence and signals (logs, metrics, traces, health, diagnostics,
  failure evidence) — operational visibility.
- **Audit** owns **canonical records** of consequential actions — the system of record for
  accountability.
- Both live in the Observability Plane (Overview §3, §21) but are distinct concerns: audit is the
  authoritative, retained, integrity-protected record; general observability is broader, may be
  sampled, and is not the legal record. Audit records are derived through governed ingestion, not
  scraped from arbitrary logs.

## 6. Observability and Audit vs Memory

- **Audit ≠ Memory.** Canonical audit records belong to the Audit Authority, **not** Memory
  (Memory Spec §5).
- Memory may reference audit only by **safe handles or redacted metadata** through a governed
  interface; it never holds the raw audit record.
- Observability/Audit is **not** a knowledge store; it does not become a hidden memory system
  (§93).

## 7. Observability and Audit vs Approval Gate

- The Approval Gate *makes* decisions; Audit *records* them. Every Gate lifecycle transition and
  decision is auditable (Gate Spec §33; §68 here).
- **Observability/Audit never authorizes actions** and never approves; it records what the Gate
  decided.

## 8. Observability and Audit vs Permissions

- Audit records permission grants, denials, revocations, expirations, and scope changes (§69); it
  does **not** grant or check permissions. It is **not** a hidden permission system (§93).

## 9. Observability and Audit vs Agents

- Agents **emit** events through governed interfaces; they **do not write canonical audit records
  directly** (§22). The Audit Authority creates the canonical record from governed ingestion.

## 10. Observability and Audit vs Tools

- Tools emit events through governed interfaces; **tools do not write canonical audit records
  directly**. Tool activity is audited via the governed path, not by tool-owned logs of record.

## 11. Observability and Audit vs Workflows

- Workflows emit events through governed interfaces; **workflows do not write canonical audit
  records directly** and do not store workflow state in observability (§93). Audit records
  workflow actions with full dependency-chain context (§80).

## 12. Relationship to GARVIS PRIME

- Implements PRIME §18 (nothing acts silently; auditable, attributable; status reportable;
  no-secrets-in-telemetry; absence of observability ⇒ capability withheld) and §19 (fail loud).

## 13. Relationship to Architecture Overview

- Realizes the cross-cutting **Observability Plane** (Overview §3, §21): every plane emits; the
  audit trail is the home of record; observability never mutates state or gates decisions.

## 14. Relationship to Approval Gate Spec

- Provides the **audit trail** the Gate writes to (Gate Spec §33) and the home for its readiness
  evidence (Gate Spec §44). Audit failure fails closed for gated actions (§85, §94 below; Gate
  Spec §35).

## 15. Relationship to Project Structure

- The Authority lives at `core/observability/` (Project Structure §21) — the single home for
  telemetry and the audit trail; no plane keeps a private, divergent log of record (§40 there).

## 16. Relationship to ADR Process

- Adopted via **ADR-0004**. Changes occur by superseding ADR; storage/tooling decisions are their
  own future ADRs (kept out of this spec).

## 17. Relationship to Testing and Verification Strategy

- The strategy mandates observability/audit tests (Strategy §22) and secret-non-leakage across
  logs/audit/diagnostics/failure paths (§24, §49). This spec is the contract those tests verify
  against (§84–§85).

## 18. Relationship to Secrets and Permissions Policy

- Secrets are **never** logged, audited, traced, or placed in diagnostics/metrics/exports; audit
  uses handles and redacted metadata only (Secrets Policy §28, §31, §67). Redaction precedes every
  emission boundary (§62).

## 19. Relationship to Memory Authority Spec

- Audit is the canonical record Memory references by safe handle/redacted metadata (Memory Spec
  §82). Memory access events are emitted to Observability (Memory Spec §81); Observability does not
  read or write durable memory (§93).

## 20. Core principles

- **One canonical Audit Authority; one governed Observability system.**
- **Evidence, not control:** observability records and reports; it never authorizes, gates,
  grants, executes, or stores business state.
- **Audit ≠ Memory** (§6); **audit by handle/redacted metadata** (§62, §66).
- **Mandatory audit for gated/security-relevant actions; fail closed on audit failure** (§85).
- **Redact before any emission** (§62).
- **Correlate everything** across the action chain (§52, §54).
- **Tamper-evident in principle** (§58, §89), even where implementation is deferred.

## 21. Ownership model

- The Observability Plane owns observability signals and the canonical audit trail. Planes/agents/
  tools/workflows/integrations **emit** through governed interfaces; **they do not own canonical
  ingestion or audit-record creation** (§22).
- Ownership means: sole creator of canonical audit records, definer of the emission/ingestion
  contracts, enforcer of redaction/retention/integrity, and provider of governed read access.

## 22. Single canonical audit authority

- There is **one** canonical Audit Authority. Canonical audit records are created **only** by it,
  from governed ingestion of emitted events.
- **Agents, tools, and workflows must not write canonical audit records directly**; no plane keeps
  a competing canonical audit store. Multiple "logs of record" are forbidden.

## 23. Event emission model

- Any plane may **emit** structured events through a governed emission interface; emission is
  one-way and never blocks a decision the Gate already made (but see fail-closed, §85).
- Emitters redact before emitting (§62); emitters never fabricate actor identity or correlation
  ids.

## 24. Event ingestion model

- The Authority owns **canonical ingestion**: it validates, classifies, redacts (defensively
  again), correlates, and creates audit/observability records.
- Ingestion is the single point where emitted events become canonical records; ungoverned writes
  to the canonical store are rejected.

## 25. Event classification model

- Every event is classified by **category** (e.g., audit vs general-observability), **event_type**,
  **risk_class** (aligned to Gate Spec §19), and **sensitivity_class** (Secrets Policy §17).
- Security-relevant and gated-action events are classified as **audit** (mandatory, retained,
  integrity-protected); routine signals may be general observability.

## 26. Audit record model

The canonical audit record carries, conceptually (described, not coded; **no raw secret/credential/
token/execution-context values**):

- **audit_event_id** — unique id of this record.
- **audit_correlation_id** — ties all records for one action chain.
- **timestamp** — trusted time of the event (§91).
- **actor_id** / **actor_type** — who/what acted (human, system, agent role, tool, workflow,
  background job).
- **originating_plane** / **target_plane** — source and target of the action.
- **event_type** / **event_category** — what happened and its class (§25).
- **action_id** / **decision_id** — the proposed action and the Gate decision it relates to.
- **approval_token_reference** — handle to the approval (never the raw token).
- **permission_scope_reference** — handle to the permission scope involved.
- **memory_reference** — safe handle to related memory (never raw memory content).
- **resource_reference** — handle/identifier of the affected resource (redacted as needed).
- **risk_class** / **sensitivity_class** — classification (§25).
- **redaction_status** — confirmation that redaction was applied.
- **idempotency_key** — to correlate retries/dedup (§53).
- **parent_event_id** / **dependency_chain** — causal lineage (§54).
- **result** / **status** — outcome (e.g., proposed/approved/denied/executed/completed/failed/
  rolled-back/rejected).
- **error_code** — coded failure reason (no secret/sensitive payload).
- **rollback_reference** — handle to a related rollback record (§73).
- **redacted_summary** — human-readable, secret-free summary.
- **integrity_reference** — tamper-evidence handle (§58, §89).
- **retention_class** — retention policy for the record (§56).

## 27. Observability signal model

- General observability comprises **logs, metrics, traces, health, and diagnostics** (§28–§32),
  all redacted, structured, and correlated where applicable. Signals are for visibility, not the
  legal record; the canonical record is audit (§26).

## 28. Logs policy

- Logs are structured, redacted (§62), and correlated; **no secrets, raw credentials, raw tokens,
  raw execution context, or unredacted sensitive data** (§65). Raw execution context is never
  logged "for debugging."

## 29. Metrics policy

- Metrics are aggregate signals; **metric names and labels never carry secrets or sensitive
  identifiers** (§64). High-cardinality labels derived from sensitive data are forbidden.

## 30. Traces policy

- Traces correlate work across planes via correlation ids (§52); trace spans/attributes are
  redacted and never carry secrets or raw sensitive payloads.

## 31. Health check policy

- Health/readiness signals report component status without exposing secrets or internal sensitive
  detail; they support "the system can report its own status" (PRIME §18).

## 32. Diagnostics policy

- Diagnostics are redacted by default and **must not become a secret-exfiltration path** (§67,
  §94); a diagnostic that could reveal a secret is withheld. Diagnostic captures are not committed
  (Project Structure §42).

## 33. Error reporting policy

- Error reports use coded reasons and redacted summaries; **failure paths are redacted** (a common
  leak vector). No stack/context dump contains secrets or raw execution context.

## 34. Security event policy

- Security events (auth attempts, permission denials, token replay attempts, redaction failures,
  bypass attempts) are **audit** (mandatory, retained, integrity-protected) and recorded by handle/
  redacted metadata only.

## 35. Approval event policy

- Every Gate event — proposed, classified, approved, denied, expired, revoked, rejected — is
  audited with action/decision references, scope, risk class, and outcome (§68; Gate Spec §33).

## 36. Permission event policy

- **Permission grants, denials, revocations, expirations, and scope changes are auditable** (§69),
  by scope handle, with actor and reason.

## 37. Secret-handling event policy

- The *occurrence* of a secret-referencing action is audited by **handle and scope** only; **the
  secret value is never recorded** (§63, §66; Secrets Policy §31).

## 38. Memory event policy

- Governed memory operations (read/write/update/delete) emit events with safe memory handles (§19;
  Memory Spec §81); the audit holds references, never raw memory content.

## 39. Agent event policy

- Agent proposals and role actions are audited via governed emission; agents never write canonical
  audit directly (§9). Agent identity/role is recorded as actor.

## 40. Tool event policy

- Tool invocations and outcomes are audited via governed emission with the approving action's
  references; tools never write canonical audit directly (§10).

## 41. Workflow event policy

- Workflow steps are audited with full dependency-chain context (§54, §80); workflows never write
  canonical audit directly and never store workflow state in observability (§93).

## 42. Integration event policy

- Integration/adapter calls to external/local systems are audited (request/outcome by redacted
  reference); no secret or raw payload is recorded.

## 43. Execution event policy

- **Command execution attempts and outcomes are auditable** (§43 list). **Destructive actions are
  auditable before and after execution** (§71, §73). Token/action binding is recorded by reference.

## 44. Autonomous workflow event policy

- **Autonomous workflow actions are auditable with full dependency-chain context** (§80); the
  autonomous origin and its standing scope/budget are recorded; deferred/denied steps are audited.

## 45. Interface Plane observability

- The Interface emits interaction/render events (redacted) and may present user-visible history
  (§78) sourced from governed audit reads; it holds no canonical store and displays no secrets.

## 46. Cognition / Voice Plane observability

- The Cognition/Voice plane emits intent/interpretation events (redacted); captured input is never
  emitted with secrets or raw sensitive content.

## 47. Orchestration Plane observability

- Orchestration emits planning/routing/proposal events and is the natural origin of the
  correlation id for an action chain (§52); it emits, it does not own the canonical store.

## 48. Command / Execution Plane observability

- Execution emits attempt/outcome/rollback events bound (by reference) to the approved action;
  raw execution context is not emitted (§65).

## 49. Memory / Knowledge Plane observability

- Memory emits governed access events with safe handles (§38); Observability records them but does
  not read/write durable memory.

## 50. Integration Plane observability

- Integration emits adapter call events (redacted); the permission boundary's checks at this edge
  are observable.

## 51. Observability Plane self-observability

- The Observability/Audit system observes itself: ingestion health, redaction failures, integrity
  checks, and dropped/blocked events are themselves recorded, so gaps are visible (PRIME §18).

## 52. Correlation ID policy

- Every action chain carries one **audit_correlation_id** from origin (typically the user/voice
  request via Orchestration) through approval, permission, execution, tool, memory, recovery, and
  rollback. All related records share it.

## 53. Idempotency correlation policy

- The **idempotency_key** (Gate Spec §26) is carried on events so retries/recovery are correlated
  and de-duplicated in the record, not double-counted as new actions.

## 54. Causality and dependency-chain tracking

- Records carry **parent_event_id** and a **dependency_chain** so causal lineage is reconstructable
  end to end, including across autonomous/background steps.

## 55. Audit record lifecycle

```
Emitted → Ingested (validated, classified, redacted, correlated) → Recorded (canonical, immutable)
        → Retained (per retention_class) → Archived/Expired (governed, integrity preserved)
```

- A canonical record, once recorded, is immutable (§57); corrections are appended as new records
  referencing the original, never edits.

## 56. Audit retention policy

- Each record carries a **retention_class** with a defined retention horizon by category/
  sensitivity. Security/gated-action audit has the longest retention; routine observability may be
  shorter or sampled. Retention is governed, not ad hoc.

## 57. Audit immutability policy

- Canonical audit records are **append-only and immutable**; they are never edited or silently
  deleted. Supersession/correction is a new appended record linking the original.

## 58. Audit integrity policy

- Audit supports **tamper-evidence in principle** (§89): each record carries an integrity_reference
  enabling detection of alteration or gaps, even if the concrete mechanism is deferred.

## 59. Audit access policy

- Audit reads are permission-scoped and themselves audited; admin/operator access (§79) is broader
  than user-visible history (§78). No reader receives unredacted secrets.

## 60. Audit export policy

- Exports apply redaction first (§62), are permission-checked and themselves audited, and never
  export raw secrets/credentials/tokens/execution-context or unredacted sensitive data.

## 61. Audit deletion and redaction policy

- Canonical audit is not casually deleted; lawful/required deletion (e.g., privacy erasure) is
  explicit, governed, auditable, and preserves integrity/tamper-evidence of the remaining trail.
- Records are stored already-redacted; there is no "raw then redact later" path (§62).

## 62. Redaction requirements

- **Redaction happens before log creation, audit record creation, trace emission, metric labels,
  diagnostics, exports, and failure reports** — at every emission/persistence boundary.
- Redaction is fail-safe: if it cannot be applied, the content is withheld, not emitted or stored
  (Secrets Policy §32, §71).

## 63. Secrets handling in observability

- **Secrets are never logged, audited, traced, displayed, stored in diagnostics, or exported as
  raw values.** Only handles/redacted metadata appear (Secrets Policy §28, §31).

## 64. Sensitive data handling

- Sensitive/personal data is minimized, redacted, and never placed in identifiers, metric labels,
  trace attributes, or exports beyond need (Secrets Policy §7, §17).

## 65. What must never be logged

- Raw secrets, raw credentials, raw approval tokens, raw execution context, unredacted sensitive/
  personal data, and any content that bypassed redaction.

## 66. What must never be audited as raw value

- **Raw credentials, raw approval tokens, raw secret values, and raw execution context must never
  be stored as audit payloads.** Audit references them by safe handle/redacted metadata only.

## 67. What must never be sent to diagnostics

- Secrets, raw sensitive payloads, or raw execution context; **diagnostics must not become a secret
  exfiltration path** (§94).

## 68. Approval Gate audit requirements

- Every Gate proposal, classification (with rationale), decision, token issuance/consumption,
  expiration/revocation, execution outcome, and rollback is audited and correlated (Gate Spec §33);
  **denied actions are auditable**; **forbidden actions are auditable as rejected, never queued**.

## 69. Permission audit requirements

- Grants, denials, revocations, expirations, and scope changes are auditable with actor, scope
  reference, reason, and time (§36).

## 70. Memory audit reference requirements

- Audit references memory by safe handle/redacted metadata (§38); the canonical record never
  contains raw memory content, and Memory never holds the raw audit record (§6).

## 71. Failure evidence requirements

- Failures produce coded, redacted evidence correlated to the action chain; a failure that cannot
  be recorded is itself surfaced (fail loud, PRIME §19). Destructive-action failures are audited.

## 72. Recovery evidence requirements

- Recovery actions are audited (from which audited state recovery resumed, what was re-proposed,
  what was not re-executed), preserving correlation and idempotency (§53).

## 73. Rollback evidence requirements

- Rollbacks are audited as their own actions with a **rollback_reference** linking to the original;
  a "Rolled Back" outcome is recorded distinctly (Gate Spec §37).

## 74. Incident handling requirements

- Suspected exposure/bypass is recorded as a security incident (by handle/redacted metadata, never
  the secret), correlated, and retained; incident records support containment and review (Secrets
  Policy §73). Incident records never contain the exposed secret.

## 75. Alerting requirements

- Alerting is derived from observability signals/audit events without exposing secrets; alerts
  carry redacted summaries and correlation ids, not raw payloads.

## 76. Operational dashboard requirements

- Operational views present redacted, permission-scoped status/metrics/health; they surface no
  secrets and are not the canonical record (they read governed observability/audit).

## 77. Developer diagnostics requirements

- Developer diagnostics are redacted, reproducible, and non-secret; they aid debugging without
  capturing secrets or raw execution context (§67).

## 78. User-visible history requirements

- Users may see a redacted, permission-scoped history of their own actions sourced from governed
  audit reads; it is a view, not the canonical store, and never shows secrets.

## 79. Admin-visible audit requirements

- Operators/admins have broader, permission-scoped, themselves-audited access to the canonical
  trail for accountability and incident review; even here, secrets are redacted.

## 80. Autonomous workflow audit requirements

- Autonomous actions are audited with **full dependency-chain context** (§54), the autonomous
  origin, standing scope/budget, and every deferred/denied/approved step.

## 81. Background job audit requirements

- **Background jobs are auditable and must not bypass correlation, approval, permission, or
  redaction**; they carry correlation ids and emit through the governed path like any actor.

## 82. Observability for tests

- Tests can observe system behavior through the same governed signals; test observability is
  isolated/sandboxed and uses synthetic, non-sensitive data (Strategy §44).

## 83. Audit for tests

- Tests assert against audit completeness and correctness (every gated action recorded, correlated,
  redacted) without using real secrets; test audit never mixes with production canonical records.

## 84. Testability requirements

Required tests (Strategy §22, §24) prove:

- Every Gate decision and gated/security-relevant action produces a complete, correlated audit
  record (no-silent-action).
- **No secret/credential/token/execution-context** appears in logs, audit, traces, metrics,
  diagnostics, exports, or **failure reports** — redaction before every boundary.
- Audit uses handles/redacted metadata only; **audit ≠ memory** (no raw audit in memory; no raw
  memory in audit).
- Correlation/causality reconstructable end-to-end (request→orchestration→approval→permission→
  execution→tool→memory→recovery→rollback).
- Immutability/append-only and integrity/tamper-evidence hold.
- **Audit failure fails closed** for gated/security-relevant actions; **observability failure does
  not authorize execution**.
- Background/autonomous work cannot bypass correlation, approval, permission, or redaction.

## 85. Verification requirements

- These are **required, blocking** suites (Strategy §51–§53). Execution, integrations, agents,
  tools, memory-backed and autonomous workflows, and production operation are not enabled until the
  applicable audit/observability tests pass. **Audit failure fails closed** for gated/security-
  relevant actions; **observability failure must not authorize execution.**

## 86. Performance considerations

- Emission is low-overhead and asynchronous where safe, **except** that audit for gated/security-
  relevant actions is on the critical path and fail-closed (§85). Redaction/correlation overhead is
  bounded and measured where budgets exist (PRIME §12). Sampling may apply to general observability,
  never to mandatory audit.

## 87. Storage considerations

- Storage technology is deferred to a later ADR. The store must support append-only, retention by
  class, integrity/tamper-evidence, and permission-scoped governed reads — behind stable contracts,
  not exposed as implementation detail.

## 88. Privacy considerations

- Personal/sensitive data is minimized and redacted across all signals and audit; retention
  respects privacy; lawful erasure is supported without breaking integrity of the remaining trail
  (§61).

## 89. Tamper-evidence requirements

- Audit is **tamper-evident in principle**: alteration, deletion, or gaps in the canonical trail
  are detectable via integrity references, even if the concrete mechanism is implemented later. A
  trail that cannot evidence its own integrity is incomplete.

## 90. Time and ordering requirements

- Events carry trusted timestamps and ordering metadata so a chain can be ordered reliably;
  correlation + causal links (§54) preserve order even across distributed emitters.

## 91. Clock and timestamp policy

- Timestamps come from a trusted time source; clock assumptions are explicit. Records are not
  back-dated; ordering does not rely solely on wall-clock equality.

## 92. Environment and deployment context policy

- Records capture non-sensitive environment/deployment context (e.g., which deployment/environment)
  to aid correlation, **without** secrets or sensitive configuration values.

## 93. What Observability must never own

- Durable business memory/knowledge; permission-granting/checking authority; workflow state as a
  system of execution; business logic; or any execution capability.
- It must not become a hidden memory, permission, or workflow-state system.

## 94. What Audit must never own

- Raw secrets, raw credentials, raw approval tokens, or raw execution context (handles/redacted
  metadata only).
- Canonical durable knowledge (that is Memory). A path where diagnostics/audit becomes a secret-
  exfiltration channel.

## 95. Migration path from current state

- **Current state:** there is **no governed observability or audit authority** and no canonical
  audit trail; the existing surface emits only ad-hoc developer console output, and historical
  verification relied on manual inspection. There is no redaction, correlation, retention,
  immutability, or integrity mechanism yet, and no separation realized between audit and memory.
- **Immediate rules (now):** no secret/raw-execution-context in any emitted output; no plane keeps
  a competing canonical audit store; nothing consequential is emitted without redaction; audit, as
  it is introduced, is by handle/redacted metadata only.
- **Phase O0 — Contracts:** define the emission/ingestion interfaces and the canonical audit record
  contract (kinds, fields, classification); no storage chosen.
- **Phase O1 — Redaction + correlation:** enforce redaction-before-everything and end-to-end
  correlation/causality, with tests.
- **Phase O2 — Canonical audit + immutability:** stand up the single Audit Authority with
  append-only, retention, integrity/tamper-evidence, and governed reads — with audit↔memory
  separation — with tests.
- **Phase O3 — Gated-action audit + fail-closed:** mandatory audit for Gate/permission/execution
  events with fail-closed semantics, with tests.
- **Phase O4 — Autonomous/background + dashboards/history:** full dependency-chain audit for
  autonomous/background work and redacted operator/user views, with tests.
- Each phase is gated by its tests; later phases never begin before earlier ones pass.

## 96. Architecture risks

- **No authority or tests yet** — until Phases O1–O3 hold, redaction, correlation, immutability,
  and fail-closed audit are intent, not fact (top risk).
- **Audit/memory blur** — the most damaging structural error; audit content drifting into memory,
  or memory becoming the audit store (mitigated by §6, §70, §94).
- **Secret leakage via logs/traces/metrics/diagnostics/failure paths** — the highest-frequency leak
  vector (mitigated by §62–§67, §84).
- **Best-effort audit on the critical path** — if gated-action audit is treated as optional, the
  Gate's accountability collapses (mitigated by §85 fail-closed).
- **Competing logs of record** — a plane/tool keeping its own canonical store (mitigated by §22).

## 97. Open decisions

- Storage technology and the integrity/tamper-evidence mechanism (future ADR; deliberately
  unspecified).
- Concrete audit record/data model and versioning (relates to the contracts/versioning decision).
- Retention horizons per category/sensitivity and the sampling policy for general observability.
- The governed interface by which Memory references audit metadata (coordinated with Memory Spec
  §82, §91 there).
- Trusted time source and ordering guarantees across distributed emitters.

## 98. Readiness checklist

Before this spec is considered active:

- [ ] ADR-0004 reviewed and Accepted (currently Proposed).
- [ ] Emission/ingestion contracts and the canonical audit record contract defined; storage left
      unspecified (O0).
- [ ] Redaction-before-everything and end-to-end correlation/causality defined + testable (O1).
- [ ] Single canonical Audit Authority with append-only/immutability/integrity and audit↔memory
      separation (O2).
- [ ] Mandatory, fail-closed audit for gated/security-relevant actions (O3).
- [ ] Required tests (§84) enumerated and owned; blockers below ratified as gates.

**Blockers before execution work:** redaction + correlation (O1) and canonical, immutable,
integrity-protected, fail-closed audit for Gate/permission/execution events (O2–O3); no command/
destructive action runs without before/after auditability. **Blockers before autonomous work:**
full dependency-chain audit for autonomous/background actions (§80–§81) with no bypass of
correlation/approval/permission/redaction, and their tests. **Blockers before production release:**
all of the above plus proven non-leakage across logs, audit, traces, metrics, diagnostics, exports,
and failure paths (§84), and operator/user history views that expose no secrets.

## 99. Recommended next foundational document

**`docs/architecture/CONTRACTS_AND_SCHEMA_VERSIONING.md`** — the audit record, memory contracts,
approval request/decision, intents, and inter-plane interfaces now all need a single governed
versioning discipline so their shapes can evolve without breaking consumers (Project Structure §26).
With the core cross-cutting authorities (Approval Gate, Secrets/Permissions, Memory, Observability/
Audit) specified, contract-and-schema versioning is the connective tissue they all depend on, and
should precede the per-capability specs (e.g., the tool permission model). See the report for the
recommended ordering.
