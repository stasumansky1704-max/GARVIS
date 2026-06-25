// GARVIS — Memory Runtime (M2 core; hardened H2)
//
// The SINGLE Memory authority (governed by MEMORY_AUTHORITY_SPEC / ADR-0003). Minimal, PURE,
// in-memory. It is the only writer of durable platform state.
//
// SINGLE-WRITER is enforced by a NON-FORGEABLE capability, not a shared string:
//   - There is NO public `write()` and NO exported writer constant.
//   - `claimWriter()` issues the one writer capability exactly once; any further claim throws.
//   - Agents, workflows, and tools receive only the read-only `MemoryReader` facade. Even a cast
//     to call `claimWriter()` fails once the composition root has claimed it.
//
// Other invariants: secret-like key/source rejected; values REDACTED before storage (so
// search/export/display can never surface a raw secret); every record carries provenance; a
// write that cannot be audited fails closed. Memory is NOT the Audit authority — redacted facts only.

import { looksSecretLike } from "../contracts/contractRegistry.ts";
import { redactText } from "../redaction/redactText.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit } from "../audit/auditRuntime.ts";

export class MemoryError extends Error {
  constructor(reason: string) {
    super(reason);
    this.name = "MemoryError";
  }
}

export interface Provenance {
  readonly source: string;
  readonly correlationId: string;
  readonly recordedAt: number;
}

export interface MemoryWriteInput {
  readonly key: string;
  readonly value: string;
  readonly source: string;
  readonly correlationId: string;
}

export interface MemoryRecord {
  readonly key: string;
  /** Redacted value — never a raw secret. */
  readonly value: string;
  readonly redactionStatus: "redacted";
  readonly provenance: Provenance;
}

/** Read-only view of the Memory authority — what agents/workflows/tools receive. */
export interface MemoryReader {
  read(key: string): MemoryRecord | undefined;
  has(key: string): boolean;
  search(substring: string): readonly MemoryRecord[];
  export(): readonly MemoryRecord[];
}

/** The single durable-write capability. Unforgeable: only obtainable once via `claimWriter()`. */
export interface MemoryWriter {
  write(input: MemoryWriteInput): MemoryRecord;
}

export interface MemoryRuntimeOptions {
  readonly audit?: Audit;
  readonly now?: () => number;
}

function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

export class MemoryRuntime implements MemoryReader {
  #store = new Map<string, MemoryRecord>();
  #audit: Audit;
  #now: () => number;
  #writerClaimed = false;

  constructor(options: MemoryRuntimeOptions = {}) {
    this.#audit = options.audit ?? new AuditRuntime();
    this.#now = options.now ?? (() => Date.now());
  }

  /**
   * Issue the SINGLE writer capability. Callable exactly once (by the composition root); any
   * further claim throws `writer-already-claimed`. This is the only way to obtain durable-write
   * access — there is no public `write()` and no shared writer identity to forge.
   */
  claimWriter(): MemoryWriter {
    if (this.#writerClaimed) throw new MemoryError("writer-already-claimed");
    this.#writerClaimed = true;
    return Object.freeze({ write: (input: MemoryWriteInput): MemoryRecord => this.#doWrite(input) });
  }

  #doWrite(input: MemoryWriteInput): MemoryRecord {
    if (!isNonEmptyString(input.correlationId)) throw new MemoryError("missing-correlation-id");
    if (!isNonEmptyString(input.key)) throw new MemoryError("missing-key");
    if (!isNonEmptyString(input.source)) throw new MemoryError("missing-source");
    if (looksSecretLike(input.key)) throw new MemoryError(`secret-like-key-rejected:${input.key}`);
    if (looksSecretLike(input.source)) throw new MemoryError("secret-like-source-rejected");

    // Audit BEFORE storage — fail closed if the write cannot be recorded.
    let audited = true;
    try {
      this.#audit.append({
        correlationId: input.correlationId, actorId: "memory-authority", actorType: "system",
        eventType: "memory-write", eventCategory: "memory", result: "committed", status: "written",
        summary: `memory write ${input.key} from ${input.source}`,
      });
    } catch {
      audited = false;
    }
    if (!audited) throw new MemoryError("audit-failure");

    const record: MemoryRecord = Object.freeze({
      key: input.key,
      value: redactText(input.value ?? ""),
      redactionStatus: "redacted",
      provenance: Object.freeze({
        source: input.source,
        correlationId: input.correlationId,
        recordedAt: this.#now(),
      }),
    });
    this.#store.set(input.key, record);
    return record;
  }

  // ── MemoryReader facade (read-only) ──────────────────────────────────────────

  read(key: string): MemoryRecord | undefined {
    return this.#store.get(key);
  }

  has(key: string): boolean {
    return this.#store.has(key);
  }

  /** Substring search over redacted keys/values — never surfaces raw secrets. */
  search(substring: string): readonly MemoryRecord[] {
    return [...this.#store.values()].filter(
      (r) => r.key.includes(substring) || r.value.includes(substring),
    );
  }

  /** Export the full store (already redacted) — safe for display/transport. */
  export(): readonly MemoryRecord[] {
    return [...this.#store.values()];
  }
}
