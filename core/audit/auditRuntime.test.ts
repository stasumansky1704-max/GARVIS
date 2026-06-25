// GARVIS — Audit Runtime tests (S3)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Covers append-only/immutability, required correlation id, secret-like field rejection,
// and summary redaction-before-storage.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { AuditRuntime } from "./auditRuntime.ts";
import type { AuditRecord } from "./auditRuntime.ts";

function baseInput() {
  return {
    correlationId: "corr-1",
    actorId: "gate",
    actorType: "system",
    eventType: "approval-request",
    eventCategory: "audit",
    result: "approved",
    status: "token-created",
  };
}

test("audit 1: appends records and never mutates existing records", () => {
  const audit = new AuditRuntime(() => 100);
  audit.append({ ...baseInput(), correlationId: "c1" });
  assert.equal(audit.records().length, 1);
  audit.append({ ...baseInput(), correlationId: "c2" });
  assert.equal(audit.records().length, 2);

  // The first record is unchanged after later appends.
  assert.equal(audit.records()[0].correlationId, "c1");

  // Stored records are frozen — existing records cannot be mutated.
  assert.throws(() => {
    (audit.records()[0] as { result: string }).result = "tampered";
  });

  // records() returns a copy: mutating the snapshot does not corrupt the log.
  const snapshot = audit.records() as AuditRecord[];
  snapshot.length = 0;
  assert.equal(audit.records().length, 2);
});

test("audit 2: an audit record requires a correlation id (fails closed)", () => {
  const audit = new AuditRuntime(() => 100);
  const { correlationId: _drop, ...noCorrelation } = baseInput();
  void _drop;
  assert.throws(() => audit.append(noCorrelation as unknown as ReturnType<typeof baseInput>), /missing-correlation-id/);
});

test("audit 3: audit rejects raw secret-like fields (fails closed)", () => {
  const audit = new AuditRuntime(() => 100);
  const withSecretField = { ...baseInput(), apiKey: "PLACEHOLDER-NOT-A-REAL-SECRET" };
  assert.throws(() => audit.append(withSecretField as unknown as ReturnType<typeof baseInput>), /secret-like-field-rejected/);
});

test("audit 4: redacts sensitive summary content before storage", () => {
  const audit = new AuditRuntime(() => 100);
  const record = audit.append({
    ...baseInput(),
    summary: "writing apiKey=SUPERSECRETVALUE to /tmp/a",
  });
  assert.equal(record.redactionStatus, "redacted");
  assert.ok(!record.redactedSummary.includes("SUPERSECRETVALUE"), "secret value must be masked");
  assert.ok(record.redactedSummary.includes("apiKey=***"), "secret-like value should be masked to ***");
  assert.ok(record.redactedSummary.includes("/tmp/a"), "non-secret content is preserved");
});
