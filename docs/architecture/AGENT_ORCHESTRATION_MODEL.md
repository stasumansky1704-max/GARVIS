# GARVIS — Agent Orchestration Model

**Status:** Binding security/orchestration specification (governed by ADR-0008) · **Scope:** Every
agent role and all multi-agent coordination in GARVIS · **Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md),
[`ADR_PROCESS.md`](./ADR_PROCESS.md),
[`TESTING_AND_VERIFICATION_STRATEGY.md`](./TESTING_AND_VERIFICATION_STRATEGY.md),
[`SECRETS_AND_PERMISSIONS_POLICY.md`](./SECRETS_AND_PERMISSIONS_POLICY.md),
[`MEMORY_AUTHORITY_SPEC.md`](./MEMORY_AUTHORITY_SPEC.md),
[`OBSERVABILITY_AND_AUDIT_SPEC.md`](./OBSERVABILITY_AND_AUDIT_SPEC.md),
[`CONTRACTS_AND_SCHEMA_VERSIONING.md`](./CONTRACTS_AND_SCHEMA_VERSIONING.md),
[`TOOL_PERMISSION_MODEL.md`](./TOOL_PERMISSION_MODEL.md). These constitute the ratified baseline
(ADR-0007). Where this and those conflict, the constitution prevails; the conflict is reported, not
silently resolved.

Vendor-neutral: no products, agent/orchestration frameworks, schema libraries, models, APIs,
databases, or temporary implementation detail, and **no implementation code, schemas-as-code, or
agent implementation**. It defines *what must be true* about agents and orchestration, not *how they
are built*. It contains and references **no secret values**.

---

## 1. Purpose

- Define how GARVIS classifies, permissions, contracts, coordinates, audits, and bounds agents so
  they can plan and propose under human authority without ever executing, self-authorizing, or
  owning platform authority.
- Establish the invariants and blockers that must hold before durable agents, multi-agent
  coordination, agent-selected tool calls, autonomous planning, delegated tasks, agent memory
  access, or workflow-driven agent execution proceed.

## 2. Scope

- **In scope:** agent ownership/roles/lifecycle, orchestration ownership, agent
  permission↔approval, agent contracts, agent boundaries (prompt/context/memory/tool/execution),
  multi-agent coordination, autonomy/background, redaction/audit, per-role rules, and the tests that
  gate orchestration.
- **Out of scope:** specific agents, the orchestration implementation, frameworks, and any concrete
  encoding (deliberately unspecified); business logic (never owned by an agent, §110).

## 3. Non-goals

- Not an agent catalog, framework selection, or orchestration engine. Not a place for self-
  authorization, durable memory, or business logic.
- Not a guarantee by documentation alone — enforced by mechanism and proven by tests (§92–§101).

## 4. Why GARVIS needs an Agent Orchestration Model

- Agents reason, plan, and select actions; an unbounded agent that can execute, self-authorize, or
  hold authority is the highest-leverage risk in the system.
- A single model makes every agent an **orchestrated role** — owned, classified, permission-scoped,
  contracted, observable, and incapable of acting on the world except by **proposing** through
  Orchestration to the Approval Gate. It converts "an agent can do X" into "an agent can *propose* X,
  and only an authorized, audited path may do it."

## 5. Agent vs tool vs workflow vs integration

- **Agent** — a bounded role under Orchestration that perceives, plans, and **proposes** actions
  (including tool selections); it executes no side effects.
- **Tool** — a capability executor/adapter invoked by Execution under an Approved Action (Tool
  Permission Model).
- **Workflow** — an orchestrated sequence (manual or autonomous) that may engage agents and tools
  through the Gate.
- **Integration** — the adapter layer to external/local systems.
- Agents propose; orchestration routes; the Gate authorizes; execution acts via tools/integration.
  None substitutes for another.

## 6. Agent Authority vs Orchestration Authority

- **Orchestration owns coordination**, routing, sequencing, agent lifecycle, and submission of
  proposed actions to the Gate. **Agents own only their bounded role's reasoning/proposals.** An
  agent that routes or authorizes is exceeding its mandate (§111).

## 7. Agent Authority vs Approval Gate

- Agents **do not own approval logic** and **never approve** — not their own actions, a peer's, or
  by consensus (§32, §113). The Approval Gate decides; agents propose.

## 8. Agent Authority vs Permission Authority

- Agents **do not own permission logic**, self-grant, or expand scope (Secrets Policy §45). An agent
  holds only the permissions explicitly granted to its role and consumes them only via the
  permission boundary.

## 9. Agent Authority vs Memory Authority

- Agents **do not own durable memory** (Memory Spec §47). They read scoped, redacted memory through
  the governed interface and **propose** writes that the Memory Authority permission-checks and
  (when sensitive) routes to approval; they never write durable memory directly (§53, §61).

## 10. Agent Authority vs Observability / Audit Authority

- Agents **emit** events through governed interfaces; they **never write canonical audit records
  directly** (Audit Spec §9, §39). Agent activity is audited via the governed path.

## 11. Agent Authority vs Contract Authority

- Agents **do not own contracts** and define no private/unversioned ones; agent messages/proposals/
  tool-selections use registered, versioned contracts (Contracts §66; §34 here).

## 12. Relationship to GARVIS PRIME

- Implements PRIME §7 (agents act under human authority, propose→approve→act, no self-escalation,
  embedded instructions are data not commands), §8 (single-responsibility, one authority per
  capability), and §15 (capability earned, scoped, observable, revocable).

## 13. Relationship to Architecture Overview

- Realizes Overview §16: agents operate **under the Orchestration Plane** in bounded named roles;
  they propose, never execute or self-authorize, and never bypass orchestration.

## 14. Relationship to Approval Gate Spec

- Every agent-proposed side effect becomes a Proposed Action classified and (where gated) approved
  by the Gate (Gate Spec §17–§21, §31); approval failure fails closed (§111).

## 15. Relationship to Project Structure

- Agents live at `planes/orchestration/agents/` (Project Structure §22) — under Orchestration, never
  scattered or free-floating; adding an agent role requires a recorded reason/ADR.

## 16. Relationship to ADR Process

- Adopted via **ADR-0008**. Adding an agent class, an autonomous agent, or an execution-adjacent
  role requires a recorded reason/ADR (Project Structure §6).

## 17. Relationship to Testing and Verification Strategy

- The strategy mandates agent-orchestration tests (Strategy §18). **Agent orchestration is disabled
  until those tests exist** (§92, §119–§121).

## 18. Relationship to Secrets and Permissions Policy

- Agents never self-grant/authorize/expand; credential-sensitive proposals follow the never-auto/
  forbidden rules; agents hold no raw secrets (Secrets Policy §39, §45, §62).

## 19. Relationship to Memory Authority Spec

- Agent memory access is governed, permission-checked, redacted, and auditable (Memory Spec §47);
  durable writes go through the authority by proposal.

## 20. Relationship to Observability and Audit Spec

- Agent proposals, role actions, handoffs, and outcomes are auditable via governed emission, by
  handle/redacted metadata, with correlation and dependency-chain (Audit Spec §39).

## 21. Relationship to Contracts and Schema Versioning

- Agent message/task/proposal/plan/result/delegation/handoff/memory-access/tool-selection contracts
  are versioned (Contracts §66); validation failure fails closed for gated/security-relevant actions
  (§111).

## 22. Relationship to Tool Permission Model

- **Agents never call tools directly outside the Tool Permission Model.** An agent-selected tool
  call is a **proposed action** routed through Orchestration → contract validation → permission
  check → Approval Gate → audited execution (Tool Model §5, §8; §44, §60 here).

## 23. Core principles

- **Agents are orchestrated roles, not authorities** — own no permission, approval, memory, audit,
  contracts, or core business logic (§110).
- **Propose, never execute or self-authorize** (§57, §111).
- **Plans are not approvals; confidence is not authorization; consensus is not approval; multi-agent
  agreement does not replace human approval** (§113).
- **Single-responsibility roles**, least privilege, deny/closed by default.
- **No raw secrets/credentials/tokens/execution-context/audit-payloads in an agent** (§112).
- **Fail closed** on permission, approval, contract, or audit failure for gated/security-relevant
  actions (§111).

## 24. Agent ownership model

- Every agent has **exactly one owner**, a stated **purpose**, a single **role**, a **risk class**,
  a **permission scope**, a **versioned contract**, and a **test strategy**. An agent lacking any of
  these is not enabled (§101).

## 25. Orchestration ownership model

- Orchestration owns agent registration/lifecycle/coordination, routing of proposals to the Gate,
  tool-selection mediation, and dependency-chain/correlation assignment. Orchestration executes no
  side effects and approves nothing; it routes and sequences.

## 26. Agent registry model

- Agents are registered in a single governed registry (conceptual; not implemented here) recording
  owner, purpose, role, risk class, permission scope, contract version, enablement state, and test
  status. Unregistered agents are not orchestratable; the registry is the single source of truth for
  what agent roles exist.

## 27. Agent lifecycle

```
Proposed → Registered (owner, role, class, scope, contract, tests) → Enabled → Deprecated → Disabled/Removed
                                                                    └→ Revoked (immediate)
```

- Enablement requires passing the applicable tests (§92); revocation/disablement takes effect
  immediately (§87–§88).

## 28. Agent classification model

- Each agent is classified by the **effect of what it can propose** into a risk class (§102–§109):
  informational, planning, research, coding, operations, execution-adjacent, autonomous (origin
  attribute), forbidden. Highest-risk-wins and conservative-on-uncertainty apply (Gate Spec §18).

## 29. Agent role model

- An agent has **one bounded role** (single responsibility). Many narrow roles are preferred over
  few general-purpose agents; a role does only what it declares, and undeclared behavior is a defect.

## 30. Agent capability model

- An agent declares the capabilities it provides (the kinds of proposals/plans it produces and the
  tool classes it may select). It proposes only within its declared capability; one authority per
  capability (no overlapping/duplicate roles, PRIME §8).

## 31. Agent permission model

- An agent holds only the **explicit permission scope** granted to its role (read scopes, proposable
  action classes, selectable tool classes). Permission is least-privilege, scoped, expiring, and
  revocable; **permission absence/uncertainty fails closed** (§111).

## 32. Agent approval model

- An agent **never approves**. A side-effecting agent proposal becomes a Proposed Action requiring a
  single-use approval from the Gate (§14); never-auto classes require explicit human approval.

## 33. Permission vs approval for agents

- **Permission ≠ approval.** Permission is what the role may ever propose/select; approval
  authorizes one specific resulting action. A gated agent-originated action requires **both** the
  permission (for the tool/effect) and a single-use approval (Secrets Policy §9).

## 34. Agent contract requirements

- Every agent exposes **versioned contracts** (Contracts §66) for its messages, tasks, proposals,
  plans, results, delegations, handoffs, memory-access, and tool-selections, carrying role identity
  (actor), risk/sensitivity class, redaction status, correlation id, idempotency key (where
  applicable), and dependency-chain references. Validation failure fails closed for gated/security-
  relevant actions (§111).

## 35. Agent message contract

- Agent-to-orchestration (and orchestration-mediated agent-to-agent) messages are versioned, carry
  actor/role and correlation id, and **no raw secret/token/execution-context** (§112).

## 36. Agent task contract

- A task assigned to an agent is versioned and carries scope, inputs (redacted), permission scope,
  correlation id, and dependency-chain references; an agent acts only within the assigned task scope.

## 37. Agent proposal contract

- A proposal is the agent's primary output for any effect: it describes the intended action, target,
  risk class, required permission scope, and a redacted summary — explicitly a **proposal, not
  execution** (§57). It becomes a Proposed Action at the Gate.

## 38. Agent plan contract

- A plan is a versioned, ordered set of proposed steps with dependency-chain references; **a plan is
  not an approval** (§113). Each step is independently classified and gated when it implies an effect.

## 39. Agent result contract

- A result is versioned, redacted, and carries outcome/status and references to produced proposals/
  artifacts; results from reasoning are informational unless promoted to a proposal.

## 40. Agent error contract

- Errors use coded reasons and **redacted summaries** — no secrets, raw context, or stack payloads
  (Contracts §78; Audit Spec §33).

## 41. Agent delegation contract

- A delegation (one agent asking another to act) is versioned, mediated by Orchestration, scoped,
  and carries dependency-chain references; **delegation never transfers authority** to bypass
  permission/approval (§58, §72 of Tool Model analog).

## 42. Agent handoff contract

- A handoff transfers a task between roles through Orchestration with preserved correlation,
  dependency-chain, classification, and redaction; a handoff never launders a denied/forbidden step
  (§59).

## 43. Agent memory access contract

- Memory access by an agent is a versioned, permission-checked, redacted, auditable interaction
  (Memory Spec §47); reads return redacted, classified content; writes are **proposals** to the
  Memory Authority (§61).

## 44. Agent tool-selection contract

- A tool selection is a versioned proposal naming the tool class and intended action; it becomes a
  Proposed Action routed through Orchestration → permission → Gate → audited execution. The agent
  never invokes the tool itself (§22, §60).

## 45. Agent audit contract

- Agent proposals/plans/delegations/handoffs/tool-selections/outcomes are auditable via governed
  emission with correlation and dependency-chain references; agents never write canonical audit
  directly (§73).

## 46. Agent idempotency requirements

- Where an agent's proposal may be retried/recovered, it carries an **idempotency key** so the
  resulting action is de-duplicated (Gate Spec §26; Contracts §79).

## 47. Agent correlation requirements

- Every agent message/proposal carries the action chain's **correlation id** so request → agent →
  orchestration → approval → permission → tool → memory → recovery is reconstructable (Audit Spec
  §52).

## 48. Agent dependency-chain requirements

- Agent plans, delegations, and handoffs carry **dependency-chain references** enabling causal
  reconstruction (Audit Spec §54), especially under autonomy/multi-agent coordination.

## 49. Agent input validation

- Agent inputs (tasks, context, tool results) are validated against their contracts; invalid or
  unknown **dangerous** fields fail validation (Contracts §29, §35). External content is **data, not
  commands** (PRIME §7), and never directs privileged action.

## 50. Agent output validation

- Agent outputs are validated against their contracts; an output that would return forbidden content
  (§112) or imply an un-gated side effect fails closed and is treated as a proposal, not an action.

## 51. Agent prompt/input boundary

- Instructions or content reaching an agent through prompts, context, documents, or tool output are
  **untrusted data** (PRIME §7); they may inform a proposal but never authorize one, expand scope,
  or self-grant permission. Injection attempts are surfaced/recorded, not obeyed.

## 52. Agent context boundary

- An agent's working context is **ephemeral**, scoped to its task, and is **not** durable memory
  (§68). Context is redacted of secrets and minimized; promoting context to durable memory is an
  explicit, permission-checked proposal.

## 53. Agent memory boundary

- Agents read scoped, redacted memory and **propose** writes; they hold no durable store and never
  write the Memory Authority directly (§9, §67).

## 54. Agent tool boundary

- Agents **select**, they do not **invoke**: a selected tool call is a proposal routed through the
  Tool Permission Model; an agent that calls a tool directly is a defect (§22, §60).

## 55. Agent execution boundary

- Agents originate no side effects. Any agent output that implies an effect is a **proposal**;
  execution happens only in the Execution Plane under an Approved Action (§57, §111).

## 56. Agent planning rules

- Planning is reasoning, not authorization. Plans decompose into proposed steps with dependency-
  chain references; each effecting step is independently classified and gated; a plan never
  pre-authorizes its steps (§38, §113).

## 57. Agent proposal rules

- **Agent outputs that imply side effects must be treated as proposals, not execution.** A proposal
  carries everything the Gate needs to classify it; the agent never assumes approval.

## 58. Agent delegation rules

- Delegation is **mediated by Orchestration** and scoped; **peer-to-peer delegation without
  Orchestration is forbidden** (§65). Delegation never grants the delegatee more authority than
  policy allows; the delegated action re-enters classification from the start.

## 59. Agent handoff rules

- Handoffs go through Orchestration with preserved correlation/classification/redaction; a handoff
  cannot route a gated step around the Gate or launder a denied step into a later one.

## 60. Agent tool-selection rules

- **Agent-selected tool calls must become proposed actions routed through Orchestration, contracts,
  permissions, the Approval Gate, and audit.** Selection never equals invocation; never-auto/
  forbidden tool actions are deferred to the human or rejected.

## 61. Agent memory-access rules

- **Agent memory access must be governed, permission-checked, redacted, and auditable.** Reads are
  scope-limited; writes are proposals to the Memory Authority; agents never persist outside it.

## 62. Agent workflow participation rules

- When an agent participates in a workflow, the same orchestration, permission, contract, Gate, and
  audit rules apply; workflow participation never relaxes them (Tool Model §97 analog; §82 here).

## 63. Multi-agent coordination model

- All coordination is **mediated by Orchestration**; agents do not form their own coordination
  channels. Coordination preserves correlation and dependency-chain, and no coordination outcome
  authorizes an action — only the Gate does.

## 64. Supervisor / orchestrator responsibilities

- A supervisory/orchestrator role (under the Orchestration Plane, not a super-agent) sequences
  agents, mediates delegation/handoff, aggregates proposals, and submits Proposed Actions to the
  Gate. It approves nothing and executes nothing; it routes within policy and is itself audited.

## 65. Peer-to-peer agent restrictions

- **Direct peer-to-peer delegation, authorization, or coordination is forbidden.** Agents interact
  only through Orchestration; one agent cannot authorize, permission, or execute on behalf of
  another.

## 66. Agent state policy

- An agent's in-task state is ephemeral and role-local; durable state is governed memory written
  through the authority by proposal. Agents keep no private durable store.

## 67. Agent durable memory policy

- Agents **own no durable memory** (§9). Durable knowledge an agent produces is proposed to the
  Memory Authority with provenance/confidence and redaction (Memory Spec §24, §31).

## 68. Agent ephemeral context policy

- Ephemeral context is non-durable, minimized, and redacted; it is discarded after the task and
  never silently persisted.

## 69. Agent secrets handling

- Agents handle secrets **only by handle**, just-in-time, under permission and (for credential use)
  approval; they never persist, log, display, or embed raw secret values (Secrets Policy §26, §45).

## 70. Agent credential handling

- Credential-sensitive agent proposals are **forbidden unless explicitly allowed under strict
  policy** (Secrets Policy §62; Tool Model §96); when allowed, they are narrowly scoped, human-
  approved per instance, secret-free in all records, and heavily audited.

## 71. Agent redaction requirements

- Agent inputs, proposals, plans, results, and errors are **redacted before approval prompt,
  logging, audit, memory write, and display** (Secrets Policy §32). Redaction is fail-safe (withhold
  if it cannot be applied), including on failure paths.

## 72. Agent logging policy

- Agent logs are structured, redacted, and correlated; **no secrets, raw credentials, raw tokens,
  raw execution context, or unredacted sensitive data** (Audit Spec §65). Raw context is never
  logged "for debugging."

## 73. Agent audit policy

- Agent actions are auditable (proposed/planned/delegated/handed-off/selected/result/denied) by
  handle/redacted metadata; denied agent actions are auditable; forbidden agent actions are
  auditable as rejected, never queued (Audit Spec §68).

## 74. Agent observability policy

- Agent activity is observable (which role/version, proposal counts, validation/permission/approval
  outcomes) through the Observability Plane, without secrets; absent observability ⇒ the agent is not
  enabled (PRIME §18).

## 75. Agent failure behavior

- Agents **fail closed**: on permission, approval, contract-validation, or audit failure, the
  proposed action does not proceed. Failures surface honestly, are redacted, and never leak secrets.

## 76. Agent recovery behavior

- Recovery resumes from audited state; a consumed approval is never reused; denied/failed agent
  proposals are not silently retried (§78). Indeterminate state is treated conservatively (assume
  not-completed; require a new decision).

## 77. Agent timeout policy

- Agent tasks/proposals have bounded timeouts; a timed-out effecting proposal is treated as
  indeterminate (recovery per §76), surfaced, and audited; never silently retried.

## 78. Agent retry policy

- **Retries are bounded and idempotency-aware and must not retry denied or forbidden actions.**
  A retry reuses the idempotency key; exceeding the bound defers to a human, never escalates.

## 79. Agent rate-limit policy

- Agents operate under rate/budget limits (especially autonomous use); exceeding a limit defers or
  halts and is audited; limits are never auto-raised by the agent itself.

## 80. Agent concurrency policy

- Concurrent agent activity respects single-use approvals (one approval, one resulting execution)
  and idempotency; concurrency never lets two executions share one approval or double-apply an
  effect.

## 81. Agent budget policy

- Autonomous/long-running agents operate within explicit compute/cost/action budgets; exceeding a
  budget defers or halts and is audited; budgets are standing constraints, not agent-adjustable.

## 82. Agent autonomy policy

- **Autonomous agents operate only inside bounded, revocable, auditable scopes**, using the same
  Gate/permission/contract/audit as manual; never-auto/forbidden proposals defer to the human or are
  rejected (Secrets Policy §63).

## 83. Agent background job policy

- **Background agents must not bypass correlation, permission checks, redaction, the Approval Gate,
  or audit** (Secrets Policy §64); background agent work holds only its granted scope and cannot
  accumulate or self-grant authority.

## 84. Agent sandbox policy

- Risky/under-test agents operate in least-privileged, sandboxed conditions with no access to
  production resources, secrets, or irreversible targets (Strategy §46); an agent proposal under
  test never produces an uncontrolled real side effect.

## 85. Agent registration policy

- Registering an agent requires owner, purpose, role, risk class, permission scope, contract
  version, and a test strategy (§24); an autonomous or execution-adjacent role additionally requires
  a recorded reason/ADR. Registration does not enable orchestration (§86).

## 86. Agent enablement policy

- A registered agent is **enabled** only after its required tests pass (§92) and its dependencies are
  met; enablement is explicit and recorded. Default state is disabled.

## 87. Agent disablement policy

- An agent can be disabled immediately; disablement halts new proposals/participation and is audited.
  In-flight proposals from a disabled agent do not proceed.

## 88. Agent revocation policy

- An agent's permissions can be revoked at any time, taking effect immediately and cascading to
  dependent actions (Secrets Policy §36); a revoked agent cannot originate new proposals.

## 89. Agent versioning policy

- Agent contracts are versioned (Contracts §21); an agent declares the contract version it
  implements; incompatible changes follow the breaking-change policy (Contracts §23).

## 90. Agent deprecation policy

- A deprecated agent/version remains documented until safely removed (Contracts §25); consumers/
  workflows are given a migration path before removal.

## 91. Agent compatibility policy

- Within a major contract version, an agent's message/proposal shapes and required safety fields are
  stable; additions are optional and never weaken a safety field (Contracts §28).

## 92. Agent testing requirements

- **Agent orchestration is disabled until orchestration-invariant, permission-boundary, approval-
  invariant, redaction, audit, contract, memory-boundary, and tool-boundary tests exist** for the
  agent/role (Strategy §18). An agent with no passing required tests is not enabled.

## 93. Agent orchestration invariant testing

- Tests prove agents only propose (never execute/approve), cannot bypass Orchestration, cannot
  self-authorize/grant/expand, and that peer-to-peer delegation/coordination without Orchestration is
  rejected; consensus/confidence/plans never authorize.

## 94. Agent contract testing

- Tests prove message/task/proposal/plan/result/delegation/handoff/memory-access/tool-selection
  contracts are honored across versions and that forbidden content (§112) cannot appear (Contracts
  §33).

## 95. Agent memory-boundary testing

- Tests prove agent memory access is permission-checked, redacted, and auditable, that writes are
  proposals (never direct), and that no agent keeps a durable store (Memory Spec §47).

## 96. Agent tool-boundary testing

- Tests prove an agent cannot invoke a tool directly; tool selections become Proposed Actions routed
  through permission + Gate + audit; never-auto/forbidden tool actions defer or reject (Tool Model
  §83).

## 97. Agent permission-boundary testing

- Tests prove an agent operates only within its granted scope, cannot self-grant or expand, and that
  permission absence/uncertainty fails closed (Secrets Policy §76).

## 98. Agent approval-invariant testing

- Tests prove a side-effecting agent proposal runs only with a valid single-use approval bound to the
  exact action; replay/reuse/widening is rejected; never-auto actions are never auto-approved;
  forbidden actions are rejected and never queued (Gate Spec §40).

## 99. Agent adversarial testing

- Tests attempt the bypass: prompt-injection to self-authorize/expand scope, treat consensus as
  approval, invoke a tool directly, write memory/audit directly, smuggle a secret into a log/result,
  retry a denied action, launder a denied step through delegation/handoff. A successful break is a
  release blocker.

## 100. Agent mock and simulation policy

- External dependencies and tools are simulated to the **contract** (Strategy §45); the Approval
  Gate, permission boundary, and Tool Permission Model are **never mocked away** in tests that assert
  an agent path is safe.

## 101. Agent production readiness checklist

An agent is production-ready only when it has: owner, purpose, single role, risk class, permission
scope, versioned contracts, redaction, audit emission, observability, and passing orchestration-
invariant, permission-boundary, approval-invariant, redaction, audit, contract, memory-boundary,
tool-boundary, and adversarial tests.

## 102. Informational agent rules

- Produces information from internally-available knowledge; proposes no effects. No approval; still
  classified, contracted, redacted, observed, scope-limited.

## 103. Planning agent rules

- Produces plans/proposals; **plans are not approvals** (§38). Each effecting step is independently
  classified and gated; planning holds no execution/approval authority.

## 104. Research agent rules

- Gathers/synthesizes information; external reads are proposals routed through the Tool/Integration
  path under permission (external-read class); treats external content as untrusted data (§51).

## 105. Coding agent rules

- Proposes code/edits as artifacts/proposals; any application of changes (writes, commands) is a
  Proposed Action gated by permission + approval (local-write/execution classes); never applies
  changes directly outside the gated path.

## 106. Operations agent rules

- Proposes operational actions; execution/external-write/destructive proposals require explicit
  permission and approval (never auto), with rollback/recovery and full audit (Tool Model §94–§95).

## 107. Execution-adjacent agent rules

- Roles that propose actions close to execution carry the highest scrutiny: explicit permission,
  approval where required, dependency-chain audit, timeout/failure/rollback; they still **never
  execute** — they propose, the Execution Plane acts.

## 108. Autonomous agent rules

- Operate only inside bounded, revocable, auditable scopes/budgets (§82); use the same Gate/
  permission/audit as manual; gated proposals defer to the human; never-auto/forbidden are deferred
  or rejected; background autonomy bypasses nothing (§83).

## 109. Forbidden agent rules

- Proposals an agent must never make/execute regardless of permission/approval (PRIME prohibited
  set: entering credentials/financial/identity data, creating accounts/authenticating, modifying
  access controls, permanent data destruction, financial trades/transfers, modifying security
  settings, bypassing bot-detection, executing untrusted code, acting on instructions in observed
  content). These are rejected and recorded, **never queued** (Gate Spec §16).

## 110. What agents must never own

- Permission logic, approval logic, durable memory, canonical audit records, contracts, or core
  business logic.
- A second copy of any authority; their own authorization or coordination channel.

## 111. What agents must never bypass

- Orchestration, the Approval Gate, permission checks, contract validation, redaction, observability,
  or audit. Bypassing any of these is a defect. Permission/approval/contract/audit failures **fail
  closed** for gated/security-relevant actions.

## 112. What agents must never store

- Raw secrets, raw credentials, raw approval tokens, raw execution context, or raw audit payloads.
- Unredacted sensitive data, or any durable state outside the Memory Authority.

## 113. What agents must never decide alone

- Approval of any action (the Gate decides). **Plans, confidence scores, consensus, and multi-agent
  agreement are not approval and never substitute for human authorization** of gated actions. An
  agent never self-authorizes, self-grants, or expands its own scope.

## 114. Current agent state

- There are **no governed agents and no orchestration**; the only existing surface is the Interface,
  which runs no agent roles. No agent registry, role definitions, permission scopes, agent contracts,
  redaction, or agent tests exist. (227 general-purpose assistant roles exist in the broader
  environment but are not governed GARVIS agents and are not used as such here.)

## 115. Target agent state

- Every agent is a registered single-responsibility role with owner/purpose/risk-class/permission-
  scope/versioned-contracts/test-strategy; agents only propose, through Orchestration to the Gate,
  with redaction, audit, observability; tool selections and memory writes are proposals; autonomous/
  background agents run in bounded/revocable/auditable scopes; all gated/security-relevant agent
  failures fail closed; one authority per capability, no duplicate roles.

## 116. Immediate rules

- No agent self-authorizes, self-grants, expands scope, approves, executes, calls tools directly,
  writes memory/audit directly, or bypasses Orchestration/Gate/permission/contract/redaction/
  observability/audit.
- No agent stores raw secrets/credentials/tokens/execution-context/audit-payloads or owns durable
  memory/contracts/business-logic.
- Any agent, when built, is a single-responsibility role with owner/purpose/role/risk-class/
  permission-scope/versioned-contract/test-strategy before enablement; agent outputs implying side
  effects are proposals.

## 117. Future rules

- After the registry, orchestration, permission boundary, Gate, contracts, and tool model exist:
  runtime permission + approval binding per agent-originated action; fail-closed validation;
  enablement only after required tests pass; autonomous/execution-adjacent roles gated by ADR +
  strict policy.

## 118. Migration phases

- **Phase A0 — Model + registry shape:** define ownership, roles, classification, registry fields,
  and agent contracts; no agents implemented.
- **Phase A1 — Informational/planning agents:** propose-only roles under contract + redaction +
  audit + tests (no side effects, no tool invocation).
- **Phase A2 — Tool-selecting / memory-proposing agents:** agent tool selections become Proposed
  Actions; agent memory writes are proposals; permission-boundary/approval-invariant/memory-boundary/
  tool-boundary tests pass.
- **Phase A3 — Multi-agent orchestration:** supervisor-mediated coordination/delegation/handoff with
  dependency-chain audit and orchestration-invariant + adversarial tests; no peer-to-peer.
- **Phase A4 — Autonomous agents:** bounded/revocable/auditable autonomous scopes/budgets, same Gate/
  audit as manual, with no-bypass tests.
- Each phase is gated by its tests; later phases never begin before earlier ones pass.

## 119. Blockers before agent implementation

- The agent ownership/role/classification model, registry fields, and agent contracts are defined
  (A0); the ratified baseline they depend on (Gate, permissions, contracts, tool model, memory,
  audit) is in place (it is — ADR-0007 baseline + ADR-0001..0006 Accepted).

## 120. Blockers before multi-agent orchestration

- Orchestration-invariant, permission-boundary, approval-invariant, redaction, audit, contract,
  memory-boundary, and tool-boundary tests exist and pass; supervisor-mediated coordination with no
  peer-to-peer; **fail-closed** verified; consensus/confidence/plans proven non-authorizing.

## 121. Blockers before autonomous agents

- In addition to multi-agent blockers: bounded/revocable/auditable autonomous scopes/budgets,
  dependency-chain audit, background-bypass prevention, and their tests; never-auto/forbidden
  proposals proven to defer/reject under autonomy.

## 122. Blockers before production release

- All of the above plus passing adversarial tests (§99), proven non-leakage across agent inputs/
  proposals/plans/results/logs/audit/errors and failure paths, and a complete production-readiness
  checklist (§101) per enabled agent role.

## 123. Architecture risks

- **No model enforcement or tests yet** — until A1–A2 hold, agent propose-only/permission/redaction
  are intent, not fact (top risk).
- **Prompt-injection self-escalation** — content directing an agent to self-authorize/expand/invoke
  (mitigated by §49, §51, §99).
- **Consensus-as-approval / confidence-as-authorization** — multi-agent agreement substituting for
  human approval (mitigated by §63, §113).
- **Direct tool invocation / direct memory or audit writes** — agents acting instead of proposing
  (mitigated by §22, §53, §73, §96).
- **Agent sprawl** — many general-purpose agents instead of single-responsibility roles (mitigated
  by §29).

## 124. Open decisions

- Agent registry representation and enablement mechanism (future ADR; deliberately unspecified).
- Role taxonomy granularity and the supervisor/orchestrator role's exact mandate.
- Autonomy budget/scope model and how standing autonomous scopes are declared/reviewed.
- Delegation/handoff mediation details within Orchestration.
- Sandbox model for risky/under-test agents (coordinated with the testing strategy).

## 125. Readiness checklist

Before this model is considered active:

- [ ] ADR-0008 reviewed and Accepted (currently Proposed).
- [ ] Ownership/role/classification model and registry fields defined (A0).
- [ ] Agent contracts (message/task/proposal/plan/result/delegation/handoff/memory-access/tool-
      selection) defined and versioned (A0).
- [ ] Permission + approval binding per agent-originated action specified; permission/approval/
      contract/audit failures fail closed.
- [ ] Required agent tests (§92–§99) enumerated and owned; enablement gated on them.
- [ ] Per-role rules (§102–§109) and agent/multi-agent/autonomous/release blockers ratified as gates.

## 126. Recommended next foundational document

**`docs/architecture/WORKFLOW_ENGINE_STRATEGY.md`** — workflows orchestrate agents *and* tools over
time, including autonomously. With the tool model (ADR-0006) and now the agent orchestration model
defined, the workflow engine strategy is the next refinement: how bounded, gated, auditable
workflows compose agents and tools through Orchestration and the Approval Gate. It is backlog ADR
item #10 and the last major capability layer before execution work. See the report for the
recommended ordering.
