// GARVIS — Approval Gate invariant tests (S0–S3)
//
// Zero-dependency Node built-in test runner with native TypeScript type-stripping.
// Run with: `npm test`.
//
// Invariants 1–4 and the permission/approval split are preserved; the S3 additions prove
// every outcome is audited (without raw tokens/secrets) and that audit failure fails closed.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { ApprovalGate, classify } from "./approvalGate.ts";
import type { ProposedAction } from "./approvalGate.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit } from "../audit/auditRuntime.ts";

function validRequest(id: string, type: string): Record<string, unknown> {
  return {
    actionId: id,
    actionType: type,
    riskClass: "gated",
    redactionStatus: "redacted",
    correlationId: `corr-${id}`,
  };
}

// ── Invariants 1–4 ──────────────────────────────────────────────────────────

test("invariant 1: no action executes without an approved action", () => {
  const gate = new ApprovalGate();
  const result = gate.authorizeExecution({ id: "a1", type: "local.write" });
  assert.equal(result.allowed, false);
  assert.equal(result.reason, "no-approved-action");
});

test("invariant 2: approval token is single-use and replay is rejected", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms);
  const action: ProposedAction = { id: "a2", type: "local.write" };

  const token = gate.requestApproval(validRequest("a2", "local.write"));
  assert.ok(token, "a valid gated request should yield a single-use token");

  const first = gate.authorizeExecution(action, token);
  assert.equal(first.allowed, true);
  assert.equal(first.reason, "approved");

  const replay = gate.authorizeExecution(action, token);
  assert.equal(replay.allowed, false);
  assert.equal(replay.reason, "token-replay-rejected");
});

test("invariant 3: unknown or unclassifiable action fails closed", () => {
  const gate = new ApprovalGate();
  const action: ProposedAction = { id: "a3", type: "totally.unknown.kind" };
  assert.equal(classify(action), "unknown");
  assert.equal(gate.requestApproval(validRequest("a3", "totally.unknown.kind")), null);
  assert.equal(gate.authorizeExecution(action).allowed, false);
});

test("invariant 4: gate refuses token creation for an invalid approval request", () => {
  const gate = new ApprovalGate();
  assert.equal(gate.requestApproval({ actionId: "a4", actionType: "local.write" }), null);
  assert.equal(
    gate.requestApproval({ ...validRequest("a4b", "local.write"), apiKey: "PLACEHOLDER-NOT-A-REAL-SECRET" }),
    null,
  );
});

// ── Permission vs approval ──────────────────────────────────────────────────

test("permission/approval: permission alone does not authorize execution", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms);
  const result = gate.authorizeExecution({ id: "p7", type: "local.write" });
  assert.equal(result.allowed, false);
  assert.equal(result.reason, "no-approved-action");
});

test("permission/approval: approval alone does not authorize execution", () => {
  const perms = new PermissionRuntime();
  const gate = new ApprovalGate(undefined, perms);
  const token = gate.requestApproval(validRequest("p8", "local.write"));
  assert.ok(token, "approval is independent of permission");
  const result = gate.authorizeExecution({ id: "p8", type: "local.write" }, token);
  assert.equal(result.allowed, false);
  assert.ok(result.reason.startsWith("permission-denied"));
});

test("permission/approval: gate requires both permission and approval", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms);
  const token = gate.requestApproval(validRequest("p9", "local.write"));
  const result = gate.authorizeExecution({ id: "p9", type: "local.write" }, token);
  assert.equal(result.allowed, true);
  assert.equal(result.reason, "approved");
});

test("permission/approval: credential-sensitive and destructive fail closed without grant", () => {
  const gate = new ApprovalGate(undefined, new PermissionRuntime());
  const dToken = gate.requestApproval(validRequest("p10d", "destructive"));
  assert.ok(dToken, "destructive is gated and tokenizable");
  assert.equal(gate.authorizeExecution({ id: "p10d", type: "destructive" }, dToken).allowed, false);
  assert.equal(gate.requestApproval(validRequest("p10c", "credential")), null);
});

// ── Audit (S3) ──────────────────────────────────────────────────────────────

test("audit 5: token creation emits an audit event without the raw token value", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  const token = gate.requestApproval(validRequest("au5", "local.write"));
  assert.ok(token);
  const created = audit.records().find((e) => e.eventType === "approval-request" && e.status === "token-created");
  assert.ok(created, "token-created event recorded");
  assert.equal(created.result, "approved");
  assert.ok(!JSON.stringify(created).includes(token.tokenId), "audit record must not contain the raw token");
});

test("audit 6: an invalid approval request emits a rejected audit event", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  const { riskClass: _omit, ...invalid } = validRequest("au6", "local.write");
  void _omit;
  assert.equal(gate.requestApproval(invalid), null);
  const rejected = audit.records().find((e) => e.eventType === "approval-request" && e.status === "invalid-request");
  assert.ok(rejected);
  assert.equal(rejected.result, "rejected");
  assert.equal(rejected.correlationId, "corr-au6");
});

test("audit 7: forbidden and unknown approval requests emit rejected audit events", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  assert.equal(gate.requestApproval(validRequest("au7f", "credential")), null);
  assert.equal(gate.requestApproval(validRequest("au7u", "totally.unknown")), null);
  const statuses = audit.records()
    .filter((e) => e.eventType === "approval-request" && e.result === "rejected")
    .map((e) => e.status);
  assert.ok(statuses.includes("forbidden"));
  assert.ok(statuses.includes("unknown"));
});

test("audit 8: a successful execution authorization emits an approved/consumed audit event", () => {
  const audit = new AuditRuntime(() => 100);
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms, audit);
  const token = gate.requestApproval(validRequest("au8", "local.write"));
  assert.equal(gate.authorizeExecution({ id: "au8", type: "local.write" }, token).allowed, true);
  const ev = audit.records().find((e) => e.eventType === "execution-authorization" && e.status === "consumed");
  assert.ok(ev);
  assert.equal(ev.result, "approved");
});

test("audit 9: a token replay emits a rejected audit event", () => {
  const audit = new AuditRuntime(() => 100);
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms, audit);
  const token = gate.requestApproval(validRequest("au9", "local.write"));
  const action: ProposedAction = { id: "au9", type: "local.write" };
  gate.authorizeExecution(action, token);
  assert.equal(gate.authorizeExecution(action, token).allowed, false);
  const ev = audit.records().find((e) => e.eventType === "execution-authorization" && e.status === "token-replay-rejected");
  assert.ok(ev);
  assert.equal(ev.result, "rejected");
});

test("audit 10: a permission-denied authorization emits a rejected audit event", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, new PermissionRuntime(), audit);
  const token = gate.requestApproval(validRequest("au10", "local.write"));
  assert.equal(gate.authorizeExecution({ id: "au10", type: "local.write" }, token).allowed, false);
  const ev = audit.records().find((e) => e.eventType === "execution-authorization" && e.status === "permission-denied");
  assert.ok(ev);
  assert.equal(ev.result, "rejected");
});

test("audit 11: audit failure fails closed for a gated execution", () => {
  // An audit that throws only for execution-authorization events (token creation still audits).
  const failOnExec: Audit = {
    append(input) {
      if (input.eventType === "execution-authorization") throw new Error("audit down");
      return {
        auditEventId: "x", correlationId: input.correlationId, timestamp: 0,
        actorId: input.actorId, actorType: input.actorType, eventType: input.eventType,
        eventCategory: input.eventCategory, result: input.result, status: input.status,
        redactionStatus: "redacted", redactedSummary: "",
      };
    },
  };
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms, failOnExec);
  const token = gate.requestApproval(validRequest("au11", "local.write"));
  assert.ok(token, "approval auditing succeeds so a token is minted");
  const result = gate.authorizeExecution({ id: "au11", type: "local.write" }, token);
  assert.equal(result.allowed, false);
  assert.equal(result.reason, "audit-failure");
});
