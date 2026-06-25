// GARVIS — Memory Runtime tests (M2 + H2 hardening)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Covers the non-forgeable single-writer capability, raw-secret rejection, redaction-before-store,
// provenance, and fail-closed auditing.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { MemoryRuntime } from "./memoryRuntime.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";

function input(over: Partial<Record<string, string>> = {}) {
  return {
    key: "project.status",
    value: "build green",
    source: "tool:project-reader",
    correlationId: "corr-mem",
    ...over,
  };
}

test("memory M2: a durable write goes through the single writer capability", () => {
  const memory = new MemoryRuntime({ audit: new AuditRuntime(() => 1) });
  const writer = memory.claimWriter();
  const record = writer.write(input());
  assert.equal(record.key, "project.status");
  assert.equal(memory.read("project.status")?.value, "build green");
});

test("memory H2: the writer capability is non-forgeable (claimable exactly once)", () => {
  const memory = new MemoryRuntime({ audit: new AuditRuntime(() => 1) });
  memory.claimWriter();
  // No second writer can ever be obtained — there is no shared writer constant to forge.
  assert.throws(() => memory.claimWriter(), /writer-already-claimed/);
  // The runtime exposes NO public write() — durable writes are impossible without the capability.
  assert.equal(typeof (memory as Record<string, unknown>).write, "undefined");
});

test("memory H2: a read-only holder cannot forge a writer (adversarial)", () => {
  const memory = new MemoryRuntime({ audit: new AuditRuntime(() => 1) });
  memory.claimWriter().write(input()); // composition root claims the one writer
  const reader = memory; // downstream consumers receive this, typed as MemoryReader
  // Even a malicious cast cannot obtain a second writer.
  assert.throws(
    () => (reader as unknown as { claimWriter(): unknown }).claimWriter(),
    /writer-already-claimed/,
  );
});

test("memory M2: rejects raw secret-like fields", () => {
  const writer = new MemoryRuntime({ audit: new AuditRuntime(() => 1) }).claimWriter();
  assert.throws(() => writer.write(input({ key: "apiKey" })), /secret-like-key-rejected/);
  assert.throws(() => writer.write(input({ source: "password-store" })), /secret-like-source-rejected/);
});

test("memory M2: redacts sensitive values before storing", () => {
  const memory = new MemoryRuntime({ audit: new AuditRuntime(() => 1) });
  const record = memory.claimWriter().write(input({ value: "deploy token=SUPERSECRETVALUE to /tmp/out" }));
  assert.equal(record.redactionStatus, "redacted");
  assert.ok(!record.value.includes("SUPERSECRETVALUE"), "secret value masked before storage");
  assert.ok(record.value.includes("token=***"));
  assert.ok(record.value.includes("/tmp/out"), "non-secret content preserved");
  assert.ok(!JSON.stringify(memory.export()).includes("SUPERSECRETVALUE"));
});

test("memory M2: stores provenance", () => {
  const memory = new MemoryRuntime({ audit: new AuditRuntime(() => 42), now: () => 42 });
  const record = memory.claimWriter().write(input({ source: "agent:summary" }));
  assert.equal(record.provenance.source, "agent:summary");
  assert.equal(record.provenance.correlationId, "corr-mem");
  assert.equal(record.provenance.recordedAt, 42);
});

test("memory M2: a write emits an audit event and fails closed if audit fails", () => {
  const audit = new AuditRuntime(() => 1);
  const memory = new MemoryRuntime({ audit });
  memory.claimWriter().write(input());
  assert.ok(audit.records().some((e) => e.eventType === "memory-write" && e.status === "written"));

  const failing = { append() { throw new Error("audit down"); } };
  const memory2 = new MemoryRuntime({ audit: failing });
  assert.throws(() => memory2.claimWriter().write(input({ key: "k2" })), /audit-failure/);
  assert.equal(memory2.has("k2"), false);
});
