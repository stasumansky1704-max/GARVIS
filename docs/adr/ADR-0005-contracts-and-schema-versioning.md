# ADR-0005: Contracts and Schema Versioning

- Status: Accepted
- Date: 2026-06-25
- Owner: GARVIS Architecture

## Context

GARVIS is a multi-plane platform whose most damaging failures occur at boundaries. The Approval
Gate, permissions, memory, audit, tools, agents, workflows, integrations, and the UI/voice surfaces
all exchange structured payloads, and the prior specifications each defined conceptual record/
message shapes (approval request/decision, permission scope, memory record/reference, audit record/
reference, intents, proposed/approved actions). Without a single governed way to specify, own,
version, and evolve these contracts, planes would exchange ad-hoc payloads, redefine the same
concept in incompatible ways, and let unsafe or secret-bearing shapes cross boundaries unchecked —
fragmenting authority (PRIME §8) and undermining the safety guarantees of the Gate, secrets policy,
memory, and audit. The constitution requires explicit contracts and single source of truth (PRIME
§4, §8); Project Structure designates a single `contracts/` authority (§26); the testing strategy
mandates contract tests at boundaries (§15); and the four cross-cutting authority specs explicitly
defer versioning to a single discipline. "Contract and schema versioning" is item #5 of the initial
ADR backlog (`ADR_PROCESS.md` §37). Today there is no registry, no versioning, and no boundary
validation.

## Decision

Adopt
[`docs/architecture/CONTRACTS_AND_SCHEMA_VERSIONING.md`](../architecture/CONTRACTS_AND_SCHEMA_VERSIONING.md)
as the governing contracts and schema versioning specification for GARVIS, effective before
execution, integrations, agents, tools, workflows, durable memory, observability, approval-gated
actions, autonomous workflows, or plugin systems proceed. Core rules: contracts are architecture
boundaries (not convenience types) with no business logic; one source of truth per contract in a
single governed registry, with no competing/forked versions; explicit, visible versioning with a
classified compatibility model (backward/forward/breaking); breaking changes require an ADR or
documented change record, a new major version, a migration path, and a deprecation window;
deprecated contracts remain documented until safe removal; every safety-relevant exchange
(approval request/decision, permission scope, memory and audit records/references, agent messages,
tool calls/results, workflow definitions/state) is an explicit versioned contract carrying required
safety fields (risk/sensitivity class, redaction status, correlation id, idempotency key,
dependency-chain references) and **never** raw secrets/credentials/tokens/execution-context/audit
payloads; consumers must not silently accept unknown dangerous fields and producers must not
silently omit required safety fields; contract validation fails closed for security-relevant or
gated actions; integrations translate vendor-native shapes at the edge and never leak them into
core; derived types/clients are artifacts, never the source of truth.

## Options considered

1. **One governed contract registry with explicit versioning and classified compatibility
   (chosen).** Single source of truth, redaction-aware, fail-closed validation, ADR-gated breaking
   changes. Strongest boundary stability and safety; conforms to PRIME; encoding deferred.

2. **Ad-hoc payloads between planes (rejected).** *Rejected:* hides drift, prevents validation and
   versioning, and lets unsafe/secret-bearing shapes cross boundaries — the exact boundary-failure
   class this spec prevents.

3. **Let each plane define its own DTOs independently (rejected).** *Rejected:* produces competing,
   incompatible definitions of the same concept, fragments authority (PRIME §8), and guarantees
   drift and duplication (a defect, §93).

4. **Use UI shapes as platform contracts (rejected).** *Rejected:* display shapes are presentation
   concerns; binding the platform to them inverts the contract→type direction and couples core to a
   surface (Overview §5; §88).

5. **Use vendor-native schemas as core architecture contracts (rejected).** *Rejected:* binds the
   architecture to external/vendor shapes (PRIME §8 — contracts over implementations) and leaks
   vendor concerns into core; integrations must translate at the edge (§69).

6. **Add versioning only after integrations exist (rejected).** *Rejected:* integrations are where
   external shapes and version skew appear; building them without a versioning discipline guarantees
   ad-hoc, untested contracts and contradicts "verification before execution" (PRIME §14–§15).

7. **Allow shared types to contain business logic (rejected).** *Rejected:* turns a vocabulary into
   a hidden behavior layer, duplicates logic, and violates the no-business-logic-in-contracts rule
   (§88, §90).

8. **Accept breaking changes without a migration policy (rejected).** *Rejected:* strands consumers,
   makes upgrades unsafe, and erases the compatibility guarantees boundaries depend on; breaking
   changes require ADR + migration + deprecation (§23, §27).

9. **Allow tools and agents to define private unversioned contracts (rejected).** *Rejected:*
   creates uncontracted, untested side-effecting boundaries — precisely where safety must be
   strongest; tools/agents must use registered versioned contracts (§66–§67).

## Consequences

- **Positive:** stable, evolvable, testable, redaction-aware boundaries; one source of truth that
  prevents drift and duplication; safe foundation for execution, tools, agents, workflows, memory,
  audit, and autonomy; storage/encoding can change beneath contracts without breaking consumers.
- **Negative / cost:** up-front registry, versioning, and validation work before boundary-crossing
  features can proceed; breaking changes incur ADR + migration overhead by design; capability gated
  behind these controls, slowing short-term delivery.
- **Neutral:** encoding format, schema representation, and codegen toolchain are deferred to later
  ADRs; this ADR adopts the *specification*, not a schema technology.

## Impact

- **Security:** contracts carry classification and redaction status, reference secrets/tokens/
  memory/audit by handle only, and never contain raw secrets/credentials/tokens/execution-context/
  audit payloads; validation fails closed for gated/security-relevant exchanges. No secret value
  appears in this ADR or the spec.
- **Architecture:** establishes the single `contracts/` registry as the authoritative boundary
  source; planes depend on contract versions, not internals; integrations isolate vendor shapes.
- **Operational:** defines lifecycle, deprecation/sunset/migration, runtime/build-time validation,
  and observability/audit of contract usage by reference.
- **Performance:** validation overhead is bounded and measured where budgets exist (PRIME §12);
  safety validation for gated actions is on the critical path and not skipped.
- **Maintainability:** one definition per contract removes drift and duplicated DTOs; derived
  types/clients regenerate from the source; compatibility classification makes change safe.
- **Testing:** mandates required contract and schema tests (cross-version compatibility,
  forbidden-content-absent, fail-closed validation) at every boundary (Strategy §15).

## Rollback strategy

This ADR records a specification and adds no executable code, schema, type, registry, or secret
material, so reversal is low-cost: it is reversed by a superseding ADR that withdraws or replaces
the spec, with the governing document updated and history preserved (`ADR_PROCESS.md` §16–§17).
Because the decision *adds* boundary governance rather than enabling capability, reversing it does
not create an unsafe state; any registry/validation implemented under it would be retired
deliberately.

## Validation strategy

- Confirm the spec conforms to PRIME, the Architecture Overview, the Approval Gate spec, Project
  Structure, the testing strategy, the secrets/permissions policy, the Memory Authority spec, and
  the Observability/Audit spec, and that no contract is required to carry forbidden content (no
  critical contradiction found during authoring).
- Validate in practice via the spec's readiness checklist (§104) and migration phases (§98): the
  decision is "validated" when, at each phase, the registry, versioning, required safety fields,
  redaction, and fail-closed validation exist and their required tests pass before the boundary
  capability they gate is enabled.
- Acceptance is a human review step (`ADR_PROCESS.md` §15); it is not self-approved. No real secret
  is used in any validation.

## Related documents

- `docs/architecture/CONTRACTS_AND_SCHEMA_VERSIONING.md` (the adopted specification)
- `docs/architecture/GARVIS_PRIME_SYSTEM_PROMPT.md`
- `docs/architecture/GARVIS_ARCHITECTURE_OVERVIEW.md`
- `docs/architecture/APPROVAL_GATE_SPEC.md`
- `docs/architecture/PROJECT_STRUCTURE.md`
- `docs/architecture/ADR_PROCESS.md`
- `docs/architecture/TESTING_AND_VERIFICATION_STRATEGY.md`
- `docs/architecture/SECRETS_AND_PERMISSIONS_POLICY.md`
- `docs/architecture/MEMORY_AUTHORITY_SPEC.md`
- `docs/architecture/OBSERVABILITY_AND_AUDIT_SPEC.md`
- `docs/adr/ADR-0001-testing-and-verification-strategy.md`
- `docs/adr/ADR-0002-secrets-and-permissions-policy.md`
- `docs/adr/ADR-0003-memory-authority.md`
- `docs/adr/ADR-0004-observability-and-audit.md`

## Supersedes

None.

## Superseded by

None.
