// GARVIS — Safe Command Runner (M3 stub)
//
// Refuses to execute real commands. It NEVER spawns a process: an unknown command returns
// "blocked:not-implemented"; only commands explicitly registered as mocks return a canned
// result. A `realExec` guard is captured but never called (its default throws).
//
// This is the seam where a future, fully-gated command capability would live — today it is a
// safe stub so workflows/agents can reference "run a command" without any real execution.

import type { ToolDefinition, ToolResult } from "./toolRegistry.ts";

function forbiddenRealExec(): never {
  throw new Error("real-command-execution-forbidden");
}

export interface SafeCommandRunnerOptions {
  readonly realExec?: () => never;
  readonly mocks?: Readonly<Record<string, ToolResult>>;
}

export class SafeCommandRunner {
  #realExec: () => never;
  #mocks: Map<string, ToolResult>;

  constructor(options: SafeCommandRunnerOptions = {}) {
    this.#realExec = options.realExec ?? forbiddenRealExec;
    this.#mocks = new Map(Object.entries(options.mocks ?? {}));
  }

  /** Return a mocked result if one is registered; otherwise refuse. Never executes a real command. */
  run(command: string): ToolResult {
    void this.#realExec; // captured but never invoked
    const mock = this.#mocks.get(command);
    if (mock) return mock;
    return { ok: false, status: "blocked:not-implemented", output: `refused real execution: ${command}` };
  }
}

export function safeCommandRunnerTool(runner: SafeCommandRunner): ToolDefinition {
  return {
    metadata: {
      name: "command.safeRunner", version: "1", capability: "command.run",
      actionType: "execution.command",
      description: "safe command runner stub; refuses real execution unless explicitly mocked",
    },
    run(input) {
      const { command } = (input ?? {}) as { command?: string };
      if (!command) return { ok: false, status: "missing-command" };
      return runner.run(command);
    },
  };
}
