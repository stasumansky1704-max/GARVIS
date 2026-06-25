// GARVIS — Audit Runtime (S3)
//
// Minimal, PURE, in-memory, APPEND-ONLY audit layer (governed by OBSERVABILITY_AND_AUDIT_SPEC.md).
// It is the smallest slice needed to record Approval Gate / Permission decisions as immutable,
// correlated, redacted, secret-free events.
//
// NOT a full observability platform: no persistence, no log files, no dashboards, no tracing,
// no metrics. No I/O, no network, no filesystem. Records live only in memory and are frozen.
//
// Fail-closed: an invalid audit input (missing correlation id, or a secret-like field name)
// THROWS — callers on gated/security-relevant paths must treat that as a hard denial.

import { looksSecretLike } from "../contracts/contractRegistry.ts";
import { redactText } from "../redaction/redactText.ts";

export class AuditError extends Error {
  constructor(reason: string) {
    super(reason);
    this.name = "AuditError";
  }
}

export interface AuditInput {
  readonly correlationId: string;
  readonly actorId: string;
  readonly actorType: string;
  readonly eventType: string;
  readonly eventCategory: string;
  readonly result: string;
  readonly status: string;
  readonly actionId?: string;
  readonly decisionId?: string;
  readonly riskClass?: string;
  /** Human-readable summary; redacted into `redactedSummary` before storage. */
  readonly summary?: string;
}

export interface AuditRecord {
  readonly auditEventId: string;
  readonly correlationId: string;
  readonly timestamp: number;
  readonly actorId: string;
  readonly actorType: string;
  readonly eventType: string;
  readonly eventCategory: string;
  readonly actionId?: string;
  readonly decisionId?: string;
  readonly result: string;
  readonly status: string;
  readonly riskClass?: string;
  readonly redactionStatus: "redacted";
  readonly redactedSummary: string;
}

/** The minimal audit surface the Approval Gate depends on. */
export interface Audit {
  append(input: AuditInput): AuditRecord;
}

function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

// Summary redaction-before-storage uses the SINGLE shared transform (core/redaction) so the
// audit log and the Memory authority redact identically and can never drift.

export class AuditRuntime implements Audit {
  #records: AuditRecord[] = [];
  #seq = 0;
  #now: () => number;

  constructor(now: () => number = () => Date.now()) {
    this.#now = now;
  }

  /**
   * Append one audit record. Fails closed (throws AuditError) when the input lacks a
   * correlation id or carries a secret-like field name. The summary is redacted before
   * storage and the stored record is frozen (existing records are never mutated).
   */
  append(input: AuditInput): AuditRecord {
    if (!isNonEmptyString(input.correlationId)) {
      throw new AuditError("missing-correlation-id");
    }
    for (const key of Object.keys(input)) {
      if (looksSecretLike(key)) {
        throw new AuditError(`secret-like-field-rejected:${key}`);
      }
    }

    const record: AuditRecord = Object.freeze({
      auditEventId: `evt-${++this.#seq}`,
      correlationId: input.correlationId,
      timestamp: this.#now(),
      actorId: input.actorId,
      actorType: input.actorType,
      eventType: input.eventType,
      eventCategory: input.eventCategory,
      actionId: input.actionId,
      decisionId: input.decisionId,
      result: input.result,
      status: input.status,
      riskClass: input.riskClass,
      redactionStatus: "redacted",
      redactedSummary: redactText(input.summary ?? ""),
    });
    this.#records.push(record);
    return record;
  }

  /** Read-only snapshot (a copy) of the append-only log. */
  records(): readonly AuditRecord[] {
    return this.#records.slice();
  }
}
