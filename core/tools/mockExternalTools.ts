// GARVIS — Mock External Tools (M3)
//
// Stand-ins for browser / GitHub / Docker capabilities that perform NO real external call. Each
// factory accepts a `realCall` guard that the handler NEVER invokes — its default throws, so any
// accidental real call would fail loudly, and tests can pass a counter to assert it stayed at 0.
//
// They return deterministic "mock-*" output only. No network, no Docker daemon, no side effects.

import type { ToolDefinition } from "./toolRegistry.ts";

function forbiddenRealCall(): never {
  throw new Error("real-external-call-forbidden");
}

export function mockBrowserTool(realCall: () => never = forbiddenRealCall): ToolDefinition {
  return {
    metadata: {
      name: "browser.mock", version: "1", capability: "web.read",
      actionType: "external.read",
      description: "mock browser read; performs no network call",
    },
    run(input) {
      void realCall; // captured but never called — proves no real network access
      const { url } = (input ?? {}) as { url?: string };
      return { ok: true, status: "mock", output: `mock-browser:${url ?? ""}` };
    },
  };
}

export function mockGithubTool(realCall: () => never = forbiddenRealCall): ToolDefinition {
  return {
    metadata: {
      name: "github.mock", version: "1", capability: "vcs.read",
      actionType: "external.read",
      description: "mock GitHub read; performs no network call",
    },
    run(input) {
      void realCall;
      const { repo } = (input ?? {}) as { repo?: string };
      return { ok: true, status: "mock", output: `mock-github:${repo ?? ""}` };
    },
  };
}

export function mockDockerTool(realCall: () => never = forbiddenRealCall): ToolDefinition {
  return {
    metadata: {
      name: "docker.mock", version: "1", capability: "container.run",
      actionType: "execution.command",
      description: "mock Docker run; performs no Docker call",
    },
    run(input) {
      void realCall;
      const { image } = (input ?? {}) as { image?: string };
      return { ok: true, status: "mock", output: `mock-docker:${image ?? ""}` };
    },
  };
}
