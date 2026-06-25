# GARVIS — Architecture Decision Record (ADR) Process

**Status:** Binding governance process · **Scope:** How GARVIS records architectural decisions ·
**Conforms to:** [`GARVIS_PRIME_SYSTEM_PROMPT.md`](./GARVIS_PRIME_SYSTEM_PROMPT.md),
[`GARVIS_ARCHITECTURE_OVERVIEW.md`](./GARVIS_ARCHITECTURE_OVERVIEW.md),
[`APPROVAL_GATE_SPEC.md`](./APPROVAL_GATE_SPEC.md),
[`PROJECT_STRUCTURE.md`](./PROJECT_STRUCTURE.md). Where this document and those conflict, the
constitution prevails; the conflict is reported, not silently resolved.

This document defines the ADR **process** — how decisions are proposed, reviewed, recorded, and
retired. It is vendor-neutral, contains no implementation code, and **creates no actual ADR
records**; it lists only candidates (§37).

---

## 1. Purpose

- Provide one durable, reviewable record for every significant architectural decision, with its
  context, trade-offs, rejected alternatives, and consequences.
- Ensure major decisions are made **before** implementation and never erased once made.

## 2. Scope

- **In scope:** what qualifies as an architectural decision, the ADR lifecycle, fields,
  storage, ownership, review/approval, amendment/superseding, and the template.
- **Out of scope:** writing individual ADRs (only candidates are listed here), implementing any
  decision, and any tooling choice.

## 3. Why GARVIS needs ADRs

- GARVIS spans multiple planes and a long horizon; decisions made implicitly are forgotten,
  re-litigated, or silently contradicted.
- The constitution requires that non-trivial, hard-to-reverse decisions be recorded with
  rationale (PRIME §11); ADRs are that record.
- ADRs turn "we chose X" into "we chose X over Y for these reasons, with these consequences and
  this rollback," so future work can trust or revisit the decision on evidence.

## 4. What qualifies as an architectural decision

An ADR is required for any decision that:

- Introduces, removes, or restructures a plane, subsystem, or cross-cutting system.
- Defines or changes a boundary, contract, or interface between planes.
- Establishes a **single authority** (memory, approval, observability, contracts) or changes
  one.
- Affects security posture, trust boundaries, permissions, or secrets handling.
- Sets repository strategy, structure, or migration sequencing.
- Selects an approach with material, hard-to-reverse trade-offs.
- **Mandatory:** no major new subsystem, agent, workflow engine, memory authority, tool system,
  approval mechanism, or repository strategy is implemented without an Accepted ADR first.

## 5. What does not require an ADR

- Reversible, local, in-scope implementation choices with no cross-plane or security impact.
- Bug fixes, refactors that preserve behavior and boundaries, documentation edits, and naming
  within an already-decided structure.
- Temporary or experimental implementation detail (which must **not** be promoted into a
  permanent architecture decision without its own ADR).
- When unsure, default to writing an ADR; the cost of a record is low, the cost of an
  unrecorded decision is high.

## 6. ADR principles

- **Decide before building.** The ADR precedes implementation of what it decides.
- **State trade-offs honestly**, including the options rejected and why.
- **No vague notes.** An ADR is a structured decision (§9 fields), not a scratchpad.
- **Conform to the constitution.** An ADR must never silently contradict PRIME (§20).
- **Preserve history.** ADRs are immutable once Accepted; change happens by superseding, not
  by erasing (§16, §17).
- **One decision per ADR.** Bundled, multi-topic ADRs are split.

## 7. ADR lifecycle

```
Draft → Proposed → Accepted ───────→ Implemented → Superseded
                 └→ Rejected                    └→ Deprecated
```

- **Draft:** authored, not yet submitted for review.
- **Proposed:** submitted for review against the required criteria (§25).
- **Accepted:** approved (§15); becomes binding and immutable in substance.
- **Rejected:** not adopted; retained when its reasoning is useful (§18).
- **Implemented:** the Accepted decision has been realized and verified.
- **Superseded:** replaced by a later ADR (link both ways; §17).
- **Deprecated:** no longer applicable but not directly replaced (§19).

## 8. ADR statuses

`Draft` · `Proposed` · `Accepted` · `Rejected` · `Implemented` · `Superseded` · `Deprecated`.
Status is a single, explicit field; transitions follow §7 and are recorded with date.

## 9. Required ADR fields

Every ADR includes, at minimum:

- **ADR number** — unique, sequential (§11).
- **Title** — concise statement of the decision.
- **Status** — one of §8.
- **Date** — decision/last-transition date.
- **Owner** — the accountable decision owner (§13).
- **Context** — the problem, constraints, and forces.
- **Decision** — the choice made, stated plainly.
- **Options considered** — alternatives, including the rejected ones and why.
- **Consequences** — resulting trade-offs, positive and negative.
- **Security impact** — effect on trust boundaries, permissions, secrets (§26).
- **Architecture impact** — effect on planes, boundaries, contracts.
- **Operational impact** — effect on running, recovery, observability (§27).
- **Testing impact** — what must be verified (§32).
- **Rollback strategy** — how to reverse the decision (§30).
- **Validation strategy** — how the decision is verified as correct/effective.
- **Related documents** — governing docs and other ADRs.
- **Supersedes** — prior ADR(s) this replaces, if any.
- **Superseded by** — later ADR replacing this one, if any.

An ADR missing security, rollback, validation, or rejected-alternatives content is incomplete
and cannot be Accepted.

## 10. ADR naming convention

- File name: `ADR-NNNN-short-kebab-title.md` (e.g., `ADR-0007-memory-authority-design.md`).
- The title in the file matches the file name's intent; vendor-neutral wording.

## 11. ADR numbering convention

- Numbers are zero-padded, sequential, and **monotonic**; once assigned, a number is never
  reused, even if the ADR is Rejected or Superseded.
- Gaps are left as-is (a Rejected ADR keeps its number); numbers are not backfilled.

## 12. ADR storage location

- All ADRs live in `docs/adr/` (per `PROJECT_STRUCTURE.md` §7) — a single, flat, discoverable
  home. No ADRs are scattered across planes or surfaces.

## 13. Decision ownership

- Each ADR has exactly one accountable **Owner** who drives it through the lifecycle.
- Ownership does not mean unilateral authority: Accepting an ADR requires review and approval
  (§14, §15). The Owner records the outcome faithfully, including dissent.

## 14. Review rules

- A Proposed ADR is reviewed against the required decision criteria (§25) and all impact fields
  (§26–§32).
- Review checks: conformance to PRIME (§20), completeness of rejected alternatives, clarity of
  trade-offs, and presence of rollback and validation strategies.
- An ADR that would contradict the constitution is not reviewed toward Acceptance; it is sent
  back, and any genuine conflict is reported per §20.

## 15. Approval rules

- An ADR becomes **Accepted** only by explicit human approval (PRIME §11; gate discipline of
  Approval Gate §29 by analogy). Automation does not Accept ADRs.
- Approval authorizes the decision, not its implementation; implementing it remains subject to
  the Approval Gate and the relevant phase gates.
- Decisions in the never-auto / security-sensitive space require explicit, attributable human
  sign-off.

## 16. Amendment rules

- An **Accepted** ADR's decision is immutable. Substance changes are made by a **new**
  superseding ADR (§17), not by editing the original.
- Non-substantive corrections (typos, broken links, clarifications that do not change meaning)
  are permitted and noted; they never alter the recorded decision or its consequences.

## 17. Superseding decisions

- A new ADR may supersede one or more prior ADRs. The new ADR lists **Supersedes**; the prior
  ADR is set to **Superseded** with **Superseded by** pointing forward.
- Superseding **preserves history**: the old ADR remains readable with its original reasoning;
  it is never deleted or overwritten.

## 18. Rejected decisions

- A **Rejected** ADR is retained when its reasoning has lasting value (why an approach was *not*
  taken), preventing the same proposal from being re-litigated blindly.
- Rejected ADRs keep their number (§11) and are clearly marked; they are not implemented.

## 19. Deprecation rules

- An ADR is **Deprecated** when its decision no longer applies and is not directly replaced
  (e.g., the subsystem it governed was removed).
- Deprecation records the reason and date; the ADR remains for history.

## 20. Relationship to the GARVIS PRIME constitution

- PRIME is supreme. An ADR **must not silently contradict** it.
- If a decision genuinely requires departing from PRIME, the conflict is **reported**, and PRIME
  is amended by its own deliberate process **before** such an ADR can be Accepted. ADRs do not
  amend PRIME by side effect.

## 21. Relationship to the Architecture Overview

- ADRs refine and evolve the plane model, boundaries, and communication paths defined in the
  Overview; they cite it and stay within its principles unless a superseding ADR explicitly and
  conformantly changes a boundary.

## 22. Relationship to the Approval Gate spec

- Two distinct mechanisms: **ADRs govern design-time decisions; the Approval Gate governs
  run-time actions.** Neither substitutes for the other.
- Any ADR that touches approval, execution, or side-effecting capability must show conformance
  to the Gate Spec, and must not weaken its invariants.

## 23. Relationship to Project Structure

- ADRs that introduce or relocate planes, contracts, or directories conform to
  `PROJECT_STRUCTURE.md` and update the relevant open decisions there.
- New plane/agent/tool/workflow directories require the "recorded reason" mandated by Project
  Structure §6 — that reason is an ADR.

## 24. Relationship to testing and verification

- Every ADR states a **Validation strategy** (§9) and **Testing impact** (§32). A decision that
  cannot be validated is not ready to be Accepted.
- Decisions enabling execution capability must align with the forthcoming testing/verification
  strategy and the constitution's "verification before execution" (PRIME §14–§15).

## 25. Required decision criteria

A Proposed ADR is evaluated on: constitutional conformance, clearly stated trade-offs, rejected
alternatives, reversibility/rollback, validation, and the five impact reviews below (§26–§29,
§32). Failing any required criterion blocks Acceptance.

## 26. Security review requirements

- State the effect on trust boundaries, permissions, secrets, and the Approval Gate.
- Confirm no secret is exposed and no never-auto rule (Gate Spec §15) is weakened.
- Security-sensitive ADRs require explicit human sign-off.

## 27. Operational review requirements

- State the effect on running, failure/recovery, and observability.
- Confirm the decision keeps actions observable and recoverable (PRIME §18–§19).

## 28. Performance review requirements

- State relevant performance budgets (latency, frame, memory, resource/cost) the decision
  affects, and how they are measured (PRIME §12). "No measurable impact" is itself a claim to
  justify.

## 29. Maintainability review requirements

- State the effect on complexity, coupling, single-authority, and anti-duplication
  (PRIME §4, §8). A decision that adds duplication or a second authority must justify it or be
  rejected.

## 30. Rollback requirements

- Every ADR states how the decision is reversed and at what cost.
- A decision with no feasible rollback requires explicit human approval and a defined recovery
  path before Acceptance (mirrors Gate Spec §37).

## 31. Documentation requirements

- An Accepted ADR is the documentation of its decision; related governing docs are updated to
  reference it where they intersect.
- ADRs are concise and structured; they do not duplicate another document's authority.

## 32. Testing requirements

- State what must be tested to consider the decision correctly implemented, and (where relevant)
  which Approval Gate or boundary invariants the change must not break.
- For execution-enabling decisions, the required verification must exist before Implementation.

## 33. ADR template

```
# ADR-NNNN: <Title>

- Status: <Draft | Proposed | Accepted | Rejected | Implemented | Superseded | Deprecated>
- Date: <YYYY-MM-DD>
- Owner: <accountable owner>

## Context
<Problem, constraints, and forces.>

## Decision
<The choice made, stated plainly.>

## Options considered
<Each option, including rejected alternatives and why they were rejected.>

## Consequences
<Resulting trade-offs, positive and negative.>

## Impact
- Security: <trust boundaries, permissions, secrets, Approval Gate>
- Architecture: <planes, boundaries, contracts>
- Operational: <running, recovery, observability>
- Performance: <budgets affected and how measured>
- Maintainability: <complexity, coupling, single-authority>
- Testing: <what must be verified; invariants not to break>

## Rollback strategy
<How the decision is reversed, and at what cost.>

## Validation strategy
<How the decision is verified as correct and effective.>

## Related documents
<Governing docs and related ADRs.>

## Supersedes / Superseded by
<Prior ADR(s) replaced / later ADR replacing this.>
```

## 34. Examples of decisions that require ADRs

- Choosing monorepo vs multi-repo, or changing repository/migration strategy.
- Defining the Approval Gate's implementation boundary.
- Establishing the memory authority's design, or the contracts/versioning scheme.
- Selecting the agent orchestration model, tool permission model, or a workflow engine.
- Setting observability/audit storage, or the secrets/permissions policy.

## 35. Examples of decisions that do not require ADRs

- A reversible refactor that preserves behavior and boundaries.
- Adjusting copy, layout, or styling within the already-decided Interface boundary.
- A local helper choice with no cross-plane, security, or contract impact.
- A clearly temporary spike, kept out of permanent architecture until an ADR promotes it.

## 36. Anti-patterns

- **Retroactive ADRs** that rubber-stamp something already built without real review.
- **Vague ADRs** lacking rejected alternatives, rollback, or validation.
- **Bundled ADRs** deciding many unrelated things at once.
- **Editing an Accepted ADR's decision** instead of superseding it.
- **Deleting Rejected/Superseded ADRs**, erasing useful history.
- **Promoting temporary implementation detail** into a permanent decision without its own ADR.
- **An ADR that quietly contradicts PRIME** instead of reporting the conflict (§20).

## 37. Initial ADR backlog

Candidates only — **no ADR files are created by this document.** Each becomes a Draft when
picked up:

1. Repository strategy: monorepo vs multi-repo.
2. Approval Gate implementation boundary.
3. Testing and verification strategy.
4. Memory authority design.
5. Contract and schema versioning.
6. Agent orchestration model.
7. Tool permission model.
8. Observability and audit storage.
9. Secrets and permissions policy.
10. Workflow engine strategy.
11. UI/interface boundary migration.

These map to the open-decision sections of the prior architecture docs; ordering and ownership
are assigned when each is opened.

## 38. Readiness checklist

Before the ADR process is considered active:

- [ ] `docs/adr/` location reserved (per Project Structure §7).
- [ ] Numbering and naming conventions (§10–§11) agreed.
- [ ] Template (§33) adopted as the required structure.
- [ ] Review/approval rules (§14–§15) understood; human sign-off required for Acceptance.
- [ ] Immutability + superseding rules (§16–§17) understood; history is never erased.
- [ ] Backlog (§37) acknowledged; first ADR selected when work begins.

## 39. Recommended next foundational document

**`docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md`** — it is the next capability-critical
document. The Approval Gate's readiness (Gate Spec §39, §44) and the constitution's "verification
before execution" (PRIME §14–§15) both depend on a defined verification strategy, and several
backlog ADRs (especially #2 and #3) cannot be Accepted without it. With the ADR process now in
place, that strategy — and the decisions it implies — can be recorded properly.
