// GARVIS — Approval Gate Runtime (S0–S4 skeleton)
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
//      security-relevant positive outcomes (token creation, execution authorization).
//   7. No self-approval: an actor never approves its own action (by identity), and only a
//      HUMAN holds approval authority — agents/tools/system may PROPOSE, never approve (§31/§32).
//   8. Never-auto: external-write, command-execution, and destructive actions require explicit,
//      per-instance human approval — no token is minted without it (§15). Credential-sensitive
//      is stricter still: Forbidden (§16).
//   9. Forbidden is rejected and audited, NEVER tokenized and NEVER queued (§16/§26).
//
// Still NOT the full gate: no deferred queue, token expiration/revocation, or real
// classification taxonomy. No I/O, no network, no filesystem. State lives only in memory.
//
// Approver identity is carried as a SEPARATE `decision` argument (who proposed, who approved),
// NOT inside the contract-validated request payload — so the approvalRequest contract and its
// tests stay unchanged, mirroring the spec's split of request (proposal) vs decision (approval).

import { ContractRegistry, defaultContractRegistry } from "../contracts/contractRegistry.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";
import type { PermissionScope } from "../permissions/permissionRuntime.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit, AuditInput } from "../audit/auditRuntime.ts";
import { actionPolicy, dispositionOf } from "../capabilities/actionPolicy.ts";
import type { Disposition } from "../capabilities/actionPolicy.ts";

export type { Disposition };

/** Who an actor is. Only a human holds approval authority (§31/§32). */
export type ActorType = "human" | "agent" | "tool" | "system";

export interface Actor {
  readonly id: string;
  readonly type: ActorType;
}

/**
 * An explicit human-in-the-loop approval decision accompanying a request: who PROPOSED the
 * action and who APPROVED it. Carried separately from the (contract-validated) ApprovalRequest
 * so the request contract stays unchanged — approver identity is a decision, not request data.
 */
export interface ApprovalDecision {
  readonly requestedBy: Actor;
  readonly approvedBy: Actor;
}

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

// Internal record kept for an issued token. It BINDS the approval to the exact action that was
// approved (id, type, the requester, the required permission scope, and risk) so execution can
// be verified against the approval and can never be downgraded by caller input. Never exposed.
interface LiveApproval {
  token: ApprovalToken;
  correlationId: string;
  actionId: string;
  actionType: string;
  requiredScope?: PermissionScope;
  riskClass: string;
  requestedBy: string;
}

// Disposition / required scope / never-auto all come from the SINGLE trusted action policy
// (core/capabilities/actionPolicy) — no duplicated maps live here.
export function classify(action: ProposedAction): Disposition | "unknown" {
  return dispositionOf(action.type);
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}
const ACTOR_TYPES: ReadonlySet<string> = new Set(["human", "agent", "tool", "system"]);
function isActor(v: unknown): v is Actor {
  return isPlainObject(v) && isNonEmptyString(v.id) && typeof v.type === "string" && ACTOR_TYPES.has(v.type);
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
   *
   * Forbidden/unknown actions are rejected and NEVER tokenized or queued. When a human-in-the-
   * loop `decision` is supplied, the gate enforces no-self-approval and human-only approval
   * authority. Never-auto actions (§15) are rejected unless such a human decision is supplied.
   */
  requestApproval(request: unknown, decision?: ApprovalDecision): ApprovalToken | null {
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

    // Forbidden status overrides any request and is NEVER queued/tokenized (§16/§26); an
    // unknown/unclassifiable action fails closed the same way.
    if (disposition === "forbidden" || disposition === "unknown") {
      this.#emit({
        correlationId: req.correlationId, actorId: "gate", actorType: "system",
        eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
        result: "rejected", status: disposition, riskClass: req.riskClass,
        summary: `approval request rejected (${disposition}): ${req.actionType}`,
      });
      return null;
    }

    const policy = actionPolicy(req.actionType);
    const neverAuto = policy?.neverAuto ?? false;

    if (decision !== undefined) {
      // A malformed decision fails closed.
      if (!isActor(decision.requestedBy) || !isActor(decision.approvedBy)) {
        this.#emit({
          correlationId: req.correlationId, actorId: "gate", actorType: "system",
          eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
          result: "rejected", status: "invalid-approval-decision", riskClass: req.riskClass,
          summary: `approval request rejected (invalid decision): ${req.actionType}`,
        });
        return null;
      }
      // Only a human holds approval authority — agents/tools/system may propose, never approve.
      if (decision.approvedBy.type !== "human") {
        this.#emit({
          correlationId: req.correlationId, actorId: decision.approvedBy.id, actorType: decision.approvedBy.type,
          eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
          result: "rejected", status: "non-human-approver-rejected", riskClass: req.riskClass,
          summary: `approval rejected: ${decision.approvedBy.type} actors cannot approve ${req.actionType}`,
        });
        return null;
      }
      // No self-approval: an actor never approves its own action.
      if (decision.approvedBy.id === decision.requestedBy.id) {
        this.#emit({
          correlationId: req.correlationId, actorId: decision.approvedBy.id, actorType: decision.approvedBy.type,
          eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
          result: "rejected", status: "self-approval-rejected", riskClass: req.riskClass,
          summary: `approval rejected: an actor cannot approve its own ${req.actionType}`,
        });
        return null;
      }
    } else if (neverAuto) {
      // Never-auto: no standing/blanket rule may approve these; without an explicit human
      // decision there is no token (§15).
      this.#emit({
        correlationId: req.correlationId, actorId: "gate", actorType: "system",
        eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
        result: "rejected", status: "requires-human-approval", riskClass: req.riskClass,
        summary: `never-auto action requires explicit human approval: ${req.actionType}`,
      });
      return null;
    }

    // Audit BEFORE minting — if it cannot be audited, fail closed (no token).
    const approver = decision?.approvedBy.id;
    const audited = this.#emit({
      correlationId: req.correlationId, actorId: "gate", actorType: "system",
      eventType: "approval-request", eventCategory: "audit", actionId: req.actionId,
      result: "approved", status: "token-created", riskClass: req.riskClass,
      summary: `token created for ${req.actionType}${approver ? ` (approved by ${approver})` : ""}`,
    });
    if (!audited) return null;

    const token: ApprovalToken = { tokenId: `tok-${++this.#seq}`, actionId: action.id };
    // Bind the approval to the EXACT approved action: id, type, requester, the required scope
    // (derived from the trusted policy — not caller input), and risk. Execution is verified
    // against this binding so it cannot be downgraded.
    this.#live.set(token.tokenId, {
      token,
      correlationId: req.correlationId,
      actionId: req.actionId,
      actionType: req.actionType,
      requiredScope: policy?.requiredScope,
      riskClass: req.riskClass,
      requestedBy: decision?.requestedBy.id ?? "unattributed",
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
      if (!live || live.actionId !== action.id) {
        status = "invalid-or-unbound-token";
        reason = "invalid-or-unbound-token";
        if (live) correlationId = live.correlationId;
      } else if (live.actionType !== action.type) {
        // Downgrade defense (H3): the presented action type must match the APPROVED type, so a
        // caller cannot present a lower-risk type to dodge the permission check.
        correlationId = live.correlationId;
        riskClass = live.riskClass;
        status = "token-action-type-mismatch";
        reason = "token-action-type-mismatch";
      } else {
        correlationId = live.correlationId;
        riskClass = live.riskClass;
        // Scope comes from the APPROVED action's binding (trusted policy), never caller input.
        const requiredScope = live.requiredScope;
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
