# GARVIS — Approval Gate Specification

**Status:** Binding security/architecture specification · **Scope:** Every outward effect in
GARVIS, from any surface, manual or autonomous · **Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md) and
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md). Where this document and
those appear to conflict, the constitution prevails; the conflict is reported, not silently
resolved.

This specification defines the **behavior and contracts** of the Approval Gate. It is
vendor-neutral and contains no implementation code, schemas in any language, products, models,
or APIs. It specifies *what must be true*, not *how to build it*.

---

## 1. Purpose

- Define the single mandatory control through which every action with a side effect passes
  before execution, regardless of which surface (interface, voice, autonomous) originated it.
- Specify the action lifecycle, classification model, request/decision contracts, token
  semantics, audit requirements, and security invariants that govern that control.
- Provide an enforceable reference that must be satisfied **before** any execution,
  automation, agent, browser, local-machine-control, repository, container, or autonomous
  workflow capability is enabled.

## 2. Why the Approval Gate exists

- Without a single chokepoint, each surface and capability would re-implement its own
  authorization, and any one of them could become a bypass.
- GARVIS aims at real-world effects; the cost of an unauthorized or irreversible action is
  high. The Gate exists to make every such effect **explicit, classified, authorized,
  reversible-aware, and recorded**.
- It converts "the system can act" into "the system can act **only** as authorized, and the
  record proves it."

## 3. Scope

- **In scope:** every proposed action that could change state outside the proposing plane,
  produce an externally-visible result, consume a permission, cross a trust boundary, or be
  irreversible — from manual, voice, and autonomous origins alike.
- **In scope:** classification, approval, denial, deferral, expiration, revocation, single-use
  tokens, audit, redaction, failure/recovery behavior, and the invariants that bind them.
- **Out of scope of the Gate (still governed elsewhere):** how planes are implemented, how
  tools work internally, the storage technology of memory or audit, and user-experience design
  of any approval surface.

## 4. Non-goals

- The Gate is **not** a user-interface feature; an approval surface is one possible presenter,
  not the control itself (§6).
- The Gate does **not** plan actions (that is Orchestration) or perform them (that is
  Execution); it authorizes or refuses them.
- The Gate does **not** grant standing capability; that is permission, a separate concern
  (§28).
- This document does **not** implement the Gate, define data formats, or choose tooling.

## 5. Core principles

- **Mandatory single chokepoint.** No outward effect reaches Execution except through one
  Approved Action issued by the Gate.
- **Deny/closed by default.** Unknown, unclassifiable, or ambiguous actions are treated as
  higher-risk and are never auto-approved; on Gate failure the answer is "no" (§35).
- **Permission is not approval** (§28). Both may be required; neither substitutes for the
  other.
- **Approval is scoped, explicit, auditable, and revocable.** It authorizes one specific
  action within stated constraints, on the record, and can be withdrawn.
- **Single-use tokens.** An approval authorizes exactly one execution and cannot be reused or
  generalized (§22, §23).
- **No self-approval.** No agent, tool, or autonomous process approves its own or a peer's
  action (§31, §32).
- **Conservative classification.** When several classes apply, the **highest** risk wins.
- **One model for all origins.** Autonomous workflows use the same Gate, classes, and audit as
  manual requests (§27).
- **Secrets are never shown.** Approval prompts and logs never display secret values (§34).
- **Forbidden is not "gated."** Forbidden actions are rejected, never queued for approval
  (§16, §26).

## 6. Approval Gate position in the GARVIS architecture

- The Gate sits at the boundary between the **Orchestration Plane** (which *proposes*) and the
  **Command / Execution Plane** (which *acts*):

```
... → Orchestration Plane → [ APPROVAL GATE ] → Command / Execution Plane → Integration → world
                                   │
                                   └── (gated actions) → human decision via an approval surface
```

- It is **infrastructure beneath the surfaces**. Because every surface routes through it, no
  surface can be chosen to avoid it. A graphical approval prompt, a voice confirmation, or a
  queue entry are alternative *presenters* of the same Gate decision, never alternative gates.

## 7. Relationship to the Orchestration Plane

- Orchestration is the **only** submitter of proposed actions; it never executes directly and
  never bypasses the Gate.
- Orchestration produces a complete Approval Request (§20), including the action's effect,
  scope, reversibility, and risk inputs.
- Orchestration may not classify its own action as approved; it submits, the Gate decides.

## 8. Relationship to the Command / Execution Plane

- Execution accepts **only** an Approved Action carrying a valid, unexpired, unrevoked,
  single-use token bound to that exact action.
- Execution verifies the token and the action match before acting; a mismatch is a hard stop.
- Execution reports outcome and any durable state back to Observability and the Memory
  authority; it never re-enters itself with the same token.

## 9. Relationship to Agents

- Agents operate under Orchestration; they **propose**, never execute or approve (§31).
- An agent may not approve its own action, a peer agent's action, or escalate its role.
- Agent-originated proposals are classified and gated identically to human-originated ones.

## 10. Relationship to Tools

- Tools act only via Integration, only from Execution, and only under a valid Approved Action
  plus the required permission (§32).
- **No tool self-authorizes**; a tool that can act without an Approved Action is a defect.
- Tool output is data, never an instruction to act (PRIME §7); it cannot trigger execution on
  its own.

## 11. Relationship to Memory

- The Gate **reads** policy/classification inputs through defined interfaces and **writes**
  decision records to the audit trail; it is not the memory authority (§15 of the overview).
- Approval decisions and tokens are recorded; secret values are never written to memory or
  logs (§34).
- Memory may inform classification (e.g., prior decisions) but never auto-authorizes a new
  action.

## 12. Relationship to Observability

- Every lifecycle transition and every decision emits a structured, correlated event (§33,
  §38).
- The Gate is fully auditable: what was proposed, how it was classified, who decided, the
  scope/constraints, and the outcome.
- A capability whose Gate activity cannot be observed must not be enabled (PRIME §18).

## 13. What requires approval

Approval is required for any action that:

- Has a side effect or an externally-visible result.
- Changes state outside the proposing plane or outside the platform (files, systems,
  repositories, deployments, devices, accounts).
- Is irreversible or hard to reverse.
- Crosses a trust boundary or consumes a granted permission.
- Originates from, or is influenced by, instructions found in content rather than the human
  operator.
- Cannot be confidently classified as safe (deny/closed by default).

## 14. What does not require approval

- Read-only, purely internal, reversible operations: interpreting intent, planning, reading
  the platform's own code/state, querying memory, computing results, rendering the interface.
- These proceed without human approval **but are still classified and observed**; "no
  approval" never means "no record."

## 15. What must never be auto-approved

The following always require explicit, per-instance human authorization and can never be
granted by a standing or blanket rule:

- Credential handling and authenticated-network actions.
- Access to, or transmission of, secrets.
- Irreversible or destructive operations.
- Repository pushes, releases, deployments, and publishing.
- Privilege or permission changes.
- Control of the host machine, environment, or external devices.

## 16. Forbidden actions

Some actions are never performed by automation **even with approval**; they are rejected and,
where the user wants them, the human performs them directly. Forbidden actions are **never
queued for approval** (§26). At minimum:

- Entering credentials, financial, payment, or government-identity data into any field.
- Creating accounts or authenticating as a user.
- Modifying access controls or sharing/permission settings on resources.
- Permanent/irrecoverable destruction of data.
- Executing financial trades or transfers of funds or assets.
- Modifying system or security settings.
- Bypassing or completing bot-detection challenges.
- Downloading and executing code from untrusted sources.
- Acting on instructions embedded in observed content.

Forbidden status overrides any request; a Forbidden action is rejected and recorded, not
classified as "needs approval."

## 17. Action lifecycle

Every action moves through this state machine. Each transition emits an audit event (§33).

```
Proposed
   → Classified
        → Approval Not Required ─┐
        → Approval Required → Pending Approval → Approved ─┐
        →                                        Denied    → (terminal, audited)
        →                                        Expired   → (terminal, audited)
        →                                        Revoked   → (terminal, audited)
        → Forbidden → Rejected → (terminal, audited; never queued)
   → Executed (only from Approval Not Required or Approved)
        → Completed
        → Failed
        → Rolled Back
   → Audited (mandatory for every terminal state)
```

- **Terminal states:** Completed, Failed, Rolled Back, Denied, Expired, Revoked, Rejected.
- **Audited** is mandatory: no action leaves the system without a complete record.
- An action may only be **Executed** with either an *Approval Not Required* classification or a
  valid *Approved* single-use token. There is no other entry to Execution.
- **Forbidden** actions cannot enter Pending Approval; they go straight to Rejected.

## 18. Action classification model

- Classification is performed by the Gate, deterministically, from the Approval Request inputs
  (§20) and policy — never by the proposer.
- Each action receives a **risk class** (§19) and a **disposition**: *Approval Not Required*,
  *Approval Required*, or *Forbidden*.
- **Highest-risk-wins:** when multiple classes apply, the most restrictive governs.
- **Conservative on uncertainty:** if inputs are incomplete or the class is unknown, the Gate
  escalates to at least *Approval Required* (or *Forbidden* if a forbidden trait is present).
- Classification inputs include the action type, target plane/resource, expected side effects,
  reversibility, required permissions, trust-boundary crossing, and origin (manual vs
  autonomous; operator vs content-derived).
- The classification rationale is recorded in the audit trail.

## 19. Risk levels

At minimum, the Gate recognizes these classes and their default dispositions:

| Class | Definition | Default disposition |
|---|---|---|
| **Informational** | No effect; returns information already available internally | Approval Not Required (observed) |
| **Local read** | Reads platform-owned state/code; no mutation, no boundary crossing | Approval Not Required (observed) |
| **Local write** | Mutates platform-owned state, reversibly and in-scope | Approval Not Required only if reversible **and** in-scope; otherwise Approval Required |
| **External read** | Reads from outside the trust boundary | Approval Required by default (sensitive/unknown targets always Required) |
| **External write** | Changes state outside the trust boundary | Approval Required — never auto |
| **Execution** | Runs a command/process/tool with effects | Approval Required — never auto |
| **Destructive** | Irreversible or hard-to-reverse loss/overwrite | Approval Required, explicit; never auto |
| **Credential-sensitive** | Touches secrets, credentials, or authenticated access | Never auto: explicit human approval **or Forbidden** by risk (§15, §16) |
| **Autonomous** | Origin attribute, not an effect: action proposed by an autonomous trigger | Inherits the effect's class; origin may only **raise** restriction, never lower it (§27) |
| **Forbidden** | Actions automation must never perform | Rejected; never queued (§16) |

- The **Autonomous** attribute is evaluated *together with* the effect class; it never grants
  auto-approval to an otherwise-gated effect.

## 20. Approval request contract

A proposed action carries, conceptually, at least these fields (described, not coded):

- **action_id** — unique identifier for this proposed action.
- **requested_by** — the proposing agent/role/process identity.
- **originating_plane** — where the proposal came from.
- **target_plane** — where the effect would be carried out.
- **action_type** — the kind of action.
- **target_resource** — the specific resource/target affected.
- **risk_class** — proposed class input (the Gate independently re-derives the final class).
- **required_permissions** — permissions the action would consume.
- **proposed_parameters** — the concrete parameters of the action.
- **redacted_parameters** — the display/log-safe form, with secrets removed/masked (§34).
- **expected_side_effects** — what would change, externally and internally.
- **user_visible_summary** — a concise, plain-language description for the decision-maker.
- **justification** — why the action is proposed.
- **preview_or_diff** — a preview or diff of the change when applicable.
- **rollback_strategy** — how the effect would be undone, when applicable (§37).
- **expiration_time** — when the proposal/approval window lapses (§24).
- **idempotency_key** — to detect/deduplicate repeats and make retries safe (§26, §36).
- **dependency_chain** — prerequisite actions/approvals this depends on.
- **audit_correlation_id** — ties all events for this action together (§33).

- A request missing fields needed to classify or to undo the action is treated conservatively
  (escalated or rejected), never assumed safe.

## 21. Approval decision contract

A decision carries, conceptually, at least:

- **decision_id** — unique identifier for the decision.
- **action_id** — the action being decided.
- **decision** — Approved / Denied (and, by reference, Expired/Revoked as decision events).
- **approved_by** — the authorizing human (or the Gate itself for *Approval Not Required*).
- **approval_scope** — exactly what is authorized (target, parameters, boundaries).
- **constraints** — limits attached to the approval (e.g., scope/quantity/conditions).
- **expiration_time** — when the resulting token expires (§24).
- **reason** — rationale for approval/denial.
- **timestamp** — when the decision was made.
- **audit_correlation_id** — same correlation id as the action.

- A decision authorizes **only** the exact action and scope described; anything outside scope
  is unauthorized.

## 22. Approval token model

- An **Approved Action** is represented by an approval **token** bound to: the specific
  action_id, the approved scope/constraints, and an expiration.
- The token is the **only** thing Execution accepts as authorization.
- A token authorizes **one** execution of **one** action within its scope; it conveys no
  standing capability.
- Tokens are unforgeable in principle (their validity is verifiable) and are never derived
  from, or shared across, other actions.

## 23. Single-use approval semantics

- A token is consumed on first use and is immediately invalid thereafter.
- Re-execution requires a **new** proposal, classification, and decision.
- A token cannot be widened, reused for a "similar" action, or applied to a different target,
  parameter set, or time window.
- Replay of a consumed or expired token is rejected and recorded as a security event.

## 24. Expiration and revocation

- Every approval has an **expiration**; an unused token past expiry transitions the action to
  **Expired** (terminal) and cannot execute.
- Approvals are **revocable** at any time before consumption; revocation transitions the action
  to **Revoked** (terminal).
- Revocation of an in-flight dependency cascades: dependent actions whose prerequisites are
  revoked/expired cannot execute.
- Expiration and revocation are both audited with reason and time.

## 25. Denial handling

- A **Denied** action is not executed and is **not automatically rephrased, re-classified, or
  retried** by any agent or process.
- The denial, with reason and scope, is returned to the requester and recorded.
- A genuinely different action may be submitted as a **new** proposal that re-enters
  classification from the start; it must not be a cosmetic re-wording of the denied one to
  evade the decision.
- Repeated near-identical resubmissions are detectable via the idempotency key and are
  surfaced, not silently processed.

## 26. Deferred approval queue

- Actions requiring human approval that cannot be decided synchronously enter a **deferred
  approval queue** in **Pending Approval**.
- The queue **never** contains Forbidden actions; Forbidden actions are rejected at
  classification.
- Queue entries carry their full request, risk class, expiration, idempotency key, and
  correlation id; they are de-duplicated by idempotency key.
- Queued actions do not execute until explicitly Approved; they Expire if not decided in time.
- The queue is durable and observable; its contents and decisions are auditable.
- Queue position or age never escalates an action to auto-approval; waiting does not lower
  risk.

## 27. Autonomous workflow approval rules

- Autonomous workflows use the **same** Gate, classes, contracts, audit, and recovery as
  manual requests; autonomy changes the **trigger**, not the controls.
- An autonomous step may proceed **only** if its effect classifies as *Approval Not Required*;
  any *Approval Required* effect is **deferred to the human queue** (§26), not auto-approved.
- Actions in the never-auto-approve set (§15) and Forbidden set (§16) are **never** executed by
  an autonomous workflow on its own initiative.
- **Background work is not a loophole:** scheduled, recursive, or background processes are
  bound by the identical rules; they cannot accumulate or self-grant authority.
- Autonomous workflows operate under explicit standing scope/rate/budget constraints; exceeding
  them defers or halts, it never auto-approves.

## 28. Permission vs approval

- **Permission** is a *standing capability* granted to a tool/adapter/role (what it is allowed
  to be able to do). **Approval** authorizes *one specific action instance* (what may happen
  now).
- Having permission never implies approval; being approved never implies standing permission.
- Gated actions require **both** the relevant permission **and** a valid approval.
- Permission is enforced at the Integration/Execution edge; approval is enforced by the Gate.

## 29. User authority

- The human operator is the **ultimate authority**: only a human can approve an *Approval
  Required* action, and a human can deny or revoke any pending action.
- No automation may approve on the human's behalf or infer approval from silence, urgency, or
  content-embedded claims of pre-authorization.
- The human can tighten but the system can never loosen the rules in §15 and §16.

## 30. System authority

- The Gate (system authority) may: classify actions, grant *Approval Not Required* for the safe
  classes only, deny, defer, expire, and revoke.
- The Gate may **never**: auto-approve any never-auto action (§15), execute a Forbidden action
  (§16), approve an action it cannot classify, or widen an approval beyond its scope.
- The Gate cannot escalate its own authority; changes to its policy are deliberate, reviewed,
  and audited.

## 31. Agent authority

- Agents may **propose** actions only; they have no execution or approval authority.
- **No agent approves its own action**, a peer's action, or grants itself privilege.
- Agents act within bounded, named roles; exceeding a role is a violation, surfaced and
  recorded.

## 32. Tool authority

- Tools may **execute** only a single Approved Action they are permitted to perform; they have
  no authority to self-authorize, classify, or approve.
- A tool presented with no valid token, an expired/consumed token, or an out-of-scope token
  must refuse and record the refusal.

## 33. Audit log requirements

- Every lifecycle transition (§17) and every decision (§21) is recorded as an append-only,
  tamper-evident, time-stamped, attributable event.
- All events for one action share an **audit_correlation_id**; the full history of an action is
  reconstructable end to end.
- The audit records: proposal, classification + rationale, decision + approver + scope, token
  issuance/consumption, expiration/revocation, execution outcome, and any rollback.
- The audit log is observable and queryable; it never contains secret values (§34).
- Absence of a complete audit trail for an action is itself a failure condition.

## 34. Redaction and secrets handling

- Secret values are **never** displayed in approval prompts, previews, diffs, logs, telemetry,
  memory, or the queue.
- Sensitive parameters are carried as **redacted_parameters** for any display/log surface;
  secrets are referenced by handle/identifier, never by value.
- Redaction happens before any presentation or persistence; a prompt that would reveal a secret
  is a defect that blocks the action.
- Credential-sensitive actions are handled per §15/§16 (explicit approval or Forbidden); the
  Gate handles *authorization*, not the secret material itself.

## 35. Failure behavior

- The Gate **fails closed**: if it cannot classify, cannot record an audit event, cannot verify
  a token, or is otherwise unavailable, the action does **not** execute.
- A failure to obtain or persist a decision is treated as a denial for execution purposes and
  is surfaced and recorded.
- No path exists in which a Gate failure results in an action proceeding unauthorized.

## 36. Recovery behavior

- Recovery resumes from the last **audited** state; the audit trail is the source of truth for
  where an action stood.
- Recovery never re-executes a consumed token and never silently retries a Failed or Denied
  action; re-attempt requires a new proposal and decision.
- The **idempotency_key** makes safe re-proposal detectable, preventing duplicate effects on
  recovery.
- An interrupted action whose state cannot be determined is treated conservatively (assume
  not-completed; require human decision before re-attempt).

## 37. Rollback expectations

- Side-effecting actions are **reversible-first**: a **rollback_strategy** is required for any
  action whose default class is Local write (non-trivial), External write, Execution, or
  Destructive.
- An action with no feasible rollback requires explicit human approval **and** a defined
  recovery path before it may run; absence of both blocks it.
- A rollback is itself an action subject to classification, approval where required, and audit.
- A **Rolled Back** outcome is a terminal, audited state distinct from Completed and Failed.

## 38. Observability requirements

- The Gate emits a structured, correlated event for every transition and decision (§33).
- Current Gate state is queryable: pending approvals, recent decisions, active tokens (by
  reference, never secret values), and rejection/denial counts.
- The Gate can report its own configuration version and the policy under which a decision was
  made.
- Observability is a precondition for enabling any new capability through the Gate.

## 39. Testing and verification requirements

- The Gate's invariants (§40) are verified by automated, repeatable, adversarial tests
  **before** any execution capability is enabled (PRIME §14, §15).
- Required test coverage includes, at minimum:
  - No execution path bypasses the Gate.
  - A token is single-use; replay/reuse is rejected.
  - No agent/tool can approve its own action.
  - Forbidden actions are never queued and never executed.
  - Never-auto actions are never auto-approved, including from autonomous origins.
  - The Gate fails closed on classification/audit/token failures.
  - Secrets never appear in prompts, logs, previews, or the queue.
  - Denied actions are not auto-retried; expired/revoked tokens do not execute.
- Tests are deterministic and isolated; a failing invariant test blocks enabling execution.

## 40. Security invariants

These must hold at all times:

1. **No bypass:** every outward effect passes through exactly one Gate decision.
2. **Single-use:** an approval authorizes exactly one execution and cannot be reused or widened.
3. **No self-approval:** no agent/tool/process approves its own or a peer's action.
4. **Permission ≠ approval:** gated actions require both; neither substitutes for the other.
5. **Never-auto holds:** credential-sensitive, destructive, external-write, deploy/publish,
   privilege-change, and host-control actions are never auto-approved.
6. **Forbidden is rejected, never queued.**
7. **Scoped authority:** an approval authorizes only the exact action and scope stated.
8. **Fail closed:** any Gate failure blocks execution.
9. **No silent retry:** denied/failed/expired/revoked actions are not auto-retried or
   auto-rephrased.
10. **Secret-safe:** no secret value is ever displayed, queued, logged, or stored.
11. **Same model for autonomy:** autonomous and background work obey identical rules.
12. **Complete audit:** every action ends Audited, with a reconstructable history.

## 41. Implementation phases

Phases are sequenced so that no capability outruns the control that governs it. Each phase is
gated by the verification in §39.

- **Phase A — Specification (this document).** Contracts, lifecycle, classes, invariants
  defined and reviewed.
- **Phase B — Enforced boundary (single plane).** The Gate is enforced for one execution path;
  classification, single-use tokens, audit, and fail-closed proven by tests before use.
- **Phase C — Deferred approval queue.** Durable Pending-Approval queue with expiration and
  idempotent de-duplication; human decision path verified.
- **Phase D — Autonomous integration.** Autonomous/background triggers routed through the same
  Gate; never-auto and Forbidden enforcement re-verified under autonomy.
- **Phase E — Capability broadening.** Additional action classes and integrations onboarded one
  at a time, each re-verifying the invariants before exposure.

No execution, automation, agent, browser, host-control, repository, or container capability is
enabled ahead of the phase that governs it.

## 42. Architecture risks

- **The Gate is specified but not yet enforced**; until Phase B holds with passing invariant
  tests, the safety model is intent, not fact. *(Highest priority.)*
- **Classification correctness** is the crux: a mis-classified action is the primary failure
  mode. Conservative defaults reduce, but do not eliminate, this risk.
- **Denial-evasion by rewording** could route around a decision if resubmission isn't policed
  (mitigated by §25 + idempotency, still requires vigilance).
- **Autonomous loophole** risk if background work is built before Phase D enforcement.
- **Audit/redaction gaps** would undermine both accountability and secret-safety if added late
  rather than from Phase B.
- **Token handling weaknesses** (replay, widening) would break single-use semantics if not
  verified adversarially.

## 43. Open decisions

- **Synchronous vs. queued approval as the default** for gated actions, and the human-decision
  channel for the queue.
- **Risk-taxonomy ownership and change process:** who defines and amends the class rules the
  Gate applies.
- **Token validity model:** lifetime defaults, binding granularity, and replay-prevention
  approach (specified behaviorally here; mechanism deferred).
- **Standing autonomous scope/budget limits:** how constraints for autonomous workflows are
  declared and reviewed.
- **Audit retention and tamper-evidence model:** retention horizon and integrity guarantees.
- **Boundary granularity:** how finely "one Gate decision per effect" is drawn for composite
  actions and dependency chains.

## 44. Readiness checklist

Before any execution capability is enabled, all of the following must be true and verified:

- [ ] Gate is enforced for the target execution path; no bypass exists (§40.1).
- [ ] Action lifecycle (§17) is implemented with all terminal states audited.
- [ ] Classification (§18–§19) is deterministic, conservative, and recorded.
- [ ] Approval request and decision contracts (§20–§21) are complete.
- [ ] Tokens are single-use, scoped, expiring, and revocable (§22–§24).
- [ ] Never-auto (§15) and Forbidden (§16) enforcement verified, including under autonomy.
- [ ] Deferred queue rejects Forbidden, de-duplicates, expires, and never auto-escalates (§26).
- [ ] Fail-closed behavior verified (§35); recovery never re-uses tokens (§36).
- [ ] Rollback strategy required and validated for risky classes (§37).
- [ ] Complete, append-only, correlated audit with no secrets (§33–§34).
- [ ] Adversarial invariant tests (§39) pass and block on failure.

## 45. Recommended next foundational document

**`docs/architecture/PROJECT_STRUCTURE.md`** — now that the load-bearing control is specified,
map the repositories, planes, and their declared interfaces onto the file system so the Gate
and the planes around it have a concrete, governed home. With the Gate's safety semantics
fixed, structure can be laid out around it without later rework.

Close seconds: an **ADR process + template** (to capture §43 as decisions are resolved) and a
**`MEMORY_AUTHORITY_SPEC.md`** (the single-writer memory authority the audit trail relies on).
