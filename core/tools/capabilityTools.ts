// GARVIS — Capability Tool Set loader (M3)
//
// Registers the safe/mock capability tools through the Tool Loader → Tool Registry (the single
// auditable registration path). Every tool here is safe or mock: no real fs/network/Docker/
// command side effects. Execution still only happens through the Tool Sandbox.

import type { ToolRegistry } from "./toolRegistry.ts";
import { ToolLoader } from "./toolLoader.ts";
import type { VirtualFileSystem } from "./virtualFileSystem.ts";
import { safeFilesystemTools } from "./safeFilesystemTools.ts";
import { projectReaderTool } from "./projectReaderTool.ts";
import { mockBrowserTool, mockGithubTool, mockDockerTool } from "./mockExternalTools.ts";
import { SafeCommandRunner, safeCommandRunnerTool } from "./safeCommandRunner.ts";

export interface CapabilityDeps {
  readonly vfs: VirtualFileSystem;
  readonly commandRunner?: SafeCommandRunner;
}

export function loadCapabilityTools(
  registry: ToolRegistry,
  deps: CapabilityDeps,
  correlationId = "capability-loader",
): void {
  const runner = deps.commandRunner ?? new SafeCommandRunner();
  new ToolLoader(registry).load(
    [
      ...safeFilesystemTools(deps.vfs),
      projectReaderTool(deps.vfs),
      mockBrowserTool(),
      mockGithubTool(),
      mockDockerTool(),
      safeCommandRunnerTool(runner),
    ],
    correlationId,
  );
}
