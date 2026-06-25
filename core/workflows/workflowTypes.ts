// GARVIS — Workflow models (M5)
//
// A workflow COORDINATES; it owns nothing. Steps receive a WorkflowIO of services they route
// effects through (sandbox/agents) — they do not own permissions, the gate, memory, tools, or
// the canonical audit. Every effecting step still goes Contract → Permission → Approval → Audit
// by routing through the Tool Sandbox / Approval Gate.

import type { StateManager } from "../state/stateManager.ts";
import type { MemoryReader } from "../memory/memoryRuntime.ts";
import type { ToolRegistry } from "../tools/toolRegistry.ts";
import type { ToolSandbox } from "../tools/toolSandbox.ts";
import type { AgentRuntime } from "../agents/agentRuntime.ts";
import type { ApprovalToken } from "../approval-gate/approvalGate.ts";

export type WorkflowStatus = "pending" | "running" | "paused-for-approval" | "completed" | "failed";
export type StepControl = "continue" | "pause-for-approval" | "fail";

export interface ApprovalRequestData {
  readonly actionId: string;
  readonly actionType: string;
  readonly correlationId: string;
}

export interface WorkflowIO {
  readonly correlationId: string;
  readonly state: StateManager;
  /** Read-only facade — the workflow can never write durable memory (no writer capability). */
  readonly memory: MemoryReader;
  readonly tools: ToolRegistry;
  readonly sandbox: ToolSandbox;
  readonly agents: AgentRuntime;
  /** Present only after an approval resume; consumed by the step that needs it. */
  readonly approvalToken?: ApprovalToken | null;
}

export interface WorkflowStepOutcome {
  readonly control: StepControl;
  readonly note?: string;
  /** Supplied when control === "pause-for-approval": what a human must approve. */
  readonly approval?: ApprovalRequestData;
}

export interface WorkflowStep {
  readonly name: string;
  run(io: WorkflowIO): WorkflowStepOutcome;
}

export interface WorkflowDefinition {
  readonly name: string;
  readonly steps: readonly WorkflowStep[];
}

/** Minimal retry policy. Authorization/permission denials are terminal (never auto-retried). */
export interface RetryPolicy {
  readonly maxRetries: number;
}

export interface WorkflowState {
  readonly definition: string;
  readonly correlationId: string;
  status: WorkflowStatus;
  stepIndex: number;
  retries: number;
  lastCheckpointId?: string;
  pendingApproval?: ApprovalRequestData;
  failedStep?: string;
}
