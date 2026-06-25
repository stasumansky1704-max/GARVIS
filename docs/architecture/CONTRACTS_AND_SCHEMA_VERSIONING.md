# GARVIS — Contracts & Schema Versioning Specification

**Status:** Binding platform-governance specification (governed by ADR-0005) · **Scope:** Every
inter-plane and cross-cutting contract in GARVIS · **Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md),
[`ADR_PROCESS.md`](./ADR_PROCESS.md),
[`TESTING_AND_VERIFICATION_STRATEGY.md`](./TESTING_AND_VERIFICATION_STRATEGY.md),
[`SECRETS_AND_PERMISSIONS_POLICY.md`](./SECRETS_AND_PERMISSIONS_POLICY.md),
[`MEMORY_AUTHORITY_SPEC.md`](./MEMORY_AUTHORITY_SPEC.md),
[`OBSERVABILITY_AND_AUDIT_SPEC.md`](./OBSERVABILITY_AND_AUDIT_SPEC.md). Where this and those
conflict, the constitution prevails; the conflict is reported, not silently resolved.

Vendor-neutral: no products, schema libraries, codegen tools, databases, models, APIs, or
temporary implementation detail, and **no implementation code, schemas-as-code, or generated
types**. It defines *what must be true* about contracts and their versioning, not *how they are
encoded*. It contains and references **no secret values**.

---

## 1. Purpose

- Define how GARVIS specifies, owns, versions, and evolves the contracts that cross plane
  boundaries, so capability can grow without breaking consumers or fragmenting truth.
- Make every safety-relevant exchange (approval, permission, memory, audit, tool, agent,
  workflow) an explicit, versioned, redaction-aware contract.

## 2. Scope

- **In scope:** contract ownership, the single registry, naming/numbering, versioning and
  compatibility, deprecation/sunset/migration, validation, per-plane and per-domain contracts,
  required safety fields, boundary/import/anti-duplication rules, and the tests that prove them.
- **Out of scope:** the encoding format, schema technology, and any generated artifact
  (deliberately unspecified); business logic (never lives in a contract, §88, §90).

## 3. Non-goals

- Not a schema-library or codegen selection; not type generation; not a data model. Not a place
  for business logic.
- Not a guarantee by documentation alone — contracts are enforced by validation and proven by
  tests (§32–§36, §33).

## 4. Why GARVIS needs explicit contracts

- The most damaging failures live at boundaries; ad-hoc payloads between planes hide drift,
  duplicate authority (PRIME §8), and let unsafe or secret-bearing shapes cross unchecked.
- Explicit, versioned contracts make boundaries stable, evolvable, testable, and redaction-aware,
  and let storage/implementation change beneath them without breaking consumers.

## 5. Contract vs schema vs type vs interface

- **Contract** — the binding, versioned agreement about what crosses a boundary (the
  architecture boundary itself).
- **Schema** — the structural definition of a contract's shape (its fields/classification),
  expressed conceptually here, encoded elsewhere.
- **Type** — a language-level realization of a schema for a consumer/producer; downstream of the
  contract, never the source of truth.
- **Interface** — the operational surface (events/commands/queries) through which a contract is
  exchanged.
- The **contract is authoritative**; schemas, types, and interfaces derive from it, never the
  reverse.

## 6. Relationship to GARVIS PRIME

- Implements PRIME §4 (explicit contracts, single source of truth, determinism at boundaries) and
  §8 (contracts over implementations, one authority per capability).

## 7. Relationship to Architecture Overview

- Realizes the Overview's "explicit contracts" and "planes interact only through declared
  interfaces" (Overview §4, §28–§29); contracts are the declared interfaces.

## 8. Relationship to Approval Gate Spec

- The approval request and approval decision are first-class versioned contracts (§62, §85);
  contract validation failures fail closed for gated actions (§35).

## 9. Relationship to Project Structure

- Contracts live in the single `contracts/` authority (Project Structure §26); types/interfaces
  in `shared/` derive from them; no plane copies or forks a contract (§17, §93).

## 10. Relationship to ADR Process

- Contract **breaking changes** require an ADR or a documented contract change record (§23, §38).
  This spec is adopted via **ADR-0005**.

## 11. Relationship to Testing and Verification Strategy

- The strategy mandates contract tests at every boundary (Strategy §15). This spec defines what
  those tests verify (§33–§34); contract changes must be testable (§32).

## 12. Relationship to Secrets and Permissions Policy

- Contracts **never expose raw secrets**; sensitive fields are handle/redacted (§46, §88).
  Permission-scope is a versioned contract (§63, §84).

## 13. Relationship to Memory Authority Spec

- Memory records and references are versioned contracts (§64, §86); contracts carry provenance/
  classification metadata, never raw memory content beyond contract scope (Memory Spec §77).

## 14. Relationship to Observability and Audit Spec

- The audit record and audit references are versioned contracts (§65, §87); they carry handles/
  redacted metadata only and never raw audit payloads (Audit Spec §26, §66).

## 15. Core principles

- **Contracts are architecture boundaries, not convenience types** (§88).
- **One source of truth per contract; one registry; no competing versions** (§17–§18).
- **Versioning is explicit and visible** (§21); compatibility is classified (§22).
- **No business logic in contracts or shared types** (§88, §90).
- **Safety fields are mandatory where applicable** (redaction status, sensitivity/risk class,
  correlation id, idempotency key, dependency-chain references; §82–§87).
- **No raw secrets/credentials/tokens/execution-context/audit-payloads in any contract** (§88).
- **Fail closed on contract validation failure** for security-relevant or gated actions (§35).

## 16. Contract ownership model

- Each contract has **exactly one owning authority** responsible for its definition, versioning,
  and deprecation. Cross-cutting contracts (approval, permission, memory, audit) are owned by
  their respective core authorities; inter-plane contracts are owned at the platform level.
- Consumers depend on a contract version; they do not redefine, fork, or extend it privately
  (§93).

## 17. Single source of truth policy

- A contract is defined **once**, in the registry; all producers and consumers reference that
  single definition. Copies, forks, or parallel "compatible" redefinitions are forbidden.

## 18. Contract registry policy

- All contracts live in one governed registry (the `contracts/` authority). The registry is
  discoverable, versioned, and the only authoritative home; nothing consumes a contract that is
  not registered.

## 19. Contract naming conventions

- Contracts are named by **domain and purpose**, vendor-neutral and stable (e.g., an approval
  request, a permission scope, an audit record). Names describe the boundary concept, not an
  implementation or vendor.

## 20. Contract numbering conventions

- Each contract has a stable identifier; versions are numbered explicitly and monotonically per
  contract. Identifiers are never reused for a different concept; a renamed concept is a new
  contract, not a silent rename.

## 21. Contract versioning model

- Every contract carries an **explicit, visible version**. A version conveys compatibility intent
  (§22): incompatible (breaking) changes increment the major version line; compatible additions
  increment a minor line; clarifications that do not change shape are non-version-affecting.
- Producers and consumers always negotiate or declare the contract version in use; "unversioned"
  is not a valid state for a boundary contract.

## 22. Compatibility model

- Compatibility is classified per change: **backward-compatible** (existing consumers keep
  working), **forward-compatible** (older consumers tolerate newer producers), or **breaking**
  (neither holds).
- Each contract states its compatibility guarantees; a change is classified before it ships and
  the classification is recorded.

## 23. Breaking change policy

- A **breaking change requires an ADR or a documented contract change record** (§38), a new major
  version, a migration path (§27), and a deprecation window for the prior version (§25).
- Breaking changes never silently replace a prior version; both coexist through the migration
  window.

## 24. Non-breaking change policy

- Backward-compatible additions (new optional fields, new tolerated values) increment the minor
  line, are documented, and must not change the meaning of existing fields or weaken a safety
  field.

## 25. Deprecation policy

- A superseded contract/version is marked **deprecated** with its replacement and a sunset
  horizon; it **remains documented and usable until safely removed** (§26).
- Deprecation is announced through the registry and recorded; consumers are given the migration
  path before removal.

## 26. Sunset policy

- A deprecated contract/version is removed only after its sunset horizon, once no required
  consumer depends on it (verified), and the removal is recorded. Removal never strands a
  consumer without a migration path.

## 27. Migration policy

- Every breaking change ships with a migration path describing how producers/consumers move from
  the old version to the new, including any dual-support window. Migration is reversible where
  practical and recorded.

## 28. Backward compatibility requirements

- Within a major version, existing required fields and their meanings do not change; additions
  are optional and ignorable by older consumers without loss of safety.

## 29. Forward compatibility requirements

- Consumers tolerate unknown **non-dangerous** additive fields (ignore-with-care), but **must not
  silently accept unknown dangerous fields** (§88) — those fail validation (§35).

## 30. Consumer compatibility requirements

- A consumer declares the contract versions it accepts and validates incoming payloads against
  them; it rejects payloads it cannot safely interpret rather than guessing.

## 31. Producer compatibility requirements

- A producer declares the contract version it emits and **must not silently omit required safety
  fields** (§88); omission of a required safety field is a validation failure, not a default.

## 32. Validation requirements

- Every boundary payload is validated against its declared contract version. Validation covers
  required fields, classification fields, and redaction status.
- **Contract changes must be testable**; an untestable contract is incomplete.

## 33. Contract testing requirements

- Each contract has tests proving producers and consumers honor it across supported versions, and
  that breaking changes are detected (Strategy §15). Cross-version compatibility is tested.

## 34. Schema testing requirements

- The structural shape (schema) of each contract version is tested for required/optional fields,
  classification, and that forbidden content (§88) cannot appear.

## 35. Runtime validation policy

- Payloads are validated at runtime at trust/plane boundaries. **Validation failure fails closed
  for security-relevant or gated actions** (no execution; Gate Spec §35); unknown dangerous fields
  and missing required safety fields are hard failures.

## 36. Build-time validation policy

- Where feasible, contract conformance is checked at build/integration time so drift is caught
  before runtime; build-time checks supplement, never replace, runtime validation for safety.

## 37. Documentation requirements

- Every contract version is documented in the registry: purpose, fields and classifications,
  version, compatibility, deprecation status, and owner. Undocumented contracts are defects.

## 38. ADR requirements for contract changes

- **Breaking changes require an ADR or a documented contract change record**; the change states
  rationale, compatibility classification, migration path, and rollback (ADR Process §9 fields).
  Non-breaking changes are documented in the registry.

## 39. Contract lifecycle

```
Draft → Proposed → Active (versioned) → Deprecated → Sunset/Removed
                         └→ superseded by a new version (both coexist through migration)
```

- Each transition is recorded; Active contracts are immutable in shape (changes create a new
  version), mirroring ADR immutability discipline.

## 40. Contract review process

- A proposed contract/version is reviewed for boundary fit, absence of business logic, presence
  of required safety fields, redaction support, compatibility classification, and conformance to
  this spec and PRIME.

## 41. Contract approval process

- Adoption of a new contract or a breaking version requires explicit human approval via the ADR
  process (ADR Process §15); automation does not self-adopt contracts.

## 42. Contract amendment process

- An Active contract's shape is not edited in place; amendments create a new version (§21). Non-
  shape clarifications to documentation are permitted and recorded.

## 43. Contract supersession process

- A new version supersedes a prior one with explicit links; the prior version is deprecated, not
  deleted, and remains documented until sunset (§25–§26). History is preserved.

## 44. Contract rollback expectations

- A problematic new version can be rolled back to the prior Active version where the migration
  window still supports it; rollback is recorded. Contracts add governance, not capability, so
  rollback does not create an unsafe state.

## 45. Contract security requirements

- Contracts carry only what a boundary needs; they encode classification and redaction status so
  downstream handling is safe. Security-relevant contracts (approval, permission, audit) have the
  strictest validation and fail-closed behavior.

## 46. Contract redaction requirements

- Contracts **support redaction**: sensitive fields are represented by handles/redacted forms,
  and a **redaction_status** field confirms redaction occurred before the payload crossed the
  boundary (Secrets Policy §32; Audit Spec §62).

## 47. Contract privacy requirements

- Personal/sensitive data in contracts is minimized, classified (§83), and never placed in
  identifiers or correlation fields; privacy classification travels with the data.

## 48. Contract observability requirements

- Contract usage at boundaries is observable (which version, validation outcome) through the
  Observability Plane, by reference and without secrets (Audit Spec §83).

## 49. Contract audit requirements

- Security-relevant contract exchanges (approval, permission, execution) are auditable by handle/
  redacted metadata; the audit references the contract version used (Audit Spec §26).

## 50. Contract performance considerations

- Validation overhead is bounded and measured where budgets exist (PRIME §12); safety validation
  for gated actions is on the critical path and is not skipped for performance.

## 51. Contract storage and publication policy

- Contracts are stored and published from the single registry; publication makes a version
  discoverable to consumers. In a multi-repo layout the registry is a **versioned shared
  dependency**, never copied (Project Structure §5, §32).

## 52. Generated artifacts policy

- Types/clients/validators generated from a contract are **derived artifacts**, never the source
  of truth; they are reproducible, clearly marked, excluded from authority, and regenerated from
  the contract (Project Structure §42). This document generates none.

## 53. Shared types policy

- Shared types realize contracts for consumers; they are **dependency-light and hold no business
  logic** (Project Structure §27). A shared type that decides or acts is a defect (§90).

## 54. Shared interfaces policy

- Shared interfaces expose contract-defined operations only; they declare versions and carry no
  behavior beyond the contract they represent.

## 55. Shared events policy

- Events are versioned contracts (§74) carrying correlation ids and classification; event
  consumers validate version and reject unsafe unknown fields.

## 56. Shared commands policy

- Commands (requests to act) are versioned contracts (§75) that reference the action, required
  permission scope, and (for gated commands) flow through the Approval Gate; a command is not an
  authorization.

## 57. Inter-plane contract policy

- All cross-plane exchange uses registered, versioned contracts; **no plane defines a competing
  version of the same contract** (§93). Planes depend on contract versions, not on each other's
  internals (Project Structure §29).

## 58. Interface Plane contracts

- The Interface consumes governed read/status contracts and produces intent/approval-relay
  contracts; it defines **no** business or platform contracts and never uses its own UI shapes as
  platform contracts (§71).

## 59. Cognition / Voice Plane contracts

- Produces **intent** contracts (versioned) with classification/confidence references; holds no
  execution or approval contracts.

## 60. Orchestration Plane contracts

- Consumes intents; produces **proposed action** contracts to the Approval Gate; coordinates
  agent/tool contracts. It owns the orchestration-facing inter-plane contracts but not the core
  authority contracts.

## 61. Command / Execution Plane contracts

- Consumes **approved action** contracts (with token reference) and produces **execution result/
  outcome** contracts; raw execution context is never a contract field (§88).

## 62. Approval Gate contracts

- The **approval request** and **approval decision** are explicit versioned contracts (Gate Spec
  §20–§21), carrying action/decision ids, risk/sensitivity class, permission-scope reference,
  redaction status, idempotency key, and dependency-chain references; the **token is referenced by
  handle, never embedded** (§85).

## 63. Permission contracts

- **Permission scope** is an explicit versioned contract (§84): the scoped capability, expiry, and
  revocation references; permission ≠ approval is preserved (the two are distinct contracts).

## 64. Memory contracts

- **Memory records and references** are explicit versioned contracts (Memory Spec §77): record
  kind, classification, provenance, confidence (where applicable), and a memory reference handle;
  **no raw secrets or raw memory content** beyond the contract's governed scope.

## 65. Observability and Audit contracts

- The **audit record and audit reference** are explicit versioned contracts (Audit Spec §26): all
  fields are handle/redacted metadata; **no raw audit payloads, secrets, tokens, or execution
  context** (§88).

## 66. Agent contracts

- **Agent messages have explicit versioned contracts before durable orchestration** — proposals,
  role identity (actor), and references; agents define no private unversioned contracts (§93).

## 67. Tool contracts

- **Tool calls and tool results have explicit versioned contracts before real side effects** —
  carrying the approved action reference, required permission scope, and redacted parameters/
  results; tools define no private unversioned contracts.

## 68. Workflow contracts

- **Workflow definitions and workflow state have explicit versioned contracts before autonomous
  execution** — steps, dependency-chain references, scope/budget; workflow state contracts carry
  classification and redaction status.

## 69. Integration contracts

- **Integration adapters use contracts and must not leak vendor-native shapes into core logic**:
  adapters translate external shapes to/from core contracts at the edge; core never depends on a
  vendor-native shape (Overview §17).

## 70. Plugin contracts

- Plugins interact only through registered, versioned platform contracts; a plugin defines no
  private core contract and connects to the same authorities (Overview §20).

## 71. User-facing surface contracts

- User-facing surfaces consume governed, redacted view/contract shapes; **UI shapes are never used
  as platform contracts** (§88). Display shapes derive from contracts, not the reverse.

## 72. Internal platform contracts

- Internal cross-cutting contracts (approval, permission, memory, audit, intent, proposed/approved
  action) are owned by their authorities, strictly validated, and the basis all planes build on.

## 73. External integration contracts

- External-facing contracts are isolated behind the Integration Plane; their versions are managed
  independently of core contracts, and changes never propagate vendor shapes inward.

## 74. Event contract policy

- Events carry a version, event type, classification (risk/sensitivity), correlation id, and
  (where applicable) idempotency key and dependency-chain references; consumers validate before
  acting.

## 75. Command contract policy

- Commands carry a version, the action reference, required permission scope, and risk class; gated
  commands route through the Approval Gate; a command never carries an embedded token (§85).

## 76. Query contract policy

- Queries (read requests) are versioned, permission-scoped, and return redacted, classified
  results; queries never return forbidden content (§89).

## 77. State contract policy

- Durable/governed state contracts (memory, workflow) carry classification, provenance/ownership
  references, and redaction status; ungoverned scratch state is not a contract.

## 78. Error contract policy

- Errors are versioned contracts carrying coded reasons and redacted summaries — **no secrets, raw
  context, or stack payloads** (Audit Spec §33). Errors are safe to log and audit by design.

## 79. Idempotency contract policy

- Where retries/recovery apply, contracts carry an **idempotency key** so duplicates are
  detectable and de-duplicated (Gate Spec §26; Audit Spec §53).

## 80. Correlation contract policy

- Action-chain contracts carry a **correlation id** so request → approval → permission → execution
  → tool → memory → recovery → rollback is reconstructable (Audit Spec §52).

## 81. Dependency-chain contract policy

- Contracts carry **dependency-chain references** (parent/lineage) where actions depend on prior
  actions/approvals, enabling causal reconstruction (Audit Spec §54), especially for autonomous
  work.

## 82. Risk-classification contract policy

- Action/event contracts carry a **risk class** aligned to the Approval Gate taxonomy (Gate Spec
  §19); highest-risk-wins and conservative-on-uncertainty are honored downstream.

## 83. Sensitivity-classification contract policy

- Contracts carry a **sensitivity class** (public/internal/restricted) so downstream redaction and
  permission handling are driven by the data's classification (Secrets Policy §17).

## 84. Permission-scope contract policy

- Permission scope is referenced as a versioned contract (§63); actions carry the permission-scope
  reference they require, enabling permission checks without embedding standing capability.

## 85. Approval-token reference contract policy

- Contracts reference an approval by a **handle/reference**, never an embedded raw token; the token
  remains single-use and is consumed only by Execution (Gate Spec §22; §88 here).

## 86. Memory-reference contract policy

- Contracts reference memory by **safe handle**, never raw memory content; references carry
  classification so consumers handle them safely (Memory Spec §82).

## 87. Audit-reference contract policy

- Contracts reference audit records by **safe handle/redacted metadata**, never the raw audit
  record; canonical audit stays with the Audit Authority (Audit Spec §82).

## 88. What contracts must never contain

- Raw secrets, raw credentials, raw approval tokens, raw execution context, or raw audit payloads.
- **Business logic** (a contract describes shape, not behavior).
- Unredacted sensitive data, or unknown **dangerous** fields a consumer would act on blindly.
- UI/implementation-specific or vendor-native shapes as the authoritative contract.

## 89. What schemas must never expose

- Secret material, raw sensitive payloads, internal storage structures, or fields whose presence
  would let a consumer bypass redaction, permission, or approval.

## 90. What shared types must never own

- Business logic, decision-making, side effects, secrets, or a second copy of a contract. Shared
  types are a vocabulary, not a place to smuggle behavior (Project Structure §27).

## 91. Boundary rules

- A contract is exchanged only at declared plane boundaries; nothing reaches across a boundary
  except through a registered contract version. Internal shapes never leak across a boundary
  un-contracted.

## 92. Import rules

- Producers/consumers import from the single `contracts/`/`shared/` source; they do not import
  another plane's internals or a forked contract. No circular contract dependencies; the fix for a
  missing dependency is a contract, not a copy (Project Structure §29).

## 93. Anti-duplication rules

- **Contract duplication is a defect.** One definition per contract; competing versions of the
  same concept (across UI, voice, agents, tools, workflows, integrations, memory, audit) are
  forbidden and consolidated to a single source.

## 94. Current contract state

- There are **no governed contracts and no registry** today; the only existing surface exchanges
  data through ad-hoc, in-process shapes within one plane (the Interface). No versioning,
  validation, classification, or redaction-aware contracts exist, and no cross-plane contracts are
  defined because the other planes are not yet implemented here.

## 95. Target contract state

- A single governed `contracts/` registry holds every inter-plane and cross-cutting contract,
  each explicitly versioned with classified compatibility, required safety fields, redaction
  support, documentation, and tests; all planes/agents/tools/workflows/integrations consume one
  source of truth, with derived types/interfaces downstream.

## 96. Immediate rules

- New cross-boundary exchange uses an explicit, registered, versioned contract from the start; no
  ad-hoc payloads across (future) plane boundaries.
- No contract contains business logic, raw secrets, or unredacted sensitive data; safety fields
  are present where applicable; no duplicate/forked contracts.

## 97. Future rules

- After the registry and validation exist: runtime fail-closed validation for gated/security
  contracts; breaking changes only via ADR + migration; deprecation windows enforced; build-time
  conformance checks added.

## 98. Migration phases

- **Phase C0 — Registry + conventions:** stand up the single `contracts/` registry, naming/
  numbering, versioning and compatibility model; no encoding chosen.
- **Phase C1 — Core safety contracts:** define approval request/decision, permission scope, audit
  record/reference, and memory record/reference contracts with required safety fields, redaction,
  and tests.
- **Phase C2 — Validation + fail-closed:** runtime/boundary validation with fail-closed for
  gated/security-relevant contracts, with tests.
- **Phase C3 — Plane/capability contracts:** intent, proposed/approved action, execution result,
  tool call/result, agent message contracts, with tests.
- **Phase C4 — Workflow/integration/plugin contracts:** workflow definition/state, integration
  adapter, and plugin contracts; dependency-chain/correlation enforced, with tests.
- Each phase is gated by its tests; later phases never begin before earlier ones pass.

## 99. Blockers before execution work

- The approval request/decision, permission-scope, and execution-result contracts exist, are
  versioned, carry required safety fields (risk/sensitivity class, redaction status, correlation/
  idempotency, permission-scope and token references), and validate **fail-closed** (C1–C2).
- No command/execution path crosses a boundary without a registered, validated contract.

## 100. Blockers before autonomous work

- In addition to execution blockers: workflow definition/state and tool/agent contracts exist and
  are versioned, carry dependency-chain and correlation references, and validate fail-closed; no
  autonomous/background path uses a private or unversioned contract (§93).

## 101. Blockers before production release

- All boundary exchanges use registered, versioned, validated contracts; breaking-change/
  deprecation/migration policy is in force; contract tests (incl. cross-version) pass; proven that
  no contract carries forbidden content (§88) on any path including failure.

## 102. Architecture risks

- **No registry or validation yet** — until C1–C2 hold, "explicit versioned contracts" are intent,
  not fact (top risk).
- **Contract duplication/drift** — the same concept redefined across planes/tools (mitigated by
  §17, §93).
- **Vendor-native shape leakage** — external shapes propagating into core (mitigated by §69, §73).
- **Unsafe field handling** — consumers acting on unknown dangerous fields, or producers omitting
  safety fields (mitigated by §29, §31, §35).
- **Breaking changes without migration** — stranding consumers (mitigated by §23, §27).

## 103. Open decisions

- Encoding format and schema representation (future ADR; deliberately unspecified).
- Versioning identifier scheme details and the registry's concrete structure (relates to Project
  Structure §46).
- Negotiation model for contract versions between producers/consumers.
- Generated-artifact toolchain (derived only; future ADR).
- Deprecation/sunset horizons per contract class.

## 104. Readiness checklist

Before this spec is considered active:

- [ ] ADR-0005 reviewed and Accepted (currently Proposed).
- [ ] Single `contracts/` registry, naming/numbering, versioning + compatibility model defined
      (C0).
- [ ] Core safety contracts (approval, permission, audit, memory) defined with required safety
      fields, redaction, and tests (C1).
- [ ] Boundary validation with fail-closed for gated/security contracts (C2).
- [ ] Breaking-change/deprecation/migration policy in force; contract tests required and owned.
- [ ] Execution / autonomous / release blockers (§99–§101) ratified as gates.

## 105. Recommended next foundational document

**`docs/architecture/TOOL_PERMISSION_MODEL.md`** — with the cross-cutting authorities specified and
a contract/versioning discipline to express them against, the tool permission model is the next
per-capability refinement: it defines tool call/result contracts (§67) and the scoped, approval-
gated permission model tools operate under (Secrets Policy; Gate Spec). It is backlog ADR item #7
and the prerequisite for safe tool side effects. See the report for the recommended ordering.
