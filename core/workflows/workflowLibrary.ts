// GARVIS — Workflow Library / Catalog (Workflow Library foundation)
//
// An in-memory catalog of workflow manifests (+ optional executable definitions). It lets GARVIS
// DISCOVER, LIST, VALIDATE, and RUN safe workflows. It owns no permissions/approval/audit of its
// own — running a workflow goes through the existing Workflow Runner, which routes every effect
// through the Tool Sandbox / Approval Gate / Permission Runtime / Audit Runtime.
//
// Validation fails closed: malformed manifests and duplicate ids are rejected at registration.

import type { RuntimeContext } from "../runtime/runtimeContext.ts";
import { AgentRuntime } from "../agents/agentRuntime.ts";
import { WorkflowRunner } from "./workflowRunner.ts";
import type { WorkflowDefinition, WorkflowState } from "./workflowTypes.ts";
import { classifyWorkflow, validateWorkflowManifest } from "./workflowManifest.ts";
import type { WorkflowManifest, WorkflowPolicy } from "./workflowManifest.ts";

export class WorkflowLibraryError extends Error {
  constructor(reason: string) {
    super(reason);
    this.name = "WorkflowLibraryError";
  }
}

export interface WorkflowEntry {
  readonly manifest: WorkflowManifest;
  readonly policyClass: WorkflowPolicy;
  /** Executable definition, if this workflow can be run through the library. */
  readonly definition?: WorkflowDefinition;
}

export class WorkflowLibrary {
  #entries = new Map<string, WorkflowEntry>();

  /** Register a manifest (+ optional definition). Rejects malformed manifests and duplicate ids. */
  register(manifest: WorkflowManifest, definition?: WorkflowDefinition): WorkflowEntry {
    const validation = validateWorkflowManifest(manifest);
    if (!validation.ok) {
      throw new WorkflowLibraryError(`malformed-manifest:${validation.errors.join(",")}`);
    }
    if (this.#entries.has(manifest.workflowId)) {
      throw new WorkflowLibraryError(`duplicate-workflow-id:${manifest.workflowId}`);
    }
    const entry: WorkflowEntry = Object.freeze({
      manifest,
      policyClass: classifyWorkflow(manifest),
      definition,
    });
    this.#entries.set(manifest.workflowId, entry);
    return entry;
  }

  get(workflowId: string): WorkflowEntry | undefined {
    return this.#entries.get(workflowId);
  }

  has(workflowId: string): boolean {
    return this.#entries.has(workflowId);
  }

  list(): readonly WorkflowEntry[] {
    return [...this.#entries.values()];
  }

  policyClassOf(workflowId: string): WorkflowPolicy | undefined {
    return this.#entries.get(workflowId)?.policyClass;
  }

  /** Group entries by manifest category. */
  byCategory(): ReadonlyMap<string, readonly WorkflowEntry[]> {
    const grouped = new Map<string, WorkflowEntry[]>();
    for (const entry of this.#entries.values()) {
      const list = grouped.get(entry.manifest.category) ?? [];
      list.push(entry);
      grouped.set(entry.manifest.category, list);
    }
    return grouped;
  }

  listByCategory(category: string): readonly WorkflowEntry[] {
    return [...this.#entries.values()].filter((e) => e.manifest.category === category);
  }

  /**
   * Run a registered workflow through the existing Workflow Runner (no bypass). Returns the
   * resulting WorkflowState (a gated workflow will pause for approval). Throws if the workflow is
   * unknown or has no executable definition.
   */
  run(workflowId: string, ctx: RuntimeContext, correlationId: string): WorkflowState {
    const entry = this.#entries.get(workflowId);
    if (!entry) throw new WorkflowLibraryError(`unknown-workflow:${workflowId}`);
    if (!entry.definition) throw new WorkflowLibraryError(`no-definition:${workflowId}`);
    const runner = new WorkflowRunner(ctx, new AgentRuntime(ctx));
    return runner.start(entry.definition, correlationId);
  }
}
