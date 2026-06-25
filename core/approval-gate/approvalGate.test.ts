// GARVIS — Approval Gate invariant tests (S0/S1)
//
// Uses the zero-dependency Node built-in test runner (`node:test`) with native
// TypeScript type-stripping (Node >= 23.6). Run with: `npm test`.
//
// These three tests encode the first non-negotiable safety invariants. They were
// written test-first (red) against an empty module, then satisfied by the minimal
// ApprovalGate skeleton (green).

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { ApprovalGate, classify } from "./approvalGate.ts";
import type { ProposedAction } from "./approvalGate.ts";

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

  const token = gate.requestApproval(action);
  assert.ok(token, "a gated action should yield a single-use token");

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

  // ...so no token may ever be issued for it...
  const token = gate.requestApproval(action);
  assert.equal(token, null);

  // ...and execution is refused (fail closed), even if someone tries with no token.
  const result = gate.authorizeExecution(action);
  assert.equal(result.allowed, false);
});
