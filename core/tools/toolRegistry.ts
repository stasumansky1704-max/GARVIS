// GARVIS — Tool Registry (M2 core; hardened H1)
//
// Registers tool ADAPTERS (metadata + an optional pure handler). It does NOT execute tools.
//
// H1 — tools CANNOT self-declare themselves safe. A tool declares only its `actionType`; whether
// it needs approval and which permission scope it requires are DERIVED from the trusted action
// policy (core/capabilities/actionPolicy), never from the tool. Registration FAILS CLOSED for an
// unknown action type or a forbidden capability, so an unsafe/mislabeled tool cannot enter the
// registry at all. One authority per capability: a duplicate name is rejected.

import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit } from "../audit/auditRuntime.ts";
import { actionPolicy } from "../capabilities/actionPolicy.ts";

export class ToolError extends Error {
  constructor(reason: string) {
    super(reason);
    this.name = "ToolError";
  }
}

export interface ToolMetadata {
  readonly name: string;
  readonly version: string;
  readonly capability: string;
  /** The trusted action type this tool performs — MUST exist in the action policy. */
  readonly actionType: string;
  readonly description: string;
}

export interface ToolContext {
  readonly correlationId: string;
}

export interface ToolResult {
  readonly ok: boolean;
  /** Stable, machine-readable status, safe to audit (no secrets). */
  readonly status: string;
  /** Optional text output; redacted by the sandbox before audit/memory. */
  readonly output?: string;
}

export interface ToolDefinition {
  readonly metadata: ToolMetadata;
  /** Pure handler. Absent in registry-only tools; provided by safe/mock tools. */
  run?(input: unknown, ctx: ToolContext): ToolResult;
}

function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

export class ToolRegistry {
  #tools = new Map<string, ToolDefinition>();
  #audit: Audit;

  constructor(audit: Audit = new AuditRuntime()) {
    this.#audit = audit;
  }

  /**
   * Register a tool adapter. Validates (H1) that the declared action type is known and not
   * forbidden — the required permission/approval policy is derived from it, never self-declared.
   * One authority per capability — duplicate names are rejected.
   */
  register(def: ToolDefinition, correlationId = "tool-registry"): void {
    const md = def.metadata;
    if (!isNonEmptyString(md?.name)) throw new ToolError("invalid-tool-name");
    if (!isNonEmptyString(md.actionType)) throw new ToolError(`invalid-action-type:${md.name}`);
    if (this.#tools.has(md.name)) throw new ToolError(`duplicate-tool:${md.name}`);

    const policy = actionPolicy(md.actionType);
    if (!policy) throw new ToolError(`unknown-action-type:${md.actionType}`);
    if (policy.disposition === "forbidden") throw new ToolError(`forbidden-capability:${md.actionType}`);

    this.#tools.set(md.name, def);
    this.#audit.append({
      correlationId, actorId: "tool-registry", actorType: "system",
      eventType: "tool-registered", eventCategory: "tool", actionId: md.name,
      result: "registered", status: policy.disposition,
      summary: `registered tool ${md.name} (${md.capability}, ${md.actionType})`,
    });
  }

  get(name: string): ToolDefinition | undefined {
    return this.#tools.get(name);
  }

  has(name: string): boolean {
    return this.#tools.has(name);
  }

  list(): readonly ToolMetadata[] {
    return [...this.#tools.values()].map((d) => d.metadata);
  }
}
