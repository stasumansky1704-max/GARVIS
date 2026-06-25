// GARVIS — Contract Registry Runtime (S1/S2)
//
// Minimal, PURE, in-memory contract-validation layer for the safety core (governed by
// CONTRACTS_AND_SCHEMA_VERSIONING.md). It is the smallest slice needed to validate the
// Approval Gate's contracts BEFORE classification or token creation.
//
// This is NOT a general schema system: no codegen, no schema library, no persistence,
// no I/O. It defines only the three contracts the Approval Gate needs today:
//   - approvalRequest@1
//   - approvalDecision@1
//   - approvalTokenReference@1
//
// Validation is deny-by-default for these safety-critical contracts: unknown fields are
// treated as dangerous and rejected; raw secret-like field names are rejected; missing
// required safety fields fail closed. (Forward-compatible "tolerate additive non-dangerous
// fields" per CONTRACTS §29 is a future per-contract refinement, intentionally not here.)

export interface ValidationResult {
  readonly valid: boolean;
  readonly errors: readonly string[];
}

export interface ContractValidator {
  readonly name: string;
  /** Explicit, visible version identifier (CONTRACTS §21). */
  readonly version: string;
  validate(payload: unknown): ValidationResult;
}

function ok(): ValidationResult {
  return { valid: true, errors: [] };
}
function fail(errors: string[]): ValidationResult {
  return { valid: false, errors };
}

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}
function isNonEmptyString(v: unknown): v is string {
  return typeof v === "string" && v.length > 0;
}

// Field names whose presence indicates a raw secret / dangerous payload. Matching is on a
// normalised (lowercase, alphanumerics-only) form, so "api_key", "apiKey", "API-KEY" all
// match. Handle fields like "tokenRef"/"tokenId" deliberately do NOT match.
const SECRET_LIKE: readonly string[] = [
  "secret", "password", "passwd", "apikey", "credential", "privatekey",
  "accesstoken", "refreshtoken", "bearer", "rawtoken", "tokenvalue",
  "mnemonic", "seedphrase", "rawexecutioncontext", "executioncontext", "sessionkey",
];
function normalise(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]/g, "");
}
export function looksSecretLike(name: string): boolean {
  const n = normalise(name);
  if (n === "token") return true; // a raw "token" field — handles must use tokenRef/tokenId
  return SECRET_LIKE.some((p) => n.includes(p));
}

interface FieldSpec {
  readonly required: readonly string[];
  readonly optional: readonly string[];
}

// Deny-by-default object validator for a safety-critical contract:
//   - reject non-objects (fail closed)
//   - reject any secret-like field name (raw-secret rejection)
//   - reject any field not in required ∪ optional (unknown == dangerous here)
//   - reject any missing required safety field
//   - require non-empty string values for required fields
function validateObject(payload: unknown, spec: FieldSpec): ValidationResult {
  if (!isPlainObject(payload)) {
    return fail(["payload-must-be-an-object"]);
  }
  const errors: string[] = [];
  const allowed = new Set<string>([...spec.required, ...spec.optional]);
  for (const key of Object.keys(payload)) {
    if (looksSecretLike(key)) errors.push(`secret-like-field-rejected:${key}`);
    else if (!allowed.has(key)) errors.push(`unknown-field-rejected:${key}`);
  }
  for (const key of spec.required) {
    if (!(key in payload)) errors.push(`missing-required-safety-field:${key}`);
    else if (!isNonEmptyString(payload[key])) errors.push(`invalid-required-field:${key}`);
  }
  return errors.length === 0 ? ok() : fail(errors);
}

function merge(base: ValidationResult, extra: string[]): ValidationResult {
  const errs = [...base.errors, ...extra];
  return errs.length === 0 ? ok() : fail(errs);
}

// ── The three Approval-Gate contracts (conceptual fields from APPROVAL_GATE_SPEC §20–§21,
//    expressed as camelCase runtime fields). Only safety-relevant fields are required. ──

export const approvalRequestV1: ContractValidator = {
  name: "approvalRequest",
  version: "1",
  validate(payload) {
    const base = validateObject(payload, {
      required: ["actionId", "actionType", "riskClass", "redactionStatus", "correlationId"],
      optional: ["idempotencyKey", "summary", "targetResource", "requiredPermissions", "dependencyChain"],
    });
    const extra: string[] = [];
    if (isPlainObject(payload) && "redactionStatus" in payload && payload.redactionStatus !== "redacted") {
      extra.push("redaction-not-confirmed"); // safety field must affirm redaction occurred
    }
    return merge(base, extra);
  },
};

export const approvalDecisionV1: ContractValidator = {
  name: "approvalDecision",
  version: "1",
  validate(payload) {
    const base = validateObject(payload, {
      required: ["decisionId", "actionId", "decision", "approvedBy", "correlationId"],
      optional: ["reason", "redactionStatus", "constraints", "expirationTime", "approvalScope"],
    });
    const extra: string[] = [];
    if (isPlainObject(payload) && "decision" in payload &&
        payload.decision !== "approved" && payload.decision !== "denied") {
      extra.push("invalid-decision-value");
    }
    return merge(base, extra);
  },
};

export const approvalTokenReferenceV1: ContractValidator = {
  name: "approvalTokenReference",
  version: "1",
  validate(payload) {
    // Tokens are referenced by HANDLE, never embedded raw (CONTRACTS §85); a raw "token"
    // field is rejected by the secret-like check in validateObject.
    return validateObject(payload, {
      required: ["tokenRef", "actionId"],
      optional: ["expirationTime"],
    });
  },
};

export class ContractRegistry {
  #byKey = new Map<string, ContractValidator>();

  /** Register a contract version. One definition per name@version (single source of truth). */
  register(validator: ContractValidator): void {
    this.#byKey.set(`${validator.name}@${validator.version}`, validator);
  }

  get(name: string, version: string): ContractValidator | undefined {
    return this.#byKey.get(`${name}@${version}`);
  }

  /** Validate a payload against a registered contract. Unregistered => fail closed. */
  validate(name: string, version: string, payload: unknown): ValidationResult {
    const validator = this.#byKey.get(`${name}@${version}`);
    if (!validator) return fail([`unknown-contract:${name}@${version}`]);
    return validator.validate(payload);
  }
}

/** A registry pre-loaded with the contracts the Approval Gate needs. */
export function defaultContractRegistry(): ContractRegistry {
  const registry = new ContractRegistry();
  registry.register(approvalRequestV1);
  registry.register(approvalDecisionV1);
  registry.register(approvalTokenReferenceV1);
  return registry;
}
