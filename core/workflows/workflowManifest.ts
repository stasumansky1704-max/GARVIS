// GARVIS — Workflow Manifest model (Workflow Library foundation)
//
// A manifest DESCRIBES a workflow for the Library/Catalog: identity, category, risk policy,
// required permissions, approval need, declared steps, version, status, tags. It is metadata
// ONLY — the executable WorkflowDefinition lives with the workflow and still routes every effect
// through the runtime path (Sandbox -> Registry -> Permission -> Approval -> Audit). Pure, zero-dep.

export type WorkflowRiskClass = "read-only" | "gated" | "forbidden";
export type WorkflowLifecycle = "active" | "draft" | "deprecated" | "forbidden";
export type WorkflowStepEffect = "read" | "write" | "agent" | "control";
export type WorkflowPolicy = "read-only" | "gated" | "forbidden";

export interface WorkflowManifestStep {
  readonly name: string;
  readonly effect: WorkflowStepEffect;
}

export interface WorkflowManifest {
  readonly workflowId: string;
  readonly name: string;
  readonly category: string;
  readonly description: string;
  readonly riskClass: WorkflowRiskClass;
  readonly requiredPermissions: readonly string[];
  readonly requiresApproval: boolean;
  readonly steps: readonly WorkflowManifestStep[];
  readonly version: string;
  readonly status: WorkflowLifecycle;
  readonly tags: readonly string[];
}

export interface ManifestValidation {
  readonly ok: boolean;
  readonly errors: readonly string[];
}

const RISK: ReadonlySet<string> = new Set(["read-only", "gated", "forbidden"]);
const LIFECYCLE: ReadonlySet<string> = new Set(["active", "draft", "deprecated", "forbidden"]);
const EFFECT: ReadonlySet<string> = new Set(["read", "write", "agent", "control"]);

function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.trim().length > 0;
}
function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === "string");
}

/** Validate a manifest shape (fail-closed). Returns the list of problems; ok === errors.length === 0. */
export function validateWorkflowManifest(input: unknown): ManifestValidation {
  if (input === null || typeof input !== "object") return { ok: false, errors: ["manifest must be an object"] };
  const m = input as Record<string, unknown>;
  const errors: string[] = [];

  if (!isNonEmptyString(m.workflowId)) errors.push("workflowId: required non-empty string");
  if (!isNonEmptyString(m.name)) errors.push("name: required non-empty string");
  if (!isNonEmptyString(m.category)) errors.push("category: required non-empty string");
  if (!isNonEmptyString(m.description)) errors.push("description: required non-empty string");
  if (!isNonEmptyString(m.version)) errors.push("version: required non-empty string");
  if (typeof m.riskClass !== "string" || !RISK.has(m.riskClass)) errors.push("riskClass: read-only|gated|forbidden");
  if (typeof m.status !== "string" || !LIFECYCLE.has(m.status)) errors.push("status: active|draft|deprecated|forbidden");
  if (typeof m.requiresApproval !== "boolean") errors.push("requiresApproval: required boolean");
  if (!isStringArray(m.requiredPermissions)) errors.push("requiredPermissions: required string[]");
  if (!isStringArray(m.tags)) errors.push("tags: required string[]");

  if (!Array.isArray(m.steps) || m.steps.length === 0) {
    errors.push("steps: required non-empty array");
  } else {
    m.steps.forEach((s, i) => {
      const st = s as Record<string, unknown> | null;
      const ok = st !== null && typeof st === "object" && isNonEmptyString(st.name)
        && typeof st.effect === "string" && EFFECT.has(st.effect);
      if (!ok) errors.push("steps[" + i + "]: { name: string, effect: read|write|agent|control } required");
    });
  }

  return { ok: errors.length === 0, errors };
}

/**
 * Derive the EFFECTIVE policy from a manifest (defence-in-depth, independent of the declared
 * riskClass): a forbidden status/class is forbidden; an approval requirement, a gated class, a
 * write step, or a write permission forces "gated"; otherwise read-only.
 */
export function classifyWorkflow(m: WorkflowManifest): WorkflowPolicy {
  if (m.status === "forbidden" || m.riskClass === "forbidden") return "forbidden";
  const hasWriteStep = m.steps.some((s) => s.effect === "write");
  const hasWritePermission = m.requiredPermissions.some((p) => /[:.]write\b/.test(p));
  if (m.requiresApproval || m.riskClass === "gated" || hasWriteStep || hasWritePermission) return "gated";
  return "read-only";
}
