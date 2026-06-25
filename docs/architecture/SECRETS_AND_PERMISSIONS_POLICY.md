# GARVIS — Secrets & Permissions Policy

**Status:** Binding security policy (governed by ADR-0002) · **Scope:** All secrets, sensitive
data, and permissions across every GARVIS plane and surface · **Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md),
[`ADR_PROCESS.md`](./ADR_PROCESS.md),
[`TESTING_AND_VERIFICATION_STRATEGY.md`](./TESTING_AND_VERIFICATION_STRATEGY.md). Where this and
those conflict, the constitution prevails; the conflict is reported, not silently resolved.

Vendor-neutral: no products, services, models, APIs, or temporary implementation detail, and no
implementation code. This document contains **no secret values** and references none. It defines
*what must be true*, not *how to build it*.

---

## 1. Purpose

- Define how GARVIS classifies, stores, retrieves, redacts, and audits secrets and sensitive
  data, and how it grants, scopes, expires, and revokes permissions.
- Make secrets non-leakable and permissions least-privilege by policy, so the Approval Gate,
  tools, agents, workflows, memory, integrations, and autonomy can be built on a safe base.

## 2. Scope

- **In scope:** secret and sensitive-data handling; permission grant/scope/expiry/revocation;
  per-plane and per-capability permission rules; redaction and audit; incident/recovery; the
  tests that must prove non-leakage; migration from the current state.
- **Out of scope:** specific secret stores, vaults, providers, or tooling (deliberately
  unspecified); contents of any secrets-bearing location.

## 3. Non-goals

- Not a vault/tool selection. Not a substitute for the Approval Gate (run-time control) or
  permission enforcement; it defines the rules those mechanisms enforce.
- Not a guarantee of secrecy by documentation alone — the policy is enforced by mechanism and
  proven by tests (§76–§77).

## 4. Security principles

- **Least privilege** and **deny-by-default**: nothing is granted broader than its task; unknown
  permission state means "no."
- **No secret ever enters the repository, a log, memory, a prompt, a screenshot, a diagnostic,
  or documentation.**
- **Secrets are referenced by handle, never by value.**
- **Permission is not approval; approval is not permission** (§9).
- **Redact before exposure** — before any display, log, memory write, approval prompt, or audit
  record (§32, §71).
- **No self-granting:** no agent, tool, workflow, or integration expands its own authority.

## 5. Threat model

GARVIS must withstand, at minimum:

- **Accidental leakage** — a secret printed to a log, shown in a prompt, captured in a
  screenshot/diagnostic, or committed to version control.
- **Over-broad authority** — a standing or wildcard grant that lets a tool/agent/workflow do
  more than intended.
- **Self-escalation** — an agent/tool/workflow/integration granting or widening its own
  permissions, or self-authorizing an action.
- **Bypass** — a background/autonomous path acting without permission checks or the Approval
  Gate.
- **Injection** — content or tool output that attempts to direct privileged action (treated as
  data, not commands; PRIME §7).
- **Persistence/exfiltration** — a secret stored as a raw value in memory, audit, or knowledge
  systems and later read out.

## 6. Definition of secrets

A **secret** is any value whose disclosure enables impersonation, unauthorized access, or
unauthorized action — including credentials, tokens, keys, passwords, signing material, and
session artifacts. Secrets are treated identically regardless of source; this document handles
*authorization about* secrets, never the secret material itself.

## 7. Definition of sensitive data

**Sensitive data** is non-secret information whose exposure causes harm or violates privacy
(personal data, identifiers, private content). It is not a credential but is minimized,
redaction-eligible, and never placed in identifiers, URLs, logs, or memory beyond need.

## 8. Definition of permissions

A **permission** is a standing, scoped capability granted to a plane/role/tool/integration —
*what it is allowed to be able to do*. Permissions are explicit, bounded, expirable, and
revocable; an absent permission means the capability is not available.

## 9. Permission vs approval

- **Permission** = standing capability (what may ever be done). **Approval** = authorization for
  one specific action instance now (Approval Gate Spec §28).
- **Permission is not approval; approval is not permission.** Possessing a permission never
  authorizes an action; an approval never confers standing capability.
- **A valid action may require both** the relevant permission **and** a single-use approval.

## 10. Relationship to GARVIS PRIME

- Implements PRIME §9 (security, least privilege, no secret handling, no auto-approved
  credential/network) and §4 (capability isolation, single authority). PRIME's prohibitions on
  secret handling are absolute and reproduced here.

## 11. Relationship to Architecture Overview

- Aligns with the plane model: the **permission boundary is enforced in the Integration/
  Execution edge** (Overview §13), and authority flows from the human downward (Overview §12).

## 12. Relationship to Approval Gate

- The Gate's never-auto set (Gate Spec §15) and forbidden set (§16) are defined here in
  permission terms. The Gate enforces *approval*; this policy governs *permission* and *secret*
  handling. Both are required for gated actions.

## 13. Relationship to Project Structure

- Secrets never live in the repository in any directory (Project Structure §41); `config/` holds
  non-secret configuration that references secrets **by handle**. The permission boundary lives
  in `planes/integration/` (§54).

## 14. Relationship to ADR Process

- This policy is adopted via **ADR-0002**. Changes occur by a superseding ADR, not silent edits.
  Decisions about secret stores, permission models, or rotation are recorded as ADRs.

## 15. Relationship to Testing and Verification Strategy

- The strategy mandates secrets/redaction and permission-boundary tests (Strategy §17, §24,
  §49). This policy is the **specification those tests verify against** (§76–§77).

## 16. Secret classification model

Secrets are classified by blast radius and reversibility, at minimum:

| Class | Meaning | Default handling |
|---|---|---|
| **Low** | Limited, easily-rotated, low-impact | Handle-referenced; explicit approval to use |
| **High** | Broad access or hard to rotate | Explicit approval under strict constraints (§62) |
| **Critical** | Catastrophic / irreversible if exposed | Forbidden to automation, or human-only use |

Classification never lowers a secret's protection below the global no-leak rules (§22, §27–§32).

## 17. Sensitive data classification model

- **Public** (no restriction) · **Internal** (minimized, not external) · **Personal/restricted**
  (privacy-bearing; minimized, redaction-eligible, never in identifiers/URLs/logs/memory beyond
  need).
- Restricted data is handled with secret-grade redaction on any human-facing or persisted
  surface.

## 18. Permission classification model

By effect and risk, aligned to the Approval Gate risk classes (Gate Spec §19):

- **Read-internal** (low) · **Local-write** (reversible/in-scope) · **External-read** ·
  **External-write** · **Execution** · **Destructive** · **Credential-sensitive** · **Host/
  environment control**.
- Higher classes are narrower, shorter-lived, and require approval to *use* even when the
  permission stands.

## 19. Risk classification alignment

- Permission classes (§18) and secret classes (§16) map onto the Gate's classification so a
  single, consistent risk taxonomy governs both *what may be done* and *what authorization is
  required*. Highest-risk-wins and conservative-on-uncertainty apply (Gate Spec §18).

## 20. Least privilege policy

- Every grant is the **minimum** scope and lifetime that satisfies the task; broad/standing/
  wildcard grants are defects to be removed (PRIME §9).
- Capability is added by explicit, narrow grants, never by default breadth.

## 21. Deny-by-default policy

- When permission state is **unknown, ambiguous, or unverifiable, the answer is no** and the
  action does not proceed (fail closed; Gate Spec §35).
- New planes, tools, agents, workflows, and integrations start with **no** permissions.

## 22. No-secret-in-repo policy

- **Secrets are never committed** to version control, in any file, branch, or history.
- The repository holds non-secret configuration that references secrets by handle only.
- A secrets-bearing location that exists outside the repository is **out of scope and its
  contents are never inspected, copied, or displayed**; its mere existence is the only thing
  reported.

## 23. Local environment policy

- Local secret material lives outside version control and outside the repository working tree.
- Local configuration references secrets by handle; developers never paste raw secrets into
  code, docs, prompts, or commits.

## 24. Configuration policy

- Configuration is split into **non-secret config** (versioned) and **secret references**
  (handles resolved at run time outside version control).
- No configuration file contains raw secret values.

## 25. Secret storage policy

- Secrets are stored only in a designated secret-management mechanism (specified later by ADR),
  never in code, repo, logs, memory, audit, or documentation.
- At rest, secrets are protected by the storage mechanism; this policy forbids storing raw
  values anywhere else.

## 26. Secret retrieval policy

- Secrets are retrieved by handle, just-in-time, by the narrowest component that needs them,
  under the required permission and (for credential-sensitive use) explicit approval.
- Retrieved secret material is held for the minimum time and never persisted into memory, logs,
  or audit as a raw value.

## 27. Secret display policy

- **Secrets are never displayed** — not in interfaces, approval prompts, previews, diffs,
  diagnostics, or error messages. A surface that would reveal a secret is a defect that blocks
  the action.

## 28. Secret logging policy

- **Secrets are never written to logs** or telemetry. Log fields that could carry secret
  material are redacted before emission (§32). Raw execution context is never logged "for
  debugging."

## 29. Secret memory policy

- **Secrets are never stored as raw values in memory or knowledge systems.** Only handles/
  references are retained; the memory authority holds no secret material (§70).

## 30. Secret approval prompt policy

- **Approval prompts never display secret values.** A credential-sensitive action is described
  by handle, scope, and effect — never by the secret itself (Gate Spec §34).

## 31. Secret audit policy

- Audit records capture *that* a secret-referencing action occurred (by handle and scope), never
  the secret value. The audit trail is secret-free by construction.

## 32. Secret redaction policy

- **Redaction happens before display, logging, memory storage, approval prompts, and audit
  output** — at every boundary where data could be seen or persisted.
- Redaction is applied to requests, decisions, previews, diagnostics, and failure/error paths
  alike; a path that could reveal a secret on failure is a defect.

## 33. Credential access policy

- Access to credentials is **never auto-approved**; it requires explicit, per-instance human
  authorization under strict constraints, or is **forbidden** by the secret's class (§16, §62).
- Automation never enters credentials into fields or authenticates as a user (§65).

## 34. Token handling policy

- Authorization tokens (including approval tokens) are single-use, scoped, expiring, and
  revocable (Gate Spec §22–§24); they are never logged or displayed and never reused or widened.

## 35. Key rotation policy

- Secrets are rotatable; rotation is supported without code changes that embed values.
- Shared or potentially-exposed secrets are rotated; rotation procedures are defined by a later
  ADR and never require placing a value in the repo.

## 36. Revocation policy

- Permissions, grants, and credentials are **revocable at any time**; revocation takes effect
  immediately and cascades to dependent actions (Gate Spec §24).
- A revoked permission/credential cannot authorize new actions.

## 37. Expiration policy

- Grants, credentials, and tokens carry expirations; expired authority does not act. Long-lived
  standing authority is minimized and justified.

## 38. Temporary credential policy

- Short-lived, narrowly-scoped credentials are preferred over standing ones; temporary
  credentials expire automatically and are never persisted as raw values.

## 39. Permission grant policy

- Grants are explicit, attributable, scoped, and recorded. **No agent grants itself
  permissions; no tool self-authorizes; no workflow expands its own scope; no integration owns
  core permission logic.**
- Granting authority belongs to the human/operator and the core permission system, not to the
  component receiving the grant.

## 40. Permission scope policy

- Every permission states its scope (targets, operations, boundaries). Actions outside scope are
  unauthorized regardless of approval.
- Scope is the narrowest that satisfies the need; "all" scopes are forbidden absent explicit,
  recorded justification.

## 41. Permission expiration policy

- Permissions expire by default; renewal is deliberate and recorded. Indefinite permissions are
  exceptional and justified.

## 42. Permission revocation policy

- Any permission can be revoked immediately; revocation is enforced at the permission boundary
  (§54) and audited. In-flight actions relying on a revoked permission do not proceed.

## 43. User authority

- The human operator is the **ultimate authority**: only a human grants/approves
  credential-sensitive or never-auto actions, and a human may revoke any permission or deny any
  action. The system can tighten but never loosen §62, §65.

## 44. System authority

- The core permission system may classify, grant within policy, deny, expire, and revoke. It may
  **never** auto-grant credential access, self-escalate, widen a scope beyond policy, or
  authorize a forbidden action.

## 45. Agent authority

- Agents hold only the permissions explicitly granted to their bounded role; they **propose**,
  never self-grant, self-authorize, or approve (PRIME §7; Gate Spec §31).

## 46. Tool authority

- Tools act only with a valid approval **and** the required permission; a tool **never
  self-authorizes** and holds no permission logic of its own (Gate Spec §32).

## 47. Workflow authority

- Workflows operate under explicit, bounded, revocable, auditable permission scopes; a workflow
  **never expands its own scope** and routes every effect through the Approval Gate.

## 48. Integration authority

- Integrations enforce the permission boundary at the edge but **do not own core permission
  logic** (it lives in core); an adapter that decides permissions is a defect.

## 49. Interface Plane permissions

- The Interface may capture input, render true state, and relay approval prompts. It holds **no**
  execution, secret-access, or grant permissions. It never displays secrets (§27, §30).

## 50. Cognition / Voice Plane permissions

- The Cognition/Voice plane may interpret input and produce intents. It holds **no** execution,
  approval, secret-access, or grant permissions; an intent is not an authorization.

## 51. Orchestration Plane permissions

- Orchestration may plan, route, coordinate agents/tools, read for planning, and submit proposed
  actions to the Gate. It holds **no** permission to execute side effects directly or to write
  durable memory or grant permissions.

## 52. Command / Execution Plane permissions

- Execution may perform an approved action via Integration, using only the permissions that
  action requires, only with a valid single-use approval. It holds **no** standing broad
  capability and no grant authority.

## 53. Memory / Knowledge Plane permissions

- The memory authority is the single writer of durable state; readers are granted scoped read
  access. It stores **no raw secrets** (§29, §70) and grants no permissions.

## 54. Integration Plane permissions

- Integration enforces the permission boundary for external/local access. Adapters carry only
  the scoped permissions their target requires; they translate, they do not decide policy.

## 55. Observability Plane permissions

- Observability may read events from all planes and write the audit trail. It holds **no**
  mutate-state, execute, or secret-access permissions and stores no secret values (§31).

## 56. Approval Gate permission checks

- The Gate verifies, for each gated action, that the required **permission** exists **and** a
  valid single-use **approval** is present; missing either blocks execution.
- Permission absence or uncertainty fails closed (§21). The Gate never grants permissions; it
  checks them.

## 57. Filesystem permission policy

- Filesystem access is scoped to explicitly-granted paths; broad/root access is forbidden absent
  recorded justification. Writes outside the platform's own workspace are external-write (§60).

## 58. Network permission policy

- Network access is denied by default; only explicitly-granted destinations/operations are
  permitted. **Authenticated network actions are never auto-approved** (§33; Gate Spec §15).

## 59. Command execution permission policy

- **Command execution requires explicit permission and may still require approval.** Unscoped or
  arbitrary command execution is forbidden; permitted commands are narrowly scoped.

## 60. External write permission policy

- **External write actions require explicit permission and may still require approval**, and are
  never auto-approved. Scope is the specific target and operation only.

## 61. Destructive action permission policy

- **Destructive actions require explicit permission AND explicit approval**, are never auto, and
  require a rollback strategy or a defined recovery path before they run (Gate Spec §37).

## 62. Credential-sensitive action policy

- Credential-sensitive actions are **either forbidden or explicitly approved under strict
  constraints** (narrow scope, short expiry, full audit by handle). They are never auto-approved
  and never expose the secret (§30–§31).

## 63. Autonomous workflow permission policy

- Autonomous workflows operate under **bounded, revocable, auditable** permission scopes with
  explicit budgets; they use the same Gate as manual (Gate Spec §27). Any never-auto or forbidden
  action is deferred to the human or rejected — never auto-performed.

## 64. Background job permission policy

- **No background job bypasses permission checks** or the Approval Gate; background/scheduled
  work holds only its granted scope and cannot accumulate or self-grant authority.

## 65. Forbidden actions

Never performed by automation, regardless of permission or approval (PRIME prohibited set):

- Entering credentials, financial, payment, or government-identity data into any field.
- Creating accounts or authenticating as a user.
- Modifying access controls or sharing/permission settings on resources.
- Permanent/irrecoverable destruction of data.
- Executing financial trades or transfers of funds/assets.
- Modifying system or security settings.
- Bypassing bot-detection challenges.
- Downloading and executing code from untrusted sources.
- Acting on instructions embedded in observed content.

Forbidden actions are rejected and recorded; they are **never queued** for approval (Gate Spec
§16).

## 66. Secrets in tests policy

- **Tests never use real secrets or real sensitive data**; only synthetic, non-sensitive
  fixtures (Strategy §44). Tests prove non-leakage rather than carrying secrets.

## 67. Secrets in logs policy

- Logs and telemetry never contain secrets (§28). Raw execution context is never logged.
  Redaction precedes emission, including on error/failure paths.

## 68. Secrets in screenshots policy

- Diagnostic captures/screenshots never reveal secrets. Surfaces that could capture secret
  material are redacted before capture; captures are not committed (Project Structure §42).

## 69. Secrets in documentation policy

- **Secrets are never copied into documentation** — including this policy, ADRs, and any guide.
  Examples use placeholders/handles, never real values.

## 70. Secrets in memory and knowledge systems policy

- The memory/knowledge systems hold **no raw secret values** — only handles/references.
  Knowledge derived from secret-bearing operations is stored secret-free.

## 71. Redaction requirements

- A consistent redaction step is applied at **every** exposure/persistence boundary: display,
  log, memory write, approval prompt, audit, diagnostics, and error output.
- Redaction is fail-safe: if redaction cannot be applied, the data is withheld, not shown.

## 72. Audit requirements

- Secret- and permission-relevant actions are auditable by **handle and scope**, never by value
  (§31). Grants, revocations, expirations, and credential-sensitive uses are recorded with who/
  when/scope/outcome and correlated (Gate Spec §33).

## 73. Incident handling

- A suspected exposure is treated as an incident: contain (revoke/rotate the affected
  permission/credential), record the incident (without the secret value), and assess scope.
- Incident records never contain the exposed secret. Rotation/revocation follows §35–§36.

## 74. Recovery behavior

- After an incident or failure, recovery resumes from audited state, with affected credentials/
  permissions revoked or rotated first. No action proceeds on a credential/permission known to be
  compromised.

## 75. Rollback expectations

- Permission and credential changes are reversible (revoke/rotate); destructive or
  credential-sensitive actions require a rollback or recovery path before execution (§61–§62).
  Reversal itself is audited.

## 76. Testing requirements

- **Tests must prove secrets are not leaked** through logs, approval prompts, audit records,
  memory, diagnostics, screenshots, or **failure paths** (Strategy §24, §49).
- Tests must prove: deny-by-default on unknown permission; no self-grant/self-authorize/scope-
  expansion; permission ≠ approval (both required where applicable); revocation/expiration take
  effect; background/autonomous paths cannot bypass checks.

## 77. Verification requirements

- These tests are **required, blocking** suites (Strategy §51–§53). A capability touching
  secrets, credentials, or permissions is not enabled until its non-leakage and least-privilege
  tests pass.

## 78. Migration path from current state

- **Current state:** version control excludes environment/secret patterns (Phase 0 ignore
  rules); **no secrets are committed in the repository**; a secrets-bearing location exists
  outside the repository and is out of scope (its contents are never inspected). There is no
  permission-enforcement mechanism and no test layer yet to prove non-leakage; historically,
  non-UI experimentation referenced credentials informally outside this repo.
- **Immediate rules (now):** no secret in repo/logs/docs/memory/prompts/screenshots; secrets by
  handle only; deny-by-default; least privilege; redaction before any exposure/persistence; no
  self-grant/self-authorize.
- **Phase S0 — Baseline:** confirm no secret material in the repo or its history; ensure config
  references secrets by handle only.
- **Phase S1 — Redaction + audit:** redaction at all boundaries and secret-free, handle-based
  audit, with tests.
- **Phase S2 — Permission boundary:** enforce least-privilege, scoped, expiring, revocable
  permissions at the Integration/Execution edge, with tests.
- **Phase S3 — Credential handling:** just-in-time, handle-based retrieval under approval, with
  rotation/revocation, with tests.
- Each phase is gated by its tests; later phases never begin before earlier ones pass.

## 79. Architecture risks

- **No enforcement or tests yet** — until Phases S1–S2 hold, non-leakage and least-privilege are
  intent, not fact (top risk).
- **Redaction gaps on failure/error paths** — a common real-world leak vector (mitigated by §32,
  §71, §76).
- **Scope creep in grants** — standing/wildcard permissions accreting over time (mitigated by
  §20, §40).
- **Out-of-repo secret location** — exists outside scope; risk is mishandling there, not here;
  this policy forbids importing any of it into the repo/logs/memory.
- **Permission logic leaking into adapters** — would fragment authority (mitigated by §48).

## 80. Open decisions

- Secret-management mechanism and retrieval model (future ADR; deliberately unspecified).
- Permission model representation and the grant/scope vocabulary.
- Rotation cadence and revocation propagation approach.
- Audit storage for secret/permission events (relates to the forthcoming memory authority spec).
- Handle/reference format for secrets in config and contracts.

## 81. Readiness checklist

Before this policy is considered active:

- [ ] ADR-0002 reviewed and Accepted (currently Proposed).
- [ ] Repo and history confirmed secret-free; config references secrets by handle only (S0).
- [ ] Redaction-at-all-boundaries and secret-free audit defined and testable (S1).
- [ ] Least-privilege, scoped, expiring, revocable permission boundary defined (S2).
- [ ] Credential handling (just-in-time, handle-based, approval-gated, rotatable) defined (S3).
- [ ] Required non-leakage and least-privilege test suites enumerated and owned (§76–§77).
- [ ] Execution / autonomous / release blockers below ratified as gates.

**Blockers before execution work:** redaction + secret-free audit (S1) and the permission
boundary (S2) defined and tested; no command/external-write/destructive path runs without
explicit permission and, where required, approval. **Blockers before autonomous work:** bounded/
revocable/auditable autonomous scopes (§63), background-bypass prevention (§64), and their tests.
**Blockers before production release:** all of the above plus proven non-leakage across logs,
prompts, audit, memory, diagnostics, and failure paths (§76).

## 82. Recommended next foundational document

**`docs/architecture/MEMORY_AUTHORITY_SPEC.md`** — the single-writer memory authority underpins
the secret-free, handle-based audit trail (§31, §70, §72) and the consistency/ownership/
redaction/audit tests this policy and the testing strategy require (Strategy §21). With secrets
and permissions specified, the memory authority can be defined against a fixed redaction/audit
contract.
