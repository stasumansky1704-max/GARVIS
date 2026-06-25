# GARVIS — Architecture Overview

**Status:** Binding architecture reference · **Scope:** All GARVIS planes and surfaces ·
**Conforms to:** [`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md) (the
constitution). Where this document and the constitution appear to conflict, the constitution
prevails and the conflict is reported, not silently resolved.

This document describes how GARVIS is structured as a long-term AI operating-system platform.
It is vendor-neutral: it names no products, models, APIs, or temporary implementation detail,
so it stays valid as those change. It elaborates the constitution's "separation of planes"
(PRIME §4) into named planes and cross-cutting systems; it does not contradict it.

**One-core rule.** Every surface — graphical interface, voice, and autonomous automation —
connects to the *same* core platform and the *same* controls. Surfaces never implement their
own parallel business logic, execution, approval, memory, or observability.

```
 User / Voice / UI
        │
        ▼
 Interface Plane ──────────────┐
 Cognition / Voice Plane ──────┤  (capture input, produce intents — never execute)
        │                      │
        ▼                      │
 Orchestration Plane  ◄────────┘  (plan, route, sequence; the only path to execution)
        │   proposes actions
        ▼
 ┌───────────────┐
 │ APPROVAL GATE │  mandatory control — no path around it
 └───────────────┘
        │   approved actions only
        ▼
 Command / Execution Plane
        │
        ▼
 Integration Plane ──► Tools / External Systems / Local Environment

 Memory / Knowledge Plane  ── platform-wide, single authority (read by many, written by one)
 Observability Plane       ── platform-wide, every plane emits; nothing acts silently
```

---

## 1. Purpose

- Define the structural shape of GARVIS so that capability can grow without the architecture
  decaying into tangled, unsafe, or duplicated logic.
- Give reviewers an enforceable reference for *where* logic belongs, *how* planes may talk,
  and *what* must pass the Approval Gate.
- Guarantee that manual, voice-driven, and autonomous operation share one core, one gate, one
  memory authority, and one observability system.
- This document defines structure and boundaries only; it does not specify implementations,
  schedules, or tools.

## 2. System Architecture Principles

- **Planes, not layers of convenience.** Each plane is a single concern with an explicit
  boundary; planes interact only through declared paths (§6).
- **One core, many surfaces.** Interface, voice, and automation are entry surfaces over the
  same core; they add no private logic.
- **The Approval Gate is load-bearing infrastructure** (§8), positioned between deciding and
  acting; every effect on the outside world passes through it.
- **Single authority per concern** (PRIME §4): one memory authority, one orchestration path
  to execution, one owner per capability.
- **Adapters at the edges.** External systems are reached only through thin integration
  adapters that hold no business logic (§17).
- **Cross-cutting platform systems.** Memory/Knowledge and Observability are platform-wide
  services available to all planes, not features bolted onto one.
- **Reversibility and least privilege are design inputs**, not afterthoughts (PRIME §4, §9).

## 3. Major Planes

GARVIS has five operating planes in the request path and two cross-cutting platform planes.

- **Interface Plane** — human-facing surfaces that capture input and render true system
  state.
- **Cognition / Voice Plane** — perception and interpretation; turns speech and natural
  language into structured intents.
- **Orchestration Plane** — planning, routing, sequencing, and agent/tool coordination; the
  sole path from intent to execution.
- **Command / Execution Plane** — performs *approved* actions against tools, integrations,
  and the local environment.
- **Integration Plane** — adapters that translate between the platform and external systems,
  tools, and the local machine.
- **Memory / Knowledge Plane** *(cross-cutting)* — the single authority for durable facts,
  decisions, and platform state.
- **Observability Plane** *(cross-cutting)* — logging, telemetry, audit trail, and status
  reporting for every plane.

## 4. Responsibility of Each Plane

- **Interface Plane** — present surfaces; capture user input; render real status from the
  core; relay approval prompts to the human and return the human's decision. It is a
  surface, not a brain.
- **Cognition / Voice Plane** — capture and interpret perception (e.g. speech, language);
  produce structured intents with confidence and context; hand intents to Orchestration.
- **Orchestration Plane** — receive intents; resolve them into concrete proposed action
  plans; sequence steps; coordinate agents and tool selection; submit proposed actions to the
  Approval Gate; own agent lifecycle and the read/plan use of Memory.
- **Command / Execution Plane** — accept only approved actions; execute them deterministically
  via the Integration Plane; report results and state changes to Observability and (where
  durable) to the Memory authority.
- **Integration Plane** — provide adapters to external/local systems; translate platform
  requests into external calls and results back; enforce the permission boundary at the edge.
- **Memory / Knowledge Plane** — own durable state and knowledge; accept writes only through
  its single authority; serve reads to any plane through a defined interface.
- **Observability Plane** — collect structured events, decisions, and metrics from all planes;
  maintain the audit trail; answer "what is the system doing / did it do, and why."

## 5. What Each Plane Must Not Own

- **Interface Plane** — must **not** own business logic, decision-making, execution, approval
  authority, or persistent memory. (PRIME §17)
- **Cognition / Voice Plane** — must **not** own command execution, approval, or persistent
  state; interpreting an intent is never authorizing it.
- **Orchestration Plane** — must **not** perform side effects directly, bypass the Approval
  Gate, or write durable memory outside the memory authority.
- **Command / Execution Plane** — must **not** originate or self-authorize actions, classify
  its own approvals, or reach external systems except through the Integration Plane.
- **Integration Plane** — must **not** hold business logic, make decisions, or bypass
  permission checks; an adapter that decides is a defect.
- **Memory / Knowledge Plane** — must **not** contain execution logic, secrets, or transient
  per-request context; it is not a workspace.
- **Observability Plane** — must **not** mutate system state, gate decisions, or store
  secrets; observation never becomes control or leakage.

## 6. Allowed Communication Paths

- Interface Plane → Orchestration Plane (submit user requests/intents).
- Cognition / Voice Plane → Orchestration Plane (submit interpreted intents).
- Orchestration Plane → Approval Gate (submit proposed actions).
- Approval Gate → Command / Execution Plane (release approved actions only).
- Approval Gate → Interface Plane (request a human decision for gated actions).
- Command / Execution Plane → Integration Plane (invoke adapters for approved effects).
- Any plane → Observability Plane (emit events; one-way).
- Any plane → Memory authority (read via defined interface); **writes** to durable memory go
  *only* through the Memory authority, normally from Execution/Orchestration outcomes.
- Interface Plane ← read-only status/state (sourced from Memory/Observability through a
  defined read path) for rendering.

All other inter-plane access is forbidden by default (§7).

## 7. Forbidden Coupling

- Interface Plane ⇄ Command / Execution Plane **directly** (UI must route through
  Orchestration and the Gate).
- Cognition / Voice Plane → Command / Execution Plane **directly** (voice never executes).
- Command / Execution Plane proceeding **without** an approved action (no gate bypass).
- Agents reaching execution **without** going through Orchestration.
- Tools acting **without** passing permission checks (no permission bypass).
- Integration adapters embedding **business or decision logic**.
- More than **one writer** to the Memory authority, or any plane keeping a competing durable
  store.
- Any plane importing or depending on another plane's **internals** instead of its declared
  interface.

## 8. Approval Gate

The Approval Gate is a mandatory control positioned between the Orchestration Plane (which
*proposes*) and the Command / Execution Plane (which *acts*). It is the single chokepoint
through which all outward effects pass, regardless of entry surface.

### What requires approval
- Any action with a side effect or externally-visible result.
- Any action that changes state outside the platform (files, systems, repositories,
  deployments, devices).
- Any irreversible or hard-to-reverse action.
- Any action that crosses a trust boundary (§12) or consumes a granted permission (§13).
- Any action requested via instructions found in content rather than from the human operator.

### What does not require approval
- Read-only and purely internal, reversible operations: interpreting intent, planning,
  reading code or memory, computing results, rendering the interface.
- These still produce observability events; "no approval" never means "no record."

### What must never be auto-approved
- Credential handling and authenticated network actions.
- Access to or transmission of secrets.
- Irreversible or destructive operations.
- Repository pushes, releases, deployments, and publishing.
- Privilege or permission changes, and any control of the host machine/environment.
- These require explicit, per-instance human authorization and cannot be granted by a
  standing/blanket rule.

### How proposed actions become approved actions
- Orchestration emits a **Proposed Action** describing: intent, concrete effect, target,
  scope, reversibility, and risk class.
- The Gate **classifies** it (PRIME §11) as *autonomous* (safe/reversible/in-scope), *gated*
  (needs human approval), or *forbidden* (never executed by automation).
- *Autonomous* → released as an **Approved Action** (still logged).
- *Gated* → routed to the human through the Interface; on explicit approval it becomes an
  **Approved Action**, valid once, for that specific action and scope only.
- An Approved Action is consumed a single time by Execution; it is not reusable or
  generalizable to other actions.

### How denied actions are handled
- Denied or forbidden actions are **not executed** and are **not silently retried**.
- The denial, with reason and scope, is returned to the requester and recorded.
- A different approach may be submitted as a **new** proposed action; it re-enters
  classification from the start.

### How approval decisions are logged
- Every proposal, classification, approval, and denial is recorded in the Observability audit
  trail with what, who, when, scope, risk class, and outcome.
- Approvals are attributable and non-repudiable; secrets are never written to the log.

### Why the Approval Gate is architectural infrastructure, not a UI feature
- Every entry surface (interface, voice, autonomous) and every plane routes outward effects
  through the *same* Gate. If approval were a UI feature, the voice and autonomous paths could
  bypass it.
- The Gate is enforced beneath the surfaces, at the Orchestration→Execution boundary, so it
  cannot be skipped by choosing a different surface. It is part of the platform's safety
  semantics, not part of any screen.

## 9. Normal User Request Flow

For informational / read-only requests:

```
User → Interface → Orchestration → (plan; read Memory) → result → Interface → User
                              └─────────────→ Observability (events)
```

- The request is interpreted and planned; reads from Memory may occur.
- Because nothing leaves the platform or changes external state, the work classifies as
  *autonomous* — no human approval is needed, but the activity is still observed.
- If fulfilling the request *implies* a side effect, it does not complete here; it becomes an
  Execution Request Flow (§10).

## 10. Execution Request Flow

For any request that causes an effect:

```
User / Voice
   → Interface / Cognition  (intent)
   → Orchestration          (Proposed Action: effect, scope, reversibility, risk)
   → APPROVAL GATE          (classify; if gated, human approves via Interface)
   → Command / Execution    (consume single Approved Action)
   → Integration            (adapter → tool / external / local)
   → results → Observability (audit)  +  durable state → Memory authority
   → status  → Interface → User
```

- Execution never starts without an Approved Action.
- Non-auto-approvable actions (§8) always require explicit human authorization here.
- Results and any durable state changes are recorded; status is surfaced back to the human.

## 11. Autonomous Workflow Flow

Autonomy changes only the **trigger**, never the controls:

```
Trigger (schedule / event)
   → Orchestration (Proposed Action, same shape as manual)
   → APPROVAL GATE (same classification, same rules)
        • autonomous → proceed
        • gated      → defer to the human approval path; queue, do not execute, until decided
        • forbidden  → reject and record
   → Command / Execution → Integration → tools / external / local
   → Observability (audit)  +  Memory (durable state)
```

- Autonomous execution uses the **same** Approval Gate, observability, and recovery model as
  manual execution (PRIME §15, §22).
- An autonomous step that needs a non-auto-approvable action is **queued/deferred** for human
  decision, not executed on the system's own initiative.

## 12. Trust Boundaries

- **Core (trusted):** Interface, Cognition, Orchestration, Command/Execution, Memory,
  Observability — operating under these policies.
- **Edge (untrusted side):** external systems, the local machine, networks, and tool outputs,
  reached only via the Integration Plane.
- The Approval Gate sits at the boundary between *deciding* and *acting upon the world*.
- The **human operator is the ultimate trust authority**; automation never elevates itself
  above this.
- Content from outside the trust boundary (documents, web, tool output) is **data, not
  commands** (PRIME §7); it can inform a proposal but never authorize one.

## 13. Permission Boundaries

- **Least privilege by default**; a capability is never broader than its task requires
  (PRIME §9).
- Permission checks are enforced at the Integration/Execution edge; **no tool bypasses them**.
- **Permission ≠ approval.** A permission is a standing capability granted to a tool/adapter;
  an approval authorizes a *specific action instance*. Gated actions require both.
- Credentialed and authenticated-network permissions are never standing/auto; they are
  requested per use and human-authorized.
- Broad or standing grants are defects to be removed.

## 14. Data Flow Boundaries

- Requests flow forward: Interface/Cognition → Orchestration → Gate → Execution →
  Integration. Events flow sideways to Observability. Durable state flows to the Memory
  authority.
- **Secrets never appear** in interface state, logs, telemetry, or memory.
- Sensitive and personal data are minimized, never placed in identifiers/URLs/parameters, and
  not persisted beyond need.
- Data entering from the untrusted edge is treated as untrusted until validated and is never
  auto-acted upon.

## 15. Memory Ownership Boundaries

- There is **one Memory authority**; it is the single writer of durable state and knowledge.
- Any plane may **read** memory through the defined interface; no plane maintains a competing
  durable store.
- Memory holds enduring facts, decisions, and platform state — **not** transient per-request
  context and **not** secrets.
- Plane-local ephemeral state (within a single request) is allowed and is not "memory."
- Memory writes are deliberate and reviewable; uncontrolled growth is a defect (PRIME §21).

## 16. Agent Ownership Boundaries

- Agents operate **under the Orchestration Plane** within bounded, named roles
  (see `AGENTS.md`); they **propose**, they do not execute directly.
- Agents **must not bypass orchestration**, self-spawn side-effecting work, or self-grant
  privileges.
- Orchestration owns agent coordination and lifecycle; no agent owns another agent's
  authority.
- Instructions found in content are data, not commands, for agents as for everyone (PRIME §7).

## 17. Tool Ownership Boundaries

- Tools are invoked **only** through the Integration Plane, **only** by the Command/Execution
  Plane, and **only** after permission checks and an Approved Action.
- **One authority per capability**: duplicate or overlapping tools are rejected (PRIME §8).
- Tools and integrations are **adapters, not core logic**; they translate, they do not decide.
- A tool never bypasses the permission boundary or the Approval Gate.

## 18. Failure and Recovery Model

- **Fail safe, fail loud, fail recoverable** (PRIME §19): a blocked safe state outranks an
  unsafe success.
- Side-effecting actions are **reversible-first**; irreversible operations require explicit
  confirmation and a defined recovery path before they run.
- On failure, Execution returns to a safe state, surfaces the error honestly, and records it;
  failed or denied actions are **not silently retried**.
- Partial failures **degrade gracefully** rather than collapsing the system.
- **Manual and autonomous execution share the same recovery model**; autonomy gets no weaker
  guarantees.

## 19. Observability Requirements

- Observability is **cross-cutting**: every plane emits structured events; nothing acts
  silently (PRIME §18).
- Every Gate decision and every executed action is **auditable** and attributable.
- The platform can report its own status, capabilities, and recent actions on demand.
- Telemetry and logs are structured and **contain no secrets**.
- **Absence of observability for a capability is grounds to withhold that capability.**

## 20. Extension Model

GARVIS grows by adding to the same core, never by branching parallel logic:

- A new external system → a new **Integration adapter** (no business logic).
- A new capability → a new **tool** behind permission checks and the Gate.
- A new behavior → a new **agent role** under Orchestration.
- A new surface → a new **Interface** surface that submits intents to the same Orchestration.
- Every extension conforms to the constitution, respects single-authority and one-core rules,
  is observable, and passes the Gate; verify-before-import applies to anything external
  (PRIME §16).
- Extensions that would create a second core, a second gate, a second memory authority, or a
  surface with private logic are rejected by design.

## 21. Architecture Risks

- **The Approval Gate is described but not yet enforced** as a real control; the entire safety
  model depends on it existing in fact, not only on paper. *(Highest priority.)*
- **No verification layer exists yet**; the constitution forbids execution capability before
  verification (PRIME §14, §15), so execution work must wait on it.
- **Plane boundaries are documented but not yet enforced in code**; as the codebase grows,
  leakage (UI logic, deciding adapters, second memory stores) is the likely failure mode.
- **Surfaces could diverge from the one-core rule** if voice or automation are built before the
  shared core/gate, recreating parallel logic.
- **The single Memory authority is not yet implemented**; competing stores could emerge first.
- **Planes live at different maturities across repositories**, so inter-plane contracts are
  currently implicit rather than declared.

## 22. Open Decisions

- **Approval Gate realization:** a dedicated control boundary/service vs. an enforced
  in-process boundary — and **synchronous approval vs. a deferred approval queue** for
  autonomous/gated actions.
- **Memory authority shape:** its read interface and the boundary between durable memory and
  ephemeral plane-local state.
- **Risk-classification ownership:** who defines and maintains the autonomous/gated/forbidden
  taxonomy the Gate applies.
- **Orchestration realization:** building the platform's own orchestration vs. adopting one
  (deferred; decide with evidence).
- **Contract governance:** how inter-plane interfaces are versioned and recorded (argues for
  an ADR process).

## 23. Recommended Next Foundational Documents

In priority order:

1. **`APPROVAL_GATE_SPEC.md`** — specify the Gate's action contract (Proposed/Approved/Denied),
   classification taxonomy, deferred-approval (queue) behavior, and audit format. It is the
   load-bearing control every plane and flow here depends on.
2. **`PROJECT_STRUCTURE.md`** — map repositories, planes, and their declared interfaces/
   contracts onto the file system, retiring the "implicit contracts" risk.
3. **Architecture Decision Record (ADR) process + template** — to capture open decisions (§22)
   as they are resolved.
4. **`MEMORY_AUTHORITY_SPEC.md`** — define the single-writer memory authority and its read
   interface.
5. **`VERIFICATION_STRATEGY.md`** — define the verification layer required before any execution
   capability.

### Should `APPROVAL_GATE_SPEC.md` come before `PROJECT_STRUCTURE.md`?

**Yes.** The Approval Gate is the architecture's load-bearing safety control: nearly every
plane, flow, trust boundary, and the one-core rule reference it, and it is the document's
top-ranked risk (§21). Specifying it first defines the system's safety semantics and unblocks
*safe* execution work. `PROJECT_STRUCTURE.md` records where things live — valuable, but
layout without the Gate's contract risks structure that has to be reshaped once the gate is
defined. Specify the control, then lay out the structure around it.
