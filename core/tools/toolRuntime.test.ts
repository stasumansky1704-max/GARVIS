// GARVIS — Tool Registry / Loader / Sandbox tests (M2 + H1 hardening)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Covers registration validation (H1: tools cannot self-declare safety; unknown/forbidden
// capabilities are rejected), the loader, sandbox redaction, and a shared-audit integration.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { ToolRegistry } from "./toolRegistry.ts";
import type { ToolDefinition } from "./toolRegistry.ts";
import { ToolLoader } from "./toolLoader.ts";
import { ToolSandbox } from "./toolSandbox.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";
import { ApprovalGate } from "../approval-gate/approvalGate.ts";
import { createRuntimeContext } from "../runtime/runtimeContext.ts";
import type { MemoryWriter } from "../memory/memoryRuntime.ts";

function mockTool(): ToolDefinition {
  return {
    metadata: {
      name: "mock.echo", version: "1", capability: "diagnostic.echo",
      actionType: "informational", description: "echoes its text input; no external call",
    },
    run(input) {
      return { ok: true, status: "ok", output: `echo:${String((input as { text?: string })?.text ?? "")}` };
    },
  };
}

test("tool registry M2: registers a tool and audits it", () => {
  const audit = new AuditRuntime(() => 1);
  const registry = new ToolRegistry(audit);
  registry.register(mockTool());
  assert.ok(registry.has("mock.echo"));
  assert.equal(registry.list().find((m) => m.name === "mock.echo")?.actionType, "informational");
  assert.ok(audit.records().some((e) => e.eventType === "tool-registered" && e.actionId === "mock.echo"));
  // One authority per capability — duplicate registration is rejected.
  assert.throws(() => registry.register(mockTool()), /duplicate-tool/);
});

test("tool registry H1: rejects an UNKNOWN action type (cannot self-declare a capability)", () => {
  const registry = new ToolRegistry(new AuditRuntime(() => 1));
  const rogue: ToolDefinition = {
    metadata: { name: "rogue", version: "1", capability: "???", actionType: "totally.unknown", description: "x" },
    run() { return { ok: true, status: "ran" }; },
  };
  assert.throws(() => registry.register(rogue), /unknown-action-type/);
  assert.equal(registry.has("rogue"), false);
});

test("tool registry H1: rejects a FORBIDDEN capability (e.g. credential)", () => {
  const registry = new ToolRegistry(new AuditRuntime(() => 1));
  const forbidden: ToolDefinition = {
    metadata: { name: "cred", version: "1", capability: "secrets", actionType: "credential", description: "x" },
    run() { return { ok: true, status: "ran" }; },
  };
  assert.throws(() => registry.register(forbidden), /forbidden-capability/);
  assert.equal(registry.has("cred"), false);
});

test("tool registry H1: a write capability cannot be registered as approval-free (derived, not declared)", () => {
  // The tool only declares actionType; "local.write" derives requiresApproval=true from policy,
  // so the sandbox will route it through the gate regardless of any author intent.
  const audit = new AuditRuntime(() => 1);
  const registry = new ToolRegistry(audit);
  const writeTool: ToolDefinition = {
    metadata: { name: "fs.write", version: "1", capability: "fs.write", actionType: "local.write", description: "x" },
    run() { return { ok: true, status: "written" }; },
  };
  registry.register(writeTool);
  // No grant, no token → the sandbox must deny (approval is derived, not opt-out).
  const sandbox = new ToolSandbox(registry, new PermissionRuntime(), new ApprovalGate(), audit);
  const r = sandbox.invoke({ tool: "fs.write", correlationId: "c", action: { id: "fs.write", type: "local.write" } });
  assert.equal(r.ok, false);
  assert.ok(r.status.includes("no-approved-action"));
});

test("tool loader M2: loads a static set of definitions into the registry", () => {
  const registry = new ToolRegistry(new AuditRuntime(() => 1));
  new ToolLoader(registry).load([mockTool()]);
  assert.ok(registry.has("mock.echo"));
});

test("tool sandbox M2: denies an unknown tool", () => {
  const audit = new AuditRuntime(() => 1);
  const sandbox = new ToolSandbox(new ToolRegistry(audit), new PermissionRuntime(), new ApprovalGate(), audit);
  const r = sandbox.invoke({ tool: "nope", correlationId: "c" });
  assert.equal(r.ok, false);
  assert.equal(r.status, "unknown-tool");
});

test("tool sandbox M2: a safe tool runs and its output is redacted before audit", () => {
  const audit = new AuditRuntime(() => 1);
  const registry = new ToolRegistry(audit);
  registry.register({
    metadata: {
      name: "mock.leak", version: "1", capability: "diagnostic.echo",
      actionType: "informational", description: "returns text containing a secret-shaped token",
    },
    run() { return { ok: true, status: "ok", output: "result token=SUPERSECRETVALUE done" }; },
  });
  const sandbox = new ToolSandbox(registry, new PermissionRuntime(), new ApprovalGate(), audit);
  const result = sandbox.invoke({ tool: "mock.leak", correlationId: "corr-y" });
  assert.equal(result.ok, true);
  assert.ok(!String(result.output).includes("SUPERSECRETVALUE"), "output redacted");
  assert.ok(!JSON.stringify(audit.records()).includes("SUPERSECRETVALUE"), "audit holds no raw secret");
});

test("tool sandbox M2: fails closed if the pre-execution audit cannot record (handler never runs)", () => {
  const registry = new ToolRegistry(new AuditRuntime(() => 1));
  let ran = false;
  registry.register({
    metadata: { name: "mock.run", version: "1", capability: "diagnostic.echo", actionType: "informational", description: "x" },
    run() { ran = true; return { ok: true, status: "ok" }; },
  });
  // An audit that throws on the "invoking" pre-execution event.
  const failOnInvoke = {
    append(i: { status: string }) { if (i.status === "invoking") throw new Error("audit down"); },
  };
  const sandbox = new ToolSandbox(registry, new PermissionRuntime(), new ApprovalGate(), failOnInvoke);
  const r = sandbox.invoke({ tool: "mock.run", correlationId: "c" });
  assert.equal(r.ok, false);
  assert.equal(r.status, "audit-failure");
  assert.equal(ran, false, "no execution when the invocation cannot be audited");
});

test("runtime context M2: memory/checkpoint/tool-registry events share one audit log", () => {
  let writer: MemoryWriter | undefined;
  const ctx = createRuntimeContext({ now: () => 5, correlationId: "corr-ctx", onMemoryWriter: (w) => { writer = w; } });
  writer!.write({ key: "k", value: "v", source: "tool:reader", correlationId: "corr-ctx" });
  ctx.checkpoints.create("c1", ctx.state.snapshot(), "corr-ctx");
  ctx.tools.register(mockTool(), "corr-ctx");

  const types = new Set(ctx.audit.records().map((e) => e.eventType));
  assert.ok(types.has("memory-write"));
  assert.ok(types.has("checkpoint-created"));
  assert.ok(types.has("tool-registered"));
});
