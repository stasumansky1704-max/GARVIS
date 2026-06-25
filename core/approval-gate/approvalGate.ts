// GARVIS — Approval Gate Runtime (S0–S3 skeleton)
//
// PURE, in-memory, side-effect-free slice of the Approval Gate (governed by
// APPROVAL_GATE_SPEC.md). It upholds these invariants:
//   1. No action executes without an approved action.
//   2. An approval token is single-use; replay is rejected.
//   3. An unknown / unclassifiable action fails closed (no token is ever issued).
//   4. An invalid approval request is rejected BEFORE classification or token creation.
//   5. Execution requires BOTH a valid single-use approval token AND the action's
//      permission scope — permission is not approval, approval is not permission.
//   6. Every outcome is audited (no raw token/secret); audit failure FAILS CLOSED for
//      security-relevant positive outcomes (token creation, execution authorization) (S3).
//
// Still NOT the full gate: no queue, token expiration/revocation, or real classification
// taxonomy. No I/O, no network, no filesystem. State lives only in memory.

import { ContractRegistry, defaultContractRegistry } from "../contracts/contractRegistry.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";
import type { PermissionScope } from "../permissions/permissionRuntime.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit, AuditInput } from "../audit/auditRuntime.ts";

export type Disposition = "auto" | "gated" | "forbidden";

export interface ProposedAction {
  readonly id: string;
  readonly type: string;
}

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
  readonly actionId: string;
}

export interface AuthorizationResult {
  readonly allowed: boolean;
  readonly reason: string;
}

// Internal record kept for an issued token so execution can recover its correlation/risk
// without trusting the caller. Never exposed.
interface LiveApproval {
  token: ApprovalToken;
  correlationId: string;
  actionType: string;
  riskClass: string;
}

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

const REQUIRED_SCOPE: ReadonlyMap<string, PermissionScope> = new Map([
  ["local.read", "local:read"],
  ["local.write", "local:write"],
  ["external.read", "external:read"],
  ["external.write", "external:write"],
  ["execution.command", "execution:command"],
  ["destructive", "destructive"],
  ["credential", "credential:sensitive"],
]);

export function classify(action: ProposedAction): Disposition | "unknown" {
  return DISPOSITIONS.get(action.type) ?? "unknown";
}

function bestEffortCorrelationId(request: unknown): string {
  if (typeof request === "object" && request !== null) {
    const c = (request as Record<string, unknown>).correlationId;
    if (typeof c === "string" && c.length > 0) return c;
  }
  return "uncorrelated";
}

export class ApprovalGate {
  #registry: ContractRegistry;
  #permissions: PermissionRuntime;
  #audit: Audit;
  #live = new Map<string, LiveApproval>();
  #consumed = new Set<string>();
  #seq = 0;

  constructor(
    registry: ContractRegistry = defaultContractRegistry(),
    permissions: PermissionRuntime = new PermissionRuntime(),
    audit: Audit = new AuditRuntime(),
  ) {
    this.#registry = registry;
    this.#permissions = permissions;
    this.#audit = audit;
  }

  /** Emit one audit event. Returns false if auditing failed (so callers can fail closed). */
  #emit(input: AuditInput): boolean {
    try {
      this.#audit.append(input);
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Request a single-use approval. Approval is INDEPENDENT of permission. Every outcome is
   * audited. Token creation is FAIL-CLOSED on audit failure (an approval that cannot be
   * audited is never granted).
   */
  requestApproval(request: unknown): ApprovalToken | null {
    const validation = this.#registry.validate("approvalRequest", "1", request);
    if (!validation.valid) {
      this.#emit({
        correlationId: bestEffortCorrelationId(request), actorId: "gate", actorType: "system",
        eventType: "approval-request", eventCategory: "audit",
        result: "rejected", status: "invalid-request",
        summary: "approval request rejected: invalid contract",
      });
      return null;
    }

    const req = request as ApprovalRequest;
    const action: ProposedAction = { id: req.actionId, type: req.actionType };
    const disposition = classify(action);

    if (disposition === "forbidden" || disposition === "unknown") {
      this.#emit({
        correlationId: req.correlationId, actorId: "gate", actorType: "system",
        eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
        result: "rejected", status: disposition, riskClass: req.riskClass,
        summary: `approval request rejected (${disposition}): ${req.actionType}`,
      });
      return null;
    }

    // Audit BEFORE minting — if it cannot be audited, fail closed (no token).
    const audited = this.#emit({
      correlationId: req.correlationId, actorId: "gate", actorType: "system",
      eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
      result: "approved", status: "token-created", riskClass: req.riskClass,
      summary: `token created for ${req.actionType}`,
    });
    if (!audited) return null;

    const token: ApprovalToken = { tokenId: `tok-${++this.#seq}`, actionId: action.id };
    this.#live.set(token.tokenId, {
      token, correlationId: req.correlationId, actionType: req.actionType, riskClass: req.riskClass,
    });
    return token;
  }

  /**
   * The ONLY path to execution. Requires a valid single-use token (approval) AND the
   * action's permission scope (permission). Every outcome is audited; audit failure FAILS
   * CLOSED (the action does not execute). The token is consumed only on a fully-authorized,
   * fully-audited success.
   */
  authorizeExecution(action: ProposedAction, token?: ApprovalToken | null): AuthorizationResult {
    let allowed = false;
    let status = "no-approved-action";
    let reason = "no-approved-action";
    let correlationId = "uncorrelated";
    let riskClass: string | undefined;
    let consumeTokenId: string | undefined;

    if (!token) {
      // defaults above
    } else if (this.#consumed.has(token.tokenId)) {
      status = "token-replay-rejected";
      reason = "token-replay-rejected";
    } else {
      const live = this.#live.get(token.tokenId);
      if (!live || live.token.actionId !== action.id) {
        status = "invalid-or-unbound-token";
        reason = "invalid-or-unbound-token";
        if (live) correlationId = live.correlationId;
      } else {
        correlationId = live.correlationId;
        riskClass = live.riskClass;
        const requiredScope = REQUIRED_SCOPE.get(action.type);
        const permission = requiredScope === undefined
          ? { allowed: true, reason: "no-scope-required" }
          : this.#permissions.check({ scope: requiredScope });
        if (!permission.allowed) {
          status = "permission-denied";
          reason = `permission-denied:${permission.reason}`;
        } else {
          allowed = true;
          status = "consumed";
          reason = "approved";
          consumeTokenId = token.tokenId;
        }
      }
    }

    const audited = this.#emit({
      correlationId, actorId: "gate", actorType: "system",
      eventType: "execution-authorization", eventCategory: "audit", actionId: action.id,
      result: allowed ? "approved" : "rejected", status, riskClass,
      summary: `authorize ${action.type}: ${status}`,
    });
    if (!audited) {
      // Fail closed: do not execute (and do not consume) if the outcome cannot be audited.
      return { allowed: false, reason: "audit-failure" };
    }

    if (allowed && consumeTokenId !== undefined) {
      this.#live.delete(consumeTokenId);
      this.#consumed.add(consumeTokenId);
    }
    return { allowed, reason };
  }
}
