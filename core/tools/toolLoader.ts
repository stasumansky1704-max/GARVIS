// GARVIS — Tool Loader (M2 skeleton)
//
// Loads a fixed set of tool definitions into a Tool Registry. This is a skeleton: it does not
// discover, download, or dynamically import anything (no network, no filesystem). It exists so
// the safe/mock tool set (M3) is registered through one explicit, auditable path.

import type { ToolDefinition, ToolRegistry } from "./toolRegistry.ts";

export class ToolLoader {
  #registry: ToolRegistry;

  constructor(registry: ToolRegistry) {
    this.#registry = registry;
  }

  /** Register each provided definition. Static input only — no dynamic loading. */
  load(definitions: readonly ToolDefinition[], correlationId = "tool-loader"): void {
    for (const def of definitions) {
      this.#registry.register(def, correlationId);
    }
  }
}
