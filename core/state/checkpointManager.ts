// GARVIS — Checkpoint Manager (M2)
//
// Minimal, PURE, in-memory create/read/restore for state snapshots. A workflow checkpoints its
// state per step so it can pause/resume and so a failure preserves the last good checkpoint.
//
// The manager stores frozen snapshots and audits create/restore through the existing Audit
// Runtime. It owns no durable facts (those belong to Memory) and performs no I/O.

import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit } from "../audit/auditRuntime.ts";
import type { StateSnapshot } from "./stateManager.ts";

export class CheckpointError extends Error {
  constructor(reason: string) {
    super(reason);
    this.name = "CheckpointError";
  }
}

export interface Checkpoint {
  readonly id: string;
  readonly label: string;
  readonly correlationId: string;
  readonly createdAt: number;
  readonly snapshot: StateSnapshot;
}

export interface CheckpointManagerOptions {
  readonly audit?: Audit;
  readonly now?: () => number;
}

export class CheckpointManager {
  #checkpoints = new Map<string, Checkpoint>();
  #order: string[] = [];
  #audit: Audit;
  #now: () => number;
  #seq = 0;

  constructor(options: CheckpointManagerOptions = {}) {
    this.#audit = options.audit ?? new AuditRuntime();
    this.#now = options.now ?? (() => Date.now());
  }

  /** Capture a frozen checkpoint of a state snapshot. Audited. */
  create(label: string, snapshot: StateSnapshot, correlationId = "checkpoint"): Checkpoint {
    const checkpoint: Checkpoint = Object.freeze({
      id: `ckpt-${++this.#seq}`,
      label,
      correlationId,
      createdAt: this.#now(),
      snapshot,
    });
    this.#checkpoints.set(checkpoint.id, checkpoint);
    this.#order.push(checkpoint.id);
    this.#audit.append({
      correlationId, actorId: "checkpoint-manager", actorType: "system",
      eventType: "checkpoint-created", eventCategory: "state", result: "committed", status: "created",
      summary: `checkpoint ${checkpoint.id} (${label})`,
    });
    return checkpoint;
  }

  read(id: string): Checkpoint | undefined {
    return this.#checkpoints.get(id);
  }

  /** Return a checkpoint's snapshot for the caller to apply (e.g. StateManager.restore). Audited. */
  restore(id: string): StateSnapshot {
    const checkpoint = this.#checkpoints.get(id);
    if (!checkpoint) throw new CheckpointError(`unknown-checkpoint:${id}`);
    this.#audit.append({
      correlationId: checkpoint.correlationId, actorId: "checkpoint-manager", actorType: "system",
      eventType: "checkpoint-restored", eventCategory: "state", result: "committed", status: "restored",
      summary: `restore checkpoint ${checkpoint.id} (${checkpoint.label})`,
    });
    return checkpoint.snapshot;
  }

  list(): readonly Checkpoint[] {
    return this.#order.map((id) => this.#checkpoints.get(id)!).filter(Boolean) as Checkpoint[];
  }

  latest(): Checkpoint | undefined {
    const id = this.#order[this.#order.length - 1];
    return id === undefined ? undefined : this.#checkpoints.get(id);
  }
}
