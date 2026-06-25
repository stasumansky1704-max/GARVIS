// GARVIS — Approval Gate invariant tests (S0–S2)
//
// Zero-dependency Node built-in test runner with native TypeScript type-stripping.
// Run with: `npm test`.
//
// Invariants 1–3 are preserved from S0/S1; invariant 4 (contract validation before
// classification/token creation) is added in S1/S2.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { ApprovalGate, classify } from "./approvalGate.ts";
import type { ProposedAction } from "./approvalGate.ts";

// A minimal valid approval-request payload (safety fields present, redaction affirmed).
function validRequest(id: string, type: string): Record<string, unknown> {
  return {
    actionId: id,
    actionType: type,
    riskClass: "gated",
    redactionStatus: "redacted",
    correlationId: `corr-${id}`,
  };
}

test("invariant 1: no action executes without an approved action", () => {
  const gate = new ApprovalGate();
  const action: ProposedAction = { id: "a1", type: "local.write" };

  // No token supplied — execution must be refused.
  const result = gate.authorizeExecution(action);
  assert.equal(result.allowed, false);
  assert.equal(result.reason, "no-approved-action");
});

test("invariant 2: approval token is single-use and replay is rejected", () => {
  const gate = new ApprovalGate();
  const action: ProposedAction = { id: "a2", type: "local.write" };

  const token = gate.requestApproval(validRequest("a2", "local.write"));
  assert.ok(token, "a valid gated request should yield a single-use token");

  // First use is allowed and consumes the token.
  const first = gate.authorizeExecution(action, token);
  assert.equal(first.allowed, true);
  assert.equal(first.reason, "approved");

  // Replaying the same token must be rejected.
  const replay = gate.authorizeExecution(action, token);
  assert.equal(replay.allowed, false);
  assert.equal(replay.reason, "token-replay-rejected");
});

test("invariant 3: unknown or unclassifiable action fails closed", () => {
  const gate = new ApprovalGate();
  const action: ProposedAction = { id: "a3", type: "totally.unknown.kind" };

  // It cannot be classified...
  assert.equal(classify(action), "unknown");

  // ...so even a contract-valid request for it mints no token (fail closed)...
  const token = gate.requestApproval(validRequest("a3", "totally.unknown.kind"));
  assert.equal(token, null);

  // ...and execution is refused.
  const result = gate.authorizeExecution(action);
  assert.equal(result.allowed, false);
});

test("invariant 4: gate refuses token creation for an invalid approval request", () => {
  const gate = new ApprovalGate();

  // Missing required safety fields (only id/type present) — must be rejected before
  // classification, so no token is issued.
  const missingFields = gate.requestApproval({ actionId: "a4", actionType: "local.write" });
  assert.equal(missingFields, null);

  // A request carrying a raw secret-like field is also rejected (value is a placeholder).
  const secretLike = gate.requestApproval({
    ...validRequest("a4b", "local.write"),
    apiKey: "PLACEHOLDER-NOT-A-REAL-SECRET",
  });
  assert.equal(secretLike, null);
});
