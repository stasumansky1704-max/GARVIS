// GARVIS — Approval Gate invariant tests (S0–S3)
//
// Zero-dependency Node built-in test runner with native TypeScript type-stripping.
// Run with: `npm test`.
//
// Invariants 1–4 from S0–S2 are preserved; the S2/S3 additions prove that execution
// requires BOTH permission and approval (permission is not approval; approval is not
// permission), and that credential-sensitive / destructive actions fail closed.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { ApprovalGate, classify } from "./approvalGate.ts";
import type { ProposedAction } from "./approvalGate.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";

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

  // No token supplied — execution must be refused (token checked before permission).
  const result = gate.authorizeExecution(action);
  assert.equal(result.allowed, false);
  assert.equal(result.reason, "no-approved-action");
});

test("invariant 2: approval token is single-use and replay is rejected", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write"); // permission present so the first authorization can succeed
  const gate = new ApprovalGate(undefined, perms);
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

  assert.equal(classify(action), "unknown");

  const token = gate.requestApproval(validRequest("a3", "totally.unknown.kind"));
  assert.equal(token, null);

  const result = gate.authorizeExecution(action);
  assert.equal(result.allowed, false);
});

test("invariant 4: gate refuses token creation for an invalid approval request", () => {
  const gate = new ApprovalGate();

  const missingFields = gate.requestApproval({ actionId: "a4", actionType: "local.write" });
  assert.equal(missingFields, null);

  const secretLike = gate.requestApproval({
    ...validRequest("a4b", "local.write"),
    apiKey: "PLACEHOLDER-NOT-A-REAL-SECRET",
  });
  assert.equal(secretLike, null);
});

test("permission/approval 7: permission alone does not authorize execution", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write"); // permission held...
  const gate = new ApprovalGate(undefined, perms);
  const action: ProposedAction = { id: "p7", type: "local.write" };

  // ...but no approval token → refused.
  const result = gate.authorizeExecution(action);
  assert.equal(result.allowed, false);
  assert.equal(result.reason, "no-approved-action");
});

test("permission/approval 8: approval alone does not authorize execution", () => {
  const perms = new PermissionRuntime(); // NO permission granted
  const gate = new ApprovalGate(undefined, perms);

  // Approval can be obtained without holding the permission (permission is not approval).
  const token = gate.requestApproval(validRequest("p8", "local.write"));
  assert.ok(token, "approval is independent of permission");

  const action: ProposedAction = { id: "p8", type: "local.write" };
  const result = gate.authorizeExecution(action, token);
  assert.equal(result.allowed, false);
  assert.ok(result.reason.startsWith("permission-denied"));
});

test("permission/approval 9: gate requires both permission and approval for a gated action", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms);

  const token = gate.requestApproval(validRequest("p9", "local.write"));
  const action: ProposedAction = { id: "p9", type: "local.write" };
  const result = gate.authorizeExecution(action, token);

  assert.equal(result.allowed, true);
  assert.equal(result.reason, "approved");
});

test("permission/approval 10: credential-sensitive and destructive fail closed without grant", () => {
  const perms = new PermissionRuntime(); // no dangerous scopes granted
  const gate = new ApprovalGate(undefined, perms);

  // Destructive is gated → a token is minted, but with no destructive grant execution fails.
  const dToken = gate.requestApproval(validRequest("p10d", "destructive"));
  assert.ok(dToken, "destructive is gated and tokenizable");
  const dResult = gate.authorizeExecution({ id: "p10d", type: "destructive" }, dToken);
  assert.equal(dResult.allowed, false);
  assert.ok(dResult.reason.startsWith("permission-denied"));

  // Credential is forbidden → no token is ever issued (fails closed before permission).
  const cToken = gate.requestApproval(validRequest("p10c", "credential"));
  assert.equal(cToken, null);
});
