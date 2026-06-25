// GARVIS — Project Daily Brief workflow (M5)
//
// The first mock workflow. Shape:
//   1. start
//   2. read the (mock) project status via the safe project-reader tool   [local:read]
//   3. an agent summarizes the status into a brief                        [propose-only agent]
//   4. an agent proposes the brief write; the workflow PAUSES for approval
//   5. (human approves via the Gate, out of band)
//   6. on resume, the safe write tool writes the brief                    [local:write + approval]
//   7. audit/telemetry recorded throughout
//   8. complete
//
// The workflow OWNS nothing: it routes the read/write through the Tool Sandbox (which enforces
// permission + approval + audit) and calls the injected agents to summarize/propose. No real
// external calls; no destructive actions.

import type { SummaryAgent } from "../agents/summaryAgent.ts";
import type { PlanningAgent } from "../agents/planningAgent.ts";
import type { WorkflowDefinition } from "./workflowTypes.ts";
import type { WorkflowManifest } from "./workflowManifest.ts";

export const PROJECT_DAILY_BRIEF_ID = "project-daily-brief";

export interface DailyBriefDeps {
  readonly summarizer: SummaryAgent;
  readonly planner: PlanningAgent;
  readonly briefPath?: string;
}

/** Library manifest for the Daily Brief: a GATED workflow (it writes a file behind approval). */
export function projectDailyBriefManifest(): WorkflowManifest {
  return {
    workflowId: PROJECT_DAILY_BRIEF_ID,
    name: "Project Daily Brief",
    category: "project",
    description: "Reads status, summarizes, and writes an approved daily brief (gated write).",
    riskClass: "gated",
    requiredPermissions: ["local:read", "local:write"],
    requiresApproval: true,
    steps: [
      { name: "read-project", effect: "read" },
      { name: "summarize", effect: "agent" },
      { name: "propose-write-and-pause", effect: "control" },
      { name: "write-brief", effect: "write" },
    ],
    version: "1",
    status: "active",
    tags: ["project", "brief", "gated"],
  };
}

export function projectDailyBriefWorkflow(deps: DailyBriefDeps): WorkflowDefinition {
  const briefPath = deps.briefPath ?? "out/daily-brief.md";
  const writeActionId = "daily-brief-write";

  return {
    name: "project-daily-brief",
    steps: [
      {
        name: "start",
        run(io) {
          io.state.set("wf.started", true);
          return { control: "continue" };
        },
      },
      {
        name: "read-project",
        run(io) {
          const r = io.sandbox.invoke({
            tool: "project.read", input: {}, correlationId: io.correlationId,
            action: { id: "project.read", type: "local.read" },
          });
          if (!r.ok) return { control: "fail", note: `read:${r.status}` };
          io.state.set("wf.projectStatus", r.output ?? "");
          return { control: "continue" };
        },
      },
      {
        name: "summarize",
        run(io) {
          const status = String(io.state.get("wf.projectStatus") ?? "");
          const result = deps.summarizer.summarize({ role: "system", content: status, correlationId: io.correlationId });
          io.state.set("wf.brief", result.summary);
          return { control: "continue" };
        },
      },
      {
        name: "propose-write-and-pause",
        run(io) {
          // The planner proposes the write; the workflow surfaces an approval request and PAUSES.
          // It does NOT approve — a human approves via the Gate before resume.
          const proposals = deps.planner.propose({ role: "system", content: "write daily brief", correlationId: io.correlationId });
          io.state.set("wf.proposalCount", proposals.length);
          return {
            control: "pause-for-approval",
            approval: { actionId: writeActionId, actionType: "local.write", correlationId: io.correlationId },
          };
        },
      },
      {
        name: "write-brief",
        run(io) {
          const brief = String(io.state.get("wf.brief") ?? "");
          const r = io.sandbox.invoke({
            tool: "fs.writeTextFileApproved", input: { path: briefPath, content: brief },
            correlationId: io.correlationId,
            action: { id: writeActionId, type: "local.write" }, token: io.approvalToken,
          });
          if (!r.ok) return { control: "fail", note: `write:${r.status}` };
          io.state.set("wf.written", true);
          return { control: "continue" };
        },
      },
    ],
  };
}
