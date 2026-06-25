# GARVIS — Implementation Roadmap

**Type:** Engineering execution roadmap (not architecture, not governance) · **Status:** Working
plan · **Governed by:** the Accepted architecture baseline (ADR-0001…ADR-0007) and the two Proposed
capability models (ADR-0008 Agent Orchestration, ADR-0009 Workflow Engine).

This document converts the approved architecture into buildable engineering work. It **describes
implementation, not architecture** — it invents no subsystem, authority, or specification. Where a
spec deferred a technology choice to a future decision, this roadmap schedules that decision; it
does not make it here. It answers one question: **what do we build tomorrow morning?**

> **Test-first law (non-negotiable, from PRIME §14–§15 and the Testing Strategy):** no component that
> can cause an effect is enabled before its required tests are green. Every milestone below is a
> *test gate*, not a feature gate.

---

## 1. Current architecture readiness

- **Specs:** complete and ratified for the foundation (constitution, overview, Approval Gate, project
  structure, ADR process) and the cross-cutting authorities (testing, secrets/permissions, memory,
  observability/audit, contracts, tools). Agent Orchestration and Workflow Engine are specified but
  **Proposed** (ratify before their runtimes).
- **Code:** only the Interface Plane surface exists (the Living UI). **Zero** runtime exists for the
  Gate, permissions, contracts, memory, audit, tools, agents, or workflows. **No test harness, no
  test suite.**
- **Readiness verdict:** architecture-ready, implementation-zero. The first engineering act is to
  stand up the test harness and the Safety Foundation runtimes — nothing downstream is safe without
  them.

## 2. Critical implementation order

```
Test Harness
  → Contract Registry (runtime validation)
    → Permission Runtime (deny-by-default)
      → Approval Gate Runtime (lifecycle + single-use tokens + classification + fail-closed)
        → Gate Invariant Suite GREEN   ← the gate that unblocks everything
          → Audit Runtime  → Memory Runtime
            → Tool Runtime (safe classes first)
              → Agent Runtime (after ADR-0008 Accepted)
                → Workflow Runtime (after ADR-0009 Accepted)
                  → Capability tools (Filesystem → Browser → GitHub → Docker → …)
                    → Human Experience → Autonomous GARVIS
```

Build inward-out: **safety core first, capability last.**

## 3. Dependency graph

- **Test Harness** → prerequisite of everything.
- **Contract Registry** → needed by Permission, Gate, Memory, Audit, Tool, Agent, Workflow.
- **Permission Runtime** → needed by Gate, Tool, Agent, Workflow.
- **Approval Gate Runtime** → needed by Tool, Agent, Workflow, all execution.
- **Audit Runtime** → needed by Gate (decisions must be auditable), Tool, Agent, Workflow.
- **Memory Runtime** → needed by Agent, Workflow, Knowledge/Projects capabilities.
- **Tool Runtime** → needed by every capability (Filesystem, Browser, GitHub, Docker, …).
- **Agent Runtime** (blocked on ADR-0008) → needed by Research/Planning and Workflow agent steps.
- **Workflow Runtime** (blocked on ADR-0009) → needed by long-running/autonomous work.
- **Human Experience** (UI/voice) → depends on the platform runtimes for *real* state, not on
  capability tools.

## 4. Sprint roadmap

Two-week sprints; sizing is indicative, not a calendar commitment.

| Sprint | Focus | Exit (test gate) |
|---|---|---|
| **S0** | Test harness, CI wiring, repo hygiene, layout decision (mirrored vs co-located tests) | Harness runs locally + in CI; a trivial red→green test proves the loop |
| **S1** | Contract Registry runtime + validation; Approval Gate core (pure, in-memory) | Gate lifecycle + single-use token + classification unit tests green |
| **S2** | Permission Runtime (deny-by-default) + Gate↔Permission integration | Permission-boundary + permission≠approval tests green |
| **S3** | **Gate Invariant Suite** (no-bypass, single-use, no-self-approval, never-auto, forbidden-not-queued, fail-closed) + Audit Runtime (append-only, correlated, redacted) | **Gate Invariant Suite GREEN** + audit-completeness tests green |
| **S4** | Memory Runtime (single-writer, redaction, provenance) + redaction library hardening | Memory consistency/ownership/redaction tests green |
| **S5** | Tool Runtime (registry, classification, contract binding) + first safe-class tools (informational, local-read) | Tool permission-boundary + approval-invariant tests green; safe-class tools enabled |
| **S6** | Ratify ADR-0008/0009; Agent Runtime (propose-only) | Agent orchestration-invariant + tool/memory-boundary tests green |
| **S7** | Workflow Runtime (lifecycle, checkpoints, recovery, approval-pause) | Workflow invariant + recovery/checkpoint tests green |
| **S8+** | Capability layer (Filesystem → Browser → GitHub → Docker), then Human Experience, then Autonomous | Per-capability adversarial + integration tests green |

## 5. Milestone roadmap

- **M0 — Harness:** test runner + CI; the test-first loop works.
- **M1 — Safe Core:** Contract Registry + Permission + Approval Gate, with the **Gate Invariant Suite
  green**. *This is the keystone milestone.*
- **M2 — Evidence Core:** Audit Runtime (canonical, immutable, redacted) wired to the Gate.
- **M3 — Knowledge Core:** Memory Runtime (single-writer, redacted, provenance).
- **M4 — Tool Core:** Tool Runtime + first safe-class tools; first *real* gated read.
- **M5 — Agent Core:** Agent Runtime (propose-only) after ADR-0008 Accepted.
- **M6 — Workflow Core:** Workflow Runtime (resumable, recoverable) after ADR-0009 Accepted.
- **M7 — First Side Effect:** first **local-write** capability behind permission + approval +
  rollback (Filesystem write).
- **M8 — Capability Expansion:** Browser, GitHub, Docker, Research, Knowledge, Projects, Execution.
- **M9 — Human Experience:** voice/conversation/avatar/UI wired to real platform state.
- **M10 — Autonomous GARVIS:** long-running, planned, delegated, self-monitoring, business automation.

## 6. Definition of Done (per milestone)

A milestone is **Done** only when **all** hold:
- Required test suites for the milestone's components are **green and required in CI** (cannot be
  skipped to pass).
- Adversarial tests for any safety-critical component pass (attempt the bypass; it fails).
- No secret appears in logs/audit/diagnostics/failure paths (proven by tests).
- The component owns nothing outside its spec'd authority and bypasses no gate (proven by invariant
  tests).
- Observability/audit emit for the component; the component can report its own status.
- Docs/readme for the component updated; no architecture doc changed.
- For any side-effecting milestone: rollback/compensation path exists and is tested.

## 7. Blocking dependencies

- **Everything** blocks on the **Test Harness** (M0).
- **Tool/Agent/Workflow runtimes** block on **M1 (Gate Invariant Suite green)** and **M2 (Audit)**.
- **Agent Runtime** additionally blocks on **ADR-0008 Accepted** (governance gate — ratify, do not
  re-author).
- **Workflow Runtime** additionally blocks on **ADR-0009 Accepted**.
- **All capability tools** block on **M4 (Tool Runtime)**; **side-effecting tools** also block on
  **M2 (Audit)** + a tested **rollback** path.
- **Autonomous (Phase 5)** blocks on **M6 (Workflow)** + bounded-scope/budget enforcement + full
  dependency-chain audit.
- Several **technology choices are deferred decisions** (storage for memory/audit/workflow state,
  contract encoding, sandbox model): each must be made via its own future ADR **before** the runtime
  that needs it ships — scheduled here, not decided here.

## 8. Engineering priorities

1. Safety core correctness (Gate, permission, contracts) over everything.
2. Evidence (audit) and redaction over features.
3. Resumability/recovery over raw throughput.
4. Narrow, single-responsibility components over broad ones.
5. Determinism and testability over cleverness.
6. Capability breadth **last** — never before its safety tests.

## 9. Risk priorities

| Risk | Severity | Mitigation milestone |
|---|---|---|
| Building any execution before the Gate invariants are green | **Critical** | Enforce M1 as a hard gate |
| Secret leakage via logs/audit/failure paths | **Critical** | Redaction library + tests at M2/M3 |
| Approval reuse across recovery/parallelism | **High** | Single-use token tests at M1; workflow tests at M6 |
| Audit↔Memory blur (one becomes the other) | **High** | Separate runtimes M2/M3 with boundary tests |
| Engine/tool/agent scope creep into business logic | **High** | Invariant tests + reviewer checklist |
| Shipping capability tools before Tool Runtime | **High** | Gate capability work on M4 |
| Autonomous bypass of correlation/permission/Gate/audit | **High** | Bounded-scope tests at M6/Phase 5 |
| Deferred tech decisions made implicitly in code | **Medium** | Require an ADR before the dependent runtime |

## 10. Implementation phases

### Phase 1 — Safety Foundation *(M0–M2)*
Build, in order: **Test Harness → Contract Registry → Permission Runtime → Approval Gate Runtime →
Invariant Tests (+ Audit Runtime)**. Pure/in-memory where possible; deny-by-default; fail-closed.
**Exit:** Gate Invariant Suite green; audit records every decision. *No capability, no side effects.*

### Phase 2 — Platform Runtime *(M3–M6)*
Build: **Memory Runtime → Audit Runtime (if not done in P1) → Tool Runtime → Agent Runtime → Workflow
Runtime.** Each gated by its tests; Agent/Workflow also gated by ADR-0008/0009 Acceptance. **Exit:**
the platform can route a proposed action end-to-end (propose→validate→permission→approval→execute via
a *safe* tool→observe→audit→recover) with no bypass.

### Phase 3 — Capability Layer *(M7–M8)*
Build capability tools in increasing blast radius, each as a permission-bounded, contracted, audited
adapter with rollback where applicable:
**Filesystem (read→write) → Browser → GitHub → Docker → Research → Knowledge → Projects → Execution.**
**Exit:** each capability passes permission-boundary, approval-invariant, redaction, audit, and
adversarial tests; first real, reversible side effect lands.

### Phase 4 — Human Experience *(M9)*
Wire the existing Living UI and the voice/conversation/avatar surfaces to **real** platform state and
the approval/observability streams: **Voice → Conversation → Avatar → UI → Animation → Visualization.**
Surfaces consume the core; they implement no business logic, execution, or approval. **Exit:** a human
can issue intents, see real status, and approve gated actions through the UI/voice.

### Phase 5 — Autonomous GARVIS *(M10)*
Enable autonomy on the proven base: **Long-running workflows → Planning → Delegation → Recovery →
Self-monitoring → Business automation.** Same Gate/permission/audit/recovery as manual; bounded,
revocable, auditable scopes; nothing self-grants. **Exit:** an autonomous workflow runs within budget,
defers gated steps to humans, recovers from failure, and is fully auditable.

## 11. Recommended engineering team order

1. **Platform/Safety squad** (first and most senior): Test Harness, Contract Registry, Permission,
   Approval Gate, Audit. Owns the invariant suites.
2. **Data/Knowledge squad:** Memory Runtime, redaction library, provenance.
3. **Capability/Integrations squad:** Tool Runtime + capability adapters (Filesystem→Docker).
4. **Orchestration squad:** Agent Runtime, Workflow Runtime (starts after M1/M2; runtimes after
   ADR-0008/0009).
5. **Experience squad** (existing Living-UI strength): Phase 4 surfaces, wired to real state.
6. **Autonomy squad** (forms last): Phase 5, built only on green platform gates.

## 12. Component implementation order

Test Harness → Contract Registry → Redaction library → Permission Runtime → Approval Gate Runtime →
Audit Runtime → Memory Runtime → Tool Runtime → (ratify 0008/0009) → Agent Runtime → Workflow Runtime
→ Filesystem tool → Browser tool → GitHub tool → Docker tool → Research → Knowledge → Projects →
Execution → UI/voice wiring → Autonomy.

## 13. Acceptance criteria

A component is **Accepted into main** only if:
- Its spec'd invariants are covered by passing, required tests (incl. adversarial for safety-critical).
- It owns nothing outside its authority and bypasses no gate (proven, not asserted).
- Fail-closed verified on permission/approval/contract/audit failure.
- No secret in any output or failure path (proven).
- Observability/audit emit; status reportable.
- For side-effecting components: rollback/compensation tested; idempotency proven.

## 14. Technical debt policy

- Debt is **recorded** (issue + owner + payoff trigger), never silent. No "broken windows."
- **Zero tolerance** for debt in the safety core (Gate, permission, contracts, redaction, audit):
  it ships correct or it does not ship.
- Capability/UI debt is allowed only behind a feature flag, with a tracked payoff and no safety
  impact.
- **Never** weaken or delete a test to clear debt (PRIME/Testing Strategy).

## 15. Regression policy

- Every bug fix ships with a regression test reproducing it.
- Safety-critical invariants have permanent guard tests; a regression there blocks all merges.
- Denied/forbidden-action handling, single-use tokens, and secret-redaction have standing regression
  suites that run on every change.

## 16. Testing gates

- **Pre-commit:** fast unit/contract tests for touched areas + lint + build.
- **Pre-merge:** all required suites for the touched capability, including its invariant/adversarial
  tests; a change touching an execution/approval path cannot merge without the Gate suite green.
- **Pre-release:** pre-merge gates + smoke + end-to-end golden paths + performance budgets + no
  required test removed/weakened.
- **Hard rule:** required safety suites are non-skippable; red = stop.

## 17. Merge policy

- Trunk-based, small reviewed PRs; minimum-viable diff.
- A PR that touches the safety core requires review by the Platform/Safety squad.
- No merge with red required tests, with a weakened/removed test, or with a new un-gated side effect.
- Architecture docs/ADRs are not edited as a side effect of implementation PRs.

## 18. Release policy

- Releases are deliberate, gated, and human-approved (no automated deploy/push without approval).
- A release requires the pre-release gate (§16) plus a clean audit of what changed.
- Capability releases are flagged off by default and enabled per the readiness checklist of the
  relevant spec.
- Roll-forward preferred; every release has a roll-back/disable path.

## 19. Definition of MVP

GARVIS-MVP = the **Safe Core demonstrably works end-to-end on one reversible capability**:
- M0–M4 done; Gate Invariant Suite green; Audit + Memory runtimes live.
- One safe-class tool (e.g., Filesystem **read**) executes through the full pipeline
  (propose→validate→permission→approval→execute→observe→audit), with a human able to approve via a
  minimal surface.
- No autonomy, no destructive capability. Proves the architecture is real, not paper.

## 20. Definition of Production Ready

- M0–M8 done; first **reversible side-effecting** capability (Filesystem write) live behind
  permission + approval + tested rollback.
- All required + adversarial suites green; secret-non-leakage proven across logs/audit/diagnostics/
  failure paths; observability/audit complete and queryable.
- Human Experience (M9) sufficient for an operator to drive and approve real work.
- Documented operational runbook for incident handling, revocation, and recovery.

## 21. Definition of Version 1.0

- Production-Ready **plus** a coherent capability set (Filesystem, Browser, GitHub, Docker, Research,
  Knowledge, Projects) each passing its full gate, and **bounded autonomous workflows** (Phase 5)
  running within budget with human-approval pauses, full dependency-chain audit, and proven recovery.
- ADR-0008 and ADR-0009 Accepted and their runtimes in production.
- Self-monitoring live; the system can report its own health and recent actions.

## 22. Success metrics

- **Safety:** 100% of gated/security-relevant actions have a complete, correlated audit record; 0
  secret-leak findings in adversarial tests; 0 successful bypass attempts.
- **Correctness:** required-suite pass rate at merge = 100%; flaky-test rate trending to ~0.
- **Recoverability:** % of interrupted workflows that resume from checkpoint with no duplicate effect.
- **Least privilege:** count of standing/broad grants trending to 0; all permissions scoped + expiring.
- **Delivery discipline:** % of side-effecting capabilities shipped with a tested rollback = 100%.
- **Coverage of safety-critical paths** (Gate/permission/secrets/recovery) ≥ agreed high bar
  (decided in the test-coverage open decision), including adversarial cases.

## 23. Estimated implementation sequence

Indicative, sequence-not-calendar:
- **S0–S3 (Phase 1):** harness, contracts, permission, Gate, audit → **M1/M2** (the keystone).
- **S4–S5:** memory + tool runtime + safe-class tools → **M3/M4** → **MVP**.
- **S6–S7:** agent + workflow runtimes (post-ratification) → **M5/M6**.
- **S8–S11:** capability layer (Filesystem→Docker) → **M7/M8** → **Production Ready**.
- **S12–S14:** Human Experience wiring → **M9**.
- **S15+:** Autonomous GARVIS → **M10** → **v1.0**.

## 24. Recommended FIRST implementation task

**Stand up the test harness and the Approval Gate core under TDD.**
- Create the test runner + CI wiring (`scripts/` + CI config), decide and apply the test layout
  (mirrored vs co-located), and prove the red→green→required loop with one trivial test.
- Begin the **Approval Gate Runtime as a pure, in-memory, side-effect-free module**: the action
  lifecycle state machine (Proposed→Classified→…→Audited), classification (highest-risk-wins,
  conservative-on-uncertainty), and the single-use token model — driven by **failing** invariant tests
  first. No I/O, no real permissions yet (stub the inputs).
- **Why first:** everything depends on it; it enables nothing on its own (pure decision logic), so it
  is the safest place to start and the highest-leverage thing to get correct.

## 25. Recommended SECOND implementation task

**Build the Contract Registry runtime + validation and wire it into the Gate.**
- Implement the registry as the single source of truth for the approval request/decision and
  permission-scope contract shapes, with explicit versioning and **fail-closed** validation at the
  boundary.
- Replace the Gate's stubbed inputs with validated, contracted ones; add contract tests (incl.
  unknown-dangerous-field rejection and missing-safety-field failure).

## 26. Recommended THIRD implementation task

**Implement the Permission Runtime (deny-by-default) and integrate Gate↔Permission.**
- Least-privilege, scoped, expiring, revocable permission checks at the boundary; prove
  **permission ≠ approval** (both required for a gated action) and that unknown permission state fails
  closed. Add permission-boundary tests.

## 27. Recommended FOURTH implementation task

**Complete the Gate Invariant Suite and stand up the Audit Runtime.**
- Make the full invariant suite green: no-bypass, single-use token (replay rejected), no-self-approval,
  never-auto enforcement, forbidden-not-queued, fail-closed.
- Implement the Audit Runtime: append-only, immutable, correlated, redacted, by-handle records for
  every Gate decision; prove audit-completeness and secret-non-leakage (incl. failure paths). **This
  reaches M1+M2 — the keystone.**

## 28. Recommended FIFTH implementation task

**Implement the Memory Runtime (single-writer) and the redaction library, then the Tool Runtime.**
- Memory: single-writer, permission-checked reads/writes, provenance/confidence, redaction; prove
  consistency, ownership, and audit-by-handle (memory≠audit).
- Tool Runtime: registry + classification + contract binding; enable the **first safe-class tools**
  (informational, local-read) through the full pipeline. **This reaches M3+M4 → MVP candidate.**

## 29. What we build tomorrow morning

1. **Create `scripts/` test-runner wiring and a CI workflow** that runs build + lint + tests and marks
   safety suites **required**. Prove the loop with one failing-then-passing test.
2. **Decide the test layout** (mirrored `tests/` vs co-located) and apply it uniformly — record the
   choice (it is an open decision in Project Structure/Testing; resolve it as a small implementation
   decision, not new architecture).
3. **Open the Approval Gate Runtime module** (pure, in-memory) and write the **first failing invariant
   tests**: *no action executes without an Approved Action*, *a token is single-use*, *the gate fails
   closed on unknown classification*. Then make them pass.

That is the morning's work: a green test loop and the first three red→green Gate invariants.

## 30. Immediate next program step

- **Governance (parallel, non-blocking for M0–M4):** put **ADR-0008 and ADR-0009** in front of the
  human owner for ratification, since the Agent and Workflow **runtimes** (M5/M6) are blocked on their
  Acceptance. Do **not** re-author them; they only need a ratification decision (as ADR-0007 did for
  the foundation).
- **Engineering:** execute §29, then proceed task §25 → §26 → §27 → §28 toward **M1/M2 (keystone)**
  and the **MVP**.
- **Deferred-decision schedule:** before the runtimes that need them, make the open technology
  decisions via their own future ADRs — contract encoding (before Contract Registry hardens), audit/
  memory/workflow persistence (before M2/M3/M6), sandbox model (before first execution tool).
