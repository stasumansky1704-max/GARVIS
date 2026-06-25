// GARVIS — Agent Runtime tests (M4)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Proves agents are propose-only: they cannot execute, approve, grant, or write, and the runtime
// routes proposals through the real Gate/Permission/Tool pipeline exactly once (no auto-retry).

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { createRuntimeContext } from "../runtime/runtimeContext.ts";
import { VirtualFileSystem } from "../tools/virtualFileSystem.ts";
import { loadCapabilityTools } from "../tools/capabilityTools.ts";
import type { MemoryWriter } from "../memory/memoryRuntime.ts";
import { PlanningAgent } from "./planningAgent.ts";
import { SummaryAgent } from "./summaryAgent.ts";
import { AgentRegistry } from "./agentRegistry.ts";
import { AgentRuntime } from "./agentRuntime.ts";
import type { AgentProposal } from "./agentTypes.ts";

function setup() {
  let writer: MemoryWriter | undefined;
  const ctx = createRuntimeContext({
    now: () => 1, correlationId: "corr-m4", onMemoryWriter: (w) => { writer = w; },
  });
  const vfs = new VirtualFileSystem({ "project/status.md": "build green; 1 PR open" });
  loadCapabilityTools(ctx.tools, { vfs });
  return { ctx, vfs, runtime: new AgentRuntime(ctx), writer: writer! };
}

function writeProposal(): AgentProposal {
  return {
    kind: "tool-call", proposedBy: "agent:planner", correlationId: "corr-m4", confidence: 1.0,
    rationale: "write the brief", tool: "fs.writeTextFileApproved",
    input: { path: "out/brief.md", content: "hi" }, actionType: "local.write",
  };
}

test("M4: an agent cannot execute a tool directly", () => {
  const { ctx, vfs } = setup();
  const agent = new PlanningAgent();
  const proposals = agent.propose({ role: "user", content: "daily brief", correlationId: "corr-m4" });
  assert.ok(Array.isArray(proposals));
  // The agent exposes no execution capability and holds no pipeline references.
  assert.equal(typeof (agent as Record<string, unknown>).invoke, "undefined");
  assert.equal(typeof (agent as Record<string, unknown>).execute, "undefined");
  // Merely proposing executed nothing: no tool ran, no fs change.
  assert.equal(ctx.audit.records().some((e) => e.eventType === "tool-invocation"), false);
  assert.equal(vfs.list().length, 1);
});

test("M4: an agent proposal does not execute a side effect", () => {
  const { vfs, runtime } = setup();
  // Even routed, a write proposal without a human approval token is denied — nothing is written.
  const r = runtime.route(writeProposal());
  assert.equal(r.ok, false);
  assert.equal(vfs.exists("out/brief.md"), false);
});

test("M4: an agent cannot approve its own action", () => {
  const { ctx } = setup();
  const token = ctx.gate.requestApproval(
    { actionId: "agent-act", actionType: "local.write", riskClass: "gated", redactionStatus: "redacted", correlationId: "corr-m4" },
    { requestedBy: { id: "agent:planner", type: "agent" }, approvedBy: { id: "agent:planner", type: "agent" } },
  );
  assert.equal(token, null, "an agent approving its own action is rejected");
});

test("M4: an agent cannot grant permission", () => {
  const { ctx, runtime } = setup();
  const agent = new PlanningAgent();
  assert.equal(typeof (agent as Record<string, unknown>).grant, "undefined");
  // Routing a write proposal does not grant the agent any permission.
  runtime.route(writeProposal());
  assert.equal(ctx.permissions.check({ scope: "local:write" }).allowed, false);
});

test("M4/H2: an agent cannot write durable memory directly (read-only facade, no forgeable writer)", () => {
  const { ctx } = setup();
  // The memory the agent layer receives exposes no write() at all.
  assert.equal(typeof (ctx.memory as Record<string, unknown>).write, "undefined");
  // And the single writer was already claimed by the composition root — it cannot be re-claimed.
  assert.throws(
    () => (ctx.memory as unknown as { claimWriter(): unknown }).claimWriter(),
    /writer-already-claimed/,
  );
});

test("M4: the planning agent emits proposals only", () => {
  const agent = new PlanningAgent();
  const proposals = agent.propose({ role: "user", content: "goal", correlationId: "corr-m4" });
  assert.ok(proposals.length >= 1);
  assert.ok(proposals.every((p) => p.kind === "tool-call" || p.kind === "memory-read"));
  assert.equal(typeof (agent as Record<string, unknown>).summarize, "undefined");
});

test("M4: the summary agent emits a result only (redacted)", () => {
  const agent = new SummaryAgent();
  const result = agent.summarize({ role: "user", content: "shipped token=SECRET\nmore", correlationId: "corr-m4" });
  assert.equal(result.producedBy, "agent:summary");
  assert.ok(result.summary.length > 0);
  assert.ok(!result.summary.includes("SECRET"), "agent result is redacted");
  assert.equal(typeof (agent as Record<string, unknown>).propose, "undefined");
});

test("M4: an agent-selected tool call routes through Tool Registry / Permission / Gate", () => {
  const { ctx, runtime } = setup();
  const proposal: AgentProposal = {
    kind: "tool-call", proposedBy: "agent:planner", correlationId: "corr-m4", confidence: 0.8,
    rationale: "read status", tool: "project.read", input: {}, actionType: "local.read",
  };
  // No permission → routed but denied at the permission boundary.
  let r = runtime.route(proposal);
  assert.equal(r.ok, false);
  assert.ok(r.status.startsWith("permission-denied"));

  // Grant local:read → the call routes through the registry+sandbox and executes.
  ctx.permissions.grant("local:read");
  r = runtime.route(proposal);
  assert.equal(r.ok, true);
  assert.ok(String(r.output).includes("build green"));
  assert.ok(ctx.audit.records().some((e) => e.eventType === "tool-invocation" && e.actionId === "project.read"));
});

test("M4: an agent memory-read proposal returns a redacted value (agent never writes)", () => {
  const { ctx, runtime, writer } = setup();
  // The memory authority (not the agent) seeds a prior brief via the writer capability.
  writer.write(
    { key: "project.lastBrief", value: "yesterday shipped token=SECRET", source: "workflow", correlationId: "corr-m4" },
  );
  const proposal: AgentProposal = {
    kind: "memory-read", proposedBy: "agent:planner", correlationId: "corr-m4", confidence: 0.5,
    rationale: "recall", memoryKey: "project.lastBrief",
  };
  const r = runtime.route(proposal);
  assert.equal(r.ok, true);
  assert.ok(!String(r.output).includes("SECRET"), "memory read returns the redacted value");
});

test("M4: a denied agent action is not retried automatically", () => {
  const { ctx, runtime, vfs } = setup();
  ctx.permissions.grant("local:write"); // permission present, but NO approval token
  const r = runtime.route(writeProposal());
  assert.equal(r.ok, false);
  assert.equal(vfs.exists("out/brief.md"), false);
  // Routed exactly once — there is no automatic retry loop.
  const execEvents = ctx.audit.records().filter(
    (e) => e.eventType === "execution-authorization" && e.actionId === "fs.writeTextFileApproved",
  );
  assert.equal(execEvents.length, 1);
});

test("M4: the agent registry registers agents and audits registration", () => {
  const { ctx } = setup();
  const registry = new AgentRegistry(ctx.audit);
  registry.register(new PlanningAgent());
  registry.register(new SummaryAgent());
  assert.ok(registry.has("agent:planner"));
  assert.equal(registry.list().length, 2);
  assert.ok(ctx.audit.records().some((e) => e.eventType === "agent-registered"));
  assert.throws(() => registry.register(new PlanningAgent()), /duplicate-agent/);
});
