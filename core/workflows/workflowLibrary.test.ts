// GARVIS — Workflow Library + Project Status Reader tests
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Covers manifest registration/validation/categorization and the first real read-only workflow
// (Project Status Reader) end-to-end through the existing runtime path.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { createRuntimeContext } from "../runtime/runtimeContext.ts";
import { VirtualFileSystem } from "../tools/virtualFileSystem.ts";
import { loadCapabilityTools } from "../tools/capabilityTools.ts";
import { WorkflowLibrary } from "./workflowLibrary.ts";
import type { WorkflowManifest } from "./workflowManifest.ts";
import {
  projectStatusReaderManifest, projectStatusReaderWorkflow, runProjectStatusReader,
} from "./projectStatusReaderWorkflow.ts";
import { projectDailyBriefManifest } from "./projectDailyBriefWorkflow.ts";

function harness(statusText = "build green; 2 PRs open") {
  const ctx = createRuntimeContext({ now: () => 1, correlationId: "corr-sr" });
  const vfs = new VirtualFileSystem({ "project/status.md": statusText });
  loadCapabilityTools(ctx.tools, { vfs });
  return { ctx, vfs };
}

// ── Workflow Library / Catalog ───────────────────────────────────────────────

test("WF-LIB 1: registers a valid workflow manifest", () => {
  const lib = new WorkflowLibrary();
  const entry = lib.register(projectStatusReaderManifest(), projectStatusReaderWorkflow());
  assert.equal(entry.manifest.workflowId, "project-status-reader");
  assert.ok(lib.has("project-status-reader"));
  assert.equal(lib.list().length, 1);
});

test("WF-LIB 2: rejects a duplicate workflow id", () => {
  const lib = new WorkflowLibrary();
  lib.register(projectStatusReaderManifest(), projectStatusReaderWorkflow());
  assert.throws(() => lib.register(projectStatusReaderManifest()), /duplicate-workflow-id/);
});

test("WF-LIB 3: rejects a malformed workflow manifest", () => {
  const lib = new WorkflowLibrary();
  // Missing required field.
  const missing = { ...projectStatusReaderManifest(), workflowId: "" } as unknown as WorkflowManifest;
  assert.throws(() => lib.register(missing), /malformed-manifest/);
  // Invalid step shape (unknown effect).
  const badStep = {
    ...projectStatusReaderManifest(),
    steps: [{ name: "bad", effect: "explode" }],
  } as unknown as WorkflowManifest;
  assert.throws(() => lib.register(badStep), /malformed-manifest/);
});

test("WF-LIB 4: lists workflows by category", () => {
  const lib = new WorkflowLibrary();
  lib.register(projectStatusReaderManifest(), projectStatusReaderWorkflow());
  lib.register(projectDailyBriefManifest());
  assert.equal(lib.byCategory().get("project")?.length, 2);
  assert.equal(lib.listByCategory("project").length, 2);
  assert.equal(lib.listByCategory("nope").length, 0);
});

test("WF-LIB: runs a read-only workflow to completion via the runner", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  const lib = new WorkflowLibrary();
  lib.register(projectStatusReaderManifest(), projectStatusReaderWorkflow());
  const state = lib.run("project-status-reader", ctx, "corr-lib");
  assert.equal(state.status, "completed");
});

// ── Project Status Reader ────────────────────────────────────────────────────

test("PSR 5: is registered as read-only", () => {
  const lib = new WorkflowLibrary();
  lib.register(projectStatusReaderManifest(), projectStatusReaderWorkflow());
  assert.equal(lib.policyClassOf("project-status-reader"), "read-only");
});

test("PSR 6: requires local:read permission and no approval", () => {
  const m = projectStatusReaderManifest();
  assert.ok(m.requiredPermissions.includes("local:read"));
  assert.equal(m.requiresApproval, false);
});

test("PSR 7: fails closed without local:read permission", () => {
  const { ctx } = harness();
  const result = runProjectStatusReader(ctx, "corr-sr"); // no grant
  assert.equal(result.ok, false);
  assert.ok(result.status.startsWith("failed"));
});

test("PSR 8: runs successfully with local:read permission", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  const result = runProjectStatusReader(ctx, "corr-sr");
  assert.equal(result.ok, true);
  assert.ok(String(result.summary).includes("build green"));
});

test("PSR 9: emits audit events", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  runProjectStatusReader(ctx, "corr-sr");
  const e = ctx.audit.records();
  assert.ok(e.some((x) => x.eventType === "tool-invocation" && x.actionId === "project.read"));
  assert.ok(e.some((x) => x.eventType === "workflow"));
});

test("PSR 10: output is redacted", () => {
  const { ctx } = harness("build green; token=SUPERSECRETVALUE in logs");
  ctx.permissions.grant("local:read");
  const result = runProjectStatusReader(ctx, "corr-sr");
  assert.equal(result.ok, true);
  assert.ok(!String(result.summary).includes("SUPERSECRETVALUE"), "summary redacted");
  assert.ok(!JSON.stringify(ctx.audit.records()).includes("SUPERSECRETVALUE"), "audit holds no raw secret");
});

test("PSR 11: does not write files", () => {
  const { ctx, vfs } = harness();
  ctx.permissions.grant("local:read");
  const before = vfs.list().length;
  runProjectStatusReader(ctx, "corr-sr");
  assert.equal(vfs.list().length, before, "no files created or written");
});

test("PSR 12: does not write durable memory", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  runProjectStatusReader(ctx, "corr-sr");
  assert.equal(ctx.memory.export().length, 0, "no durable memory written");
});

test("PSR 13: does not create an approval token", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  runProjectStatusReader(ctx, "corr-sr");
  const e = ctx.audit.records();
  assert.equal(e.some((x) => x.eventType === "execution-authorization"), false, "no gate authorization");
  assert.equal(e.some((x) => x.eventType === "approval-request" && x.status === "token-created"), false, "no token minted");
});

test("PSR 14: does not call network (no external/mock tools invoked)", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  runProjectStatusReader(ctx, "corr-sr");
  const toolEvents = ctx.audit.records().filter((x) => x.eventType === "tool-invocation");
  assert.ok(toolEvents.length > 0);
  assert.ok(toolEvents.every((x) => x.actionId === "project.read"), "only the local read tool ran");
});

test("PSR 15: does not execute commands", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  runProjectStatusReader(ctx, "corr-sr");
  const ran = ctx.audit.records().filter((x) => x.eventType === "tool-invocation").map((x) => x.actionId);
  assert.equal(ran.includes("docker.mock"), false);
  assert.equal(ran.includes("command.safeRunner"), false);
});

test("PSR 16: uses the Tool Registry / Tool Sandbox path", () => {
  const { ctx } = harness();
  ctx.permissions.grant("local:read");
  assert.ok(ctx.tools.has("project.read"), "tool is in the registry");
  runProjectStatusReader(ctx, "corr-sr");
  // Proof it ran through the sandbox: a redacted tool-invocation audit event exists.
  assert.ok(ctx.audit.records().some((x) => x.eventType === "tool-invocation" && x.actionId === "project.read"));
});

// ── Project Daily Brief (registered as gated) ────────────────────────────────

test("PSR 17: Project Daily Brief is registered and remains gated", () => {
  const lib = new WorkflowLibrary();
  lib.register(projectDailyBriefManifest());
  assert.equal(lib.policyClassOf("project-daily-brief"), "gated");
  assert.equal(lib.get("project-daily-brief")?.manifest.requiresApproval, true);
});
