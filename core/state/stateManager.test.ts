// GARVIS — State Manager + Checkpoint Manager tests (M2)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Covers the state update/read lifecycle and checkpoint create/read/restore (with audit).

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { StateManager } from "./stateManager.ts";
import { CheckpointManager } from "./checkpointManager.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";

test("state M2: update/read lifecycle bumps version", () => {
  const state = new StateManager();
  assert.equal(state.version(), 0);
  assert.equal(state.get("step"), undefined);

  state.set("step", "start");
  assert.equal(state.get("step"), "start");
  assert.equal(state.version(), 1);

  state.set("step", "read");
  assert.equal(state.get("step"), "read");
  assert.equal(state.version(), 2);
});

test("checkpoint M2: create / read / restore round-trips state", () => {
  const audit = new AuditRuntime(() => 7);
  const checkpoints = new CheckpointManager({ audit, now: () => 7 });
  const state = new StateManager();

  state.set("brief", "v1");
  const cp = checkpoints.create("after-step-1", state.snapshot(), "corr-wf");
  assert.equal(checkpoints.read(cp.id)?.label, "after-step-1");

  // Mutate, then restore the checkpoint — state returns to the captured value.
  state.set("brief", "v2");
  assert.equal(state.get("brief"), "v2");
  state.restore(checkpoints.restore(cp.id));
  assert.equal(state.get("brief"), "v1");

  // Both create and restore were audited.
  assert.ok(audit.records().some((e) => e.eventType === "checkpoint-created"));
  assert.ok(audit.records().some((e) => e.eventType === "checkpoint-restored"));
  // Restoring an unknown checkpoint fails closed.
  assert.throws(() => checkpoints.restore("ckpt-999"), /unknown-checkpoint/);
});

test("checkpoint M2: stored snapshot is frozen (immutable)", () => {
  const checkpoints = new CheckpointManager({ audit: new AuditRuntime(() => 1) });
  const state = new StateManager();
  state.set("a", 1);
  const cp = checkpoints.create("c", state.snapshot());
  assert.throws(() => {
    (cp.snapshot as { version: number }).version = 99;
  });
});
