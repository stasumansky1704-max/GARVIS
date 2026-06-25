// GARVIS — Workflow Runtime tests (M5)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Proves the workflow coordinates only: it checkpoints per step, pauses for human approval,
// cannot write without approval/permission, resumes to completion, fails closed (preserving the
// checkpoint, no auto-retry), and never bypasses the registry/gate/permission runtime.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { createRuntimeContext } from "../runtime/runtimeContext.ts";
import type { RuntimeContext } from "../runtime/runtimeContext.ts";
import { VirtualFileSystem } from "../tools/virtualFileSystem.ts";
import { loadCapabilityTools } from "../tools/capabilityTools.ts";
import { AgentRuntime } from "../agents/agentRuntime.ts";
import { PlanningAgent } from "../agents/planningAgent.ts";
import { SummaryAgent } from "../agents/summaryAgent.ts";
import { WorkflowRunner } from "./workflowRunner.ts";
import { projectDailyBriefWorkflow } from "./projectDailyBriefWorkflow.ts";
import type { ApprovalRequestData } from "./workflowTypes.ts";

function harness(projectStatus = "build green; 2 PRs open") {
  const ctx = createRuntimeContext({ now: () => 1, correlationId: "corr-wf" });
  const vfs = new VirtualFileSystem({ "project/status.md": projectStatus });
  loadCapabilityTools(ctx.tools, { vfs });
  const runner = new WorkflowRunner(ctx, new AgentRuntime(ctx));
  const def = projectDailyBriefWorkflow({ summarizer: new SummaryAgent(), planner: new PlanningAgent() });
  return { ctx, vfs, runner, def };
}

// A human approving out of band: grants local:write and mints a token via the Gate.
function humanApprove(ctx: RuntimeContext, pending: ApprovalRequestData, opts: { grant?: boolean } = {}) {
  if (opts.grant !== false) ctx.permissions.grant("local:write");
  return ctx.gate.requestApproval(
    { actionId: pending.actionId, actionType: "local.write", riskClass: "gated", redactionStatus: "redacted", correlationId: pending.correlationId },
    { requestedBy: { id: "agent:planner", type: "agent" }, approvedBy: { id: "human-owner", type: "human" } },
  );
}

test("M5: workflow starts and checkpoints the first step", () => {
  const { ctx, runner, def } = harness();
  ctx.permissions.grant("local:read");
  const state = runner.start(def, "corr-wf");
  assert.ok(ctx.checkpoints.list().some((c) => c.label.includes(":start")), "first-step checkpoint exists");
  assert.equal(state.status, "paused-for-approval");
});

test("M5: workflow pauses for approval before the write", () => {
  const { ctx, vfs, runner, def } = harness();
  ctx.permissions.grant("local:read");
  const state = runner.start(def, "corr-wf");
  assert.equal(state.status, "paused-for-approval");
  assert.equal(state.pendingApproval?.actionType, "local.write");
  assert.equal(vfs.exists("out/daily-brief.md"), false, "nothing written before approval");
});

test("M5: workflow cannot write without approval", () => {
  const { ctx, vfs, runner, def } = harness();
  ctx.permissions.grant("local:read");
  let state = runner.start(def, "corr-wf");
  state = runner.resume(def, state, undefined); // resume with NO token
  assert.equal(state.status, "failed");
  assert.equal(vfs.exists("out/daily-brief.md"), false);
});

test("M5: workflow resumes after approval and completes after the approved safe write", () => {
  const { ctx, vfs, runner, def } = harness();
  ctx.permissions.grant("local:read");
  let state = runner.start(def, "corr-wf");
  assert.equal(state.status, "paused-for-approval");
  const token = humanApprove(ctx, state.pendingApproval!);
  state = runner.resume(def, state, token);
  assert.equal(state.status, "completed");
  assert.ok(vfs.exists("out/daily-brief.md"));
  assert.ok(String(vfs.readFile("out/daily-brief.md")).startsWith("Daily brief"));
});

test("M5: workflow audit chain contains all major steps", () => {
  const { ctx, runner, def } = harness();
  ctx.permissions.grant("local:read");
  let state = runner.start(def, "corr-wf");
  const token = humanApprove(ctx, state.pendingApproval!);
  state = runner.resume(def, state, token);
  assert.equal(state.status, "completed");
  const e = ctx.audit.records();
  assert.ok(e.some((x) => x.eventType === "workflow" && x.status === "started"));
  assert.ok(e.some((x) => x.eventType === "tool-invocation" && x.actionId === "project.read"));
  assert.ok(e.some((x) => x.eventType === "execution-authorization" && x.status === "consumed"));
  assert.ok(e.some((x) => x.eventType === "tool-invocation" && x.actionId === "fs.writeTextFileApproved"));
  assert.ok(e.some((x) => x.eventType === "checkpoint-created"));
  assert.ok(e.some((x) => x.eventType === "workflow" && x.status === "completed"));
});

test("M5: workflow failure preserves the last checkpoint", () => {
  const { ctx, runner, def } = harness();
  ctx.permissions.grant("local:read");
  let state = runner.start(def, "corr-wf");
  const pausedCheckpoint = state.lastCheckpointId;
  state = runner.resume(def, state, undefined); // write denied → failed
  assert.equal(state.status, "failed");
  assert.equal(state.lastCheckpointId, pausedCheckpoint, "checkpoint not overwritten on failure");
  assert.ok(ctx.checkpoints.read(pausedCheckpoint!), "checkpoint still readable");
});

test("M5: workflow retry does not retry a denied action automatically", () => {
  const { ctx, runner, def } = harness();
  ctx.permissions.grant("local:read");
  let state = runner.start(def, "corr-wf");
  state = runner.resume(def, state, undefined);
  assert.equal(state.status, "failed");
  const execEvents = ctx.audit.records().filter(
    (x) => x.eventType === "execution-authorization" && x.actionId === "daily-brief-write",
  );
  assert.equal(execEvents.length, 1, "the denied write was attempted exactly once");
});

test("M5: workflow does not bypass the tool registry", () => {
  // No capability tools are loaded — the read step must fail via the registry, not a direct fs read.
  const ctx = createRuntimeContext({ now: () => 1, correlationId: "corr-wf" });
  const runner = new WorkflowRunner(ctx, new AgentRuntime(ctx));
  const def = projectDailyBriefWorkflow({ summarizer: new SummaryAgent(), planner: new PlanningAgent() });
  ctx.permissions.grant("local:read");
  const state = runner.start(def, "corr-wf");
  assert.equal(state.status, "failed");
  assert.equal(state.failedStep, "read-project");
});

test("M5: workflow does not bypass the approval gate", () => {
  const { ctx, runner, def } = harness();
  ctx.permissions.grant("local:read");
  ctx.permissions.grant("local:write"); // permission granted, but NO approval token
  let state = runner.start(def, "corr-wf");
  state = runner.resume(def, state, undefined);
  assert.equal(state.status, "failed");
  assert.ok(ctx.audit.records().some((x) => x.eventType === "execution-authorization" && x.status === "no-approved-action"));
});

test("M5: workflow does not bypass the permission runtime", () => {
  const { ctx, vfs, runner, def } = harness();
  ctx.permissions.grant("local:read");
  let state = runner.start(def, "corr-wf");
  // Approve (mint token) but do NOT grant local:write.
  const token = humanApprove(ctx, state.pendingApproval!, { grant: false });
  state = runner.resume(def, state, token);
  assert.equal(state.status, "failed");
  assert.equal(vfs.exists("out/daily-brief.md"), false);
  assert.ok(ctx.audit.records().some((x) => x.eventType === "execution-authorization" && x.status === "permission-denied"));
});

test("M5: the Project Daily Brief mock workflow completes safely end-to-end (no raw secrets)", () => {
  const { ctx, vfs, runner, def } = harness("build green; 2 PRs open; token=SUPERSECRETVALUE in logs");
  ctx.permissions.grant("local:read");
  let state = runner.start(def, "corr-wf");
  assert.equal(state.status, "paused-for-approval");
  const token = humanApprove(ctx, state.pendingApproval!);
  state = runner.resume(def, state, token);
  assert.equal(state.status, "completed");
  const brief = String(vfs.readFile("out/daily-brief.md"));
  assert.ok(brief.startsWith("Daily brief"));
  assert.ok(!brief.includes("SUPERSECRETVALUE"), "the brief carries no raw secret");
  assert.ok(!JSON.stringify(ctx.audit.records()).includes("SUPERSECRETVALUE"), "audit carries no raw secret");
});
