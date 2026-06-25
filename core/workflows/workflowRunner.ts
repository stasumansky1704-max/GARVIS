// GARVIS — Workflow Runner (M5)
//
// Drives a WorkflowDefinition step by step. It checkpoints after each step, PAUSES for human
// approval before any gated write, and RESUMES with the human-supplied token. It fails closed:
// a denied/permission/throwing step ends the run, preserving the last good checkpoint, and an
// authorization denial is NEVER auto-retried.
//
// The runner coordinates only. It holds no permissions and no approval logic of its own — gated
// effects route through the Tool Sandbox / Approval Gate inside each step. It emits workflow
// lifecycle telemetry to observability; the canonical security audit (approval/execution) is
// written by the Gate, not the workflow.

import type { RuntimeContext } from "../runtime/runtimeContext.ts";
import type { AgentRuntime } from "../agents/agentRuntime.ts";
import type { ApprovalToken } from "../approval-gate/approvalGate.ts";
import type {
  RetryPolicy, WorkflowDefinition, WorkflowIO, WorkflowState, WorkflowStepOutcome,
} from "./workflowTypes.ts";

export class WorkflowRunner {
  #ctx: RuntimeContext;
  #agents: AgentRuntime;
  #retry: RetryPolicy;

  constructor(ctx: RuntimeContext, agents: AgentRuntime, retry: RetryPolicy = { maxRetries: 0 }) {
    this.#ctx = ctx;
    this.#agents = agents;
    this.#retry = retry;
  }

  #telemetry(correlationId: string, status: string, summary: string): void {
    try {
      this.#ctx.audit.append({
        correlationId, actorId: "workflow-runner", actorType: "system",
        eventType: "workflow", eventCategory: "orchestration", result: "reported", status, summary,
      });
    } catch {
      // lifecycle telemetry is best-effort; gated effects are independently (and fail-closed) audited.
    }
  }

  /** Start a workflow: telemetry + first-step checkpoint, then run until pause/complete/fail. */
  start(definition: WorkflowDefinition, correlationId: string): WorkflowState {
    const state: WorkflowState = {
      definition: definition.name, correlationId, status: "running", stepIndex: 0, retries: 0,
    };
    this.#telemetry(correlationId, "started", `workflow ${definition.name} started`);
    const cp = this.#ctx.checkpoints.create(`${definition.name}:start`, this.#ctx.state.snapshot(), correlationId);
    state.lastCheckpointId = cp.id;
    return this.#run(definition, state, undefined);
  }

  /**
   * Compensation (placeholder): restore working state to the last good checkpoint. The MVP has
   * no irreversible effects to compensate; this rolls the in-memory state back to a known point.
   */
  rollback(state: WorkflowState): WorkflowState {
    if (state.lastCheckpointId === undefined) return state;
    const snapshot = this.#ctx.checkpoints.restore(state.lastCheckpointId);
    this.#ctx.state.restore(snapshot);
    this.#telemetry(state.correlationId, "rolled-back", `${state.definition} rolled back to ${state.lastCheckpointId}`);
    return state;
  }

  /** Resume a paused workflow with a human-approved token. */
  resume(definition: WorkflowDefinition, state: WorkflowState, token?: ApprovalToken | null): WorkflowState {
    if (state.status !== "paused-for-approval") return state;
    state.status = "running";
    this.#telemetry(state.correlationId, "resumed", `workflow ${definition.name} resumed`);
    return this.#run(definition, state, token);
  }

  #run(definition: WorkflowDefinition, state: WorkflowState, token?: ApprovalToken | null): WorkflowState {
    let approval = token;
    while (state.stepIndex < definition.steps.length) {
      const step = definition.steps[state.stepIndex]!;
      const io: WorkflowIO = {
        correlationId: state.correlationId,
        state: this.#ctx.state,
        memory: this.#ctx.memory,
        tools: this.#ctx.tools,
        sandbox: this.#ctx.sandbox,
        agents: this.#agents,
        approvalToken: approval,
      };

      // Retry policy applies ONLY to genuinely thrown (transient) steps, up to maxRetries. A
      // step that returns control "fail" (e.g. an authorization/permission denial) is terminal
      // and is never auto-retried.
      let outcome: WorkflowStepOutcome;
      let attempts = 0;
      for (;;) {
        try {
          outcome = step.run(io);
          break;
        } catch {
          attempts += 1;
          state.retries += 1;
          if (attempts > this.#retry.maxRetries) {
            outcome = { control: "fail", note: "step-threw" };
            break;
          }
        }
      }
      this.#telemetry(state.correlationId, `step:${step.name}:${outcome.control}`, `${definition.name}/${step.name}`);

      if (outcome.control === "pause-for-approval") {
        state.pendingApproval = outcome.approval;
        state.stepIndex += 1; // advance past the approval step so resume runs the next step
        state.status = "paused-for-approval";
        const cp = this.#ctx.checkpoints.create(
          `${definition.name}:${step.name}:paused`, this.#ctx.state.snapshot(), state.correlationId,
        );
        state.lastCheckpointId = cp.id;
        return state;
      }

      if (outcome.control === "fail") {
        // Fail closed: do not auto-retry an authorization/permission denial. The last good
        // checkpoint is preserved (we do not overwrite it on failure).
        state.status = "failed";
        state.failedStep = step.name;
        this.#telemetry(state.correlationId, "failed", `${definition.name}/${step.name}: ${outcome.note ?? ""}`);
        return state;
      }

      // continue
      state.stepIndex += 1;
      const cp = this.#ctx.checkpoints.create(
        `${definition.name}:${step.name}:done`, this.#ctx.state.snapshot(), state.correlationId,
      );
      state.lastCheckpointId = cp.id;
      approval = undefined; // single-use approval is consumed by the step that needed it
    }

    state.status = "completed";
    this.#telemetry(state.correlationId, "completed", `workflow ${definition.name} completed`);
    return state;
  }
}
