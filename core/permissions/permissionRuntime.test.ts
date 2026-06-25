// GARVIS — Permission Runtime tests (S2/S3)
//
// Zero-dependency Node built-in test runner. Run with: `npm test`.
// Covers deny-by-default, grant, deny precedence, revocation, expiration, bounded scopes,
// and that credential-sensitive / destructive scopes are denied without an explicit grant.

import { test } from "node:test";
import { strict as assert } from "node:assert";

import { PermissionRuntime } from "./permissionRuntime.ts";

test("permission 1: unknown permission state denies by default", () => {
  const perms = new PermissionRuntime();
  const decision = perms.check({ scope: "local:write" });
  assert.equal(decision.allowed, false);
  assert.equal(decision.reason, "no-active-grant");
});

test("permission 2: explicit grant allows matching scope", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  assert.equal(perms.check({ scope: "local:write" }).allowed, true);
});

test("permission 3: explicit deny blocks matching scope (deny wins over grant)", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  perms.deny("local:write");
  const decision = perms.check({ scope: "local:write" });
  assert.equal(decision.allowed, false);
  assert.equal(decision.reason, "explicit-deny");
});

test("permission 4: revocation blocks a previously granted scope", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write");
  assert.equal(perms.check({ scope: "local:write" }).allowed, true);
  perms.revoke("local:write");
  assert.equal(perms.check({ scope: "local:write" }).allowed, false);
});

test("permission 5: expiration blocks a previously granted scope", () => {
  const perms = new PermissionRuntime(() => 1000); // fixed clock at now=1000
  perms.grant("local:write", { expiresAt: 500 }); // already expired
  assert.equal(perms.check({ scope: "local:write" }).allowed, false);

  perms.grant("local:read", { expiresAt: 2000 }); // still valid
  assert.equal(perms.check({ scope: "local:read" }).allowed, true);
});

test("permission 6: a narrower (bounded) grant does not allow a broader request", () => {
  const perms = new PermissionRuntime();
  perms.grant("local:write", { target: "/tmp/project" }); // bounded grant

  // A broader, whole-scope request is not covered by a bounded grant.
  assert.equal(perms.check({ scope: "local:write" }).allowed, false);
  // A sibling target outside the bound is not covered.
  assert.equal(perms.check({ scope: "local:write", target: "/tmp/other" }).allowed, false);
  // A nested target within the bound IS covered.
  assert.equal(perms.check({ scope: "local:write", target: "/tmp/project/file" }).allowed, true);
});

test("permission 7: credential-sensitive and destructive deny by default without grant", () => {
  const perms = new PermissionRuntime();
  assert.equal(perms.check({ scope: "credential:sensitive" }).allowed, false);
  assert.equal(perms.check({ scope: "destructive" }).allowed, false);
});
