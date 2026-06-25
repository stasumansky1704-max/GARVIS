# GARVIS — Project & Repository Structure

**Status:** Binding structure reference · **Scope:** How GARVIS is organized as a long-term
platform · **Conforms to:** [`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md). Where this document and those appear to
conflict, the constitution prevails; the conflict is reported, not silently resolved.

This document defines target structure and the **rules** that govern it. It is vendor-neutral:
no products, models, APIs, or temporary implementation detail, and **no implementation code**.
It does **not** move, rename, or delete any file; it specifies *where things must live* and the
migration discipline to get there.

**Governing rule:** *directory structure follows architecture, never the reverse.* A folder
exists because a plane, contract, or cross-cutting system requires it — not because code
happened to land there.

---

## 1. Purpose

- Define the long-term, plane-aligned organization of GARVIS so capability can grow without
  tangled, duplicated, or hidden logic.
- Give reviewers an enforceable map of where each concern lives, who owns it, and how
  directories may depend on one another.
- Establish migration discipline: a path from the current structure to the target without
  unsafe, unreviewed moves.

## 2. Scope

- **In scope:** directory and repository organization, plane-to-directory mapping, ownership,
  boundary/import rules, naming, anti-duplication, migration rules, and structure readiness.
- **Out of scope:** implementing any plane, moving/renaming/deleting files now, choosing
  tools, and writing code. Those are governed elsewhere and gated by future phases.

## 3. Current repository role

- This repository is the **Interface Plane** surface (the Living UI). Its `src/` holds the
  presentation/interaction code (`scene/`, `hud/`, composition, styles, local assets).
- The other planes are **not present here yet**: cognition/voice, orchestration, command/
  execution, integration, memory, observability, and the Approval Gate exist today as
  specification (these architecture docs) and, for some, as separate areas outside this repo.
- The repository root currently also holds development artifacts (captures, logs, scratch
  scripts) that are excluded from version control; they are not structure and have no
  architectural standing.
- **Implication:** this repo is one *surface* of a larger platform. It must not grow a second
  copy of platform logic; it consumes the shared core, it does not reimplement it.

## 4. Target repository strategy

- GARVIS is organized **by plane**, around a **shared core** and a **single contracts
  authority**. The five path planes (Interface, Cognition/Voice, Orchestration, Command/
  Execution, Integration) sit around cross-cutting systems (Memory, Observability) and the
  Approval Gate, which is core safety infrastructure.
- **One core, many surfaces** (Overview): every surface depends on the same core, contracts,
  gate, memory authority, and observability. Surfaces never carry private business logic.
- Whether the platform is physically one repository or several, the **logical** boundaries in
  this document are mandatory and identical.

## 5. Monorepo vs multi-repo guidance

- The structure here is **physical-layout-agnostic**: it must hold in a monorepo and in a
  multi-repo equally.
- **Current reality:** multi-repo/poly-area (this UI repo; voice and command-system areas
  separate). That is acknowledged, not endorsed as the end state.
- **Decision criteria** (apply, then record the choice as a decision — §46):

  | Favor monorepo when | Favor multi-repo when |
  |---|---|
  | Contracts/core/gate change together and must stay in lockstep | Planes have independent lifecycles and release cadences |
  | Cross-plane refactors are frequent | Strong isolation/ownership boundaries are required |
  | One verification pipeline is preferred | Planes use incompatible toolchains |

- **Mandatory regardless of choice:** contracts, the shared core, the Approval Gate, and the
  memory authority each have **exactly one source of truth**. In a multi-repo layout they are a
  **versioned shared dependency**, never copied or forked into a surface.
- **Effective immediately:** no plane or surface duplicates another plane's logic, regardless
  of how many repositories exist.

## 6. Top-level structure principles

- Every directory has **one purpose and one owner**; an unowned or purpose-ambiguous folder is
  a defect.
- **Planes are bounded**; cross-cutting systems (Memory, Observability) and the Approval Gate
  live in the **core**, not inside any surface or tool.
- **Contracts are explicit and versioned**, in a single location all planes consume.
- **Generated and transient artifacts are excluded** from version control (§42).
- **No new plane, agent, tool, or workflow directory** is created without a recorded reason
  (an ADR or equivalent).
- Structure is discoverable: a reader can locate any concern from the top level without tribal
  knowledge.

## 7. Required architecture directories

- `docs/architecture/` — the governing documents (constitution, overview, gate spec, this
  document, and successors). Single home for binding architecture.
- `docs/adr/` — Architecture Decision Records (to be introduced): one record per non-trivial,
  hard-to-reverse decision.

## 8. Required source directories (target)

Source is organized by plane and core, not by file type:

```
contracts/                 # single source of truth for inter-plane interfaces/schemas (versioned)
core/
  approval-gate/           # the Approval Gate — its own home; NOT inside UI or tools
  memory/                  # the single Memory authority
  observability/           # cross-cutting observability + audit trail home
shared/
  types/                   # shared, dependency-light types/interfaces (no business logic)
planes/
  interface/               # Interface Plane surfaces (today's src/ maps here)
  cognition/               # Cognition / Voice Plane
  orchestration/           # Orchestration Plane
    agents/                # agent roles — owned by orchestration (not scattered)
    workflows/             # autonomous/automation workflow definitions
  execution/               # Command / Execution Plane
  integration/             # Integration Plane (adapters)
    tools/                 # tool adapters — permission-bounded, no business logic
plugins/                   # optional extension points (conform to the extension model)
```

- This is the **target**; the current repo realizes only `planes/interface/` (as today's
  `src/`). The rest are introduced as their planes are built, each in its mapped home.

## 9. Required test directories

- Tests **mirror architecture boundaries** (§39): per-plane unit tests, **contract tests** at
  plane boundaries, **Approval Gate invariant tests**, and integration tests behind adapters.
- Either a top-level `tests/` mirroring the plane tree, or co-located `__tests__`/`*.test.*`
  per module — chosen once and applied uniformly (record as a decision). Tests are never
  shipped as production logic and never live in `src/` as runtime code.

## 10. Required documentation directories

- `docs/architecture/` (binding architecture) and `docs/adr/` (decisions) are the only
  authoritative documentation homes.
- Docs describe **architecture and decisions**; they are not a dumping ground for code, logs,
  captures, or transient notes (§35).

## 11. Required configuration directories

- `config/` — non-secret configuration only, versioned and reviewable.
- **Secrets are never placed in the repository** in any directory (§41); configuration
  references secrets by handle, never by value.

## 12. Required scripts/tools directories

- `scripts/` — developer/operations automation (build, verify, maintenance). Clearly named,
  reviewed, and reproducible.
- Scripts **must not become a hidden production system**: they do not perform gated runtime
  effects, do not embed business logic, and do not bypass the Approval Gate. Anything that
  acts on the world at runtime belongs to a plane and the Gate, not to `scripts/`.

## 13. Plane-to-directory mapping

| Plane / system | Target home | Owner |
|---|---|---|
| Interface | `planes/interface/` | Interface Plane |
| Cognition / Voice | `planes/cognition/` | Cognition Plane |
| Orchestration | `planes/orchestration/` | Orchestration Plane |
| Agents | `planes/orchestration/agents/` | Orchestration Plane |
| Workflows | `planes/orchestration/workflows/` | Orchestration Plane |
| Command / Execution | `planes/execution/` | Execution Plane |
| **Approval Gate** | `core/approval-gate/` | Core / platform |
| Integration | `planes/integration/` | Integration Plane |
| Tools | `planes/integration/tools/` | Integration Plane |
| Memory / Knowledge | `core/memory/` | Memory authority |
| Observability | `core/observability/` | Core / platform |
| Contracts | `contracts/` | Platform (single authority) |
| Shared types | `shared/types/` | Platform |
| Plugins | `plugins/` | Governed by extension model |

## 14. Interface Plane structure

- **Home:** `planes/interface/` (today: this repo's `src/`, including `scene/` and `hud/`).
- **Contains:** presentation surfaces, input capture, rendering of true system state, and
  relay of approval prompts to the human.
- **Must not contain:** business logic, decision-making, execution, the Approval Gate, memory,
  or integration adapters. It submits intents to Orchestration and renders results.

## 15. Cognition / Voice Plane structure

- **Home:** `planes/cognition/`.
- **Contains:** perception/interpretation that turns speech/language into structured intents.
- **Must not contain:** command execution, approval authority, persistent state, or tool
  invocation. It produces intents and hands them to Orchestration.

## 16. Orchestration Plane structure

- **Home:** `planes/orchestration/` (with `agents/` and `workflows/` beneath it).
- **Contains:** planning, routing, sequencing, agent coordination, tool selection, and
  submission of proposed actions to the Approval Gate.
- **Must not contain:** direct side effects, an embedded gate, or durable memory writes outside
  the memory authority. It is the **only** path from intent to the Gate.

## 17. Command / Execution Plane structure

- **Home:** `planes/execution/`.
- **Contains:** execution of **approved** actions via the Integration Plane; reporting of
  outcomes to Observability and durable state to the Memory authority.
- **Must not contain:** action origination/self-authorization, classification, the Gate, or
  direct reach to external systems except through Integration.

## 18. Approval Gate structure

- **Home:** `core/approval-gate/` — a **first-class, dedicated home**. The Gate is core safety
  infrastructure (Gate Spec §6).
- **Must not be** hidden inside Interface, Orchestration internals, Execution, or any tool.
  Placing approval logic inside a surface or a tool is a forbidden structure (§44).
- **Boundary:** Orchestration submits to it; Execution consumes only what it releases; it
  writes decision records to the audit trail (`core/observability/`).

## 19. Memory / Knowledge Plane structure

- **Home:** `core/memory/` — the **single** memory authority and the only writer of durable
  state.
- **Contains:** durable facts, decisions, and platform state behind a defined read interface.
- **Must not contain:** execution logic, secrets, or transient per-request context. No other
  directory may host a competing durable store (§32).

## 20. Integration Plane structure

- **Home:** `planes/integration/` (with `tools/` beneath it).
- **Contains:** thin adapters that translate between the platform and external/local systems,
  and the enforcement point for the permission boundary.
- **Must not contain:** business or decision logic. Adapters translate; they do not decide.
  Integrations are isolated from core logic (Overview §17).

## 21. Observability Plane structure

- **Home:** `core/observability/` — cross-cutting; the audit-trail home.
- **Contains:** structured event collection, telemetry, audit records, and status reporting
  consumed from all planes.
- **Must not contain:** state mutation, gate-decision logic, or secrets (§34 of the Gate Spec).

## 22. Agent structure

- **Home:** `planes/orchestration/agents/` — agents live **under Orchestration**, never as a
  scattered or top-level free-floating set.
- **Contains:** bounded, named agent roles that **propose** actions.
- **Must not contain** (§36): execution code, approval authority, self-authorization, tool
  implementations, or business logic owned by core/orchestration. Adding an agent directory or
  role requires a recorded reason.

## 23. Tool structure

- **Home:** `planes/integration/tools/` — tools are **adapters with permission boundaries**.
- **Contains:** adapter wrappers invoked by Execution under a valid Approved Action and the
  required permission.
- **Must not contain** (§37): business/decision logic, approval or permission bypass, secrets,
  or core logic. **One authority per capability** — no duplicate tools.

## 24. Workflow structure

- **Home:** `planes/orchestration/workflows/` — autonomous/automation workflow definitions,
  owned by Orchestration.
- **Contains:** declarative workflow definitions that route every effect through the Approval
  Gate, with explicit scope/budget constraints.
- **Must not contain** (§38): direct execution that bypasses the Gate, hidden production logic,
  secrets, or logic owned by core.

## 25. Plugin structure

- **Home:** `plugins/` — optional extension points conforming to the extension model
  (Overview §20) and the constitution.
- **Contains:** isolated extensions that connect to the same core, gate, memory, and
  observability — never a second core or a private gate.
- **Must not contain:** parallel platform logic, an independent approval path, or unvetted
  external code inside the trust boundary. New plugins require a recorded reason and
  verify-before-import (PRIME §16).

## 26. Shared contracts and schemas

- **Home:** `contracts/` — the **single source of truth** for inter-plane interfaces and
  schemas (e.g., intent, proposed action, approval request/decision, audit event shapes,
  described conceptually).
- Contracts are **explicit and versioned**; consumers depend on a contract version, never on
  another plane's internals.
- A contract has one owner and one definition; copies/forks are forbidden (§32).

## 27. Shared types and interfaces

- **Home:** `shared/types/` — pure, dependency-light shared types/interfaces.
- **Must not contain:** business logic, plane-specific behavior, side effects, or secrets.
  Shared types are a vocabulary, not a place to smuggle logic.

## 28. Boundary rules between directories

- Planes interact **only** through `contracts/` and `shared/`; no plane reaches into another
  plane's internal files.
- Cross-cutting needs (memory, observability) are met through `core/` interfaces, not by
  embedding copies in a plane.
- The Approval Gate is reached only at the Orchestration→Execution boundary; nothing imports a
  "side door" into it.
- A directory that needs another's internals is a boundary violation to be redesigned, not
  worked around.

## 29. Import rules

- **Allowed dependency directions:** surfaces and planes depend on `contracts/`, `shared/`, and
  declared `core/` interfaces. They do **not** depend on each other's internals.
- `planes/integration/` depends on `contracts/`, not on core business logic; `tools/` depend on
  `integration/`, not on core or other planes.
- The Interface and Cognition planes depend on `contracts/` to submit intents; they never
  import Execution or the Gate.
- **No circular dependencies.** **No surface duplicates core logic** to avoid an import; the
  fix for a missing dependency is a contract, not a copy.

## 30. Naming conventions

- Directories are named by **plane, role, or responsibility** — vendor-neutral, lowercase,
  hyphen- or single-word, one concept per name.
- No product, model, or vendor names in directory names; no ambiguous catch-alls
  (`misc/`, `stuff/`, `helpers/` as a logic dump).
- Names are stable: a rename is a recorded decision, not a casual edit (and not part of this
  document's work).

## 31. File ownership rules

- Every file belongs to **exactly one** plane or core system; orphan files (no owning plane)
  are defects.
- Ownership is explicit and discoverable (e.g., an ownership manifest is introduced with the
  target structure); ambiguous ownership blocks a merge.
- A file's location reflects its owner; logic for plane B does not live under plane A.

## 32. Anti-duplication rules

- **One authority per capability** (PRIME §8): one Gate, one memory authority, one contracts
  definition, one observability/audit home.
- Shared behavior lives **once** in `core/` or `shared/`; surfaces consume it.
- Copying a contract, a core module, or gate logic into a surface or repo is forbidden;
  duplication is resolved by extracting a single shared source.

## 33. Migration rules from current structure

- **No file is moved, renamed, or deleted by this document.** Migration is a separate, future,
  reviewed effort.
- Migration proceeds in small, reversible, audited steps; each move is justified and verified;
  history is preserved.
- Target mapping for existing code: today's `src/` (the Living UI) maps to
  `planes/interface/`; development artifacts at the root are not migrated (they are excluded
  from version control).
- A move happens only in a dedicated migration phase with passing verification before and
  after; structure changes never ride inside feature work.
- Until migration, **new** code is placed in its correct target location from the start
  wherever the target home already exists; it is not added to the wrong plane "for now."

## 34. What must not be placed in `src/` (and any plane source)

- Secrets or credentials; build artifacts or generated output; another plane's logic.
- The Approval Gate, the memory authority, agent logic, or integration adapters.
- Tests masquerading as runtime code; scratch scripts; a catch-all dumping ground.

## 35. What must not be placed in `docs/`

- Application or implementation code; secrets; generated artifacts; transient logs/captures.
- Vendor-specific or temporary implementation detail in binding architecture docs.
- A second authority that duplicates an existing document's scope.

## 36. What must not be placed in `agents/`

- Execution code or direct side effects; approval authority or self-authorization.
- Tool implementations; business logic owned by core/orchestration.
- Scattered or unowned agents outside `planes/orchestration/agents/`.

## 37. What must not be placed in `tools/`

- Business or decision logic (tools are adapters).
- Approval-gate or permission bypass; secrets; core logic.
- Duplicate tools serving a capability another tool already owns.

## 38. What must not be placed in `workflows/`

- Direct execution that bypasses the Approval Gate.
- Hidden production logic, secrets, or logic owned by core.
- Unbounded autonomy: workflows without explicit scope/budget constraints.

## 39. Testing layout

- Tests **mirror architecture boundaries**: unit per plane; **contract tests** where planes
  meet; **Approval Gate invariant tests** (Gate Spec §39) as a first-class, required suite;
  integration tests behind Integration adapters.
- Test code is clearly separated from runtime code and is never shipped as production logic.
- The chosen layout (mirrored `tests/` vs co-located) is applied uniformly and recorded.

## 40. Observability layout

- `core/observability/` is the single home for telemetry, structured events, and the **audit
  trail** that the Approval Gate writes to.
- Every plane emits to it through a defined interface; no plane keeps a private, divergent log
  of record. No secrets are stored there (§41, Gate Spec §34).

## 41. Security and secrets layout

- **Secrets never enter the repository** — no plane, config, doc, or script holds secret
  values. Secret material is supplied and stored outside version control.
- `config/` holds non-secret configuration that **references** secrets by handle.
- The **permission boundary** is enforced in `planes/integration/`; nothing downstream
  bypasses it (Gate Spec §28, §32).

## 42. Generated files and artifacts policy

- Build output, generated code, captures, logs, and dependency installs are **excluded from
  version control** and are not structure.
- Generated files are clearly identified, reproducible from source, and never hand-edited.
- A generated artifact is never treated as the source of truth.

## 43. Examples of allowed structure

```
docs/architecture/  + docs/adr/
contracts/                      # one definition, versioned, consumed by all planes
core/approval-gate/             # the Gate, dedicated home
core/memory/                    # single memory authority
core/observability/             # audit trail + telemetry
shared/types/
planes/interface/               # today's src/ (Living UI) maps here
planes/cognition/
planes/orchestration/agents/    # agents under orchestration
planes/orchestration/workflows/ # gated autonomous workflows
planes/execution/
planes/integration/tools/       # permission-bounded adapters
config/                         # non-secret config
scripts/                        # dev/ops only, no runtime effects
tests/                          # mirrors the plane tree (or co-located, applied uniformly)
```

## 44. Examples of forbidden structure

- `planes/interface/approval/…` — the Gate hidden inside a surface.
- `planes/integration/tools/<tool>/business-logic` — decision logic inside an adapter.
- `agents/` at the repository root, unowned and outside Orchestration.
- `contracts` copied into two repos/planes and edited independently.
- `core/memory-2/` or a second durable store in a surface — a competing memory authority.
- `scripts/` that performs gated runtime effects — a hidden production system.
- `docs/` holding code, secrets, logs, or captures.
- Any `secrets/`, `.env`, or credential file committed anywhere.

## 45. Architecture risks

- **Structure exists only on paper until migration** — the current single-surface repo could
  accrete cross-plane logic before the target homes exist (mitigated by §33's "place new code
  in its correct home from the start").
- **Premature directories** — creating empty plane/agent/tool/workflow folders before their
  reason exists invites unowned, purpose-less structure (mitigated by §6's recorded-reason
  rule).
- **Contract duplication under multi-repo** — the highest structural risk if contracts/core are
  copied rather than shared as a versioned dependency (§5, §32).
- **Gate or memory leaking into a surface** — the most damaging boundary violation; structure
  must keep them in `core/` (§18, §19).
- **Scripts-as-production drift** — operational scripts quietly becoming an ungoverned runtime
  (§12).

## 46. Open decisions

- **Monorepo vs multi-repo** end state, and (if multi-repo) the shared-dependency mechanism for
  contracts/core/gate.
- **Test layout:** mirrored `tests/` tree vs co-located tests (choose once, apply uniformly).
- **Ownership manifest format** for §31 (how file/folder ownership is declared).
- **Contract versioning scheme** for `contracts/` (§26).
- **Migration sequencing:** order in which existing UI code moves into `planes/interface/`, and
  the phase that authorizes it.

## 47. Readiness checklist

Before the target structure is adopted (migration authorized):

- [ ] Mono/multi-repo decision recorded with criteria (§5, §46).
- [ ] `contracts/` location and versioning scheme decided; single source of truth.
- [ ] `core/approval-gate/`, `core/memory/`, `core/observability/` homes reserved and owned.
- [ ] Plane-to-directory mapping (§13) ratified; each folder has an owner and a recorded reason.
- [ ] Import/boundary rules (§28–§29) expressible and checkable (lint/architecture test, future).
- [ ] Test layout chosen and applied uniformly (§9, §39).
- [ ] Secrets-exclusion and generated-artifact policies in force (§41–§42).
- [ ] Migration plan (§33) phased, reversible, and gated by verification.

## 48. Recommended next foundational document

**`docs/architecture/ADR_PROCESS.md`** — an Architecture Decision Record process and template.
Across the constitution, overview, gate spec, and this document, a backlog of open decisions
has accumulated (§46 here, and the open-decision sections of each prior doc). An ADR process is
the smallest, immediately-useful instrument that lets those decisions be made and recorded on
the record, and it is a prerequisite for resolving the structural and gate decisions without
re-litigation.

**Sequencing of the three candidates:**

1. **`ADR_PROCESS.md` — next.** Lightweight, unblocks recording every accumulating decision;
   prerequisite for ratifying §46 and the gate's open decisions.
2. **`TESTING_AND_VERIFICATION_STRATEGY.md` — the next *capability-critical* doc.** The Approval
   Gate's readiness (Gate Spec §39, §44) and the constitution's "verification before execution"
   (PRIME §14–§15) both depend on it; it must precede any execution capability.
3. **`MEMORY_AUTHORITY_SPEC.md` — after the above.** It underpins the audit trail and the
   single-writer memory rule, and benefits from having the ADR process and test strategy in
   place first.
