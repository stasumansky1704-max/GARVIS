# ADR-0007: Foundational Architecture Ratification

- Status: Accepted
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

GARVIS authored a sequence of foundational architecture documents and recorded six decisions
(ADR-0001 through ADR-0006) adopting the cross-cutting specifications (testing/verification,
secrets/permissions, memory, observability/audit, contracts/versioning, tool permission model). A
read-only ratification review found those six ADRs complete, mutually consistent, and ready to
Accept unchanged, with **one governance gap**: the foundational documents themselves — the
constitution, the architecture overview, the Approval Gate specification, the project structure,
and the ADR process — were **binding by declaration only** and had no explicit ratification record.
This matters most for the Approval Gate, which is the load-bearing run-time control every other
decision depends on, and which `ADR_PROCESS.md` §4 treats as an "approval mechanism" requiring an
Accepted ADR before implementation. The human project owner is now approving ratification. This ADR
establishes the binding architecture baseline and closes that gap; the six capability ADRs are then
accepted in dependency order.

## Decision

Ratify the following foundational GARVIS architecture documents as the **binding architecture
baseline**:

- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md` (the constitution — supreme; amended only by
  its own deliberate process, this ADR records its ratification, not an amendment)
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`

This ratification closes the governance gap identified by the review: the Approval Gate and the
other foundational documents were binding by declaration but did not yet have an explicit
ratification record. With this baseline ratified, ADR-0001 through ADR-0006 are accepted in
dependency order (ADR-0001 → ADR-0002 → ADR-0003 → ADR-0004 → ADR-0005 → ADR-0006). This ADR does
not implement, enable, or weaken any control; it records the baseline as binding.

## Options considered

1. **Do nothing and leave the foundational docs binding only by declaration (rejected).** Continue
   relying on each document's "Status: Binding" header without a ratification record. *Rejected:*
   leaves the Approval Gate governance gap unresolved — the central run-time control would remain
   un-ratified while six ADRs that depend on it are accepted, an inconsistent baseline that
   `ADR_PROCESS.md` §4 specifically guards against for an approval mechanism.

2. **Create ADR-0000 retroactively (rejected).** Back-fill a zeroth ADR for the foundation.
   *Rejected:* ADR-0001 through ADR-0006 already exist and numbering must remain **chronological and
   monotonic** (`ADR_PROCESS.md` §11); inserting an out-of-sequence ADR-0000 would break that
   discipline and rewrite the record's order.

3. **Create ADR-0007 as a forward ratification record (chosen).** A new, chronological ADR that
   ratifies the foundational baseline going forward. Preserves monotonic numbering, leaves the
   foundational documents unchanged, and produces a single, explicit, auditable ratification record.

4. **Amend every foundational architecture document with ratification language (rejected).** Edit
   each foundational doc to add an "Accepted/ratified" statement. *Rejected:* creates **unnecessary
   churn** across multiple binding documents, risks unintended edits to load-bearing specs, and
   scatters the ratification fact instead of recording it once; a single ADR is the cleaner,
   lower-risk instrument (and the foundational docs already declare conformance to PRIME).

5. **Accept ADR-0001 through ADR-0006 without ratifying the foundation (rejected).** Ratify only the
   six capability ADRs. *Rejected:* **leaves the Approval Gate governance gap unresolved** — the six
   ADRs would be Accepted while the Gate, Overview, Project Structure, and ADR Process they all
   build on remain merely declared, exactly the incoherence the review flagged.

## Consequences

- **Positive:** GARVIS gains a single, explicit, auditable baseline-ratification record; the
  Approval Gate and the other foundational documents are now binding by decision, not only by
  declaration; the six capability ADRs can be accepted on a coherent foundation. Foundational
  documents remain unmodified (no churn).
- **Negative / cost:** none material — this ADR adds a governance record and enables no capability;
  it introduces a standing expectation that future foundational baseline changes are recorded by
  ADR (a benefit framed as a cost).
- **Neutral:** PRIME remains supreme and is still amended only by its own deliberate process; this
  ADR records, but does not alter, the constitution.

## Security impact

Records the Approval Gate specification as a ratified, binding control rather than a declared one —
strengthening the accountability of the platform's central safety mechanism. No control is
weakened; no secret value is read, written, or referenced; no execution capability is enabled.

## Architecture impact

Establishes the binding architecture baseline (constitution, overview, Approval Gate, project
structure, ADR process) on which all subsequent decisions rest, and the precedent that the baseline
is changed only through the ADR process. No plane, boundary, or authority is added or altered.

## Operational impact

Provides operators and reviewers a single ratification record to point to; future baseline changes
follow the ADR lifecycle (supersede, never erase). No runtime behavior changes.

## Performance impact

None. This is a governance record with no executable effect and no performance-budget implications.

## Maintainability impact

Reduces ambiguity about what is binding and how the foundation evolves; a single ratification record
is easier to maintain than ratification language duplicated across many documents.

## Testing impact

None directly; this ADR adds no tests and enables no capability. It reaffirms that the
verification-before-execution gates defined in `TESTING_AND_VERIFICATION_STRATEGY.md` and the
Approval Gate readiness criteria remain prerequisites before any execution work.

## Rollback strategy

This ADR records a ratification and adds no executable code, schema, or secret material, so reversal
is low-cost: it is reversed by a superseding ADR that withdraws or replaces the ratification, with
history preserved (`ADR_PROCESS.md` §16–§17). Because it *records governance* rather than enabling
capability, reversing it does not create an unsafe state; the foundational documents themselves are
unaffected by a rollback of this record.

## Validation strategy

- Confirm the five foundational documents exist, are internally consistent, and are referenced as
  conformance targets by ADR-0001 through ADR-0006 (verified during the ratification review).
- Confirm this ADR follows `ADR_PROCESS.md` (required fields, template, chronological numbering) and
  that accepting it plus the six capability ADRs introduces no contradiction with PRIME.
- This ADR is **Accepted** by explicit human project-owner approval (`ADR_PROCESS.md` §15); it is
  not self-approved by automation. No real secret is used in validation.

## Related documents

- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md`
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`
- `docs/adr/ADR-0002-secrets-and-permissions-policy.md`
- `docs/adr/ADR-0003-memory-authority.md`
- `docs/adr/ADR-0004-observability-and-audit.md`
- `docs/adr/ADR-0005-contracts-and-schema-versioning.md`
- `docs/adr/ADR-0006-tool-permission-model.md`

## Supersedes

None.

## Superseded by

None.
