# ADR-0001: Testing and Verification Strategy

- Status: Proposed
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

GARVIS aims to perform real, side-effecting actions under human authority. The constitution
requires that the verification layer exist **before** any execution capability is enabled
(`GARVIS_PRIME_SYSTEM_PROMPT.md` §14–§15), and the Approval Gate's readiness depends on passing
invariant tests (`APPROVAL_GATE_SPEC.md` §39, §44). Today the project has build and lint scripts
but **no test runner, no test suite, and no test script**; a browser-automation library exists as
an unused dependency, and the Interface has historically been checked by manual visual
inspection. "Testing and verification strategy" is item #3 of the initial ADR backlog
(`ADR_PROCESS.md` §37) and is a prerequisite for the execution and autonomy work that several
other backlog items depend on. A single, governing strategy is needed so that capability is
gated by proof rather than by schedule.

## Decision

Adopt
[`docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md`](../architecture/TESTING_AND_VERIFICATION_STRATEGY.md)
as the governing testing and verification strategy for GARVIS, effective before execution and
autonomy work proceeds. Capability is enabled only when its required tests pass:

- No execution capability before the Approval Gate invariant suite, permission-boundary tests,
  execution token-binding/fail-closed tests, secrets/redaction tests, and audit/observability
  tests pass (Strategy §51).
- No autonomous capability before deferred-approval, denial-handling, idempotency, and recovery
  tests pass, and autonomy is proven to use the same Gate and recovery model as manual
  (Strategy §52).
- No production release before smoke, end-to-end golden paths, negative/adversarial suites, and
  performance budgets pass, with no required test removed or weakened (Strategy §53).

## Options considered

1. **Adopt a single, plane-aligned, safety-invariant-gated strategy (chosen).** One strategy
   that mirrors the architecture, defines the required safety-invariant suites, and blocks
   capability until proof exists. Strongest safety guarantee; conforms to PRIME and the Gate
   spec; modest up-front documentation cost.

2. **Ad-hoc manual testing only (rejected).** Continue verifying by human inspection.
   *Rejected:* manual inspection is non-repeatable, does not scale, and cannot prove safety
   invariants (no-bypass, single-use tokens, secret redaction). It violates PRIME §14 and Gate
   Spec §39 and would leave execution capability ungated by proof.

3. **Test after execution features are implemented (rejected).** Build capability first, add
   tests later. *Rejected:* directly violates "verification before execution" (PRIME §14–§15);
   it would enable side-effecting paths before their safety is proven — the exact risk the
   Approval Gate exists to prevent.

4. **Separate testing strategies per plane (rejected).** Each plane defines its own approach.
   *Rejected:* the most damaging risks live at plane **boundaries** and in cross-cutting
   invariants (Gate, permissions, secrets, audit). Per-plane silos would fragment the invariant
   suites, duplicate authority (PRIME §8), and let boundary gaps slip through; it conflicts with
   "tests mirror architecture boundaries" (Architecture Overview, Project Structure §39).

5. **UI-only validation (rejected).** Validate the Interface surface and treat the rest as
   covered. *Rejected:* the Interface owns no business logic, execution, or approval (Overview
   §5); validating only the surface proves nothing about the Gate, execution, integration,
   memory, or secrets. It would give false confidence about the parts that actually act on the
   world.

## Consequences

- **Positive:** safety-critical behavior becomes provable and gated; execution/autonomy cannot
  outrun verification; boundary and cross-cutting risks are covered by required suites; a clear
  migration path (Strategy §61) replaces ad-hoc visual checks.
- **Negative / cost:** up-front investment to stand up a harness and the invariant suites before
  execution work can proceed; capability delivery is intentionally gated behind passing tests,
  which slows feature enablement in the short term (by design).
- **Neutral:** tool selection is deliberately deferred to a later ADR; this ADR adopts the
  *strategy*, not a framework.

## Impact

- **Security:** establishes mandatory secrets/redaction, permission-boundary, trust-boundary,
  and adversarial test requirements (Strategy §23–§24, §49); strengthens the Approval Gate's
  never-auto and forbidden guarantees with required tests. No secret is used in tests.
- **Architecture:** tests mirror plane boundaries and contracts (Overview §4; Project Structure
  §39); reinforces single-authority and anti-duplication by verifying them.
- **Operational:** defines CI/local/pre-merge/pre-release gates and fail-closed/recovery tests
  (Strategy §25, §39–§43); keeps actions observable and recoverable.
- **Performance:** requires performance-budget verification where budgets are defined
  (Strategy §33; PRIME §12); no budget is asserted without measurement.
- **Maintainability:** "never weaken/remove tests to pass" and "regression test per bug fix"
  (Strategy §10, §34) protect long-term quality; risk-weighted coverage avoids coverage theater.
- **Testing:** this ADR *is* the testing decision; it enumerates the required suites and the
  blockers (Strategy §51–§53) and the readiness checklists (Strategy §58–§60).

## Rollback strategy

This ADR records a strategy and adds no executable code, so reversal is low-cost: it is reversed
by a superseding ADR that withdraws or replaces the strategy, with the governing document updated
accordingly (history preserved per `ADR_PROCESS.md` §16–§17). No data migration or code rollback
is involved. Because the decision *adds* verification gates rather than enabling capability,
reversing it does not create an unsafe state.

## Validation strategy

- Confirm the strategy document conforms to PRIME, the Architecture Overview, the Approval Gate
  spec, and Project Structure (no critical contradiction found during authoring).
- Validate via the strategy's own readiness checklist (§64) and the Approval-Gate and autonomous
  readiness checklists (§59–§60): the decision is "validated in practice" when, at each phase,
  the corresponding required suites exist and pass before the capability they gate is enabled.
- Acceptance of this ADR is a human review step (`ADR_PROCESS.md` §15); it is not self-approved.

## Related documents

- `docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md` (the adopted strategy)
- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md`
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`

## Supersedes

None.

## Superseded by

None.
