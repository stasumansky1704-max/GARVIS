// GARVIS — Shared redaction transform (S5/M2)
//
// Single source of the "mask secret-like content in free text" transform, reused by the
// Memory authority and the Tool Sandbox so redaction-before-storage behaves identically
// everywhere. Secret-name detection itself stays single-sourced in the Contract Registry
// (`looksSecretLike`); this module only owns the masking of secret-shaped text.
//
// Conservative, not exhaustive: it masks the value after a secret-like key (e.g. "apiKey=..",
// "password: ..") and bearer tokens. It never throws and never inspects secret values.

import { looksSecretLike } from "../contracts/contractRegistry.ts";

export function redactText(text: string): string {
  return text
    .replace(/\bBearer\s+\S+/gi, "Bearer ***")
    .replace(/([A-Za-z0-9_]+)(\s*[:=]\s*)(\S+)/g, (match, key: string, sep: string) =>
      looksSecretLike(key) ? `${key}${sep}***` : match,
    );
}
