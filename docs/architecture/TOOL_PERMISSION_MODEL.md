# GARVIS — Tool Permission Model

**Status:** Binding security/tooling specification (governed by ADR-0006) · **Scope:** Every tool
that can read, write, network, integrate, execute, modify state, or cause external side effects ·
**Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md),
[`ADR_PROCESS.md`](./ADR_PROCESS.md),
[`TESTING_AND_VERIFICATION_STRATEGY.md`](./TESTING_AND_VERIFICATION_STRATEGY.md),
[`SECRETS_AND_PERMISSIONS_POLICY.md`](./SECRETS_AND_PERMISSIONS_POLICY.md),
[`MEMORY_AUTHORITY_SPEC.md`](./MEMORY_AUTHORITY_SPEC.md),
[`OBSERVABILITY_AND_AUDIT_SPEC.md`](./OBSERVABILITY_AND_AUDIT_SPEC.md),
[`CONTRACTS_AND_SCHEMA_VERSIONING.md`](./CONTRACTS_AND_SCHEMA_VERSIONING.md). Where this and those
conflict, the constitution prevails; the conflict is reported, not silently resolved.

Vendor-neutral: no products, schema libraries, codegen tools, databases, models, APIs, or
temporary implementation detail, and **no implementation code, schemas-as-code, generated types, or
registry implementation**. It defines *what must be true* about tools and their permissions, not
*how they are built*. It contains and references **no secret values**.

---

## 1. Purpose

- Define how GARVIS classifies, permissions, approves, contracts, audits, and bounds tools so they
  can act on the world only as authorized, observable, and reversible.
- Establish the invariants and blockers that must hold before any tool reads/writes files, accesses
  networks, calls integrations, executes commands, modifies state, or causes external side effects.

## 2. Scope

- **In scope:** tool ownership, registry/lifecycle, classification, the tool↔permission↔approval
  relationship, tool contracts, redaction/audit/observability for tools, per-risk-class rules,
  sandbox/preview/rollback, failure/recovery/retry, and the tests that gate tool execution.
- **Out of scope:** specific tools, the registry implementation, and any concrete encoding
  (deliberately unspecified); business logic (never owned by a tool, §99).

## 3. Non-goals

- Not a tool catalog, not a registry implementation, not a permission engine. Not a place for
  business logic or self-authorization.
- Not a guarantee by documentation alone — enforced by mechanism and proven by tests (§81–§88).

## 4. Why GARVIS needs a Tool Permission Model

- Tools are where the platform actually touches the world; an unconstrained tool is an unbounded
  risk (file loss, network exfiltration, irreversible external change, secret leakage).
- A single model makes every tool owned, classified, permission-scoped, approval-gated where
  required, contracted, audited, and reversible — converting "the system can use a tool" into "the
  system can use a tool **only** as authorized, and the record proves it."

## 5. Tool vs agent vs workflow vs integration

- **Tool** — a bounded capability executor / adapter invoked to perform a specific action.
- **Agent** — a bounded role under Orchestration that **proposes** actions (and may select tools);
  it does not execute side effects itself.
- **Workflow** — an orchestrated sequence (manual or autonomous) that may invoke tools through the
  Gate.
- **Integration** — the adapter layer to external/local systems; tools act **through** Integration
  and the permission boundary, never around it.
- Tools execute; agents/workflows propose/orchestrate; integration translates. None substitutes
  for another.

## 6. Tool Authority vs Permission Authority

- Tools **do not own permission logic** (Secrets Policy §46). The permission authority grants and
  the boundary enforces; a tool merely requires and consumes a permission scope it was given.

## 7. Tool Authority vs Approval Gate

- Tools **do not own approval logic**. The Approval Gate decides; a tool executes only an **Approved
  Action** (Gate Spec §32) and never self-authorizes.

## 8. Tool Authority vs Execution Plane

- Tools are invoked **by the Command/Execution Plane** under an Approved Action; the Execution Plane
  consumes the single-use approval and binds it to the tool call. Tools do not originate or
  self-trigger actions.

## 9. Tool Authority vs Integration Plane

- Tools reach external/local systems **only through the Integration Plane**, where the permission
  boundary and vendor-shape translation live. A tool that bypasses Integration is a defect.

## 10. Relationship to GARVIS PRIME

- Implements PRIME §8 (tools add execution value, one authority per capability, least privilege),
  §9 (security), and §15 (capability earned, scoped, observable, revocable).

## 11. Relationship to Architecture Overview

- Realizes Overview §10/§17: tools are adapters invoked by Execution via Integration, with no
  business logic, one authority per capability, and no self-authorization.

## 12. Relationship to Approval Gate Spec

- A tool that produces a side effect runs only behind a valid, unexpired, unrevoked, single-use
  approval bound to its exact action (Gate Spec §22–§23, §32); approval failure fails closed (§100).

## 13. Relationship to Project Structure

- Tools live at `planes/integration/tools/` (Project Structure §23) — permission-bounded adapters,
  no business logic, one authority per capability.

## 14. Relationship to ADR Process

- Adopted via **ADR-0006**. Adding a new tool class, a destructive tool, or a credential-sensitive
  tool requires a recorded reason/ADR (Project Structure §6; §74 here).

## 15. Relationship to Testing and Verification Strategy

- The strategy mandates tool-adapter and permission-boundary tests (Strategy §17, §19). **Tool
  execution is disabled until those tests exist** (§81, §107–§108).

## 16. Relationship to Secrets and Permissions Policy

- Tools never self-grant, self-authorize, or expand scope; credential-sensitive tools are forbidden
  or strictly approved; tools hold no raw secrets (Secrets Policy §39, §45–§46, §59, §62).

## 17. Relationship to Memory Authority Spec

- Tools **do not own durable memory** (Memory Spec §48); durable results are written through the
  Memory Authority under permission, redacted and attributed.

## 18. Relationship to Observability and Audit Spec

- Tools **emit** events through governed interfaces; they **never write canonical audit records
  directly** (Audit Spec §10, §40); tool activity is audited via the governed path.

## 19. Relationship to Contracts and Schema Versioning

- **Tool calls and results use versioned contracts** (Contracts §67); vendor-native payloads are
  translated at the Integration edge and never leak into core tool contracts (§30, §69 there).

## 20. Core principles

- **Tools are capability executors/adapters, not authorities** — no permission, approval, memory,
  or audit ownership (§99).
- **No self-authorization, self-granting, or scope-expansion** (§100).
- **Permission + approval where required; least privilege; deny/closed by default.**
- **Every tool is owned, classified, scoped, contracted, observable, reversible-aware, and tested**
  (§21, §88).
- **No raw secrets/credentials/tokens/execution-context/audit-payloads in a tool** (§101).
- **Fail closed** on permission, approval, contract, or audit failure for gated/security-relevant
  tools (§100, §63).

## 21. Tool ownership model

- Every tool has **exactly one owner**, a stated **purpose**, a **risk class**, a **permission
  scope**, a **versioned contract**, and a **test strategy**. A tool lacking any of these is not
  enabled (§88).
- Owners are accountable for the tool's classification, scope, contract, and tests; ownership is
  discoverable.

## 22. Tool registry model

- Tools are registered in a single governed registry (conceptual; not implemented here) recording
  owner, purpose, risk class, permission scope, contract version, enablement state, and test
  status. Unregistered tools are not invocable; the registry is the single source of truth for what
  tools exist.

## 23. Tool lifecycle

```
Proposed → Registered (owner, class, scope, contract, tests) → Enabled → Deprecated → Disabled/Removed
                                                              └→ Revoked (immediate)
```

- Enablement requires passing the applicable tests (§81); revocation/disablement takes effect
  immediately (§76–§77).

## 24. Tool classification model

- Each tool is classified by **effect** into a risk class (§89–§98): informational, local read,
  local write, external read, external write, execution, destructive, credential-sensitive,
  autonomous (origin attribute), forbidden.
- Highest-risk-wins and conservative-on-uncertainty apply (Gate Spec §18); a multi-effect tool takes
  the most restrictive class.

## 25. Tool capability model

- A tool declares the precise capabilities it provides (operations, targets, boundaries). It may do
  only what it declares; undeclared behavior is a defect. One authority per capability — no
  duplicate/overlapping tools (PRIME §8).

## 26. Tool risk model

- Risk is assessed by blast radius and reversibility; the risk class drives the required permission,
  whether approval is needed, the contract's safety fields, and the test depth (§82–§86).

## 27. Tool permission model

- A tool runs only with the **explicit permission scope** it requires (Secrets Policy §18, §40),
  granted by the permission authority and enforced at the Integration/Execution boundary.
- Permission is least-privilege, scoped, expiring, and revocable; **permission absence or
  uncertainty fails closed** (§100).

## 28. Tool approval model

- A side-effecting tool action requires a valid **single-use approval** in addition to permission
  (§29). Never-auto classes (credential, destructive, external write, host control) require explicit
  per-instance human approval (Gate Spec §15).

## 29. Permission vs approval for tools

- **Permission ≠ approval.** Permission is a standing capability the tool may use; approval
  authorizes one specific tool action now. A gated tool action requires **both** (Contracts §63;
  Secrets Policy §9).

## 30. Tool contract requirements

- Every tool exposes **versioned call and result contracts** (Contracts §67) carrying the approved-
  action reference, required permission-scope reference, risk/sensitivity class, redaction status,
  correlation id, and (where applicable) idempotency key and dependency-chain references. Contract
  validation failure fails closed for gated/security-relevant tools (§100).

## 31. Tool call contract

- The call contract carries: tool identity + version, action reference, target/parameters
  (redacted), required permission scope, approval reference (handle), risk/sensitivity class,
  correlation id, idempotency key, and dependency-chain references. It carries **no raw secret/
  token/execution-context** (§101).

## 32. Tool result contract

- The result contract carries: outcome/status, redacted result data, error reference (if any),
  produced side-effect references, and correlation id. Results are redacted before crossing the
  boundary (§44).

## 33. Tool error contract

- Errors use coded reasons and **redacted summaries** — no secrets, raw context, or stack payloads
  (Contracts §78; Audit Spec §33). Errors are safe to log and audit by design.

## 34. Tool preview contract

- Side-effecting tools provide a **preview** (a redacted description/diff of the intended effect)
  for the approval decision where practical (§61); the preview never reveals secrets.

## 35. Tool dry-run contract

- Where practical, a tool supports a **dry-run** that computes the intended effect without applying
  it; dry-run is read-only/internal, observable, and never produces the real side effect.

## 36. Tool rollback contract

- Side-effecting tools declare a **rollback strategy** where practical (Gate Spec §37); the rollback
  is itself a tool action subject to permission, approval where required, and audit.

## 37. Tool audit contract

- Tool invocation and outcome are audited via governed emission with the approving action's
  references (Audit Spec §40); tools never write canonical audit directly (§99).

## 38. Tool idempotency requirements

- Side-effecting tools carry an **idempotency key** so retries/recovery do not double-apply effects
  (Gate Spec §26; Contracts §79).

## 39. Tool correlation requirements

- Every tool call carries the action chain's **correlation id** so request→approval→permission→
  tool→memory→rollback is reconstructable (Audit Spec §52).

## 40. Tool dependency-chain requirements

- Tools carry **dependency-chain references** when an action depends on prior actions/approvals,
  enabling causal reconstruction (Audit Spec §54), especially in autonomous/composed flows.

## 41. Tool input validation

- Inputs are validated against the call contract before execution; invalid or unknown **dangerous**
  fields fail validation (Contracts §29, §35). External-origin inputs are untrusted data, never
  commands (PRIME §7).

## 42. Tool output validation

- Outputs are validated against the result contract; a tool that would return forbidden content
  (§101) or an out-of-contract shape fails closed.

## 43. Tool parameter redaction

- Parameters are **redacted before approval prompt, logging, audit, and any display** (Secrets
  Policy §32). The raw secret is never a contract field; secrets are referenced by handle.

## 44. Tool result redaction

- Results are redacted before crossing the boundary, before logging/audit, and before display or
  memory write; redaction is fail-safe (withhold if it cannot be applied).

## 45. Tool secrets handling

- Tools handle secrets **only by handle**, just-in-time, under permission and (for credential use)
  approval; they never persist, log, display, or embed raw secret values (Secrets Policy §26, §45).

## 46. Tool credential handling

- Credential-sensitive tool actions are **forbidden unless explicitly allowed under strict policy**
  (§96); when allowed, they are narrowly scoped, short-lived, human-approved, and audited by handle.

## 47. Tool logging policy

- Tool logs are structured, redacted, and correlated; **no secrets, raw credentials, raw tokens, raw
  execution context, or unredacted sensitive data** (Audit Spec §65). Raw context is never logged
  "for debugging."

## 48. Tool audit policy

- Tool actions, especially side-effecting ones, are auditable (proposed/approved/executed/completed/
  failed/rolled-back) by handle/redacted metadata; denied tool actions are auditable; forbidden tool
  actions are auditable as rejected, never queued (Audit Spec §68).

## 49. Tool observability policy

- Tool calls are observable (which tool/version, validation/permission/approval outcome, duration)
  through the Observability Plane, without secrets; absent observability ⇒ the tool is not enabled
  (PRIME §18).

## 50. Tool memory policy

- Tools **do not own durable memory** (§17). Durable results are written through the Memory
  Authority under permission, redacted and attributed; transient tool state is ephemeral, not
  system memory.

## 51. Tool state policy

- A tool's in-invocation state is ephemeral and tool-local; durable state is governed memory written
  through the authority. Tools never keep a private durable store.

## 52. Tool filesystem access policy

- Filesystem tools are scoped to explicitly-granted paths; broad/root access is forbidden absent
  recorded justification (Secrets Policy §57). Writes outside the platform workspace are external-
  write (§93). Reads are local-read (§90); writes local-write/destructive per target (§91, §95).

## 53. Tool network access policy

- Network tools are denied by default; only explicitly-granted destinations/operations are
  permitted; **authenticated network actions are never auto-approved** (Secrets Policy §58).
  External reads/writes follow §92–§93.

## 54. Tool command execution policy

- **Execution tools require explicit permission, approval where required, audit, timeout, failure
  handling, and rollback expectations** (§94). Arbitrary/unscoped command execution is forbidden;
  permitted commands are narrowly scoped and validated.

## 55. Tool external write policy

- **External write tool actions require explicit permission and may still require approval, and are
  never auto-approved** (§93; Secrets Policy §60). Scope is the specific target and operation only.

## 56. Tool destructive action policy

- **Destructive tools require explicit permission AND explicit approval**, are never auto, and
  require a rollback strategy or defined recovery path before they run (§95; Gate Spec §37).

## 57. Tool credential-sensitive action policy

- **Credential-sensitive tools are forbidden unless explicitly allowed under strict policy** (§96);
  if allowed, they are scoped, short-lived, human-approved per instance, secret-free in all records,
  and heavily audited.

## 58. Tool autonomous workflow policy

- **Autonomous workflows must not call tools outside their bounded, revocable, auditable permission
  scope** (Secrets Policy §63). Never-auto/forbidden tool actions are deferred to the human or
  rejected, never auto-performed.

## 59. Tool background job policy

- **Background jobs must not call tools without correlation, permission checks, redaction, and
  audit** (Secrets Policy §64). Background tool use holds only its granted scope and cannot
  accumulate or self-grant access.

## 60. Tool sandbox policy

- Tools execute within the least-privileged environment their action requires; risky/under-test
  tools run sandboxed with no access to production resources, secrets, or irreversible targets
  (Strategy §46). A test must never produce an uncontrolled real side effect.

## 61. Tool dry-run and preview requirements

- Side-effecting tools provide preview and (where practical) dry-run so the approver sees the
  intended effect before authorizing it; neither reveals secrets nor applies the real effect.

## 62. Tool rollback expectations

- Side-effecting tools are reversible-first; a rollback strategy is required for local-write
  (non-trivial), external-write, execution, and destructive classes (Gate Spec §37). Absence of a
  feasible rollback requires explicit approval + recovery path before running.

## 63. Tool failure behavior

- Tools **fail closed**: on permission, approval, contract-validation, or audit failure, the action
  does not execute. Failures surface honestly, are redacted, and never leak secrets (§47, §101).

## 64. Tool recovery behavior

- Recovery resumes from audited state; a consumed approval is never reused; failed/denied tool
  actions are not silently retried (§66). Indeterminate state is treated conservatively (assume
  not-completed; require a new decision).

## 65. Tool timeout policy

- Tool actions have bounded timeouts; a timed-out side-effecting action is treated as indeterminate
  (recovery per §64), surfaced, and audited; it is never silently retried.

## 66. Tool retry policy

- **Retries are bounded and idempotency-aware and must not retry denied or forbidden actions.**
  A retry reuses the idempotency key to avoid duplicate effects; exceeding the bound defers to a
  human, it does not escalate.

## 67. Tool rate-limit policy

- Tools operate under rate/budget limits (especially autonomous use); exceeding a limit defers or
  halts and is audited; limits are never auto-raised by the tool itself.

## 68. Tool concurrency policy

- Concurrent invocations respect single-use approvals (one approval, one execution) and idempotency;
  concurrency never lets two executions share one approval or double-apply an effect.

## 69. Tool dependency policy

- A tool declares its dependencies (permissions, integrations, contracts); a tool with unmet
  dependencies is not enabled. Tools do not acquire dependencies implicitly at run time.

## 70. Tool composition policy

- Composed tool actions are still individually classified, permission-checked, and (where gated)
  approved; composition never bundles a gated effect under a non-gated wrapper to evade approval.

## 71. Tool chaining policy

- Chained tool calls carry dependency-chain references (§40); each link is independently authorized.
  A chain cannot launder a denied/forbidden step through a later step.

## 72. Tool delegation policy

- A tool may not delegate its authority to another tool/agent to bypass permission or approval; any
  delegated action re-enters classification and authorization from the start.

## 73. Tool discovery policy

- Available tools are discovered only from the governed registry (§22); discovery never exposes
  disabled/forbidden tools as invocable or reveals secrets in tool metadata.

## 74. Tool registration policy

- Registering a tool requires owner, purpose, risk class, permission scope, contract version, and a
  test strategy (§21); a destructive or credential-sensitive tool additionally requires a recorded
  reason/ADR. Registration does not enable execution (§75).

## 75. Tool enablement policy

- A registered tool is **enabled** only after its required tests pass (§81) and its dependencies are
  met; enablement is explicit and recorded. Default state is disabled.

## 76. Tool disablement policy

- A tool can be disabled immediately; disablement halts new invocations and is audited. In-flight
  actions relying on a disabled tool do not proceed.

## 77. Tool revocation policy

- A tool's permissions can be revoked at any time, taking effect immediately and cascading to
  dependent actions (Secrets Policy §36); a revoked tool cannot authorize new actions.

## 78. Tool versioning policy

- Tool contracts are versioned (Contracts §21); a tool declares the contract version it implements;
  incompatible changes follow the breaking-change policy (Contracts §23).

## 79. Tool deprecation policy

- A deprecated tool/version remains documented until safely removed (Contracts §25); consumers are
  given a migration path before removal; deprecation never strands an in-use consumer.

## 80. Tool compatibility policy

- Within a major contract version, a tool's call/result shape and required safety fields are stable;
  additions are optional and never weaken a safety field (Contracts §28).

## 81. Tool testing requirements

- **Tool execution is disabled until permission-boundary, approval-invariant, redaction, audit, and
  contract tests exist** for that tool (Strategy §17, §19, §22, §24). A tool with no passing
  required tests is not enabled.

## 82. Tool permission-boundary testing

- Tests prove the tool runs only within its granted scope, cannot self-grant or expand scope, and
  that permission absence/uncertainty fails closed (Secrets Policy §76).

## 83. Tool approval invariant testing

- Tests prove a side-effecting tool runs only with a valid single-use approval bound to its exact
  action; replay/reuse/widening is rejected; never-auto actions are never auto-approved; forbidden
  actions are rejected and never queued (Gate Spec §40).

## 84. Tool contract testing

- Tests prove call/result/error contracts are honored across supported versions and that forbidden
  content (§101) cannot appear; cross-version compatibility is tested (Contracts §33).

## 85. Tool integration testing

- Tests exercise the tool through the Integration Plane against simulated/sandboxed externals
  (never uncontrolled real side effects, §60), proving vendor shapes do not leak into core
  contracts.

## 86. Tool adversarial testing

- Tests attempt the bypass: self-authorize, reuse an approval, exceed scope, smuggle a secret into a
  log/result, retry a denied action, double-apply via concurrency/retry. A successful break is a
  release blocker.

## 87. Tool mock and simulation policy

- External dependencies are simulated faithfully to the **contract** (Strategy §45); the Approval
  Gate and permission boundary are **never mocked away** in tests that assert a tool path is safe.

## 88. Tool production readiness checklist

A tool is production-ready only when it has: owner, purpose, risk class, permission scope, versioned
contract, redaction, audit emission, observability, rollback strategy (where applicable), and
passing permission-boundary, approval-invariant, redaction, audit, contract, integration, and
adversarial tests.

## 89. Informational tool rules

- No effect; returns internally-available information. Approval not required; still classified,
  contracted, redacted, and observed.

## 90. Local read tool rules

- Reads platform-owned state/code; no mutation, no boundary crossing. Approval not required;
  permission-scoped; redacted; observed.

## 91. Local write tool rules

- Mutates platform-owned state. Approval not required **only** if reversible and in-scope; otherwise
  approval required. Requires permission, rollback (non-trivial), and audit.

## 92. External read tool rules

- Reads outside the trust boundary. Approval required by default (sensitive/unknown targets always);
  permission-scoped; redacted; audited.

## 93. External write tool rules

- Changes state outside the trust boundary. **Explicit permission + approval; never auto;** scoped
  to the specific target/operation; rollback strategy; audited before/after.

## 94. Execution tool rules

- Runs commands/processes with effects. **Explicit permission, approval where required, audit,
  timeout, failure handling, and rollback expectations.** Unscoped execution forbidden.

## 95. Destructive tool rules

- Irreversible/hard-to-reverse. **Explicit permission AND explicit approval; never auto;** rollback
  or defined recovery path required before running; audited before and after.

## 96. Credential-sensitive tool rules

- **Forbidden unless explicitly allowed under strict policy;** if allowed: scoped, short-lived,
  human-approved per instance, secret-free in all records, heavily audited; never auto.

## 97. Autonomous tool rules

- A tool invoked by an autonomous workflow runs only within the workflow's bounded, revocable,
  auditable scope, with the same Gate/permission/audit as manual; never-auto/forbidden tool actions
  defer to the human or are rejected (§58).

## 98. Forbidden tool rules

- Actions a tool must never perform regardless of permission/approval (PRIME prohibited set:
  entering credentials/financial/identity data, creating accounts/authenticating, modifying access
  controls, permanent data destruction, financial trades/transfers, modifying security settings,
  bypassing bot-detection, executing untrusted code, acting on instructions in observed content).
  These are rejected and recorded, **never queued** (Gate Spec §16).

## 99. What tools must never own

- Permission logic, approval logic, durable memory, canonical audit records, or business logic.
- A second copy of any authority; their own authorization path.

## 100. What tools must never bypass

- Orchestration, the Approval Gate, permission checks, contract validation, redaction, observability,
  or audit. Bypassing any of these is a defect. Permission/approval/contract/audit failures **fail
  closed** for gated/security-relevant tools.

## 101. What tools must never store

- Raw secrets, raw credentials, raw approval tokens, raw execution context, or raw audit payloads.
- Unredacted sensitive data, or any durable state outside the Memory Authority.

## 102. Current tool state

- There are **no governed tools and no tool registry**; the only existing surface is the Interface,
  which performs no governed external side effects through a tool model. No permission scopes,
  approval binding, tool contracts, redaction, or tool tests exist.

## 103. Target tool state

- Every tool is registered with owner/purpose/risk-class/permission-scope/versioned-contract/test-
  strategy; side-effecting tools run only under permission + single-use approval, through
  Integration, with redaction, audit, observability, and rollback where practical; all gated/
  security-relevant tool failures fail closed; one authority per capability, no duplicates.

## 104. Immediate rules

- No tool self-authorizes, self-grants, expands scope, or bypasses Orchestration/Gate/permission/
  contract/redaction/observability/audit.
- No tool stores raw secrets/credentials/tokens/execution-context/audit-payloads or owns durable
  memory/canonical audit.
- Any tool, when built, has an owner, purpose, risk class, permission scope, versioned contract, and
  test strategy before it is enabled.

## 105. Future rules

- After the registry, permission boundary, Gate, and contracts exist: runtime permission + approval
  binding per tool call; fail-closed validation; enablement only after required tests pass;
  destructive/credential-sensitive tools gated by ADR + strict policy.

## 106. Migration phases

- **Phase T0 — Model + registry shape:** define ownership, classification, registry fields, and tool
  call/result/error contracts; no tools implemented.
- **Phase T1 — Safe-class tools:** informational/local-read tools under permission + contract +
  redaction + audit + tests (no side effects).
- **Phase T2 — Side-effecting tools:** local-write/external-read tools with approval where required,
  rollback where practical, and passing permission-boundary/approval-invariant/redaction/audit/
  contract tests.
- **Phase T3 — Execution/external-write/destructive tools:** under explicit permission + approval,
  timeout/failure/rollback, with adversarial tests.
- **Phase T4 — Autonomous tool use:** tools invoked by autonomous workflows within bounded/revocable
  scopes, with full dependency-chain audit and no-bypass tests.
- Each phase is gated by its tests; later phases never begin before earlier ones pass.

## 107. Blockers before tool implementation

- The tool ownership/classification model, registry fields, and tool call/result/error contracts are
  defined (T0); the Approval Gate, permission boundary, and contract validation specifications they
  depend on are in place (they are, as Proposed specs).

## 108. Blockers before execution tools

- Permission-boundary, approval-invariant, redaction, audit, and contract tests exist and pass for
  the tool; the tool runs only with permission + single-use approval, through Integration, with
  timeout/failure/rollback; **fail-closed** verified.

## 109. Blockers before autonomous tools

- In addition to execution blockers: bounded/revocable/auditable autonomous tool scopes, dependency-
  chain audit, background-bypass prevention, and their tests; never-auto/forbidden tool actions
  proven to defer/reject under autonomy.

## 110. Blockers before production release

- All of the above plus passing adversarial tests (§86), proven non-leakage across tool params/
  results/logs/audit/errors and failure paths, and a complete production-readiness checklist (§88)
  per enabled tool.

## 111. Architecture risks

- **No model enforcement or tests yet** — until T1–T2 hold, tool permission/approval/redaction are
  intent, not fact (top risk).
- **Tool self-authorization / scope creep** — a tool acquiring or widening authority (mitigated by
  §27, §100).
- **Vendor-shape leakage** — external payloads entering core tool contracts (mitigated by §19, §85).
- **Secret leakage via tool params/results/errors/failure paths** — a high-frequency vector
  (mitigated by §43–§47, §63).
- **Denied-action retry / forbidden-action queueing** — laundering a decision (mitigated by §66,
  §98).

## 112. Open decisions

- Tool registry representation and enablement mechanism (future ADR; deliberately unspecified).
- Permission-scope granularity for tools and the scope-declaration vocabulary.
- Preview/dry-run feasibility per tool class and the standard preview shape.
- Rate/budget model for autonomous tool use.
- Sandbox model for risky/under-test tools (coordinated with the testing strategy).

## 113. Readiness checklist

Before this model is considered active:

- [ ] ADR-0006 reviewed and Accepted (currently Proposed).
- [ ] Ownership/classification model and registry fields defined (T0).
- [ ] Tool call/result/error contracts defined and versioned (T0).
- [ ] Permission + approval binding per tool call specified; permission/approval/contract/audit
      failures fail closed.
- [ ] Required tool tests (§81–§86) enumerated and owned; enablement gated on them.
- [ ] Per-risk-class rules (§89–§98) and execution/autonomous/release blockers ratified as gates.

## 114. Recommended next foundational document

**`docs/architecture/AGENT_ORCHESTRATION_MODEL.md`** — tools are *selected and proposed* by agents
under Orchestration; with the tool permission model defined, the agent orchestration model is the
next per-capability refinement (how bounded agent roles propose actions/tool calls through
Orchestration to the Gate, never executing or self-authorizing). It is backlog ADR item #6 and the
prerequisite the workflow engine then builds on. See the report for the recommended ordering.
