// GARVIS — Summary Agent (M4)
//
// Single responsibility: turn input text into a concise RESULT. Like all agents it holds no
// side-effecting references; it cannot execute/approve/grant/write. Its output is redacted so an
// agent result never carries a raw secret downstream.

import { redactText } from "../redaction/redactText.ts";
import type { AgentMessage, AgentResult, SummarizingAgent } from "./agentTypes.ts";

export class SummaryAgent implements SummarizingAgent {
  id = "agent:summary";
  role = "summary";

  summarize(message: AgentMessage): AgentResult {
    const firstLine = message.content.split("\n")[0] ?? "";
    const summary = redactText(`Daily brief — ${firstLine}`).slice(0, 280);
    return { producedBy: this.id, correlationId: message.correlationId, summary };
  }
}
