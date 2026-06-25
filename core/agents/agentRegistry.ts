// GARVIS — Agent Registry (M4)
//
// Registers bounded, named agent roles (one per id). It stores agents and audits registration;
// it grants them no authority. Agents remain propose-only.

import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit } from "../audit/auditRuntime.ts";
import type { Agent } from "./agentTypes.ts";

export class AgentError extends Error {
  constructor(reason: string) {
    super(reason);
    this.name = "AgentError";
  }
}

export class AgentRegistry {
  #agents = new Map<string, Agent>();
  #audit: Audit;

  constructor(audit: Audit = new AuditRuntime()) {
    this.#audit = audit;
  }

  register(agent: Agent, correlationId = "agent-registry"): void {
    if (this.#agents.has(agent.id)) throw new AgentError(`duplicate-agent:${agent.id}`);
    this.#agents.set(agent.id, agent);
    this.#audit.append({
      correlationId, actorId: agent.id, actorType: "agent",
      eventType: "agent-registered", eventCategory: "orchestration", actionId: agent.id,
      result: "registered", status: agent.role,
      summary: `registered agent ${agent.id} (${agent.role})`,
    });
  }

  get(id: string): Agent | undefined {
    return this.#agents.get(id);
  }

  has(id: string): boolean {
    return this.#agents.has(id);
  }

  list(): readonly Agent[] {
    return [...this.#agents.values()];
  }
}
