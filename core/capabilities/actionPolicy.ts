// GARVIS — Action-Type Policy (M5 single source; foundation for H1 + H3)
//
// The SINGLE trusted definition of what each action type means: its Approval Gate disposition,
// the permission scope it requires, whether it needs an approval token, and whether it is in the
// never-auto set. Both the Approval Gate and the Tool Sandbox derive their decisions from here —
// there is no second scope map and no self-declared tool safety.
//
// Adding/altering a capability is an explicit, reviewable edit to THIS table — not something a
// tool author can do by setting a metadata flag.

import type { PermissionScope } from "../permissions/permissionRuntime.ts";

export type Disposition = "auto" | "gated" | "forbidden";

export interface ActionPolicy {
  /** Approval Gate classification of the action. */
  readonly disposition: Disposition;
  /** Permission scope the action requires (undefined = informational, no scope). */
  readonly requiredScope?: PermissionScope;
  /** Whether execution requires a single-use approval token (gated effecting types). */
  readonly requiresApproval: boolean;
  /** §15 never-auto: requires explicit, per-instance human approval; no standing rule may grant it. */
  readonly neverAuto: boolean;
}

const ACTION_POLICY: ReadonlyMap<string, ActionPolicy> = new Map([
  ["informational",     { disposition: "auto",      requiredScope: undefined,             requiresApproval: false, neverAuto: false }],
  ["local.read",        { disposition: "auto",      requiredScope: "local:read",          requiresApproval: false, neverAuto: false }],
  ["external.read",     { disposition: "gated",     requiredScope: "external:read",       requiresApproval: false, neverAuto: false }],
  ["local.write",       { disposition: "gated",     requiredScope: "local:write",         requiresApproval: true,  neverAuto: false }],
  ["external.write",    { disposition: "gated",     requiredScope: "external:write",      requiresApproval: true,  neverAuto: true  }],
  ["execution.command", { disposition: "gated",     requiredScope: "execution:command",   requiresApproval: true,  neverAuto: true  }],
  ["destructive",       { disposition: "gated",     requiredScope: "destructive",         requiresApproval: true,  neverAuto: true  }],
  ["credential",        { disposition: "forbidden", requiredScope: "credential:sensitive", requiresApproval: true,  neverAuto: true  }],
]) as ReadonlyMap<string, ActionPolicy>;

/** The trusted policy for an action type, or undefined if the type is unknown (fail closed). */
export function actionPolicy(actionType: string): ActionPolicy | undefined {
  return ACTION_POLICY.get(actionType);
}

export function knownActionType(actionType: string): boolean {
  return ACTION_POLICY.has(actionType);
}

/** Gate classification, with unknown types failing closed to "unknown". */
export function dispositionOf(actionType: string): Disposition | "unknown" {
  return ACTION_POLICY.get(actionType)?.disposition ?? "unknown";
}
