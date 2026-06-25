# GARVIS — Memory Authority Specification

**Status:** Binding subsystem specification (governed by ADR-0003) · **Scope:** All durable
memory, knowledge, and governed context in GARVIS · **Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md),
[`ADR_PROCESS.md`](./ADR_PROCESS.md),
[`TESTING_AND_VERIFICATION_STRATEGY.md`](./TESTING_AND_VERIFICATION_STRATEGY.md),
[`SECRETS_AND_PERMISSIONS_POLICY.md`](./SECRETS_AND_PERMISSIONS_POLICY.md). Where this and those
conflict, the constitution prevails; the conflict is reported, not silently resolved.

Vendor-neutral: no products, databases, vector stores, embedding providers, models, APIs, or
temporary implementation detail, and **no implementation code or schemas-as-code**. It defines
*what must be true* about memory, not *how it is stored*. It contains and references **no secret
values**.

---

## 1. Purpose

- Define the single governed authority for GARVIS memory, knowledge, governed context,
  retrieval, persistence, redaction, provenance, and lifecycle.
- Make durable memory consistent, attributable, redaction-safe, permission-checked, and clearly
  separate from audit/observability.

## 2. Scope

- **In scope:** ownership, access (read/write/update/delete), classification, provenance,
  confidence, lifecycle, contracts, consistency/durability/isolation, per-plane access, memory's
  interaction with permissions and the Approval Gate, and the tests that prove it safe.
- **Out of scope:** storage technology, indexing engines, and any concrete data model
  (deliberately unspecified); canonical audit trails (owned by Observability, §5).

## 3. Non-goals

- Not a database design, storage selection, or schema-as-code. Not a logging system, a
  permission system, an audit system, or a workflow engine.
- Not a guarantee by documentation alone — the rules are enforced by mechanism and proven by
  tests (§84–§85).

## 4. Why GARVIS needs one Memory Authority

- Multiple competing memory layers would fragment truth, duplicate authority (PRIME §8), and let
  secrets or unredacted content leak through an ungoverned store.
- One authority gives durable knowledge a single, governed home with consistent provenance,
  redaction, and permission rules, so every plane reads one truth and writes through one door.

## 5. Memory Authority vs Audit Authority

- **Memory Authority ≠ Audit Authority.** The Observability Plane / audit system owns the
  **canonical** audit trail (Gate Spec §33; Overview §21).
- Memory **must not own** raw audit logs, raw execution context, raw approval records, raw
  secrets, or security-event logs.
- Memory may **reference, summarize, or index allowed audit metadata only through governed
  interfaces**, and only by **safe handles or redacted metadata** — never the raw record.
- The two remain **separate authorities**; neither is the other's store of record.

## 6. Memory Authority vs Observability

- Observability captures *what happened* (events, telemetry, audit) as the system of record for
  activity. Memory holds *what is durably known* (facts, knowledge, governed state).
- Memory is not a hidden logging system (§66); it does not duplicate the event stream. It may
  hold derived, redacted summaries with provenance pointing (by handle) at observability, never
  the raw stream.

## 7. Memory Authority vs Knowledge Management

- "Knowledge" is a classification of memory content (§25), not a separate authority. All durable
  knowledge lives under the Memory Authority with provenance and confidence; there is no parallel
  knowledge store.

## 8. Memory Authority vs Agent Context

- Agent working context is **ephemeral** and local to a task; it is not durable memory. Agents
  **do not own durable memory** (§47); anything an agent must persist is written, permission-
  checked, through the Memory Authority.

## 9. Memory Authority vs Tool State

- Transient tool state within a single invocation is ephemeral and tool-local; it is **not**
  system memory. Tools **do not own durable memory** (§48); durable results are written through
  the Authority under permission.

## 10. Relationship to GARVIS PRIME

- Implements PRIME §21 (single memory authority; curated, durable, truthful; no competing layers;
  no secrets in memory; recalled memory verified before acted upon) and §4 (single source of
  truth).

## 11. Relationship to Architecture Overview

- Memory is the cross-cutting **Memory/Knowledge Plane** (Overview §3, §15): single writer, many
  readers via a defined interface; no plane keeps a competing durable store.

## 12. Relationship to Approval Gate

- Memory writes that are sensitive, durable, user-visible, external-facing, or security-relevant
  may require approval (§21, §57); memory never approves actions and stores no raw approval tokens
  (§28, §67).

## 13. Relationship to Project Structure

- The Authority lives at `core/memory/` (Project Structure §19) — the single writer of durable
  state; no surface or plane hosts a competing store (§32 there).

## 14. Relationship to ADR Process

- Adopted via **ADR-0003**. Changes occur by superseding ADR. Storage-technology and data-model
  decisions are recorded as their own future ADRs (kept out of this spec).

## 15. Relationship to Testing and Verification Strategy

- The strategy mandates memory consistency, single-writer ownership, redaction, and audit tests
  (Strategy §21). This spec is the contract those tests verify against (§84–§85).

## 16. Relationship to Secrets and Permissions Policy

- Memory holds **no raw secrets** and stores secret references by handle only (Secrets Policy
  §29, §70). Memory writes/reads are permission-checked (§58); redaction precedes write, indexing,
  summarization, export, and display (§30).

## 17. Core principles

- **One authority, single writer, many governed readers.**
- **Contracts over storage:** consumers depend on stable contracts, never on storage internals
  (§77).
- **Provenance always; confidence when inferred** (§31, §33).
- **Redact before persist or expose** (§30).
- **Permission-checked writes; approval when sensitive** (§21, §57).
- **Separate from audit** (§5); reference audit only by safe handle/redacted metadata.
- **User corrections are never silently overwritten** (§44).

## 18. Memory ownership model

- The Memory Authority **owns** all durable memory and knowledge. No plane, agent, tool,
  workflow, or integration owns a competing durable store (§47–§50, §66).
- Ownership means: sole writer, definer of contracts, enforcer of classification/redaction/
  provenance, and arbiter of lifecycle.

## 19. Single-writer rule

- Durable state is written by **exactly one** authority. Concurrent or competing writers are
  rejected; all writes pass through the Authority's governed write path (§21).
- Ephemeral, plane-local working state is permitted but is **not** memory and is never durable.

## 20. Read access model

- Reads are served through a **defined read interface** to permitted readers; readers receive
  redacted, classified content with provenance, never storage internals.
- Read access is permission-scoped (§58); a reader sees only what its permission allows.

## 21. Write access model

- Writes go only through the Authority's governed write path and are **permission-checked**.
- A write **may require approval** when the content is sensitive, durable, user-visible,
  external-facing, or security-relevant (§57; Gate Spec).
- Every write carries classification (§24), provenance (§31), and (where applicable) confidence
  (§33); redaction is applied first (§30).

## 22. Update access model

- Updates are governed, attributable, and versioned (§34); an update preserves prior versions
  (history is not erased) and records who/when/why.
- Updates to user-corrected content follow §44 (never silently overwritten).

## 23. Delete access model

- Deletion is **explicit, auditable, and recoverable when practical** (§41); never implicit or
  silent. High-impact deletions may require approval.
- "Delete" distinguishes soft-retire/archival (§43) from hard removal; hard removal of
  recoverable content is exceptional and recorded.

## 24. Memory classification model

Every durable item is classified by **kind**, at minimum:

- **Fact** — asserted truth with a source.
- **Preference** — a user/operator choice.
- **Inference** — derived/concluded content (carries confidence, §33).
- **Plan** — intended future action sequence.
- **Task** — a unit of work and its status.
- **State** — governed operational/project/workflow/execution state (§63–§65).
- **Summary** — condensed derivation of other content (carries confidence + provenance).

Memory **must distinguish** these kinds; conflating them is a defect.

## 25. Knowledge classification model

- Durable **knowledge** is Fact/Inference/Summary with explicit provenance and confidence; it is
  classified by sensitivity (public/internal/restricted) per the Secrets Policy (§17 there).
- Restricted knowledge is redaction-eligible and permission-scoped on read.

## 26. Context classification model

- **Governed context** (durable, shareable across sessions under permission) is memory.
- **Ephemeral context** (single task/session working set) is **not** memory and is not persisted
  by default; promoting ephemeral context to durable memory is an explicit, permission-checked
  write.

## 27. Sensitive memory classification

- Items touching personal/restricted data are marked sensitive, minimized, redaction-eligible,
  and permission-scoped; their write may require approval (§21).

## 28. Forbidden memory content

Memory **must never store**:

- Raw secrets or credentials (handles only).
- Raw approval tokens.
- Raw audit logs or security-event logs (owned by Observability).
- Raw execution context by default (§67).
- Anything whose storage would make memory a hidden logging, permission, or audit system (§66).

## 29. Secret handling in memory

- Memory holds **no raw secret values** — only handles/references (Secrets Policy §29, §70).
- Knowledge derived from secret-bearing operations is stored secret-free.

## 30. Redaction requirements

- **Redaction happens before memory write, before search/indexing, before summarization, before
  export, and before display.**
- Redaction is fail-safe: if it cannot be applied, the content is withheld, not stored or shown
  (Secrets Policy §32, §71).

## 31. Provenance requirements

- **Durable knowledge preserves provenance:** where it came from, when, and by what process
  (asserted vs inferred vs summarized).
- Provenance that would reference audit/secret material uses **safe handles or redacted
  metadata** only (§5, §82).

## 32. Source attribution requirements

- Each durable Fact/Inference/Summary attributes its source(s); unattributed durable knowledge is
  incomplete and is not treated as fact.
- External-content sources are marked as data-origin (PRIME §7); they never confer authority.

## 33. Confidence and uncertainty model

- **Inferred or summarized content carries an explicit confidence/uncertainty marker.**
- Low-confidence content is labeled and is not promoted to Fact without corroboration; recalled
  memory is verified before being acted upon (PRIME §21).

## 34. Versioning model

- Durable items are versioned; updates create new versions and preserve prior ones (history is
  not erased). Each version records who/when/why and supersession links.

## 35. Memory lifecycle

```
Created → Active → Updated (versioned) → Corrected (§44)
       → Archived (retired, retained)  → Deleted (explicit, auditable, recoverable when practical)
       → Expired (policy-driven)
```

- Every transition is governed and recorded (by reference; §81–§82).

## 36. Creation rules

- Creation is an explicit, permission-checked write with classification, provenance, and (if
  inferred) confidence; redaction is applied first.
- Ephemeral content is not created as durable memory unless explicitly promoted.

## 37. Retrieval rules

- Retrieval returns redacted, classified, attributed content to permitted readers via the read
  interface; results never expose storage internals or unredacted sensitive data.
- Retrieval is permission-scoped and bounded (§68).

## 38. Update rules

- Updates are versioned and attributable; they never erase prior versions or silently change
  user-corrected content (§44).

## 39. Merge rules

- Merging related items preserves each source's provenance and confidence; a merge that would
  drop attribution is rejected.
- Conflicting values are not blindly combined; they go to conflict resolution (§40).

## 40. Conflict resolution rules

- Conflicts are resolved by explicit rules (recency, source authority, user correction priority),
  with the outcome recorded and prior values retained as superseded versions.
- **User corrections take priority** over inferred/automated values (§44).

## 41. Deletion rules

- Deletion is explicit, attributable, and recoverable when practical (soft-retire preferred);
  hard removal of recoverable content is exceptional, may require approval, and is recorded.
- Deletion never silently drops user corrections or provenance history.

## 42. Expiration rules

- Items may carry expiration/retention policies; expired items are archived or removed per policy,
  recorded, and recoverable where practical.

## 43. Archival rules

- Archived items are retired from active retrieval but retained for history; archival is
  reversible where practical and recorded.

## 44. User correction rules

- **Memory must not silently overwrite user corrections.** A user correction is durable,
  attributed to the user, and takes precedence over inferred/automated content.
- Automated processes proposing to change user-corrected content must surface the conflict, not
  override it.

## 45. User authority over memory

- The user/operator is the **ultimate authority** over their memory: they may read (within
  policy), correct, request deletion, and override inferred content. The system can tighten but
  never override a user correction silently.

## 46. System authority over memory

- The Memory Authority may classify, version, redact, enforce lifecycle, and serve governed
  reads/writes within policy. It may **never** store forbidden content (§28), bypass permission/
  redaction, or override user corrections.

## 47. Agent authority over memory

- Agents **do not own durable memory.** They may read (scoped) and **propose** writes that the
  Authority permission-checks and (when sensitive) routes to approval. Agents never self-grant
  memory access or expand scope.

## 48. Tool authority over memory

- Tools **do not own durable memory.** Durable results are written through the Authority under
  permission; transient tool state is ephemeral and not system memory.

## 49. Workflow authority over memory

- Workflows **do not own durable memory.** Workflow state is governed memory only when explicitly
  classified and permitted (§64); workflows never create a private durable store and never expand
  their own memory access (§59).

## 50. Integration authority over memory

- Integrations **do not own durable memory** and hold no memory logic; durable results from
  external systems are written through the Authority, redacted and permission-checked.

## 51. Interface Plane memory access

- The Interface reads governed, redacted memory to render true state and may relay a user
  correction as a write proposal. It holds **no** durable store and never persists business memory
  independently.

## 52. Cognition / Voice Plane memory access

- The Cognition/Voice plane reads scoped context and proposes writes (e.g., a captured preference)
  through the Authority. It holds no durable store; an intent is not a memory write.

## 53. Orchestration Plane memory access

- Orchestration reads memory for planning and proposes writes through the Authority; it does not
  write durable state directly or keep a competing store.

## 54. Command / Execution Plane memory access

- Execution writes durable outcomes/state through the Authority (permission-checked), and reads
  scoped state as needed. It stores no raw execution context by default (§65, §67).

## 55. Integration Plane memory access

- Integration writes redacted, attributed external results through the Authority under permission;
  it never caches durable memory privately.

## 56. Observability Plane memory access

- Observability owns the canonical audit/event store and is **not** a memory reader/writer of
  record. Memory may reference observability data only by safe handle/redacted metadata through a
  governed interface (§5, §82); the two stay separate authorities.

## 57. Memory and Approval Gate interactions

- A memory write that is sensitive, durable, user-visible, external-facing, or security-relevant
  is routed through the Approval Gate; memory enforces this routing but never itself approves.
- Memory stores no raw approval tokens; it may store, by handle, the fact that an approval
  occurred for provenance.

## 58. Memory and permissions interactions

- **Memory reads and writes are permission-checked** (Secrets Policy §53). Permission ≠ approval;
  a permitted-but-unapproved sensitive write does not persist; deny-by-default on unknown
  permission.

## 59. Memory and autonomous workflows

- **Autonomous workflows must not expand their own memory access.** They operate under bounded,
  revocable, auditable memory scopes; sensitive durable writes defer to the human or are rejected
  (Secrets Policy §63).

## 60. Memory and background jobs

- **Background jobs must not bypass memory permissions.** Background/scheduled work holds only its
  granted memory scope and cannot accumulate or self-grant access.

## 61. Memory and project knowledge

- Project knowledge is durable memory (Fact/Inference/Summary) with provenance and confidence; it
  is the single governed home for "what GARVIS durably knows about the project," not a scattered
  set of notes.

## 62. Memory and user preferences

- Preferences are durable, user-attributed memory (kind: Preference); they take precedence over
  inferred defaults and follow user-correction rules (§44).

## 63. Memory and operational state

- Governed operational state (kind: State) is durable memory only when explicitly classified and
  permitted; it carries provenance and is not a hidden logging stream.

## 64. Memory and workflow state

- Workflow state is memory **only when explicitly governed** (classified, permission-scoped,
  redacted). Memory must not silently become a workflow-state system (§66); ungoverned workflow
  scratch state is ephemeral, not memory.

## 65. Memory and execution state

- Durable execution outcomes/state are written through the Authority, redacted and attributed.
  **Raw execution context is not stored by default** (§67); only governed, redacted, necessary
  state persists.

## 66. What memory must never own

- Raw audit logs, raw security-event logs, raw execution context, raw approval records, or raw
  secrets.
- A hidden logging system, a hidden permission system, or an ungoverned workflow-state system.
- Any competing durable store belonging to another plane.

## 67. What must never be stored in memory

- Raw secrets, raw credentials, raw approval tokens, raw audit logs, raw security events, and
  **raw execution context by default**.
- Unredacted sensitive/personal data; unattributed content treated as fact; content that bypassed
  permission or redaction.

## 68. Memory retrieval boundaries

- Retrieval is permission-scoped, redacted, and bounded in volume/scope; it never returns
  forbidden content (§67) or storage internals.
- Cross-scope retrieval requires the appropriate permission; unknown scope fails closed.

## 69. Memory write boundaries

- Writes are single-path, permission-checked, classified, attributed, redacted, and (when
  sensitive) approval-gated. Direct writes that bypass the Authority are forbidden.

## 70. Memory deletion boundaries

- Deletion is explicit, auditable, recoverable-when-practical, and (for high-impact cases)
  approval-gated; it never silently erases provenance or user corrections.

## 71. Memory export boundaries

- Export applies redaction first (§30), is permission-checked, and never exports forbidden content
  (§67) or raw sensitive data. Exports are attributable and bounded.

## 72. Memory import boundaries

- Imported content is treated as untrusted external data until validated (PRIME §7); it is
  classified, attributed as imported, redacted, and permission-checked before it becomes durable
  memory. Import never confers authority or bypasses redaction.

## 73. Memory indexing policy

- Indexing operates on **redacted** content only (§30); no index contains secrets, raw audit, or
  unredacted sensitive data. Indexes are an internal optimization behind the contracts, not a
  separate store of record.

## 74. Memory search policy

- Search returns permission-scoped, redacted, attributed results; it never surfaces forbidden
  content and never leaks via ranking/snippets. Search respects retrieval boundaries (§68).

## 75. Memory summarization policy

- Summarization redacts first, preserves provenance, marks the result as kind: Summary with
  confidence (§33), and never fabricates attribution. A summary never elevates inferred content to
  fact.

## 76. Memory compaction policy

- Compaction (condensing/aging content) preserves provenance and user corrections, records what
  was compacted, and remains reversible where practical; it never silently drops attributed facts
  or corrections.

## 77. Memory schema and contracts

- Memory exposes **stable, versioned contracts** (record kinds §24; required metadata:
  classification, provenance, source, confidence-where-applicable, timestamps, version,
  redaction-status), **not implementation-specific storage details**.
- Consumers depend on contract versions; storage may change beneath a stable contract without
  breaking consumers. (Contracts are described conceptually here; concrete schemas are deferred to
  implementation under their own ADR — not created in this document.)

## 78. Memory consistency model

- Reads reflect committed writes; no torn/partial state is observable. Concurrent writes are
  serialized through the single writer (§19); conflicting durable values resolve via §40, not by
  last-writer-wins on user-corrected content.

## 79. Memory durability model

- Committed durable memory survives restart and is recoverable; durability guarantees are provided
  by the storage mechanism (chosen later) behind the contracts. Ephemeral context is explicitly
  non-durable.

## 80. Memory isolation model

- Memory scopes (e.g., per user/project/domain) are isolated; cross-scope access requires explicit
  permission. One scope cannot read or corrupt another's durable memory.

## 81. Memory access logging

- Memory **access** is observable via the Observability Plane (not via a memory-owned log):
  governed reads/writes/deletes emit events to the audit/observability system by reference.
- Memory does not keep its own parallel access log (that would make it a hidden logging system,
  §66); it relies on Observability for the record of activity.

## 82. Memory audit references

- Memory may store **references** to audit records only as **safe handles or redacted metadata**
  through a governed interface; it never holds the raw audit record (§5).
- Such references are provenance, not a copy of the audit trail; the canonical record stays with
  Observability.

## 83. Memory observability requirements

- Governed memory operations are observable and attributable through Observability (correlated
  events), with **no secrets** in the emitted events (Secrets Policy §31). Absence of observability
  for a memory capability is grounds to withhold it.

## 84. Testing requirements

Required tests (Strategy §21) prove:

- **Single-writer ownership:** only the Authority writes durable state; competing writers rejected.
- **Consistency:** reads reflect committed writes; no torn state; conflict resolution honors user
  corrections.
- **Redaction:** no secret/raw-audit/raw-execution-context/unredacted-sensitive content is
  written, indexed, summarized, exported, or displayed — including on failure paths.
- **Provenance/confidence:** durable knowledge carries source/provenance; inferred/summarized
  content carries confidence.
- **Permissions:** reads/writes are permission-checked; deny-by-default; no self-grant/scope-
  expansion by agents/tools/workflows/background jobs.
- **Memory ≠ audit:** memory never stores raw audit/approval/security records; references are
  handle/redacted only.
- **User corrections** are never silently overwritten.

## 85. Verification requirements

- These are **required, blocking** suites (Strategy §51–§53). Durable memory, knowledge
  management, agent/workflow memory, autonomous memory usage, and memory-backed execution are not
  enabled until the applicable tests pass.

## 86. Failure behavior

- Memory **fails closed**: if classification, redaction, permission check, or attribution cannot
  be completed, the write is rejected and the read withholds, rather than persisting or exposing
  ungoverned content.
- A failed memory operation never silently drops or partially writes durable state.

## 87. Recovery behavior

- Recovery restores committed, consistent state; in-doubt writes are treated as not-committed and
  re-proposed, never assumed durable. Recovery never resurrects forbidden content or pre-redaction
  values.

## 88. Rollback expectations

- Durable changes are versioned and reversible to a prior version (§34); user corrections are
  preserved across rollback. High-impact deletions require a recovery path before they run (§70).
  Rollback is itself recorded (by reference).

## 89. Migration path from current state

- **Current state:** there is **no governed Memory Authority** and no durable memory in this
  surface; any state is ephemeral UI state. Elsewhere in the platform, a latent state layer exists
  as specification only (registries/reports), not as a governed store; there is no redaction,
  provenance, permission enforcement, or memory/audit separation yet.
- **Immediate rules (now):** no plane/agent/tool/workflow/integration creates a competing durable
  store; nothing durable is written without classification, provenance, redaction, and permission;
  no raw secrets/audit/execution-context in any persisted state.
- **Phase M0 — Contracts:** define memory contracts (kinds, metadata, classification) and the
  read/write interface; no storage chosen.
- **Phase M1 — Redaction + provenance:** enforce redaction-before-everything and mandatory
  provenance/confidence, with tests.
- **Phase M2 — Single-writer + permissions:** stand up the single-writer authority with
  permission-checked reads/writes and memory↔audit separation, with tests.
- **Phase M3 — Lifecycle + corrections:** versioning, conflict resolution, user-correction
  priority, deletion/archival/expiration, with tests.
- **Phase M4 — Governed advanced use:** indexing/search/summarization/compaction on redacted
  content, with tests; only then memory-backed execution.
- Each phase is gated by its tests; later phases never begin before earlier ones pass.

## 90. Architecture risks

- **No authority or tests yet** — until Phases M1–M2 hold, single-writer, redaction, and
  separation are intent, not fact (top risk).
- **Memory/audit blur** — the most damaging structural error; memory absorbing raw audit/execution
  context would create a hidden, unredacted store (mitigated by §5, §66, §82).
- **Competing stores** — a plane/agent/tool quietly persisting state (mitigated by §18, §47–§50).
- **Provenance/confidence erosion** — inferred content hardening into "fact" without markers
  (mitigated by §31, §33, §75).
- **Redaction gaps on export/summarization/failure paths** — leak vectors (mitigated by §30, §86).

## 91. Open decisions

- Storage technology and durability mechanism (future ADR; deliberately unspecified).
- Concrete memory contract/data model and versioning scheme (relates to Project Structure §26).
- Scope/isolation model granularity (per user/project/domain).
- Retention/expiration defaults per kind and per sensitivity.
- The governed interface by which memory references observability/audit metadata (coordinated with
  the forthcoming observability/audit spec).

## 92. Readiness checklist

Before this spec is considered active:

- [ ] ADR-0003 reviewed and Accepted (currently Proposed).
- [ ] Memory contracts (kinds + metadata) defined; storage left unspecified (M0).
- [ ] Redaction-before-everything and mandatory provenance/confidence defined + testable (M1).
- [ ] Single-writer authority with permission-checked access and memory↔audit separation (M2).
- [ ] Lifecycle, versioning, conflict resolution, user-correction priority defined (M3).
- [ ] Required tests (§84) enumerated and owned; blockers below ratified as gates.

**Blockers before execution work:** redaction + provenance (M1) and single-writer + permissions +
memory↔audit separation (M2) defined and tested; no durable write occurs without classification,
provenance, redaction, and permission. **Blockers before autonomous work:** bounded/revocable/
auditable autonomous memory scopes (§59), background-bypass prevention (§60), and their tests.
**Blockers before production release:** all of the above plus proven non-leakage across write,
index, search, summarization, export, display, and failure paths (§84).

## 93. Recommended next foundational document

**`docs/architecture/OBSERVABILITY_AND_AUDIT_SPEC.md`** — this spec deliberately keeps the
canonical audit trail with Observability and references it only by safe handle/redacted metadata
(§5, §82). The Observability/Audit Authority now needs its own specification so that the governed
interface Memory references is defined, the Approval Gate's audit requirements have a home, and
the memory↔audit boundary is enforceable on both sides.
