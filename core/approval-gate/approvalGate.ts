// GARVIS — Approval Gate Runtime (S0–S3 skeleton)
//
// PURE, in-memory, side-effect-free slice of the Approval Gate (governed by
// APPROVAL_GATE_SPEC.md). It upholds these invariants:
//   1. No action executes without an approved action.
//   2. An approval token is single-use; replay is rejected.
//   3. An unknown / unclassifiable action fails closed (no token is ever issued).
//   4. An invalid approval request is rejected BEFORE classification or token creation.
//   5. Execution requires BOTH a valid single-use approval token AND the action's
//      permission scope — permission is not approval, approval is not permission (S2/S3).
//
// Still NOT the full gate: no audit, queue, expiration of tokens, revocation of tokens, or
// real classification taxonomy yet. No I/O, no network, no filesystem. State lives only in
// memory inside an ApprovalGate instance.

import { ContractRegistry, defaultContractRegistry } from "../contracts/contractRegistry.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";
import type { PermissionScope } from "../permissions/permissionRuntime.ts";

export type Disposition = "auto" | "gated" | "forbidden";

export interface ProposedAction {
  /** Unique id of this specific proposed action. */
  readonly id: string;
  /** The action kind; only known kinds are classifiable (otherwise fail closed). */
  readonly type: string;
}

/**
 * The validated approval-request shape the gate accepts. `requestApproval` takes
 * `unknown` and validates against the registered approvalRequest@1 contract; this
 * interface documents the expected fields. Secrets are never embedded (handles only).
 */
export interface ApprovalRequest {
  readonly actionId: string;
  readonly actionType: string;
  readonly riskClass: string;
  readonly redactionStatus: "redacted";
  readonly correlationId: string;
  readonly idempotencyKey?: string;
  readonly summary?: string;
  readonly targetResource?: string;
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

// Known action kinds → disposition. Anything NOT listed here is UNKNOWN and must fail
// closed. This stub list is deliberately tiny; the real taxonomy is future work.
const DISPOSITIONS: ReadonlyMap<string, Disposition> = new Map([
  ["informational", "auto"],
  ["local.read", "auto"],
  ["local.write", "gated"],
  ["external.read", "gated"],
  ["external.write", "gated"],
  ["execution.command", "gated"],
  ["destructive", "gated"],
  ["credential", "forbidden"],
]);

// Known action kinds → the permission scope they require. The gate derives this
// authoritatively from the action type (it does not trust a proposer-declared field).
// `informational` requires no scope.
const REQUIRED_SCOPE: ReadonlyMap<string, PermissionScope> = new Map([
  ["local.read", "local:read"],
  ["local.write", "local:write"],
  ["external.read", "external:read"],
  ["external.write", "external:write"],
  ["execution.command", "execution:command"],
  ["destructive", "destructive"],
  ["credential", "credential:sensitive"],
]);

/**
 * Pure classification. Conservative-on-uncertainty: an unrecognised action type is
 * "unknown" and never treated as auto-approvable.
 */
export function classify(action: ProposedAction): Disposition | "unknown" {
  return DISPOSITIONS.get(action.type) ?? "unknown";
}

export class ApprovalGate {
  #registry: ContractRegistry;
  #permissions: PermissionRuntime;
  /** Issued, not-yet-consumed tokens, keyed by tokenId. */
  #live = new Map<string, ApprovalToken>();
  /** TokenIds that have already been consumed once (used to reject replay). */
  #consumed = new Set<string>();
  #seq = 0;

  constructor(
    registry: ContractRegistry = defaultContractRegistry(),
    permissions: PermissionRuntime = new PermissionRuntime(),
  ) {
    this.#registry = registry;
    this.#permissions = permissions;
  }

  /**
   * Request a single-use approval for an action described by an approval-request payload.
   * Approval is INDEPENDENT of permission (you can obtain a token without holding the
   * permission — permission is checked at execution). The request is validated against the
   * approvalRequest@1 contract FIRST; an invalid request fails closed. A `forbidden` or
   * `unknown` classification also fails closed. Only valid `auto`/`gated` requests mint a token.
   */
  requestApproval(request: unknown): ApprovalToken | null {
    // (4) Contract validation BEFORE classification / token creation — fail closed.
    const validation = this.#registry.validate("approvalRequest", "1", request);
    if (!validation.valid) {
      return null;
    }
    const req = request as ApprovalRequest;
    const action: ProposedAction = { id: req.actionId, type: req.actionType };

    // (3) Classification fail-closed for forbidden / unknown.
    const disposition = classify(action);
    if (disposition === "forbidden" || disposition === "unknown") {
      return null;
    }

    const token: ApprovalToken = {
      tokenId: `tok-${++this.#seq}`,
      actionId: action.id,
    };
    this.#live.set(token.tokenId, token);
    return token;
  }

  /**
   * The ONLY path to execution. Requires BOTH:
   *   (a) a valid, unconsumed token bound to this exact action (approval), and
   *   (b) the action's required permission scope to be currently granted (permission).
   * Missing either blocks execution. The token is consumed ONLY on a fully-authorized
   * (allowed) execution; a permission failure does not waste the approval.
   */
  authorizeExecution(action: ProposedAction, token?: ApprovalToken | null): AuthorizationResult {
    // (a) approval (token) checks first
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

    // (b) permission check — separate authority from approval, fail closed.
    const requiredScope = REQUIRED_SCOPE.get(action.type);
    if (requiredScope !== undefined) {
      const permission = this.#permissions.check({ scope: requiredScope });
      if (!permission.allowed) {
        // Do NOT consume the token on a permission failure.
        return { allowed: false, reason: `permission-denied:${permission.reason}` };
      }
    }

    // Both halves satisfied → consume the single-use token and allow.
    this.#live.delete(token.tokenId);
    this.#consumed.add(token.tokenId);
    return { allowed: true, reason: "approved" };
  }
}
