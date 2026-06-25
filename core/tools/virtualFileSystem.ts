// GARVIS — Virtual File System (M3)
//
// An in-memory text filesystem that backs the "safe filesystem" tools. It exists so the safe
// FS capability can be exercised end-to-end (read / list / preview / approved-write) WITHOUT any
// real disk side effect — keeping the runtime pure, deterministic, and test-driven.
//
// It has NO delete/truncate primitive: there are no destructive filesystem operations in the MVP.

export class VirtualFileSystem {
  #files = new Map<string, string>();

  constructor(seed: Readonly<Record<string, string>> = {}) {
    for (const [path, content] of Object.entries(seed)) this.#files.set(path, content);
  }

  exists(path: string): boolean {
    return this.#files.has(path);
  }

  readFile(path: string): string | undefined {
    return this.#files.get(path);
  }

  /** Create or update a text file. The only mutation this FS supports (no deletes). */
  writeFile(path: string, content: string): void {
    this.#files.set(path, content);
  }

  /** Sorted list of paths under a prefix (a flat namespace stands in for directories). */
  list(prefix = ""): readonly string[] {
    return [...this.#files.keys()].filter((p) => p.startsWith(prefix)).sort();
  }
}
