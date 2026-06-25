// GARVIS — Contract Registry tests (S1/S2)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Covers: valid payload passes; missing safety field, unknown field, and secret-like
// field all fail closed; unknown contract id fails closed.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { defaultContractRegistry, looksSecretLike } from "./contractRegistry.ts";

// A minimal valid approval request (safety fields present; redaction affirmed).
function validApprovalRequest(): Record<string, unknown> {
  return {
    actionId: "a1",
    actionType: "local.write",
    riskClass: "gated",
    redactionStatus: "redacted",
    correlationId: "corr-1",
  };
}

test("contract: valid approval request passes contract validation", () => {
  const registry = defaultContractRegistry();
  const result = registry.validate("approvalRequest", "1", validApprovalRequest());
  assert.equal(result.valid, true);
  assert.deepEqual(result.errors, []);
});

test("contract: missing required safety field fails closed", () => {
  const registry = defaultContractRegistry();
  const { riskClass: _omitted, ...missingSafetyField } = validApprovalRequest();
  void _omitted; // intentionally dropped: a required safety field
  const result = registry.validate("approvalRequest", "1", missingSafetyField);
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.startsWith("missing-required-safety-field")));
});

test("contract: unknown dangerous field fails closed", () => {
  const registry = defaultContractRegistry();
  const withUnknown = { ...validApprovalRequest(), arbitraryExtra: "x" };
  const result = registry.validate("approvalRequest", "1", withUnknown);
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.startsWith("unknown-field-rejected")));
});

test("contract: raw secret-like field name fails closed", () => {
  const registry = defaultContractRegistry();
  // The field NAME triggers rejection regardless of value; the value here is a placeholder,
  // never a real secret.
  const withSecretName = { ...validApprovalRequest(), apiKey: "PLACEHOLDER-NOT-A-REAL-SECRET" };
  const result = registry.validate("approvalRequest", "1", withSecretName);
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.startsWith("secret-like-field-rejected")));
});

test("contract: unknown contract id fails closed", () => {
  const registry = defaultContractRegistry();
  const result = registry.validate("approvalRequest", "999", validApprovalRequest());
  assert.equal(result.valid, false);
  assert.ok(result.errors.some((e) => e.startsWith("unknown-contract")));
});

test("contract: secret-like detector flags raw secrets but not handle fields", () => {
  assert.equal(looksSecretLike("apiKey"), true);
  assert.equal(looksSecretLike("password"), true);
  assert.equal(looksSecretLike("token"), true);
  assert.equal(looksSecretLike("tokenRef"), false); // handles are allowed
  assert.equal(looksSecretLike("correlationId"), false);
});
