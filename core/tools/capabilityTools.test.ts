// GARVIS — Capability tool tests (M3)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Proves the safe/mock capability layer routes through Permission → Approval → Audit, performs
// no real external side effects, and redacts results.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { createRuntimeContext } from "../runtime/runtimeContext.ts";
import { VirtualFileSystem } from "./virtualFileSystem.ts";
import { loadCapabilityTools } from "./capabilityTools.ts";
import { mockBrowserTool, mockGithubTool, mockDockerTool } from "./mockExternalTools.ts";
import { SafeCommandRunner } from "./safeCommandRunner.ts";
import type { MemoryWriter } from "../memory/memoryRuntime.ts";

function setup() {
  let writer: MemoryWriter | undefined;
  const ctx = createRuntimeContext({
    now: () => 1, correlationId: "corr-m3", onMemoryWriter: (w) => { writer = w; },
  });
  const vfs = new VirtualFileSystem({
    "project/status.md": "build green; 2 PRs open",
    "secrets/note.txt": "apiKey=SUPERSECRETVALUE",
  });
  loadCapabilityTools(ctx.tools, { vfs });
  return { ctx, vfs, writer: writer! };
}

function approvalRequest(actionId: string) {
  return {
    actionId, actionType: "local.write", riskClass: "gated",
    redactionStatus: "redacted", correlationId: "corr-m3",
  };
}

test("M3: safe read requires local:read", () => {
  const { ctx } = setup();
  let r = ctx.sandbox.invoke({ tool: "fs.readTextFile", input: { path: "project/status.md" }, correlationId: "corr-m3" });
  assert.equal(r.ok, false);
  assert.ok(r.status.startsWith("permission-denied"), "denied without local:read");

  ctx.permissions.grant("local:read");
  r = ctx.sandbox.invoke({ tool: "fs.readTextFile", input: { path: "project/status.md" }, correlationId: "corr-m3" });
  assert.equal(r.ok, true);
  assert.equal(r.output, "build green; 2 PRs open");
});

test("M3: safe write requires local:write + approval", () => {
  const { ctx, vfs } = setup();
  // Approval token but no local:write grant → permission-denied (approval ≠ permission).
  const token1 = ctx.gate.requestApproval(approvalRequest("write-brief"));
  assert.ok(token1);
  let r = ctx.sandbox.invoke({
    tool: "fs.writeTextFileApproved", input: { path: "out/brief.md", content: "hi" },
    correlationId: "corr-m3", action: { id: "write-brief", type: "local.write" }, token: token1,
  });
  assert.equal(r.ok, false);
  assert.equal(vfs.exists("out/brief.md"), false, "no write without permission");

  // local:write granted + a fresh approval token → write succeeds.
  ctx.permissions.grant("local:write");
  const token2 = ctx.gate.requestApproval(approvalRequest("write-brief"));
  r = ctx.sandbox.invoke({
    tool: "fs.writeTextFileApproved", input: { path: "out/brief.md", content: "hi" },
    correlationId: "corr-m3", action: { id: "write-brief", type: "local.write" }, token: token2,
  });
  assert.equal(r.ok, true);
  assert.equal(vfs.readFile("out/brief.md"), "hi");
});

test("M3: write without approval fails closed", () => {
  const { ctx, vfs } = setup();
  ctx.permissions.grant("local:write"); // permission present, but NO approval token
  const r = ctx.sandbox.invoke({
    tool: "fs.writeTextFileApproved", input: { path: "out/x.md", content: "y" },
    correlationId: "corr-m3", action: { id: "write-x", type: "local.write" },
  });
  assert.equal(r.ok, false);
  assert.ok(r.status.includes("no-approved-action"));
  assert.equal(vfs.exists("out/x.md"), false);
});

test("M3: write preview creates no side effect", () => {
  const { ctx, vfs } = setup();
  const r = ctx.sandbox.invoke({
    tool: "fs.writeTextFilePreview", input: { path: "out/brief.md", content: "draft" }, correlationId: "corr-m3",
  });
  assert.equal(r.ok, true);
  assert.equal(r.status, "preview");
  assert.equal(vfs.exists("out/brief.md"), false, "preview must not create the file");
});

test("M3: mock browser performs no network call", () => {
  let called = false;
  const spy = (() => { called = true; throw new Error("forbidden"); }) as () => never;
  const r = mockBrowserTool(spy).run!({ url: "https://example.com" }, { correlationId: "c" });
  assert.equal(called, false);
  assert.ok(String(r.output).startsWith("mock-browser:"));
});

test("M3: mock GitHub performs no network call", () => {
  let called = false;
  const spy = (() => { called = true; throw new Error("forbidden"); }) as () => never;
  const r = mockGithubTool(spy).run!({ repo: "org/repo" }, { correlationId: "c" });
  assert.equal(called, false);
  assert.ok(String(r.output).startsWith("mock-github:"));
});

test("M3: mock Docker performs no Docker call", () => {
  let called = false;
  const spy = (() => { called = true; throw new Error("forbidden"); }) as () => never;
  const r = mockDockerTool(spy).run!({ image: "node:24" }, { correlationId: "c" });
  assert.equal(called, false);
  assert.ok(String(r.output).startsWith("mock-docker:"));
});

test("M3: safe command runner refuses real command execution", () => {
  let executed = false;
  const runner = new SafeCommandRunner({
    realExec: (() => { executed = true; throw new Error("forbidden"); }) as () => never,
  });
  const r = runner.run("rm -rf /");
  assert.equal(r.ok, false);
  assert.ok(r.status.startsWith("blocked"));
  assert.equal(executed, false, "no real command is ever executed");

  // Only explicitly mocked commands return a canned result.
  const mocked = new SafeCommandRunner({ mocks: { "echo hi": { ok: true, status: "mock", output: "hi" } } });
  assert.equal(mocked.run("echo hi").output, "hi");
  assert.equal(mocked.run("anything-else").ok, false);
});

test("M3: tool result is redacted before audit and memory (no raw secrets)", () => {
  const { ctx, writer } = setup();
  ctx.permissions.grant("local:read");
  const r = ctx.sandbox.invoke({ tool: "fs.readTextFile", input: { path: "secrets/note.txt" }, correlationId: "corr-m3" });
  assert.equal(r.ok, true);
  assert.ok(!String(r.output).includes("SUPERSECRETVALUE"), "sandbox output redacted");
  assert.ok(!JSON.stringify(ctx.audit.records()).includes("SUPERSECRETVALUE"), "audit holds no raw secret");

  writer.write({ key: "scan.note", value: String(r.output ?? ""), source: "tool:fs.readTextFile", correlationId: "corr-m3" });
  assert.ok(!JSON.stringify(ctx.memory.export()).includes("SUPERSECRETVALUE"), "memory holds no raw secret");
});

test("M3/M2: a read tool fails closed when its invocation cannot be audited", () => {
  // A custom context whose audit throws on the pre-execution "invoking" event for reads.
  const failOnInvoke = {
    append(i: { status: string }) { if (i.status === "invoking") throw new Error("audit down"); },
  };
  const ctx = createRuntimeContext({ now: () => 1, correlationId: "corr-m3", audit: failOnInvoke });
  const vfs = new VirtualFileSystem({ "project/status.md": "build green" });
  loadCapabilityTools(ctx.tools, { vfs });
  ctx.permissions.grant("local:read");
  const r = ctx.sandbox.invoke({ tool: "fs.readTextFile", input: { path: "project/status.md" }, correlationId: "corr-m3" });
  assert.equal(r.ok, false);
  assert.equal(r.status, "audit-failure", "read does not execute if it cannot be audited");
});
