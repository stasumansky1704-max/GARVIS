// GARVIS — Runtime Context (M2)
//
// The composition root for the core runtime: one object that wires the safety core (contracts,
// permissions, gate, audit) together with the M2 runtime services (memory, state, checkpoints,
// tools/sandbox) sharing a SINGLE audit log and clock. Higher layers (tools, agents, workflows)
// receive this context instead of constructing services themselves, so every effect routes
// through the same Gate / Permission / Audit instances.
//
// Pure wiring — no I/O, no globals. Everything is injectable for tests.

import { ContractRegistry, defaultContractRegistry } from "../contracts/contractRegistry.ts";
import { PermissionRuntime } from "../permissions/permissionRuntime.ts";
import { ApprovalGate } from "../approval-gate/approvalGate.ts";
import { AuditRuntime } from "../audit/auditRuntime.ts";
import type { Audit } from "../audit/auditRuntime.ts";
import { MemoryRuntime } from "../memory/memoryRuntime.ts";
import type { MemoryReader, MemoryWriter } from "../memory/memoryRuntime.ts";
import { StateManager } from "../state/stateManager.ts";
import { CheckpointManager } from "../state/checkpointManager.ts";
import { ToolRegistry } from "../tools/toolRegistry.ts";
import { ToolSandbox } from "../tools/toolSandbox.ts";

export interface RuntimeContext {
  readonly correlationId: string;
  readonly audit: Audit;
  readonly registry: ContractRegistry;
  readonly permissions: PermissionRuntime;
  readonly gate: ApprovalGate;
  /** Read-only Memory facade — durable writes require the separately-issued writer capability. */
  readonly memory: MemoryReader;
  readonly state: StateManager;
  readonly checkpoints: CheckpointManager;
  readonly tools: ToolRegistry;
  readonly sandbox: ToolSandbox;
}

export interface RuntimeContextOptions {
  readonly correlationId?: string;
  readonly audit?: Audit;
  readonly registry?: ContractRegistry;
  readonly permissions?: PermissionRuntime;
  readonly gate?: ApprovalGate;
  readonly memory?: MemoryRuntime;
  readonly state?: StateManager;
  readonly checkpoints?: CheckpointManager;
  readonly tools?: ToolRegistry;
  readonly sandbox?: ToolSandbox;
  readonly now?: () => number;
  /**
   * Receives the SINGLE memory-writer capability (the memory authority). If omitted, the writer
   * is claimed at construction and dropped — so no consumer of the context can ever claim it,
   * and durable memory stays read-only to everything downstream.
   */
  readonly onMemoryWriter?: (writer: MemoryWriter) => void;
}

export function createRuntimeContext(options: RuntimeContextOptions = {}): RuntimeContext {
  const audit = options.audit ?? new AuditRuntime(options.now);
  const registry = options.registry ?? defaultContractRegistry();
  const permissions = options.permissions ?? new PermissionRuntime(options.now);
  const gate = options.gate ?? new ApprovalGate(registry, permissions, audit);
  const memory = options.memory ?? new MemoryRuntime({ audit, now: options.now });
  const state = options.state ?? new StateManager();
  const checkpoints = options.checkpoints ?? new CheckpointManager({ audit, now: options.now });
  const tools = options.tools ?? new ToolRegistry(audit);
  const sandbox = options.sandbox ?? new ToolSandbox(tools, permissions, gate, audit);

  // Claim the single writer capability at construction so no downstream consumer (agent / tool /
  // workflow) can claim it. Hand it to the authority callback if one was provided; otherwise it
  // is dropped and durable memory is effectively read-only for the lifetime of this context.
  let writer: MemoryWriter | undefined;
  try {
    writer = memory.claimWriter();
  } catch {
    writer = undefined; // an injected memory whose writer was already claimed by the caller
  }
  if (writer && options.onMemoryWriter) options.onMemoryWriter(writer);

  return {
    correlationId: options.correlationId ?? "ctx-root",
    audit, registry, permissions, gate, memory, state, checkpoints, tools, sandbox,
  };
}
