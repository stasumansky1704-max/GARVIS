// GARVIS — Planning Agent (M4)
//
// Single responsibility: turn a goal message into PROPOSALS. It holds no gate/permission/tool/
// memory references and therefore cannot execute, approve, grant, or write anything. Output is
// inert data routed later by the Agent Runtime.

import type { AgentMessage, AgentProposal, ProposingAgent } from "./agentTypes.ts";

export class PlanningAgent implements ProposingAgent {
  id = "agent:planner";
  role = "planning";

  propose(message: AgentMessage): readonly AgentProposal[] {
    const correlationId = message.correlationId;
    return [
      {
        kind: "memory-read", proposedBy: this.id, correlationId, confidence: 0.6,
        rationale: "recall the previous brief before planning a new one",
        memoryKey: "project.lastBrief",
      },
      {
        kind: "tool-call", proposedBy: this.id, correlationId, confidence: 0.8,
        rationale: "read current project status to base the brief on",
        tool: "project.read", input: {}, actionType: "local.read",
      },
    ];
  }
}
