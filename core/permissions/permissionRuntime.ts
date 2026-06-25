// GARVIS — Permission Runtime (S2/S3)
//
// Minimal, PURE, in-memory permission boundary (governed by SECRETS_AND_PERMISSIONS_POLICY.md).
// Deny-by-default; explicit grant / deny / revoke / expiration; bounded scopes.
//
// Permission is NOT approval: this decides standing capability (what may ever be done); the
// Approval Gate decides approval (what may happen now). A gated action needs BOTH.
//
// NOT a policy engine: no persistence, no RBAC, no users/accounts, no real OS permissions —
// the smallest boundary the Approval Gate needs.

export type PermissionScope =
  | "local:read"
  | "local:write"
  | "external:read"
  | "external:write"
  | "execution:command"
  | "credential:sensitive"
  | "destructive";

export interface PermissionRequest {
  readonly scope: PermissionScope;
  /** Optional resource the action touches; used for bounded grants. */
  readonly target?: string;
}

export interface PermissionDecision {
  readonly allowed: boolean;
  /** Stable machine-readable reason, safe to log (no secrets). */
  readonly reason: string;
}

export interface GrantOptions {
  /** Bound the grant to a resource (prefix). Omitted = scope-wide. */
  readonly target?: string;
  /** Epoch ms after which the grant is inactive. Omitted = no expiry. */
  readonly expiresAt?: number;
}

interface Grant {
  scope: PermissionScope;
  target?: string;
  revoked: boolean;
  expiresAt?: number;
}

// A scope-wide grant (no target) covers any target. A bounded grant covers only equal or
// nested targets, and does NOT cover an unbounded (whole-scope) request.
function covers(grantTarget: string | undefined, requestTarget: string | undefined): boolean {
  if (grantTarget === undefined) return true;
  if (requestTarget === undefined) return false;
  return requestTarget === grantTarget || requestTarget.startsWith(`${grantTarget}/`);
}

export class PermissionRuntime {
  #grants: Grant[] = [];
  #denied = new Set<PermissionScope>();
  #now: () => number;

  constructor(now: () => number = () => Date.now()) {
    this.#now = now;
  }

  /** Grant a (optionally bounded, optionally expiring) permission scope. */
  grant(scope: PermissionScope, options: GrantOptions = {}): void {
    this.#grants.push({
      scope,
      target: options.target,
      revoked: false,
      expiresAt: options.expiresAt,
    });
  }

  /** Explicitly deny a scope. Deny takes precedence over any grant. */
  deny(scope: PermissionScope): void {
    this.#denied.add(scope);
  }

  /** Revoke all grants for a scope, effective immediately. */
  revoke(scope: PermissionScope): void {
    for (const g of this.#grants) {
      if (g.scope === scope) g.revoked = true;
    }
  }

  /** Deny-by-default permission check. */
  check(request: PermissionRequest): PermissionDecision {
    if (this.#denied.has(request.scope)) {
      return { allowed: false, reason: "explicit-deny" };
    }
    const now = this.#now();
    for (const g of this.#grants) {
      if (g.scope !== request.scope) continue;
      if (g.revoked) continue;
      if (g.expiresAt !== undefined && g.expiresAt <= now) continue;
      if (!covers(g.target, request.target)) continue;
      return { allowed: true, reason: "granted" };
    }
    return { allowed: false, reason: "no-active-grant" }; // deny by default
  }
}
