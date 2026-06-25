// GARVIS — Tool Sandbox (hardened H1 + H3 + M2)
//
// The ONLY path that invokes a tool's handler. It fails closed and enforces, in order:
//   1. Unknown tool / unknown action type / forbidden capability → denied.
//   2. Approval-gated action → routed through the Approval Gate (token + permission). The action
//      TYPE comes from the tool's TRUSTED metadata, not caller input, so it cannot be downgraded.
//   3. Non-approval read action → deny-by-default permission check for its required scope.
//   4. Handler missing → "not-implemented".
//   5. M2 — the invocation is audited BEFORE the handler runs; if it cannot be recorded the tool
//      does NOT execute (reads included). The outcome is audited (redacted) afterward, also
//      fail-closed.
//
// Whether a tool needs approval and which scope it requires are DERIVED from the trusted action
// policy — never self-declared by the tool. The sandbox holds no permissions/approval logic of
// its own; it composes the Permission Runtime and the Approval Gate. No I/O, no network.

import { redactText } from "../redaction/redactText.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit } from "../audit/auditRuntime.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";
import { ApprovalGate } from "../approval-gate/approvalGate.ts";
import type { ApprovalToken, ProposedAction } from "../approval-gate/approvalGate.ts";
import type { ToolRegistry, ToolResult } from "./toolRegistry.ts";
import { actionPolicy } from "../capabilities/actionPolicy.ts";

export interface ToolInvocation {
  readonly tool: string;
  readonly input?: unknown;
  readonly correlationId: string;
  /** Action identity for gated tools; ONLY the id is used — the type comes from trusted metadata. */
  readonly action?: ProposedAction;
  /** Single-use approval token for approval-gated tools. */
  readonly token?: ApprovalToken | null;
}

export class ToolSandbox {
  #registry: ToolRegistry;
  #permissions: PermissionRuntime;
  #gate: ApprovalGate;
  #audit: Audit;

  constructor(
    registry: ToolRegistry,
    permissions: PermissionRuntime = new PermissionRuntime(),
    gate: ApprovalGate = new ApprovalGate(),
    audit: Audit = new AuditRuntime(),
  ) {
    this.#registry = registry;
    this.#permissions = permissions;
    this.#gate = gate;
    this.#audit = audit;
  }

  /** Append one tool-invocation audit event. Returns false if it could not be recorded. */
  #tryAudit(inv: ToolInvocation, result: string, status: string, output?: string): boolean {
    try {
      this.#audit.append({
        correlationId: inv.correlationId, actorId: "tool-sandbox", actorType: "system",
        eventType: "tool-invocation", eventCategory: "tool", actionId: inv.tool,
        result, status,
        summary: `tool ${inv.tool}: ${status}${output ? ` -> ${output}` : ""}`,
      });
      return true;
    } catch {
      return false;
    }
  }

  #deny(inv: ToolInvocation, status: string): ToolResult {
    this.#tryAudit(inv, "rejected", status); // the denial stands regardless of audit success
    return { ok: false, status };
  }

  /** Invoke a tool through all safety gates. Fails closed on every uncertainty. */
  invoke(inv: ToolInvocation): ToolResult {
    const def = this.#registry.get(inv.tool);
    if (!def) return this.#deny(inv, "unknown-tool");

    const policy = actionPolicy(def.metadata.actionType);
    if (!policy) return this.#deny(inv, "unknown-action-type"); // defense in depth (registry rejects)
    if (policy.disposition === "forbidden") return this.#deny(inv, "forbidden-capability");

    if (policy.requiresApproval) {
      // Type from TRUSTED metadata — not caller input — so the approved scope cannot be downgraded.
      const action: ProposedAction = { id: inv.action?.id ?? inv.tool, type: def.metadata.actionType };
      const auth = this.#gate.authorizeExecution(action, inv.token);
      if (!auth.allowed) return this.#deny(inv, `denied:${auth.reason}`);
    } else if (policy.requiredScope !== undefined) {
      const permission = this.#permissions.check({ scope: policy.requiredScope });
      if (!permission.allowed) return this.#deny(inv, `permission-denied:${permission.reason}`);
    }

    if (!def.run) return this.#deny(inv, "not-implemented");

    // M2 — FAIL CLOSED: record the invocation BEFORE executing. If it cannot be recorded, the
    // tool does NOT run (reads included).
    if (!this.#tryAudit(inv, "authorized", "invoking")) {
      return { ok: false, status: "audit-failure" };
    }

    let result: ToolResult;
    try {
      result = def.run(inv.input, { correlationId: inv.correlationId });
    } catch {
      return this.#deny(inv, "tool-error");
    }

    const output = result.output === undefined ? undefined : redactText(result.output);
    // M2 — FAIL CLOSED: record the outcome (redacted). If it cannot be recorded, report failure.
    if (!this.#tryAudit(inv, result.ok ? "executed" : "failed", result.status, output)) {
      return { ok: false, status: "audit-failure" };
    }
    return { ok: result.ok, status: result.status, output };
  }
}
