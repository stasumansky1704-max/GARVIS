// GARVIS Intel Hub — STATIC display data.
//
// This is local, hand-authored PREVIEW data. The Intel Hub is a DISPLAY layer only: it never
// calls the runtime, never executes a tool / workflow / agent, never requests approval, and never
// mutates anything. When a live read-only runtime→UI status bridge exists, replace these
// constants with status snapshots — the components below stay the same.
//
// Event lines mirror the real runtime's audit vocabulary (eventType · target · status) and are
// already redacted summaries — there are no secrets here.

export const INTEL_DATA_SOURCE = "static-preview" as const;

export type Health = "ok" | "secure" | "active" | "idle" | "locked" | "waiting";

export const HEALTH_COLOR: Record<Health, string> = {
  ok: "#34d399",       // emerald — operational
  secure: "#38bdf8",   // cyan — enforced / protected
  active: "#7dd3fc",   // pale energy — in use
  idle: "#64748b",     // slate — quiet
  locked: "#fbbf24",   // amber — gated / not yet enabled
  waiting: "#fbbf24",  // amber — awaiting approval
};

export interface StatusRow {
  readonly label: string;
  readonly value: string;
  readonly health: Health;
}

// 2 — Runtime Status
export const RUNTIME_MODULES: readonly StatusRow[] = [
  { label: "Core Runtime", value: "Operational", health: "ok" },
  { label: "Approval Gate", value: "Enforcing", health: "secure" },
  { label: "Permissions", value: "Deny-by-default", health: "secure" },
  { label: "Audit", value: "Append-only", health: "ok" },
  { label: "Memory", value: "Single-writer", health: "secure" },
  { label: "Workflows", value: "2 registered", health: "active" },
];

// 3 — Workflows
export interface WorkflowRow {
  readonly name: string;
  readonly policy: string;
  readonly state: string;
  readonly health: Health;
}
export const WORKFLOWS: readonly WorkflowRow[] = [
  { name: "Project Status Reader", policy: "Read-only", state: "Ready", health: "ok" },
  { name: "Project Daily Brief", policy: "Gated", state: "Waiting approval", health: "waiting" },
];

// 4 — Skills
export interface SkillRow {
  readonly name: string;
  readonly state: "Ready" | "Locked";
}
export const SKILLS_SUMMARY = { installed: 5, ready: 1, locked: 4 } as const;
export const SKILLS: readonly SkillRow[] = [
  { name: "Project Status Reader", state: "Ready" },
  { name: "Browser", state: "Locked" },
  { name: "GitHub", state: "Locked" },
  { name: "Docker", state: "Locked" },
  { name: "Command Runner", state: "Locked" },
];

// 5 — Approval Queue (display only — no direct execution)
export interface ApprovalItem {
  readonly workflow: string;
  readonly action: string;
  readonly scope: string;
}
export const APPROVAL_QUEUE: readonly ApprovalItem[] = [
  { workflow: "Project Daily Brief", action: "write daily-brief", scope: "local:write" },
];

// 6 — Audit Stream (redacted summaries only)
export interface AuditLine {
  readonly event: string;
  readonly target: string;
  readonly status: string;
}
export const AUDIT_STREAM: readonly AuditLine[] = [
  { event: "tool-invocation", target: "project.read", status: "executed" },
  { event: "execution-authorization", target: "daily-brief-write", status: "consumed" },
  { event: "memory-write", target: "project.lastBrief", status: "written" },
  { event: "approval-request", target: "daily-brief-write", status: "token-created" },
  { event: "permission-check", target: "local:read", status: "granted" },
  { event: "tool-registered", target: "fs.writeTextFileApproved", status: "gated" },
];

// 7 — Intel Hub
export const INTEL_SIGNALS: readonly StatusRow[] = [
  { label: "Intelligence", value: "Nominal", health: "ok" },
  { label: "Signals", value: "0 active", health: "idle" },
  { label: "Research queue", value: "Idle", health: "idle" },
  { label: "Readiness", value: "Read-only ready", health: "active" },
];

// Projects
export interface ProjectRow {
  readonly name: string;
  readonly state: string;
  readonly health: Health;
}
export const PROJECTS: readonly ProjectRow[] = [
  { name: "GARVIS Core", state: "Hardened", health: "ok" },
];
