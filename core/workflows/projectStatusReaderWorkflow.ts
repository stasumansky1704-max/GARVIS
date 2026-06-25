// GARVIS — Project Status Reader workflow (first real Workflow Library entry)
//
// READ-ONLY. Reads the local (mock) project status via the safe project-reader tool, summarizes
// it with a propose-only agent, and returns a redacted, audited status result.
//
// It needs local:read, needs NO approval, writes NO files, writes NO memory, mints NO approval
// token, makes NO network/command calls. Every effect goes through the existing runtime path:
//   Workflow → Tool Sandbox → Permission Runtime → Audit Runtime → Result.

import type { RuntimeContext } from "../runtime/runtimeContext.ts";
import { AgentRuntime } from "../agents/agentRuntime.ts";
import { SummaryAgent } from "../agents/summaryAgent.ts";
import { WorkflowRunner } from "./workflowRunner.ts";
import type { WorkflowDefinition } from "./workflowTypes.ts";
import type { WorkflowManifest } from "./workflowManifest.ts";

export const PROJECT_STATUS_READER_ID = "project-status-reader";
const SUMMARY_STATE_KEY = "statusReader.summary";

export function projectStatusReaderManifest(): WorkflowManifest {
  return {
    workflowId: PROJECT_STATUS_READER_ID,
    name: "Project Status Reader",
    category: "project",
    description: "Reads and summarizes the local project status (read-only, redacted, audited).",
    riskClass: "read-only",
    requiredPermissions: ["local:read"],
    requiresApproval: false,
    steps: [
      { name: "read-project", effect: "read" },
      { name: "summarize", effect: "agent" },
    ],
    version: "1",
    status: "active",
    tags: ["read-only", "project", "status"],
  };
}

export function projectStatusReaderWorkflow(deps: { summarizer?: SummaryAgent } = {}): WorkflowDefinition {
  const summarizer = deps.summarizer ?? new SummaryAgent();
  return {
    name: PROJECT_STATUS_READER_ID,
    steps: [
      {
        name: "read-project",
        run(io) {
          const r = io.sandbox.invoke({
            tool: "project.read", input: {}, correlationId: io.correlationId,
            action: { id: "project.read", type: "local.read" },
          });
          if (!r.ok) return { control: "fail", note: `read:${r.status}` };
          io.state.set("statusReader.raw", r.output ?? "");
          return { control: "continue" };
        },
      },
      {
        name: "summarize",
        run(io) {
          const raw = String(io.state.get("statusReader.raw") ?? "");
          const result = summarizer.summarize({ role: "system", content: raw, correlationId: io.correlationId });
          io.state.set(SUMMARY_STATE_KEY, result.summary);
          return { control: "continue" };
        },
      },
    ],
  };
}

export interface StatusReaderResult {
  readonly ok: boolean;
  readonly status: string;
  /** Redacted status summary (present only on success). */
  readonly summary?: string;
}

/**
 * Run the Project Status Reader through the existing Workflow Runner and return its redacted
 * result. No approval, no write, no memory, no token — fails closed without local:read.
 */
export function runProjectStatusReader(ctx: RuntimeContext, correlationId: string): StatusReaderResult {
  const definition = projectStatusReaderWorkflow();
  const runner = new WorkflowRunner(ctx, new AgentRuntime(ctx));
  const state = runner.start(definition, correlationId);
  if (state.status !== "completed") {
    return { ok: false, status: state.failedStep ? `failed:${state.failedStep}` : state.status };
  }
  return { ok: true, status: "completed", summary: String(ctx.state.get(SUMMARY_STATE_KEY) ?? "") };
}
