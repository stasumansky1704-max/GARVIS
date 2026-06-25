// GARVIS — Approval Gate Runtime (S0/S1 skeleton)
//
// Smallest possible, PURE, in-memory, side-effect-free slice of the Approval Gate
// (governed by APPROVAL_GATE_SPEC.md). It exists only to uphold three invariants:
//   1. No action executes without an approved action.
//   2. An approval token is single-use; replay is rejected.
//   3. An unknown / unclassifiable action fails closed (no token is ever issued).
//
// This is NOT the full gate: no permissions, contracts, audit, queue, expiration,
// revocation, or real classification taxonomy yet. No I/O, no network, no filesystem.
// Token state lives only in memory inside an ApprovalGate instance.

export type Disposition = "auto" | "gated" | "forbidden";

export interface ProposedAction {
  /** Unique id of this specific proposed action. */
  readonly id: string;
  /** The action kind; only known kinds are classifiable (otherwise fail closed). */
  readonly type: string;
}

export interface ApprovalToken {
  readonly tokenId: string;
  /** The exact action this token authorizes. */
  readonly actionId: string;
}

export interface AuthorizationResult {
  readonly allowed: boolean;
  /** Stable machine-readable reason, safe to log (no secrets). */
  readonly reason: string;
}

// Known action kinds → disposition. Anything NOT listed here is UNKNOWN and must
// fail closed. This stub list is deliberately tiny; the real taxonomy is future work.
const DISPOSITIONS: ReadonlyMap<string, Disposition> = new Map([
  ["informational", "auto"],
  ["local.read", "auto"],
  ["local.write", "gated"],
  ["external.write", "gated"],
  ["destructive", "gated"],
  ["credential", "forbidden"],
]);

/**
 * Pure classification. Conservative-on-uncertainty: an unrecognised action type is
 * "unknown" and never treated as auto-approvable.
 */
export function classify(action: ProposedAction): Disposition | "unknown" {
  return DISPOSITIONS.get(action.type) ?? "unknown";
}

export class ApprovalGate {
  /** Issued, not-yet-consumed tokens, keyed by tokenId. */
  #live = new Map<string, ApprovalToken>();
  /** TokenIds that have already been consumed once (used to reject replay). */
  #consumed = new Set<string>();
  #seq = 0;

  /**
   * Request a single-use approval for an action. An `auto` action is auto-approved;
   * a `gated` action represents a human decision (driven by the caller in tests).
   * A `forbidden` or `unknown` action FAILS CLOSED: no token is ever issued.
   */
  requestApproval(action: ProposedAction): ApprovalToken | null {
    const disposition = classify(action);
    if (disposition === "forbidden" || disposition === "unknown") {
      return null; // fail closed — never mint a token for what we cannot safely classify
    }
    const token: ApprovalToken = {
      tokenId: `tok-${++this.#seq}`,
      actionId: action.id,
    };
    this.#live.set(token.tokenId, token);
    return token;
  }

  /**
   * The ONLY path to execution. Requires a valid, unconsumed token bound to this exact
   * action. No token => not allowed. A consumed token (replay) => rejected. On success
   * the token is consumed (single-use).
   */
  authorizeExecution(action: ProposedAction, token?: ApprovalToken | null): AuthorizationResult {
    if (!token) {
      return { allowed: false, reason: "no-approved-action" };
    }
    if (this.#consumed.has(token.tokenId)) {
      return { allowed: false, reason: "token-replay-rejected" };
    }
    const live = this.#live.get(token.tokenId);
    if (!live || live.actionId !== action.id) {
      return { allowed: false, reason: "invalid-or-unbound-token" };
    }
    // consume the single-use token
    this.#live.delete(token.tokenId);
    this.#consumed.add(token.tokenId);
    return { allowed: true, reason: "approved" };
  }
}
