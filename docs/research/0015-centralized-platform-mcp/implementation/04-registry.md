# Implementation 04 — Handler Registry

**Status:** Implementation plan (Phase B). Implements [Decision 0015](../../../decisions/0015-centralized-platform-mcp.md).
**Owner:** 17-eng-ai (Platform Engineer lens)
**Date:** 2026-05-04
**Effort estimate:** `4 d [ASSUMED]`

## 1. Overview

The handler registry is the single source of truth for tool catalog, dispatch metadata, schema references, and policy gates in the Platform MCP server. This artifact specifies the DynamoDB table (`platform-mcp-handler-registry`), the registration API Lambda that gates writes, the `mcp-handler-lint` rule module, and the seed item for `<product>.checkUserAccess` v1.0.0. The table deploys ahead of `03-mcp-server` per cross-cutting decision **CC-3**; the seed custom resource fires after `03-mcp-server` is up so the broker is ready to consume the first item. Schemas live in a separate S3 bucket owned by 11-eng-cloudops and referenced via `inputSchemaRef` / `outputSchemaRef`.

## 2. Concrete artifacts

### 2.1 DynamoDB CFN excerpt

```yaml
# infrastructure/04-registry/template.yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: Platform MCP Handler Registry — DynamoDB table, Streams, GSIs.

Parameters:
  Environment:
    Type: String
    AllowedValues: [dev, stage, prod]

Resources:
  HandlerRegistryTable:
    Type: AWS::DynamoDB::Table
    DeletionPolicy: Retain
    UpdateReplacePolicy: Retain
    Properties:
      TableName: !Sub "platform-mcp-handler-registry-${Environment}"
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - { AttributeName: pk,             AttributeType: S }
        - { AttributeName: sk,             AttributeType: S }
        - { AttributeName: status,         AttributeType: S }
        - { AttributeName: owner,          AttributeType: S }
        - { AttributeName: productAccount, AttributeType: S }
      KeySchema:
        - { AttributeName: pk, KeyType: HASH }
        - { AttributeName: sk, KeyType: RANGE }
      GlobalSecondaryIndexes:
        - IndexName: GSI1-by-status
          KeySchema:
            - { AttributeName: status, KeyType: HASH }
            - { AttributeName: pk,     KeyType: RANGE }
          Projection: { ProjectionType: ALL }
        - IndexName: GSI2-by-owner
          KeySchema:
            - { AttributeName: owner, KeyType: HASH }
            - { AttributeName: pk,    KeyType: RANGE }
          Projection: { ProjectionType: ALL }
        - IndexName: GSI3-by-account
          KeySchema:
            - { AttributeName: productAccount, KeyType: HASH }
            - { AttributeName: pk,             KeyType: RANGE }
          Projection: { ProjectionType: ALL }
      StreamSpecification:
        StreamViewType: NEW_AND_OLD_IMAGES
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true
      SSESpecification:
        SSEEnabled: true
      Tags:
        - { Key: linq:owner,   Value: platform }
        - { Key: linq:purpose, Value: mcp-handler-registry }

Outputs:
  TableName:
    Value: !Ref HandlerRegistryTable
    Export: { Name: !Sub "platform-mcp-registry-table-${Environment}" }
  StreamArn:
    Value: !GetAtt HandlerRegistryTable.StreamArn
    Export: { Name: !Sub "platform-mcp-registry-stream-${Environment}" }
```

Streams are consumed by the `listChanged` debounce Lambda (specified in `03-mcp-server.md`); the 30–60s coalesce window mitigates **R11**.

### 2.2 Sample registry item — `erp.checkUserAccess` v1.0.0

Inserted by a CFN custom resource in stack `04-registry-seed`, deployed **after** `03-mcp-server` per **CC-3**.

```json
{
  "pk":               "TOOL#erp.checkUserAccess",
  "sk":               "VERSION#1.0.0",
  "toolId":           "erp.checkUserAccess",
  "version":          "1.0.0",
  "status":           "active",
  "deprecatedAfter":  null,
  "retiredAfter":     null,

  "handlerType":      "lambda",
  "arn":              "arn:aws:lambda:us-east-1:111122223333:function:erp-check-user-access:prod",
  "productAccount":   "111122223333",
  "assumeRoleArn":    "arn:aws:iam::111122223333:role/PlatformMcpInvoker",
  "externalId":       "linq-erp-7c4a9b2e",

  "title":            "Check ERP user access",
  "description":      "Read-only. Returns whether a user has access to the LINQ ERP product for a specific tenant, plus the user's role assignments (e.g., 'admin', 'viewer'). Inputs: user email and tenant slug. Use this when verifying ERP entitlement before reading ERP data. Do NOT use this for general user profile lookups (see iam.lookupUser) or for CRM access checks (see crm.checkUserAccess). P50 ~180ms.",

  "inputSchemaRef":   "s3://platform-mcp-schemas/erp.checkUserAccess/1.0.0/input.json",
  "outputSchemaRef":  "s3://platform-mcp-schemas/erp.checkUserAccess/1.0.0/output.json",

  "sideEffects":      "read",
  "idempotent":       true,
  "tenantSourceClaim":"https://linq.com/claims/tenant_id",
  "timeoutMs":        5000,
  "expectedLatencyP50Ms": 180,
  "retryPolicy":      { "maxAttempts": 3, "backoffMs": 200, "jitter": "full" },
  "cacheTtlSeconds":  null,

  "requiredScopes":      ["erp:read", "user:read"],
  "requiredPermissions": ["erp:user:read"],
  "visibility":          { "agentIdentities": ["claude-code-internal"], "featureFlag": null },

  "owner":            "team-erp",
  "annotations":      { "readOnlyHint": true, "destructiveHint": false },

  "createdAt":        "2026-05-04T12:00:00Z",
  "updatedAt":        "2026-05-04T12:00:00Z"
}
```

A parallel `LABEL#stable` item points the broker at this version:

```json
{
  "pk":         "TOOL#erp.checkUserAccess",
  "sk":         "LABEL#stable",
  "points_to":  "1.0.0",
  "updatedAt":  "2026-05-04T12:00:00Z"
}
```

`cacheTtlSeconds: null` documents the **CC-5 / Q9** disposition — the field is reserved on every item; V1 dispatcher treats `null` as "no per-handler caching." A default is not forced.

### 2.3 `mcp-handler-lint` rule skeleton (TypeScript, Node 20 — **CC-1**)

```ts
// packages/mcp-handler-lint/src/rules.ts
import type { RegistryItem } from "@linq/mcp-handler-registry-types";

export type Severity = "error" | "warn";

export interface LintFinding {
  rule:     string;
  severity: Severity;
  message:  string;
  path?:    string;
}

export interface LintRule {
  id:       string;
  severity: Severity;
  hook:     "registryItem" | "description" | "schema";
  check:    (item: RegistryItem) => LintFinding | null;
}

const BANNED_SUBSTRATE  = ["Lambda", "Step Function", "ECS", "DynamoDB", "Calls", "Internal use of"];
const BANNED_MARKETING  = ["Powerful", "Robust", "Easy-to-use", "Comprehensive", "Best-in-class"];
const RETURNS_VERBS     = /\b(Returns|Lists|Looks up|Finds)\b/;
const READONLY_PREFIX   = /^Read-only\.\s/;
const DISAMBIGUATE      = /(Use this\s|Do NOT use this\s)/;

// R12 — description starts with safety prefix.
export const ruleReadOnlyPrefix: LintRule = {
  id: "DESC001-readonly-prefix",
  severity: "error",
  hook: "description",
  check: (it) => READONLY_PREFIX.test(it.description) ? null : {
    rule: "DESC001-readonly-prefix", severity: "error",
    message: "Description must start with 'Read-only.' in V1.",
    path: "description",
  },
};

// R12 — description length 80–500 chars.
export const ruleDescriptionLength: LintRule = {
  id: "DESC002-length",
  severity: "error",
  hook: "description",
  check: (it) => {
    const n = it.description.length;
    return n >= 80 && n <= 500 ? null : {
      rule: "DESC002-length", severity: "error",
      message: `Description length ${n} outside [80, 500].`,
      path: "description",
    };
  },
};

// R12 — first sentence ≤ 200 chars.
export const ruleFirstSentence: LintRule = {
  id: "DESC003-first-sentence",
  severity: "error",
  hook: "description",
  check: (it) => {
    const first = it.description.split(/(?<=\.)\s/)[0] ?? "";
    return first.length <= 200 ? null : {
      rule: "DESC003-first-sentence", severity: "error",
      message: `First sentence ${first.length} chars; cap is 200.`,
      path: "description",
    };
  },
};

// R12 — Returns clause present.
export const ruleReturnsClause: LintRule = {
  id: "DESC004-returns-clause",
  severity: "error",
  hook: "description",
  check: (it) => RETURNS_VERBS.test(it.description) ? null : {
    rule: "DESC004-returns-clause", severity: "error",
    message: "Description must contain a Returns/Lists/Looks up/Finds clause.",
    path: "description",
  },
};

// R12 — required input fields named in description text.
export const ruleSchemaParity: LintRule = {
  id: "DESC005-schema-parity",
  severity: "error",
  hook: "schema",
  check: (it) => {
    const required = it.inputSchema?.required ?? [];
    const missing  = required.filter((f) => !it.description.toLowerCase().includes(f.toLowerCase()));
    return missing.length === 0 ? null : {
      rule: "DESC005-schema-parity", severity: "error",
      message: `Required input fields not named in description: ${missing.join(", ")}.`,
      path: "description",
    };
  },
};

// R12 — disambiguation phrase (gated by semantic-neighbor check, deferred to M2).
export const ruleDisambiguation: LintRule = {
  id: "DESC006-disambiguation",
  severity: "warn",
  hook: "description",
  check: (it) => DISAMBIGUATE.test(it.description) ? null : {
    rule: "DESC006-disambiguation", severity: "warn",
    message: "Consider 'Use this ...' or 'Do NOT use this ...' phrasing.",
    path: "description",
  },
};

// R12 — substrate leakage.
export const ruleNoSubstrate: LintRule = {
  id: "DESC007-no-substrate",
  severity: "error",
  hook: "description",
  check: (it) => {
    const hit = BANNED_SUBSTRATE.find((p) => it.description.includes(p));
    return hit ? {
      rule: "DESC007-no-substrate", severity: "error",
      message: `Substrate leakage: '${hit}' forbidden in description.`,
      path: "description",
    } : null;
  },
};

// R12 — marketing copy.
export const ruleNoMarketing: LintRule = {
  id: "DESC008-no-marketing",
  severity: "error",
  hook: "description",
  check: (it) => {
    const hit = BANNED_MARKETING.find((p) => it.description.includes(p));
    return hit ? {
      rule: "DESC008-no-marketing", severity: "error",
      message: `Marketing copy: '${hit}' forbidden in description.`,
      path: "description",
    } : null;
  },
};

// R12 — title and description must differ.
export const ruleTitleDescDistinct: LintRule = {
  id: "DESC009-title-distinct",
  severity: "error",
  hook: "registryItem",
  check: (it) => it.title.trim() !== it.description.trim() ? null : {
    rule: "DESC009-title-distinct", severity: "error",
    message: "title and description must not be identical.",
  },
};

export const ALL_RULES: readonly LintRule[] = [
  ruleReadOnlyPrefix, ruleDescriptionLength, ruleFirstSentence,
  ruleReturnsClause, ruleSchemaParity, ruleDisambiguation,
  ruleNoSubstrate, ruleNoMarketing, ruleTitleDescDistinct,
];

export function lint(item: RegistryItem): LintFinding[] {
  return ALL_RULES.map((r) => r.check(item)).filter((f): f is LintFinding => f !== null);
}
```

Tests are fixture-driven (`tests/fixtures/{good,bad}/*.json`); each rule ships with at least one passing and one failing fixture.

### 2.4 Registration API Lambda skeleton

```ts
// packages/mcp-registration-api/src/handler.ts
import type { APIGatewayProxyHandlerV2 } from "aws-lambda";
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { PutItemCommand } from "@aws-sdk/client-dynamodb";
import { marshall } from "@aws-sdk/util-dynamodb";
import { lint } from "@linq/mcp-handler-lint";
import { RegistryItemSchema, type RegistryItem } from "@linq/mcp-handler-registry-types";

const ddb = new DynamoDBClient({});
const TABLE = process.env.REGISTRY_TABLE!;
const ACCOUNT_ALLOWLIST = (process.env.ACCOUNT_ALLOWLIST ?? "").split(",").filter(Boolean);

interface ErrorEnvelope {
  class:     "INVALID_INPUT" | "AUTH" | "INTERNAL";
  code:      string;
  retryable: boolean;
  message:   string;
  traceId:   string;
  details?:  unknown;
}

function err(c: ErrorEnvelope["class"], code: string, message: string, traceId: string, details?: unknown): ErrorEnvelope {
  return { class: c, code, retryable: false, message, traceId, details };
}

export const handler: APIGatewayProxyHandlerV2 = async (event) => {
  const traceId = event.headers["x-amzn-trace-id"] ?? crypto.randomUUID();

  // 1. Parse + structural validation.
  const parsed = RegistryItemSchema.safeParse(JSON.parse(event.body ?? "{}"));
  if (!parsed.success) {
    return resp(400, err("INVALID_INPUT", "SCHEMA_INVALID", "Body failed schema validation.", traceId, parsed.error.format()));
  }
  const item: RegistryItem = parsed.data;

  // 2. R3 — sideEffects: "write" gate (V1 read-only).
  if (item.sideEffects !== "read") {
    return resp(400, err("INVALID_INPUT", "SIDE_EFFECTS_FORBIDDEN",
      "V1 registers sideEffects='read' only.", traceId));
  }

  // 3. R1 — tenantSourceClaim required.
  if (!item.tenantSourceClaim || item.tenantSourceClaim.trim() === "") {
    return resp(400, err("INVALID_INPUT", "TENANT_SOURCE_CLAIM_REQUIRED",
      "tenantSourceClaim is required on every handler entry.", traceId));
  }

  // 4. assumeRoleArn account allowlist.
  const acct = item.assumeRoleArn.split(":")[4];
  if (!ACCOUNT_ALLOWLIST.includes(acct)) {
    return resp(400, err("INVALID_INPUT", "ACCOUNT_NOT_ALLOWLISTED",
      `Account ${acct} is not in the platform allowlist.`, traceId));
  }

  // 5. R6 — reject any per-handler M2M field. The schema does not define one;
  //    a stray top-level property triggers the generic schema check above. We
  //    additionally guard against future field-name drift here.
  if ("m2mClientId" in item || "auth0ClientId" in item) {
    return resp(400, err("INVALID_INPUT", "PER_HANDLER_M2M_FORBIDDEN",
      "Per-handler M2M apps are forbidden. Use a service-identity-class M2M app.", traceId));
  }

  // 6. R12 — description-quality lint.
  const findings = lint(item).filter((f) => f.severity === "error");
  if (findings.length > 0) {
    return resp(400, err("INVALID_INPUT", "LINT_FAILED",
      "mcp-handler-lint rejected the entry.", traceId, findings));
  }

  // 7. Write (write-only API; reads go via the broker's cached path).
  await ddb.send(new PutItemCommand({
    TableName: TABLE,
    Item: marshall({ ...item, updatedAt: new Date().toISOString() }, { removeUndefinedValues: true }),
    ConditionExpression: "attribute_not_exists(pk) OR attribute_not_exists(sk) OR #v <> :v",
    ExpressionAttributeNames:  { "#v": "version" },
    ExpressionAttributeValues: marshall({ ":v": item.version }),
  }));

  return resp(201, { ok: true, toolId: item.toolId, version: item.version, traceId });
};

function resp(status: number, body: unknown) {
  return { statusCode: status, headers: { "content-type": "application/json" }, body: JSON.stringify(body) };
}
```

The API Gateway in front authenticates the platform's CI identity (one of the 3–5 service-identity-class M2M apps); there is no per-handler client. **R23** is mitigated indirectly: the broker's 5-min in-process registry cache and 23-h Auth0 M2M token cache mean a registration-API or Auth0 outage does not stop in-flight tool calls.

## 3. Acceptance criteria

Maps to **AC4** in [`04-phase-1-poc.md`](../04-phase-1-poc.md):

| Test | Expected | Lambda gate |
|---|---|---|
| POST item with `sideEffects: "write"` | 400, `SIDE_EFFECTS_FORBIDDEN` | step 2 |
| POST item missing `tenantSourceClaim` | 400, `TENANT_SOURCE_CLAIM_REQUIRED` | step 3 |
| POST item with `assumeRoleArn` outside allowlist | 400, `ACCOUNT_NOT_ALLOWLISTED` | step 4 |
| POST item with description failing lint (e.g., missing `Read-only.`) | 400, `LINT_FAILED`, findings array | step 6 |
| POST `erp.checkUserAccess` v1.0.0 valid item | 201, item present in `GetItem` | step 7 |

Fixture-driven contract tests live under `packages/mcp-registration-api/tests/contract/`.

## 4. Effort estimate

`4 d [ASSUMED]` — 1 d CFN + seed custom resource, 1.5 d lint module + fixtures, 1 d registration Lambda + contract tests, 0.5 d wiring through CI / deploy ordering.

## 5. Open questions

- **Q9 — per-handler `cacheTtlSeconds` default (CC-5).** The field is reserved on every registry item; V1 leaves it `null` (no per-handler caching). Documenting only — non-blocking. A default lands when the result-cache layer ships, not before.
- **Embedding-based semantic-collision check — deferred to M2.** V1 has one tool (`erp.checkUserAccess`); cosine-similarity over a single-item corpus is meaningless. The lint emits `DESC006-disambiguation` as `warn` only until M2 lights up the embedding store. Per [`deep-dives/description-quality.md`](../deep-dives/description-quality.md) section "Semantic-collision detection."

## 6. Cross-references

- [`role-passes/platform.md`](../role-passes/platform.md) — DynamoDB schema, error envelope, onboarding workflow (the registry's external-facing contract surface).
- [`deep-dives/description-quality.md`](../deep-dives/description-quality.md) — full rationale for each `mcp-handler-lint` rule.
- [`03-risks-register.md`](../03-risks-register.md) — risk catalog this artifact mitigates.
- [`04-phase-1-poc.md`](../04-phase-1-poc.md) — POC milestone M2 consumes this registry.
- [Decision 0015](../../../decisions/0015-centralized-platform-mcp.md) — ADR.

## 7. Risks protected against

- **R1 — Tenant leakage.** Registration API rejects any entry missing `tenantSourceClaim` (step 3).
- **R3 — `sideEffects: "write"`.** Registration API rejects non-`read` entries in V1 (step 2).
- **R6 — Auth0 M2M cost explosion.** Registration API rejects per-handler M2M fields (step 5); registry schema does not define any per-handler client field.
- **R12 — Description quality.** `mcp-handler-lint` enforces all rules from the description-quality deep dive at registration time (step 6).
- **R14 — Schema drift.** `inputSchemaRef` / `outputSchemaRef` point at versioned S3 objects (separate stack — 11-eng-cloudops); registry version bumps and S3 versioning together give a tamper-evident audit trail.
- **R23 — Auth0 outage absorbs into cache.** Registry cache TTL (5 min in-process + 15 min ElastiCache) means registration-API or Auth0 short outages do not stop in-flight tool calls.
- **R25 — Annotation trust drift in V2.** The `annotations` block (`readOnlyHint`, `destructiveHint`) shipped in §2.2 is descriptive metadata only — V1 enforcement runs off `sideEffects: "read"`, not annotations. V2 must enforce write/destructive policy at the broker (registry + dispatcher), never via annotation hints, since annotations are model-readable but not authoritative. ADR 0015 §"V2 considerations" pins this; this artifact's sideEffects gate is the V1 implementation of that rule.
