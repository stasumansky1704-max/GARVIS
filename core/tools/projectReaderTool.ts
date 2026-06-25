// GARVIS — Project Reader Tool (M3)
//
// A safe, local read adapter that returns the project's status text from the virtual workspace.
// Used by the Daily Brief workflow as its read step. local.read, no approval, no external call.

import type { ToolDefinition } from "./toolRegistry.ts";
import type { VirtualFileSystem } from "./virtualFileSystem.ts";

export function projectReaderTool(vfs: VirtualFileSystem, statusPath = "project/status.md"): ToolDefinition {
  return {
    metadata: {
      name: "project.read", version: "1", capability: "project.read",
      actionType: "local.read",
      description: "read the local project status file (mock project state)",
    },
    run() {
      const content = vfs.readFile(statusPath);
      return content === undefined
        ? { ok: false, status: "no-project-state" }
        : { ok: true, status: "read", output: content };
    },
  };
}
