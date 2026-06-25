// GARVIS — Approval Gate invariant tests (S0–S4)
//
// Zero-dependency Node built-in test runner with native TypeScript type-stripping.
// Run with: `npm test`.
//
// Invariants 1–4 and the permission/approval split are preserved; the S3 additions prove
// every outcome is audited (without raw tokens/secrets) and that audit failure fails closed.
// The S4 additions close the gate invariant suite: no self-approval, human-only approval
// authority, never-auto enforcement, and forbidden-is-rejected-never-queued.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { ApprovalGate, classify } from "./approvalGate.ts";
import type { ProposedAction, ApprovalDecision } from "./approvalGate.ts";
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

// A valid human-in-the-loop approval decision: an agent proposes, a (distinct) human approves.
function humanApproval(): ApprovalDecision {
  return { requestedBy: { id: "agent-1", type: "agent" }, approvedBy: { id: "human-1", type: "human" } };
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
  // destructive is never-auto: with an explicit human approval it is tokenizable, but without a
  // permission grant execution still fails closed (permission ≠ approval).
  const dToken = gate.requestApproval(validRequest("p10d", "destructive"), humanApproval());
  assert.ok(dToken, "destructive is tokenizable with explicit human approval");
  assert.equal(gate.authorizeExecution({ id: "p10d", type: "destructive" }, dToken).allowed, false);
  // credential is Forbidden: never tokenized, even with a human approver.
  assert.equal(gate.requestApproval(validRequest("p10c", "credential"), humanApproval()), null);
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

// ── Gate invariant suite (S4): no self-approval, human-only authority, never-auto, forbidden ──

test("gate invariant 1: a requester cannot approve its own action (self-approval rejected)", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  const decision: ApprovalDecision = {
    requestedBy: { id: "human-1", type: "human" },
    approvedBy: { id: "human-1", type: "human" }, // same identity → self-approval
  };
  assert.equal(gate.requestApproval(validRequest("s1", "local.write"), decision), null);
  const ev = audit.records().find((e) => e.eventType === "approval-request" && e.actionId === "s1");
  assert.ok(ev);
  assert.equal(ev.result, "rejected");
  assert.equal(ev.status, "self-approval-rejected");
});

test("gate invariant 2: an agent actor cannot approve its own action", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  const decision: ApprovalDecision = {
    requestedBy: { id: "agent-7", type: "agent" },
    approvedBy: { id: "agent-7", type: "agent" },
  };
  assert.equal(gate.requestApproval(validRequest("s2", "local.write"), decision), null);
  const ev = audit.records().find((e) => e.eventType === "approval-request" && e.actionId === "s2");
  assert.ok(ev);
  assert.equal(ev.result, "rejected");
  assert.equal(ev.status, "non-human-approver-rejected"); // agents may propose, never approve
});

test("gate invariant 3: a tool actor cannot approve its own action", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  const decision: ApprovalDecision = {
    requestedBy: { id: "tool-3", type: "tool" },
    approvedBy: { id: "tool-3", type: "tool" },
  };
  assert.equal(gate.requestApproval(validRequest("s3", "local.write"), decision), null);
  const ev = audit.records().find((e) => e.eventType === "approval-request" && e.actionId === "s3");
  assert.ok(ev);
  assert.equal(ev.status, "non-human-approver-rejected");
});

test("gate invariant 4: a system actor cannot approve its own action", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  const decision: ApprovalDecision = {
    requestedBy: { id: "sys-0", type: "system" },
    approvedBy: { id: "sys-0", type: "system" },
  };
  assert.equal(gate.requestApproval(validRequest("s4", "local.write"), decision), null);
  const ev = audit.records().find((e) => e.eventType === "approval-request" && e.actionId === "s4");
  assert.ok(ev);
  assert.equal(ev.status, "non-human-approver-rejected");
});

test("gate invariant 5: a human actor can approve a gated action for another requester", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  const token = gate.requestApproval(validRequest("s5", "local.write"), humanApproval());
  assert.ok(token, "a distinct human approver yields a token");
  const ev = audit.records().find(
    (e) => e.eventType === "approval-request" && e.status === "token-created" && e.actionId === "s5",
  );
  assert.ok(ev);
  assert.equal(ev.result, "approved");
  assert.ok(ev.redactedSummary.includes("approved by human-1"), "audit records the approver");
});

test("gate invariant 6: a credential-sensitive action is never auto-approved", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  assert.equal(gate.requestApproval(validRequest("s6", "credential")), null, "no token without explicit human approval");
  const created = audit.records().find((e) => e.status === "token-created" && e.actionId === "s6");
  assert.equal(created, undefined, "credential-sensitive is never tokenized");
});

test("gate invariant 7: a destructive action is never auto-approved", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  assert.equal(gate.requestApproval(validRequest("s7", "destructive")), null);
  const ev = audit.records().find((e) => e.eventType === "approval-request" && e.actionId === "s7");
  assert.ok(ev);
  assert.equal(ev.result, "rejected");
  assert.equal(ev.status, "requires-human-approval");
});

test("gate invariant 8: an external-write action is never auto-approved", () => {
  const gate = new ApprovalGate();
  assert.equal(gate.requestApproval(validRequest("s8", "external.write")), null, "no auto token");
  // never-AUTO, not never: an explicit human approval makes it tokenizable.
  assert.ok(gate.requestApproval(validRequest("s8b", "external.write"), humanApproval()));
});

test("gate invariant 9: a command-execution action is never auto-approved", () => {
  const gate = new ApprovalGate();
  assert.equal(gate.requestApproval(validRequest("s9", "execution.command")), null, "no auto token");
  assert.ok(gate.requestApproval(validRequest("s9b", "execution.command"), humanApproval()));
});

test("gate invariant 10: a forbidden action returns no token", () => {
  const gate = new ApprovalGate();
  assert.equal(gate.requestApproval(validRequest("s10", "credential")), null);
});

test("gate invariant 11: a forbidden action is audited as rejected", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  gate.requestApproval(validRequest("s11", "credential"));
  const ev = audit.records().find((e) => e.eventType === "approval-request" && e.actionId === "s11");
  assert.ok(ev);
  assert.equal(ev.result, "rejected");
  assert.equal(ev.status, "forbidden");
});

test("gate invariant 12: a forbidden action cannot enter a pending queue or token set", () => {
  const audit = new AuditRuntime(() => 100);
  const gate = new ApprovalGate(undefined, undefined, audit);
  // Even with a valid human approver, Forbidden overrides the request (§16).
  assert.equal(gate.requestApproval(validRequest("s12", "credential"), humanApproval()), null);
  // It was never tokenized/queued — no token-created event exists for the action.
  const created = audit.records().find((e) => e.status === "token-created" && e.actionId === "s12");
  assert.equal(created, undefined);
  // And there is no live token to authorize against; a forged handle still fails closed.
  const forged = { tokenId: "tok-forged", actionId: "s12" };
  assert.equal(gate.authorizeExecution({ id: "s12", type: "credential" }, forged).allowed, false);
});

test("gate invariant 13: a human-approved gated action with permission still executes once", () => {
  const perms = new PermissionRuntime();
  perms.grant("destructive");
  const gate = new ApprovalGate(undefined, perms);
  const token = gate.requestApproval(validRequest("s13", "destructive"), humanApproval());
  assert.ok(token, "never-auto action is approvable with explicit human approval");
  const result = gate.authorizeExecution({ id: "s13", type: "destructive" }, token);
  assert.equal(result.allowed, true);
  assert.equal(result.reason, "approved");
});

test("gate invariant 14: a human-approved token replay is still rejected (single-use)", () => {
  const perms = new PermissionRuntime();
  perms.grant("destructive");
  const gate = new ApprovalGate(undefined, perms);
  const token = gate.requestApproval(validRequest("s14", "destructive"), humanApproval());
  const action: ProposedAction = { id: "s14", type: "destructive" };
  assert.equal(gate.authorizeExecution(action, token).allowed, true);
  const replay = gate.authorizeExecution(action, token);
  assert.equal(replay.allowed, false);
  assert.equal(replay.reason, "token-replay-rejected");
});

// ── H3: token binding / downgrade defense ────────────────────────────────────

test("gate H3: a token cannot be downgraded to a lower-risk action type at execution", () => {
  const perms = new PermissionRuntime(); // NO grants
  const gate = new ApprovalGate(undefined, perms);
  const token = gate.requestApproval(validRequest("dg", "local.write"));
  assert.ok(token, "local.write is auto-tokenizable");

  // Present the approved token with a downgraded type ("informational" has no required scope) to
  // try to dodge the permission check. The gate binds to the APPROVED type and rejects.
  const downgrade = gate.authorizeExecution({ id: "dg", type: "informational" }, token);
  assert.equal(downgrade.allowed, false);
  assert.equal(downgrade.reason, "token-action-type-mismatch");

  // The mismatch did not consume the token; the correct type still requires the APPROVED scope
  // (local:write), which was never granted — proving scope comes from the approval, not the caller.
  const correct = gate.authorizeExecution({ id: "dg", type: "local.write" }, token);
  assert.equal(correct.allowed, false);
  assert.ok(correct.reason.startsWith("permission-denied"), "scope is derived from the approved action");
});

test("gate H3: a bound token authorizes once when type matches and the approved scope is granted", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  const gate = new ApprovalGate(undefined, perms);
  const token = gate.requestApproval(validRequest("ok", "local.write"));
  const result = gate.authorizeExecution({ id: "ok", type: "local.write" }, token);
  assert.equal(result.allowed, true);
  assert.equal(result.reason, "approved");
});
