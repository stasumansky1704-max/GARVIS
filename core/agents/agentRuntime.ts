// GARVIS — Agent Runtime (M4)
//
// The orchestration boundary that takes an agent's PROPOSAL and routes it through the real
// platform pipeline. The agent never touches the pipeline; the runtime does — and only with the
// same Gate/Permission/Tool/Audit everything else uses.
//
// Guarantees:
//   - The runtime NEVER mints approval from an agent's identity or confidence. Approval-gated
//     tool proposals require a human-approved token passed in by the caller; without it they are
//     denied (no auto-approval, no self-approval).
//   - The runtime grants no permission and writes no durable memory on an agent's behalf (it may
//     READ memory for a memory-read proposal — reads are non-mutating).
//   - Routing happens exactly ONCE per call: a denial is returned, never auto-retried.
//   - It records routing to the canonical audit (orchestration → observability); the AGENT does
//     not write audit records.

import type { RuntimeContext } from "../runtime/runtimeContext.ts";
import type { ApprovalToken } from "../approval-gate/approvalGate.ts";
import type { AgentProposal } from "./agentTypes.ts";

export interface RouteOptions {
  /** A human-approved single-use token for approval-gated tool proposals. */
  readonly token?: ApprovalToken | null;
}

export interface RouteResult {
  readonly kind: string;
  readonly ok: boolean;
  readonly status: string;
  readonly output?: string;
}

export class AgentRuntime {
  #ctx: RuntimeContext;

  constructor(ctx: RuntimeContext) {
    this.#ctx = ctx;
  }

  #audit(proposal: AgentProposal, status: string, summary: string): void {
    try {
      this.#ctx.audit.append({
        correlationId: proposal.correlationId, actorId: "agent-runtime", actorType: "system",
        eventType: "agent-proposal", eventCategory: "orchestration", actionId: proposal.tool ?? proposal.memoryKey,
        result: "routed", status,
        summary,
      });
    } catch {
      // best-effort orchestration log; any gated effect is independently audited (fail-closed)
      // inside the Gate / Tool Sandbox.
    }
  }

  #result(proposal: AgentProposal, ok: boolean, status: string, output?: string): RouteResult {
    return { kind: proposal.kind, ok, status, output };
  }

  /** Route ONE proposal through the pipeline. No auto-retry, no auto-approval. */
  route(proposal: AgentProposal, options: RouteOptions = {}): RouteResult {
    // Confidence is advisory only — recorded, never used to authorize.
    this.#audit(
      proposal, "received",
      `routing ${proposal.kind} from ${proposal.proposedBy} (confidence ${proposal.confidence})`,
    );

    if (proposal.kind === "memory-read") {
      if (!proposal.memoryKey) return this.#result(proposal, false, "missing-memory-key");
      const record = this.#ctx.memory.read(proposal.memoryKey);
      return record === undefined
        ? this.#result(proposal, false, "not-found")
        : this.#result(proposal, true, "read", record.value);
    }

    // tool-call: route through the Tool Sandbox (permission + approval + audit).
    if (!proposal.tool) return this.#result(proposal, false, "missing-tool");
    const def = this.#ctx.tools.get(proposal.tool);
    if (!def) return this.#result(proposal, false, "unknown-tool");

    const result = this.#ctx.sandbox.invoke({
      tool: proposal.tool,
      input: proposal.input,
      correlationId: proposal.correlationId,
      action: { id: proposal.tool, type: def.metadata.actionType },
      token: options.token,
    });
    return this.#result(proposal, result.ok, result.status, result.output);
  }
}
