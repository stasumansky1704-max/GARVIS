# GARVIS — Testing & Verification Strategy

**Status:** Binding strategy (governed by ADR-0001) · **Scope:** How GARVIS proves correctness
and safety before capability is enabled · **Conforms to:**
[`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md),
[`ADR_PROCESS.md`](./ADR_PROCESS.md). Where this document and those conflict, the constitution
prevails; the conflict is reported, not silently resolved.

Vendor-neutral: no products, test frameworks, models, APIs, or temporary implementation detail,
and no implementation code. It defines *what must be verified and when*, not *which tool does
it*.

---

## 1. Purpose

- Define the long-term testing and verification discipline that lets GARVIS earn capability
  safely: nothing acts on the world until its correctness and safety are proven.
- Establish the invariant tests, blockers, and checklists that gate execution, autonomy, and
  release.

## 2. Scope

- **In scope:** test types, per-plane and per-capability verification, safety-invariant tests,
  manual/automated rules, CI/local/pre-merge/pre-release gates, data/mocking/sandbox policy,
  coverage expectations, blockers, ownership, and the migration from today's state.
- **Out of scope of this doc:** which frameworks/tools are used, and writing the tests
  themselves (no tests are added here).

## 3. Non-goals

- Not a tool selection; not a coverage-percentage fetish; not a substitute for the Approval
  Gate (run-time control) or ADRs (decision record).
- Not a promise that tests guarantee correctness — they reduce risk and **block** unproven
  capability; they do not license unverified action.

## 4. Why verification must precede execution

- GARVIS aims at real effects; an unverified side-effecting path is an unbounded risk.
- The constitution requires the verification layer to exist **before** execution capability
  (PRIME §14–§15); the Approval Gate's readiness depends on passing invariant tests
  (Gate Spec §39, §44).
- Therefore: **capability is gated by proof.** A capability with no passing required tests is
  not enabled, regardless of schedule pressure.

## 5. Relationship to GARVIS PRIME

- Implements PRIME §10 (quality), §14 (testing), §15 (capability earned in stages), and §19
  (fail safe). "Verification before execution" is a constitutional rule this document
  operationalizes.

## 6. Relationship to Architecture Overview

- Tests **mirror the plane boundaries** (Overview §4, §6–§7). Each plane and the cross-cutting
  systems (Memory, Observability) have defined verification; boundaries are checked by contract
  tests.

## 7. Relationship to Approval Gate

- The Approval Gate's invariants (Gate Spec §40) are a **first-class, required** test suite.
- No execution path may bypass Gate tests; the Gate's readiness checklist (Gate Spec §44) is
  reproduced and extended here (§59).

## 8. Relationship to Project Structure

- Tests follow `PROJECT_STRUCTURE.md` §9/§39: they mirror the plane tree, are separated from
  runtime code, and never ship as production logic.

## 9. Relationship to ADR Process

- This strategy is adopted via **ADR-0001** (per `ADR_PROCESS.md`). Changes to it occur by a
  superseding ADR, not by silent edits. Every ADR states a validation strategy that conforms to
  this document.

## 10. Testing principles

- **Tests mirror architecture**, not file layout convenience.
- **Deterministic and isolated:** no order dependence, no shared hidden state, no flakiness;
  flaky tests are defects.
- **Fast feedback first**, broad coverage second; the pyramid (§12) reflects this.
- **Negative and adversarial paths are first-class**, not afterthoughts.
- **Never weaken or remove a test to make a build pass.** A failing required test is a stop,
  not an obstacle.

## 11. Verification principles

- **Proof gates capability:** a capability is enabled only when its required tests pass (§51–§53).
- **Evidence over assertion** (PRIME §10): "works" requires demonstrated, repeatable proof.
- **Conservative on uncertainty:** unverifiable behavior is treated as unsafe and is not enabled.
- **Verification is layered:** unit → integration → contract → end-to-end, plus invariant and
  adversarial suites that cut across layers.

## 12. Test pyramid for GARVIS

- **Base — unit tests:** many, fast, per-module (§13).
- **Middle — integration & contract tests:** plane interactions and boundary contracts (§14–§15).
- **Cross-cutting — invariant & adversarial suites:** Approval Gate, permissions, secrets,
  failure/recovery (§16–§27, §49) — required regardless of layer.
- **Top — end-to-end & smoke:** few, representative golden paths (§35–§36).
- Heavier, slower, or external-touching tests sit higher and run less often, but the safety
  invariants are never optional.

## 13. Unit testing strategy

- Each module/plane has unit tests for its own logic in isolation, with dependencies replaced by
  controlled doubles (§45).
- Pure logic (classification, contract validation, redaction) is unit-tested exhaustively,
  including edge and boundary inputs.

## 14. Integration testing strategy

- Verify that planes cooperate across their declared interfaces (Interface→Orchestration,
  Orchestration→Gate→Execution, Execution→Integration).
- Integration tests use sandboxed or simulated externals (§46), never real side effects, unless
  explicitly and safely sandboxed.

## 15. Contract testing strategy

- Every inter-plane contract (`contracts/`, Project Structure §26) has tests proving producers
  and consumers honor it.
- A contract change requires updated contract tests before adoption; **no integration is
  considered safe without contract tests.**

## 16. Approval Gate invariant testing

Required, blocking suite covering the Gate's invariants (Gate Spec §40):

- **No bypass:** every outward effect requires a Gate decision; no execution entry exists
  without one.
- **Single-use tokens:** a token authorizes exactly one execution; replay/reuse/widening is
  rejected (§22, §27 of Gate Spec).
- **No self-approval:** no agent/tool/process approves its own or a peer's action.
- **Classification correctness:** highest-risk-wins and conservative-on-uncertainty hold.
- **Never-auto enforcement:** credential-sensitive, destructive, external-write, deploy/publish,
  privilege-change, and host-control actions are never auto-approved.
- **Forbidden handling:** forbidden actions are rejected and **never queued**.
- **Fail closed:** classification/audit/token failure blocks execution.
- **No command execution path may bypass Approval Gate tests.**

## 17. Permission boundary testing

- Tests prove the permission boundary is enforced at the Integration/Execution edge (Gate Spec
  §28) and cannot be bypassed.
- **No tool adapter may execute real side effects without passing permission-boundary tests.**
- Permission ≠ approval is verified: a permitted-but-unapproved action does not execute, and an
  approved-but-unpermitted action does not execute.

## 18. Agent orchestration testing

- Tests prove agents operate **only** under Orchestration: they propose, never execute or
  approve, and cannot bypass orchestration or self-escalate.
- **No agent may operate outside orchestration tests**; an agent path with no orchestration test
  is not enabled.

## 19. Tool adapter testing

- Each tool adapter has tests proving it is a thin adapter: it requires a valid Approved Action
  and permission, holds no business/decision logic, and refuses invalid/expired/out-of-scope
  tokens.
- Duplicate-tool detection: tests confirm one authority per capability (no overlapping adapter
  silently added).

## 20. Workflow testing

- Workflow definitions are tested to route every effect through the Gate, honor scope/budget
  constraints, and never embed direct execution that bypasses approval.
- Workflow tests cover gated-step deferral to the approval queue and correct handling of denial.

## 21. Memory authority testing

- **No memory authority may be introduced without** consistency, single-writer ownership,
  redaction, and audit tests:
  - **Consistency:** reads reflect committed writes; no torn/partial state observable.
  - **Single-writer ownership:** only the authority writes durable state; competing writers are
    rejected (Project Structure §32).
  - **Redaction:** secrets are never stored (§24).
  - **Audit:** durable writes are observable and correlated (§22).

## 22. Observability and audit testing

- Tests prove every lifecycle transition and Gate decision emits a structured, correlated audit
  event (Gate Spec §33), reconstructable end-to-end.
- The audit trail is append-only/tamper-evident as specified, contains no secrets, and is
  queryable; missing audit for an action fails the test.

## 23. Security testing

- Trust-boundary tests prove external content is treated as data, not commands (PRIME §7), and
  cannot trigger execution on its own.
- Least-privilege tests prove no standing broad grants and no auto-approved
  credential/authenticated-network actions exist (Gate Spec §15).
- Security tests are adversarial (§49): they attempt the bypass, not just the happy path.

## 24. Secrets and redaction testing

- **Secrets must have tests proving they are never displayed, logged, stored in memory, or
  exposed in approval prompts/previews/queue** (Gate Spec §34).
- Redaction tests cover requests, decisions, audit events, observability output, and any
  human-facing surface; a path that could reveal a secret fails.

## 25. Failure and recovery testing

- Tests prove fail-closed behavior (Gate Spec §35): on classification/audit/token failure, no
  action proceeds.
- Recovery tests prove resumption from the last audited state, no silent retry of
  failed/denied/expired actions, and conservative handling of indeterminate state (§36 of Gate
  Spec).

## 26. Rollback testing

- For actions whose class requires a rollback strategy (Gate Spec §37), tests prove the rollback
  works and that a "Rolled Back" terminal state is recorded.
- Actions with no feasible rollback are tested to require explicit approval + recovery path
  before they can run.

## 27. Idempotency testing

- Tests prove the idempotency key prevents duplicate effects on retry/recovery (Gate Spec §26,
  §36): a re-proposed identical action is detected and deduplicated, not double-executed.

## 28. Autonomous workflow testing

- **No autonomous workflow capability may be enabled before** tests exist for: deferred
  approval, audit, idempotency, recovery, and denial handling.
- Tests prove autonomy uses the **same** Gate, classes, and recovery as manual (Gate Spec §27);
  background/recursive work cannot accumulate or self-grant authority; never-auto and forbidden
  rules hold under autonomy.

## 29. UI / Interface Plane testing

- Tests prove the Interface renders **true** system state (no fabricated/placeholder status as
  real, PRIME §17), submits intents to Orchestration, and contains no business logic, execution,
  or approval authority.
- Interface tests verify approval prompts relay the human decision faithfully and never display
  secrets.

## 30. Voice / Cognition Plane testing

- Tests prove the Cognition/Voice plane produces structured intents and **never executes or
  approves**; an intent is not an authorization.
- Interpretation edge cases (low confidence, ambiguity) resolve to a proposal, not an action.

## 31. Command / Execution Plane testing

- Tests prove Execution accepts **only** a valid, unexpired, unrevoked, single-use Approved
  Action bound to the exact action, reaches externals only via Integration, and reports outcomes
  to Observability/Memory.
- A mismatch between token and action is a verified hard stop.

## 32. Integration Plane testing

- Each adapter has contract tests against its external interface (using simulation/sandbox), and
  tests proving it holds no business logic and enforces the permission boundary.
- Integration tests never perform uncontrolled real side effects (§46).

## 33. Performance testing

- Performance budgets (PRIME §12) are verified where defined: interactive/real-time
  responsiveness, memory, and resource/cost ceilings.
- Performance claims require measurement; "no impact" is itself tested where it matters.

## 34. Regression testing

- **Every bug fix includes a regression test whenever practical**; the test reproduces the
  defect and proves the fix.
- **Denied actions have regression tests proving they are not retried automatically**
  (Gate Spec §25); **forbidden actions have tests proving they are rejected and never queued**
  (Gate Spec §16, §26).

## 35. Smoke testing

- A minimal, fast smoke suite proves the system starts and its golden paths are reachable;
  smoke replaces ad-hoc visual eyeballing for "is it alive."

## 36. End-to-end testing

- A small set of representative golden-path scenarios exercises the full chain
  (surface → orchestration → gate → execution → integration) in a sandbox, including at least
  one gated-approval scenario.

## 37. Manual verification rules

- Manual testing may **supplement** automated testing but **must not replace** it for
  safety-critical behavior (Gate, permissions, secrets, destructive/irreversible actions).
- Manual checks are documented and reproducible; "looked fine" is not verification for
  safety-critical paths.

## 38. Automated verification rules

- Safety-critical behavior is verified by automated, repeatable tests; these are the source of
  truth for "verified."
- Automated suites are deterministic and run in CI and locally (§39–§40).

## 39. CI readiness requirements

- A continuous-integration path runs build, lint, and the required test suites; required
  failures **block**.
- The Gate invariant, permission, secrets/redaction, and (when present) autonomous suites are
  marked required and cannot be skipped to pass.

## 40. Local developer verification requirements

- Developers can run the same required suites locally before submitting changes; local results
  match CI (no "works in CI only" divergence for required suites).

## 41. Pre-commit verification guidance

- At minimum, fast unit and contract tests for touched areas, plus lint and build, run before
  commit. Pre-commit checks are advisory-fast, not a substitute for pre-merge gates.

## 42. Pre-merge verification guidance

- Before merge: all required suites pass — build, lint, unit, integration, contract, and every
  applicable safety-invariant suite (Gate, permission, secrets) for the touched capability.
- A change that touches an execution/approval path cannot merge without its Gate tests passing.

## 43. Pre-release verification guidance

- Before release: pre-merge gates plus smoke, end-to-end golden paths, performance budgets, and
  the production-release blockers (§53) are satisfied and recorded.

## 44. Test data policy

- Test data is synthetic and non-sensitive; **real secrets and real personal data are never used
  in tests** (PRIME §9; §24 here).
- Fixtures are deterministic and owned; shared mutable fixtures that cause order dependence are
  prohibited.

## 45. Mocking and simulation policy

- External systems are replaced by controlled doubles/simulations in unit and integration tests;
  doubles must faithfully reflect the **contract** (§15) to avoid false confidence.
- The Approval Gate is **never mocked away** in tests that assert a path is safe; its real
  decision behavior is exercised.

## 46. Sandbox execution policy

- Any test that exercises real-ish execution runs in an isolated sandbox with no access to
  production resources, secrets, or irreversible targets.
- A test must never perform an uncontrolled real side effect; doing so is a defect, not a test.

## 47. Golden-path test requirements

- Each capability has at least one golden-path test proving the intended flow succeeds end to
  end (including approval where required).

## 48. Negative-path test requirements

- Each capability has negative-path tests: denial, expiration, revocation, missing permission,
  invalid contract, and failure are handled per spec (not by crashing or by proceeding).

## 49. Adversarial test requirements

- Safety-critical areas have adversarial tests that **attempt to break the invariant**: bypass
  the Gate, replay a token, self-approve, smuggle a secret into a log, escalate an agent, queue a
  forbidden action, double-execute via retry.
- An adversarial test that succeeds in breaking an invariant is a release blocker until fixed.

## 50. Coverage expectations

- Coverage is risk-weighted, not a single global number: safety-critical paths (Gate,
  permissions, secrets, recovery) require the **highest** coverage including adversarial cases;
  cosmetic/presentation code requires less.
- Coverage is a signal, never a substitute for the required invariant suites; high coverage does
  not waive any §51–§53 blocker.

## 51. What must block execution capability

Execution capability is **not enabled** until all hold:

- Approval Gate invariant tests exist and pass (§16).
- Permission-boundary tests pass for the execution path (§17).
- Command/Execution token-binding and fail-closed tests pass (§31, §25).
- Secrets/redaction tests pass for any path that could surface data (§24).
- Audit/observability tests prove the path is fully recorded (§22).

## 52. What must block autonomous capability

Autonomous capability is **not enabled** until, in addition to §51:

- Deferred-approval, denial-handling, idempotency, and recovery tests pass (§28, §25–§27).
- Tests prove autonomy uses the same Gate/recovery as manual and that background work cannot
  bypass approval (§28).
- Never-auto and forbidden enforcement re-verified under autonomous origin (§16, §28).

## 53. What must block production release

Production release is **blocked** until §51 (and §52 if autonomy is shipped) plus:

- Smoke and end-to-end golden paths pass (§35–§36).
- Negative and adversarial suites pass (§48–§49).
- Performance budgets met where defined (§33).
- No required test was removed or weakened to pass (§10).

## 54. Test ownership

- Tests are owned by the same plane/owner as the code they verify (Project Structure §31);
  orphan tests are defects.
- Safety-invariant suites (Gate, permissions, secrets) are owned at the platform/core level, not
  by a single surface.

## 55. Test naming conventions

- Test names state the behavior and expectation in plain terms (what is verified and the
  expected outcome), including the negative/adversarial intent where applicable, so a failure
  name communicates the broken invariant.

## 56. Test directory conventions

- Tests mirror the plane tree per Project Structure §9/§39 (mirrored `tests/` or co-located,
  chosen once and applied uniformly — an open decision, §63).
- Safety-invariant suites have a clearly identifiable, central location so they cannot be
  overlooked.

## 57. Risk-based test prioritization

- Prioritize by blast radius and reversibility: irreversible/external/credential/destructive
  paths first; cosmetic/internal/reversible paths last.
- The Gate, permission, and secrets suites are always top priority regardless of feature
  schedule.

## 58. Validation checklist for new subsystems

Before a new subsystem is enabled:

- [ ] Unit tests for its own logic, including edges.
- [ ] Contract tests for every boundary it exposes/consumes.
- [ ] Negative and adversarial tests for its failure modes.
- [ ] Conformance to its governing ADR's validation strategy.
- [ ] Observability/audit proven for its actions.

## 59. Validation checklist for Approval Gate readiness

(Extends Gate Spec §44.) Before any execution capability:

- [ ] No-bypass, single-use, no-self-approval, never-auto, forbidden-not-queued, fail-closed
      invariants all tested and passing (§16).
- [ ] Token expiration, revocation, and scope-limit tests passing.
- [ ] Denied-not-auto-retried regression test passing (§34).
- [ ] Secrets never surfaced in prompts/logs/queue/memory (§24).
- [ ] Complete, correlated audit for every decision (§22).

## 60. Validation checklist for autonomous workflow readiness

Before any autonomous capability (in addition to §59):

- [ ] Deferred-approval queue behavior tested (reject forbidden, dedupe, expire, no
      auto-escalation).
- [ ] Idempotency and recovery tested (no duplicate or silent-retry effects).
- [ ] Denial handling tested under autonomy.
- [ ] Same-Gate/same-recovery-as-manual proven.

## 61. Migration path from current verification state

- **Current state:** build and lint scripts exist; **there is no test runner, no test suite, and
  no test script**; a browser-automation library is present as an unused dependency; the
  Interface has historically been checked by manual visual inspection.
- **Immediate rules (effective now):** safety-critical behavior, when built, requires automated
  tests; manual visual checks do not count as verification for it; no required test is ever
  removed/weakened to pass.
- **Phase T0 — Harness:** establish a test runner and the mirrored/co-located layout decision; no
  capability claims yet.
- **Phase T1 — Interface baseline:** replace ad-hoc visual eyeballing with smoke + golden-path
  tests for the existing surface.
- **Phase T2 — Gate invariants:** implement the Approval Gate invariant suite (§16) — the
  prerequisite for any execution work.
- **Phase T3 — Execution enablement:** only after §51 holds.
- **Phase T4 — Autonomous enablement:** only after §52 holds.
- Each phase is gated by its checklist; later phases never begin before earlier ones pass.

## 62. Architecture risks

- **Tests do not yet exist;** until Phase T2 holds, "verification before execution" is intent,
  not fact — the top risk.
- **Mock fidelity:** doubles that drift from contracts give false confidence (mitigated by §15,
  §45).
- **Flaky/edited tests:** flakiness or weakening tests to pass would erode the gating model
  (mitigated by §10).
- **Coverage theater:** chasing a coverage number instead of the required invariant suites
  (mitigated by §50).
- **Sandbox leaks:** a test performing a real side effect (mitigated by §46).

## 63. Open decisions

- Test layout (mirrored `tests/` vs co-located) — shared with Project Structure §46.
- Test runner/tooling selection (a future ADR; deliberately unspecified here).
- Coverage thresholds per risk tier and how they are enforced.
- CI provider/triggering model and required-suite gating mechanism.
- Sandbox/simulation approach for external integrations.

## 64. Readiness checklist

Before this strategy is considered active:

- [ ] ADR-0001 reviewed and Accepted (currently Proposed).
- [ ] Test harness and layout decision recorded (Phase T0).
- [ ] Required safety-invariant suites enumerated and owned (§16–§24, §54).
- [ ] Execution/autonomous/release blockers (§51–§53) ratified as gates.
- [ ] Migration phases (§61) sequenced with owners.

## 65. Recommended next foundational document

**`docs/architecture/SECRETS_AND_PERMISSIONS_POLICY.md`** — the secrets/redaction and
permission-boundary tests this strategy mandates (§17, §24) need a governing policy to test
against. `MEMORY_AUTHORITY_SPEC.md` is the close second (its consistency/ownership/redaction/
audit tests, §21, need a spec to verify). See the report for the recommended ordering.
