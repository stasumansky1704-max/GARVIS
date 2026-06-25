// GARVIS — State Manager (M2)
//
// Minimal, PURE, in-memory, LOCAL state container with a monotonic version. Holds transient
// runtime/working state (not durable facts — those belong to the Memory authority). Supports
// versioned snapshot/restore so the Checkpoint Manager can capture and roll back to a step.
//
// No I/O, no network, no persistence. Snapshots are frozen so a captured checkpoint cannot be
// mutated after the fact.

export interface StateSnapshot {
  readonly version: number;
  readonly entries: ReadonlyArray<readonly [string, unknown]>;
}

export class StateManager {
  #state = new Map<string, unknown>();
  #version = 0;

  get(key: string): unknown {
    return this.#state.get(key);
  }

  has(key: string): boolean {
    return this.#state.has(key);
  }

  /** Set a key; bumps the version (update/read lifecycle is observable via version()). */
  set(key: string, value: unknown): void {
    this.#state.set(key, value);
    this.#version += 1;
  }

  delete(key: string): void {
    if (this.#state.delete(key)) this.#version += 1;
  }

  version(): number {
    return this.#version;
  }

  /** Frozen point-in-time snapshot, safe to hand to the Checkpoint Manager. */
  snapshot(): StateSnapshot {
    const entries = [...this.#state.entries()].map(
      (e) => Object.freeze([e[0], e[1]]) as readonly [string, unknown],
    );
    return Object.freeze({ version: this.#version, entries: Object.freeze(entries) });
  }

  /** Replace all state with a snapshot's contents (used by checkpoint restore). */
  restore(snapshot: StateSnapshot): void {
    this.#state = new Map(snapshot.entries.map((e) => [e[0], e[1]]));
    this.#version = snapshot.version;
  }
}
