// GARVIS — Agent models (M4)
//
// Agents PROPOSE; they never execute, approve, grant, or write. These models are inert data:
// an AgentProposal does nothing on its own — only the Agent Runtime (orchestration) routes it
// through the real Gate/Permission/Tool/Audit pipeline.
//
// Confidence is advisory metadata, NEVER authorization. Consensus among agents is NEVER approval.

export interface AgentMessage {
  readonly role: "user" | "system" | "agent";
  readonly content: string;
  readonly correlationId: string;
}

export type ProposalKind = "tool-call" | "memory-read";

export interface AgentProposal {
  readonly kind: ProposalKind;
  /** The proposing agent's identity (an actor of type "agent"). */
  readonly proposedBy: string;
  readonly correlationId: string;
  /** Advisory only — has no bearing on authorization. */
  readonly confidence: number;
  readonly rationale: string;
  // tool-call:
  readonly tool?: string;
  readonly input?: unknown;
  readonly actionType?: string;
  // memory-read:
  readonly memoryKey?: string;
}

export interface AgentResult {
  readonly producedBy: string;
  readonly correlationId: string;
  /** Redacted text result. */
  readonly summary: string;
}

export interface Agent {
  readonly id: string;
  readonly role: string;
}

/** A single-responsibility agent that only emits proposals. */
export interface ProposingAgent extends Agent {
  propose(message: AgentMessage): readonly AgentProposal[];
}

/** A single-responsibility agent that only emits a result. */
export interface SummarizingAgent extends Agent {
  summarize(message: AgentMessage): AgentResult;
}
