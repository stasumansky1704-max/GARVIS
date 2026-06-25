# GARVIS — Workflow Engine Strategy

**Status:** Binding runtime-coordination specification (governed by ADR-0009) · **Scope:** All
durable, long-running, background, and autonomous workflow coordination in GARVIS · **Conforms to:**
the ratified baseline (ADR-0007) and Accepted decisions —
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
[`TOOL_PERMISSION_MODEL.md`](./TOOL_PERMISSION_MODEL.md) — and the
[`AGENT_ORCHESTRATION_MODEL.md`](./AGENT_ORCHESTRATION_MODEL.md) (governed by ADR-0008, currently
Proposed, used here as a documented input). Where this and those conflict, the constitution
prevails; the conflict is reported, not silently resolved.

Vendor-neutral: no products, workflow/orchestration engines, schedulers, schema libraries, models,
APIs, databases, or temporary implementation detail, and **no implementation code, schemas-as-code,
or engine implementation**. It defines *what must be true* about workflow coordination, not *how it
is built*. It contains and references **no secret values**.

**The Workflow Engine is the execution coordinator of GARVIS.** It is **not** a tool, an agent, a
scheduler, a permission system, the Approval Gate, memory, or observability — it **coordinates**
them. It is orchestration infrastructure.

---

## 1. Purpose

- Define how GARVIS coordinates multi-step, long-running, background, and autonomous work as durable,
  resumable, gated, auditable workflows that compose agents and tools without ever owning or
  bypassing platform authority.
- Establish the lifecycle, state/checkpoint/recovery model, and the mandatory per-action pipeline
  through which every workflow step must pass.

## 2. Scope

- **In scope:** workflow responsibilities/ownership, lifecycle/states/checkpoints, recovery/retries/
  compensation/rollback/cancellation/timeout, scheduling/persistence/context/variables/events, the
  graph/branching/loops/parallelism/joins model, human-approval pauses, the interactions with Gate/
  permissions/memory/tools/agents/observability/audit/contracts, idempotency/correlation, security,
  versioning/migration/compatibility, and the tests that gate workflow execution.
- **Out of scope:** the engine implementation, scheduler/persistence technology, and any concrete
  encoding (deliberately unspecified); business logic (never owned by the engine, §53).

## 3. Non-goals

- Not an engine/scheduler selection, not a business-process modeler, not an integration layer. Not a
  place for business logic, permissions, approvals, or durable memory.
- Not a guarantee by documentation alone — enforced by mechanism and proven by tests (§48–§52).

## 4. Workflow Engine responsibilities

- **Coordinate** the ordered execution of workflow steps: sequence, branch, loop, parallelize, join,
  synchronize, checkpoint, pause for approval, recover, and resume.
- Drive each step through the mandatory pipeline (§37): **Proposed → Validated → Permission Checked →
  Approval Checked → Executed → Observed → Audited → Recovered if necessary.**
- Persist workflow state for resumability; assign/propagate correlation and dependency-chain
  references; enforce timeouts, bounded retries, compensation, cancellation, and budgets.
- It **coordinates**; it does not decide permissions, grant approvals, execute side effects itself,
  hold durable knowledge, or own audit.

## 5. Workflow Engine ownership

- The engine owns **workflow definitions and workflow state** (governed contracts) and the
  **coordination** of steps — nothing more. It is part of the Orchestration Plane and lives with
  workflows at `planes/orchestration/workflows/` (Project Structure §24).
- It **owns no** permissions, approvals, durable memory, business logic, tools, agents, contracts
  (beyond its own workflow-definition/state contracts, which it consumes from the contract
  authority), or canonical audit records (§53, §110-analogues).

## 6. Workflow lifecycle

```
Defined (versioned) → Instantiated → Running → [Paused | Waiting-Approval | Checkpointed]
      → Completed | Failed | Compensated | Rolled Back | Cancelled | Timed Out
      → Audited (always)
```

- A definition is versioned and registered; an instance is created from a definition; each transition
  is checkpointed (§8) and audited (§35).

## 7. Workflow states

- **Defined / Instantiated / Running / Paused / Waiting-Approval / Checkpointed / Recovering /
  Completed / Failed / Compensating / Compensated / Rolling-Back / Rolled-Back / Cancelled /
  Timed-Out.**
- States are explicit and persisted; terminal states (Completed/Failed/Compensated/Rolled-Back/
  Cancelled/Timed-Out) are always **Audited** (§35).

## 8. Workflow checkpoints

- The engine checkpoints durable state at well-defined points (after each step transition and before/
  after any gated effect) so a workflow is resumable from the last consistent, audited checkpoint.
- Checkpoints are redacted (no secrets/raw-execution-context) and reference memory/audit by handle
  only (§31, §35).

## 9. Workflow recovery

- On interruption/failure, recovery resumes from the last **audited** checkpoint; in-doubt steps are
  treated as not-completed and re-proposed (never assumed executed); consumed approvals are never
  reused (§41, §42; Gate Spec §36).

## 10. Workflow retries

- **Retries are bounded and idempotency-aware and must not retry denied or forbidden steps.** A
  retry reuses the step's idempotency key to avoid duplicate effects; exceeding the bound defers to a
  human or fails the step, never escalates (Tool Model §66; Agent Model §78).

## 11. Workflow compensation

- For steps without a clean rollback, the engine runs declared **compensating actions** to logically
  undo prior effects. A compensation is itself a workflow step subject to the full pipeline (§37) —
  permission, approval where required, and audit.

## 12. Workflow rollback

- Where a step is reversible, the engine invokes its declared rollback (Tool Model §36; Gate Spec
  §37). A "Rolled-Back" outcome is a distinct, audited terminal state; steps with no rollback and no
  compensation require explicit approval and a recovery path before they run.

## 13. Workflow cancellation

- A workflow can be **cancelled** at any time; cancellation halts new steps, triggers compensation/
  rollback for completed reversible effects where defined, reaches a Cancelled terminal state, and is
  audited. In-flight gated steps relying on a now-cancelled workflow do not proceed.

## 14. Workflow timeout model

- Workflows and steps carry bounded timeouts; a timed-out step is treated as indeterminate (recovery
  per §9), surfaced, and audited; long-running workflows use checkpoints + waits, not unbounded
  blocking. Timeouts never silently retry (§10).

## 15. Workflow scheduling model

- The engine may **start** workflows from triggers (time-based, event-based, or manual) but is **not a
  scheduler-only system** (§53): scheduling is a trigger into the same coordination + pipeline.
  Triggered/background starts carry correlation and run under bounded permission scopes (§43–§44).

## 16. Workflow persistence model

- Workflow definitions and instance state are persisted durably so workflows are resumable across
  restarts. Persistence holds **no raw secrets/credentials/tokens/execution-context/audit payloads**
  (handles/redacted only); it is not a competing memory or audit store (§31, §35). The storage
  technology is deferred to a later ADR.

## 17. Workflow context model

- A workflow carries a **governed context** (its inputs, current state, references) that is redacted,
  classified, and permission-scoped. Context is durable workflow state, distinct from agent ephemeral
  context (Agent Model §52) and from the Memory Authority (§31).

## 18. Workflow variable model

- Workflow variables are typed, classified (risk/sensitivity), and redaction-aware; secret values are
  never stored as variables — only handles. Variables flow between steps through the workflow's
  governed context, validated against contracts (§36).

## 19. Workflow event model

- The engine consumes and emits versioned workflow events (started/step-completed/paused/approval-
  required/resumed/failed/compensated/cancelled) carrying correlation and dependency-chain
  references; events are redacted and emitted to Observability (§34) — the engine never writes
  canonical audit directly.

## 20. Workflow dependency model

- Steps declare dependencies; the engine enforces that a step runs only when its prerequisites
  (including required prior approvals) are satisfied. Dependency references are carried for causal
  reconstruction (Audit Spec §54).

## 21. Workflow graph model

- A workflow is a directed graph of steps (typically acyclic at the top level, with governed loops,
  §24). The graph is part of the versioned workflow-definition contract; the engine executes the
  graph, it does not embed business decisions in it (§53).

## 22. Workflow branching

- Branching selects among declared paths based on evaluated **conditions** (§23). Each branch's
  effecting steps are independently classified and gated; branching never pre-authorizes a branch's
  steps.

## 23. Workflow conditions

- Conditions are declarative evaluations over the governed context/variables; they are deterministic
  where possible (§38-analog), redaction-safe (no secrets in condition logs), and contain no business
  logic that belongs to the core platform (§53).

## 24. Workflow loops

- Loops are **bounded** (explicit iteration/budget limits); each iteration's effecting steps pass the
  full pipeline (§37). Unbounded loops are forbidden (§53); exceeding a loop budget defers/halts and
  is audited.

## 25. Workflow parallelism

- Parallel branches execute concurrently under the engine's coordination; concurrency respects
  single-use approvals (one approval → one execution) and idempotency, so two parallel paths never
  share an approval or double-apply an effect (§38).

## 26. Workflow joins

- Joins synchronize parallel branches (all/any/quorum as declared) before proceeding; a join
  aggregates branch outcomes but **does not authorize** the next step — gated next steps still pass
  the Gate.

## 27. Workflow synchronization

- The engine provides governed synchronization (barriers, ordering guarantees) for dependent/parallel
  steps; synchronization preserves correlation and never creates an ungoverned coordination channel
  outside Orchestration (Agent Model §63).

## 28. Workflow human approval pauses

- A workflow **must support pausing to wait for human approval** at any gated step: it reaches
  **Waiting-Approval**, checkpoints, and resumes only on an explicit Gate-issued approval. Waiting
  never escalates risk or auto-approves; an unmet approval expires/defers per policy (Gate Spec §26).

## 29. Workflow Gate interaction

- Every workflow step that implies a side effect becomes a **Proposed Action** submitted to the
  Approval Gate; the engine consumes only single-use Approved Actions and **never bypasses the Gate**
  (Gate Spec §6, §22). Autonomous/background steps use the **same** Gate (Gate Spec §27).

## 30. Workflow permission interaction

- The engine **owns no permission logic**; each step runs under the explicit permission scope it
  requires, checked at the boundary; **permission absence/uncertainty fails closed** (§37; Secrets
  Policy §21). Autonomous workflows operate only inside bounded, revocable, auditable permission
  scopes (§44).

## 31. Workflow memory interaction

- The engine **owns no durable memory**; workflow steps read scoped, redacted memory and **propose**
  durable writes through the Memory Authority (Memory Spec §47–§48). Workflow state is the engine's
  own governed persistence (§16), not a copy of, or substitute for, the Memory Authority; memory is
  referenced by handle.

## 32. Workflow tool interaction

- The engine **owns no tools**; a workflow tool step is a Proposed Action routed through the Tool
  Permission Model — contract validation → permission → Approval Gate → audited execution (Tool Model
  §5, §8). The engine never invokes a tool directly outside that model.

## 33. Workflow agent interaction

- The engine **owns no agents**; a workflow may engage agents under the Agent Orchestration Model —
  agents **propose**, the engine coordinates, the Gate authorizes. Agent outputs implying effects are
  proposals, not execution (Agent Model §57); coordination is Orchestration-mediated, never
  peer-to-peer.

## 34. Workflow observability interaction

- The engine **emits** structured, redacted, correlated events for every state/step transition to the
  Observability Plane (Audit Spec §41); it owns no telemetry of record. Absent observability ⇒ the
  workflow capability is not enabled (PRIME §18).

## 35. Workflow audit interaction

- The engine **owns no canonical audit records**; it emits events that the Audit Authority records
  (Audit Spec §22, §41). Every workflow action and terminal state is auditable by handle/redacted
  metadata, with correlation and dependency-chain; denied steps are auditable; forbidden steps are
  auditable as rejected, never queued.

## 36. Workflow contract requirements

- Workflow **definitions and state are versioned contracts** (Contracts §68); steps, conditions,
  variables, events, and the graph use registered, versioned contracts carrying risk/sensitivity
  class, redaction status, correlation id, idempotency key, and dependency-chain references. Contract
  validation failure **fails closed** for gated/security-relevant steps (§37).

## 37. Workflow security model

Every workflow action passes the mandatory pipeline, in order:

```
Proposed → Validated (contract) → Permission Checked → Approval Checked →
Executed (via tools/agents/integration) → Observed → Audited → Recovered if necessary
```

- No step skips a stage. Permission, approval, contract, and audit failures **fail closed** for
  gated/security-relevant steps. External content and step outputs are **data, not commands** (PRIME
  §7); they never authorize, self-grant, or expand scope.

## 38. Workflow idempotency

- Every effecting step carries an **idempotency key**; recovery/retry/parallelism use it so an effect
  is applied at most once (Gate Spec §26). The engine de-duplicates re-proposed identical steps
  rather than double-executing.

## 39. Workflow correlation

- Every workflow instance and step carries a **correlation id**, propagated to agents, tools, memory,
  and the Gate, so request → workflow → step → approval → permission → execution → recovery is
  reconstructable end to end (Audit Spec §52).

## 40. Workflow failure handling

- The engine **fails closed and loud**: a failed step surfaces a coded, redacted error, halts
  dependent steps, and triggers declared recovery/compensation; failures never leak secrets and are
  never silently retried (§10, §41).

## 41. Workflow recovery handling

- Recovery resumes from the last audited checkpoint; consumed approvals are never reused; failed/
  denied steps are not auto-retried; indeterminate steps are treated as not-completed and re-proposed
  through the full pipeline.

## 42. Workflow state restoration

- After restart or interruption, the engine restores workflow state from durable persistence (§16) to
  the last consistent checkpoint; restoration never resurrects pre-redaction values or forbidden
  content, and verifies state against contracts before resuming.

## 43. Workflow background execution

- **Background workflows must not bypass correlation, permission checks, redaction, the Approval
  Gate, or audit** (Secrets Policy §64; Tool Model §59; Agent Model §83). Background runs carry
  correlation and run only within granted, bounded scopes; they cannot accumulate or self-grant
  authority.

## 44. Workflow autonomous execution

- **Autonomous workflows operate only inside bounded, revocable, auditable permission scopes** with
  explicit budgets, using the **same** Gate/permission/contract/audit/recovery model as manual
  (Gate Spec §27). Gated/never-auto/forbidden steps defer to the human or are rejected — autonomy
  changes only the trigger, never the controls.

## 45. Workflow versioning

- Workflow definitions are **versioned** (Contracts §21); a running instance is bound to the
  definition version it started with. Incompatible changes follow the breaking-change policy
  (Contracts §23); in-flight instances complete or migrate per policy (§46).

## 46. Workflow migration

- Migrating an in-flight workflow to a new definition version is explicit, governed, checkpoint-based,
  reversible where practical, and audited; migration never strands a running instance or silently
  changes its meaning (Contracts §27).

## 47. Workflow compatibility

- Within a major definition version, step/contract shapes and required safety fields are stable;
  additions are optional and never weaken a safety field (Contracts §28). Consumers/triggers declare
  the version they target.

## 48. Workflow testing requirements

- **Workflow execution is disabled until invariant, permission-boundary, approval-invariant,
  redaction, audit, contract, recovery/checkpoint, idempotency, and integration tests exist** for the
  workflow capability (Strategy §20). A workflow with no passing required tests is not enabled.

## 49. Workflow invariant tests

- Tests prove: every effecting step passes the full pipeline (§37) with no bypass of Gate/permission/
  contract/redaction/observability/audit/tool-model/agent-orchestration; single-use approvals are
  never reused across recovery/parallelism; denied steps are not auto-retried; forbidden steps are
  rejected and never queued; fail-closed holds; the engine writes no canonical audit and no durable
  memory directly.

## 50. Workflow integration tests

- Tests exercise end-to-end workflows (compose agent proposals + gated tool steps + memory proposals)
  against simulated/sandboxed externals, proving correlation, dependency-chain, checkpoint/recovery,
  cancellation, and compensation/rollback work without uncontrolled real side effects (Strategy §46).

## 51. Workflow simulation strategy

- Workflows are testable via deterministic simulation/replay: the same definition + inputs + recorded
  decisions reproduce the same path (determinism where possible). The Approval Gate, permission
  boundary, Tool Permission Model, and Agent Orchestration Model are **never mocked away** in tests
  that assert a workflow path is safe (Strategy §45).

## 52. Workflow production readiness

- A workflow is production-ready only when it has: owner, purpose, risk class, permission scope,
  versioned definition/state contracts, redaction, audit emission, observability, checkpoint/recovery/
  compensation/rollback (where applicable), bounded timeouts/retries/loops/budgets, and passing
  invariant, permission-boundary, approval-invariant, redaction, audit, contract, recovery, and
  integration/adversarial tests.

## 53. Workflow forbidden behaviors

The Workflow Engine must **never**:

- Own permissions, approvals, durable memory, business logic, tools, agents, contracts, or canonical
  audit records.
- Bypass the Approval Gate, permission checks, contract validation, the Memory Authority,
  observability, audit, the Tool Permission Model, or Agent Orchestration.
- Execute a side effect itself (it coordinates; tools/integration execute under approval).
- Become **business logic**, an **integration layer**, an **agent**, or a **scheduler-only system** —
  it must remain orchestration infrastructure.
- Run unbounded loops, retry denied/forbidden steps, queue forbidden steps, reuse a consumed
  approval, store raw secrets/credentials/tokens/execution-context/audit payloads, or self-grant/
  expand scope.

## 54. Workflow readiness checklist

Before this strategy is considered active:

- [ ] ADR-0009 reviewed and Accepted (currently Proposed).
- [ ] Workflow definition/state contracts and the lifecycle/state model defined (and the Agent
      Orchestration Model it composes is Accepted).
- [ ] Persistence/checkpoint/recovery model defined; resumability proven by tests.
- [ ] Mandatory pipeline (§37) enforced per step with fail-closed on permission/approval/contract/
      audit.
- [ ] Human-approval pause/resume, cancellation, timeout, bounded retries/loops/budgets defined.
- [ ] Required tests (§48–§51) enumerated and owned; execution gated on them.
- [ ] Background/autonomous bounded-scope rules and forbidden behaviors ratified as gates.

## 55. Architecture risks

- **No engine or tests yet** — until the invariant/recovery/contract tests exist, resumability and
  no-bypass are intent, not fact (top risk).
- **Engine scope creep** — the engine absorbing business logic, integration, agent behavior, or
  becoming scheduler-only (mitigated by §53).
- **Approval reuse across recovery/parallelism** — a recovered or parallel path reusing a consumed
  single-use approval (mitigated by §9, §25, §38, §49).
- **State/secret leakage in persisted state, checkpoints, events, or failure paths** (mitigated by
  §16, §18, §35, §40).
- **Autonomous/background bypass** — a triggered run skipping correlation/permission/Gate/audit
  (mitigated by §43–§44).

## 56. Open decisions

- Persistence and checkpoint technology, and the durability/consistency guarantees (future ADR;
  deliberately unspecified).
- Workflow definition/graph representation and versioning scheme (relates to Contracts §103).
- Scheduling/trigger model boundaries (what may start a workflow) and autonomous budget/scope
  declaration.
- Compensation vs rollback selection policy per step class.
- Determinism/replay guarantees and how non-deterministic steps are bounded.

## 57. Recommended next document

**First implementation, not a document.** With the cross-cutting authorities (ADR-0001..0007
Accepted) and the capability models (Tool Model Accepted; Agent Orchestration and Workflow Engine
Proposed) defined, the architecture is sufficiently specified to **begin building to the gates**
rather than writing further specs. The recommended next step after ADR-0008/0009 are reviewed is the
**Approval Gate invariant test suite and the testing harness (Testing Strategy phases T0–T2)** — the
prerequisite, under "verification before execution" (PRIME §14–§15), for any workflow/tool/agent
execution work. (If a further document is preferred first, an **Architecture Decision Record for the
workflow persistence/checkpoint mechanism** is the natural follow-up once ADR-0009 is Accepted.)
