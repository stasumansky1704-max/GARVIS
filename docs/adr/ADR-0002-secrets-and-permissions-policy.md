# ADR-0002: Secrets and Permissions Policy

- Status: Proposed
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

GARVIS is designed to perform real, side-effecting actions under human authority. Every
capability that follows — the Approval Gate, tools, agents, workflows, memory, integrations, and
autonomous execution — depends on a strict, consistent way of handling secrets and permissions.
Today, version control excludes environment/secret patterns and **no secrets are committed to the
repository**; however, there is no permission-enforcement mechanism, no redaction mechanism, and
no test layer to prove non-leakage, and a secrets-bearing location exists outside the repository
(out of scope, contents never inspected). The constitution forbids automation from handling
secrets and requires least privilege and no auto-approved credential/network actions
(`GARVIS_PRIME_SYSTEM_PROMPT.md` §9); the Approval Gate defines a never-auto set and forbidden set
(`APPROVAL_GATE_SPEC.md` §15–§16); and the testing strategy mandates secrets/redaction and
permission-boundary tests (`TESTING_AND_VERIFICATION_STRATEGY.md` §17, §24, §49) — but there is no
single policy those mechanisms and tests verify against. "Secrets and permissions policy" is item
#9 of the initial ADR backlog (`ADR_PROCESS.md` §37).

## Decision

Adopt
[`docs/architecture/SECRETS_AND_PERMISSIONS_POLICY.md`](../architecture/SECRETS_AND_PERMISSIONS_POLICY.md)
as the governing secrets and permissions policy for GARVIS, effective before execution,
integrations, agents, tools, memory, and autonomous workflows proceed. Core rules: secrets never
enter the repo, logs, memory, prompts, screenshots, diagnostics, or documentation and are
referenced by handle only; least privilege and deny-by-default; permission is not approval and
approval is not permission (a gated action may require both); no component self-grants or
self-authorizes; redaction precedes every display/log/memory/prompt/audit boundary including
failure paths; credential-sensitive actions are forbidden or explicitly approved under strict
constraints; autonomous and background work hold only bounded, revocable, auditable scopes and
never bypass permission checks or the Gate.

## Options considered

1. **Adopt one platform-wide secrets & permissions policy (chosen).** A single specification all
   planes verify against, aligned with the Approval Gate and testing strategy. Strongest, most
   consistent guarantee; conforms to PRIME; modest documentation cost.

2. **Ad-hoc environment-variable usage without a policy (rejected).** Rely on environment
   variables and convention. *Rejected:* no enforced redaction, classification, least-privilege,
   or audit; environment values leak easily into logs, prompts, and diagnostics; violates PRIME
   §9 and gives no testable contract.

3. **Let each plane manage secrets independently (rejected).** Per-plane secret/permission
   handling. *Rejected:* fragments authority (PRIME §8), produces inconsistent redaction and
   gaps at boundaries — exactly where leaks occur — and duplicates security logic; conflicts with
   single-authority and the plane model (Architecture Overview).

4. **Treat approval as permission (rejected).** Assume an approved action implies standing
   capability. *Rejected:* conflates a one-time authorization with a durable grant; would let an
   approval silently widen capability and erode least privilege (Gate Spec §28).

5. **Treat permission as approval (rejected).** Assume a permitted capability authorizes the
   action. *Rejected:* removes the per-action human authorization the Approval Gate exists to
   provide; never-auto and destructive actions would proceed on standing permission alone —
   directly unsafe.

6. **Log raw execution context for easier debugging (rejected).** Capture full context including
   secret material to ease troubleshooting. *Rejected:* the most direct leak path; violates the
   no-secret-in-logs rule and the redaction requirement (§28, §32); convenience does not justify
   exposure.

7. **Delay the secrets policy until integrations are implemented (rejected).** Build integrations
   first, formalize secrets later. *Rejected:* integrations are precisely where secrets and
   external permissions appear; building them without a policy guarantees ad-hoc, untested
   handling and contradicts "verification before execution" (PRIME §14–§15).

## Consequences

- **Positive:** a single, enforceable, testable basis for all secret and permission handling;
  secrets become non-leakable by policy; least-privilege and deny-by-default are the default
  posture; the Approval Gate, tools, agents, workflows, memory, and autonomy can be built safely.
- **Negative / cost:** up-front mechanism work (redaction, permission boundary, handle-based
  retrieval) before execution/integration features can proceed; capability is gated behind these
  controls, slowing short-term delivery by design.
- **Neutral:** the secret store, permission representation, and rotation mechanism are
  deliberately deferred to later ADRs; this ADR adopts the *policy*, not a tool.

## Impact

- **Security:** establishes the project's core security posture — no-secret-everywhere,
  least-privilege, deny-by-default, redaction-before-exposure, credential-sensitive forbidden-or-
  strictly-approved, and a defined threat model. Directly strengthens the Approval Gate's
  never-auto and forbidden guarantees. No secret value appears in this ADR or the policy.
- **Architecture:** places the permission boundary at the Integration/Execution edge and keeps
  permission logic in core, not in adapters (single authority; anti-duplication).
- **Operational:** defines revocation, expiration, rotation, incident handling, and recovery so
  exposure can be contained and authority withdrawn immediately.
- **Performance:** redaction and just-in-time secret retrieval add minor overhead at exposure/
  retrieval boundaries; this is acceptable and measured where budgets exist (PRIME §12). No
  budget is asserted without measurement.
- **Maintainability:** one consistent policy reduces duplicated, divergent security logic;
  handle-based references and scoped grants keep changes localized and auditable.
- **Testing:** mandates required, blocking non-leakage and least-privilege suites — proving
  secrets do not leak via logs, prompts, audit, memory, diagnostics, or failure paths, and that
  permission ≠ approval, deny-by-default, and no-self-grant hold (Strategy §17, §24, §49).

## Rollback strategy

This ADR records a policy and adds no executable code or secret material, so reversal is
low-cost: it is reversed by a superseding ADR that withdraws or replaces the policy, with the
governing document updated and history preserved (`ADR_PROCESS.md` §16–§17). Because the decision
*adds* security controls rather than enabling capability, reversing it does not create an unsafe
state; any controls already implemented under it would be retired deliberately, not abandoned.

## Validation strategy

- Confirm the policy conforms to PRIME, the Architecture Overview, the Approval Gate spec,
  Project Structure, and the testing strategy (no critical contradiction found during authoring).
- Validate in practice via the policy's readiness checklist (§81) and migration phases (§78):
  the decision is "validated" when, at each phase, the corresponding redaction, permission, and
  credential-handling controls exist and their required non-leakage/least-privilege tests pass
  before the capability they gate is enabled.
- Acceptance is a human review step (`ADR_PROCESS.md` §15); it is not self-approved. No real
  secret is used in any validation.

## Related documents

- `docs/architecture/SECRETS_AND_PERMISSIONS_POLICY.md` (the adopted policy)
- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md`
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`
- `docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md`
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`

## Supersedes

None.

## Superseded by

None.
