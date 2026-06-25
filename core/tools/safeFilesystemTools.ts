// GARVIS — Safe Filesystem Tools (M3)
//
// Four permission-bounded adapters over an in-memory VirtualFileSystem. They carry no decision
// logic: the Tool Sandbox enforces permission/approval before any handler runs.
//
//   - fs.readTextFile        local.read,  no approval   — reads a text file.
//   - fs.listDirectory       local.read,  no approval   — lists paths under a prefix.
//   - fs.writeTextFilePreview informational, no approval — DRY RUN: shows the proposed change,
//                                                          performs NO mutation/side effect.
//   - fs.writeTextFileApproved local.write, APPROVAL    — writes; only runs after the Approval
//                                                          Gate consumes a valid single-use token.
//
// No destructive operations (no delete/overwrite-of-unrelated paths). All I/O is in-memory.

import type { ToolDefinition } from "./toolRegistry.ts";
import type { VirtualFileSystem } from "./virtualFileSystem.ts";

export interface SafeFsInput {
  readonly path?: string;
  readonly content?: string;
  readonly prefix?: string;
}

export function safeFilesystemTools(vfs: VirtualFileSystem): ToolDefinition[] {
  return [
    {
      metadata: {
        name: "fs.readTextFile", version: "1", capability: "fs.read",
        actionType: "local.read",
        description: "read a text file from the local (virtual) workspace",
      },
      run(input) {
        const { path } = (input ?? {}) as SafeFsInput;
        if (!path) return { ok: false, status: "missing-path" };
        const content = vfs.readFile(path);
        return content === undefined
          ? { ok: false, status: "not-found" }
          : { ok: true, status: "read", output: content };
      },
    },
    {
      metadata: {
        name: "fs.listDirectory", version: "1", capability: "fs.list",
        actionType: "local.read",
        description: "list paths under a prefix",
      },
      run(input) {
        const { prefix } = (input ?? {}) as SafeFsInput;
        return { ok: true, status: "listed", output: vfs.list(prefix ?? "").join("\n") };
      },
    },
    {
      metadata: {
        name: "fs.writeTextFilePreview", version: "1", capability: "fs.write.preview",
        actionType: "informational",
        description: "dry-run a write; shows the proposed change without mutating anything",
      },
      run(input) {
        const { path, content } = (input ?? {}) as SafeFsInput;
        if (!path) return { ok: false, status: "missing-path" };
        const kind = vfs.exists(path) ? "(update)" : "(new)";
        // Deliberately NO vfs.writeFile here — a preview must have no side effect.
        return { ok: true, status: "preview", output: `preview ${path} ${kind}: ${content ?? ""}` };
      },
    },
    {
      metadata: {
        name: "fs.writeTextFileApproved", version: "1", capability: "fs.write",
        actionType: "local.write",
        description: "write a text file; requires local:write permission AND an approval token",
      },
      run(input) {
        const { path, content } = (input ?? {}) as SafeFsInput;
        if (!path) return { ok: false, status: "missing-path" };
        vfs.writeFile(path, content ?? "");
        return { ok: true, status: "written", output: `wrote ${path}` };
      },
    },
  ];
}
