# Implementation 07 — POC Product Handler (`erp.checkUserAccess`)

**Decision:** [`0015-centralized-platform-mcp`](../../../decisions/0015-centralized-platform-mcp.md) — Phase B sample handler that exercises the cross-account dispatch path end-to-end.
**Owner:** `18-eng-product-handler` (Product Handler Owner; standing in for the ERP product team until that team is available).
**Status:** Draft for Phase B implementation.
**Effort estimate:** `2 d [ASSUMED]`.
**Cross-cutting decisions in force:** **CC-1** Node 20 + TypeScript runtime; **CC-4** sample product = ERP `[ASSUMED]`, with a synthetic-product fallback if the ERP team is unavailable for the POC.

## 1. Overview

This artifact specifies the Phase-1 POC product handler for the LINQ Platform MCP Server: a Lambda function deployed in the ERP product account that answers `erp.checkUserAccess(userId, tenantId)` against a seed DynamoDB table. The handler is intentionally trivial — two tenants, three users — because the value of the POC is exercising the full agent → broker → IdentityBroker → STS → handler → audit path, not modeling real ERP data. The handler verifies the IdentityBroker JWT against the platform JWKS at `/.well-known/jwks.json` before serving (defense in depth — closes R3 from the handler side), reads `tenant_id` from the verified JWT and never from `args` (closes R1 from the handler side), and ships with contract tests in the handler repo's CI that diff input and output schemas against the registry's published schema (closes R14). Every TypeScript snippet uses `@linq/mcp-handler-sdk` envelope wrappers, structured logging with `request_id` propagation, and the minimal IAM exec role surface defined in §2.4. The CloudFormation stack uses `DeletionPolicy: Delete` throughout because this is a V1 sandbox; production handlers will switch to `DeletionPolicy: Retain` per the platform contract.

## 2. Concrete artifacts

### 2.1 Tool input and output JSON Schemas

The registry stores both schemas in S3 under `s3://platform-mcp-schemas/erp.checkUserAccess/1.0.0/{input,output}.json`. The MCP server fetches and caches them; the handler ships its own copies in-repo and uses the contract test in §2.6 to assert byte-equivalence with the registry copy.

`input.json` — note that `tenantId` is **declared** so the schema describes the full envelope agents see, but the MCP server overwrites `tenantId` from the verified user JWT before invocation. The handler ignores any `tenantId` value in `args` and reads it from the JWT (see §2.3, §2.5).

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.linq.platform/erp.checkUserAccess/1.0.0/input.json",
  "title": "erp.checkUserAccess input",
  "type": "object",
  "additionalProperties": false,
  "required": ["userId"],
  "properties": {
    "userId": {
      "type": "string",
      "pattern": "^u-[a-z0-9]{6,32}$",
      "description": "ERP user identifier. Lowercase alphanumeric with 'u-' prefix."
    },
    "tenantId": {
      "type": "string",
      "pattern": "^t-[a-z0-9]{4,16}$",
      "description": "Tenant slug. AGENTS MUST NOT SUPPLY THIS — the MCP server injects tenant_id from the verified user JWT before invocation. Declared here for envelope completeness; ignored by the handler."
    }
  }
}
```

`output.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.linq.platform/erp.checkUserAccess/1.0.0/output.json",
  "title": "erp.checkUserAccess output",
  "type": "object",
  "additionalProperties": false,
  "required": ["userId", "tenantId", "hasAccess", "roles"],
  "properties": {
    "userId": { "type": "string" },
    "tenantId": { "type": "string" },
    "hasAccess": { "type": "boolean" },
    "roles": {
      "type": "array",
      "items": { "type": "string", "enum": ["viewer", "editor", "admin"] },
      "uniqueItems": true
    },
    "lastSeenAt": {
      "type": ["string", "null"],
      "format": "date-time",
      "description": "ISO-8601 timestamp of the user's most recent ERP session, or null."
    }
  }
}
```

### 2.2 Sample DynamoDB seed table — CloudFormation YAML

Two tenants — `t-acme` and `t-globex` — and three users per tenant. The CFN snippet sits in the handler repo at `infrastructure/seed-table.yaml` and deploys into the ERP product account. `BillingMode: PAY_PER_REQUEST` keeps cost-discipline aligned with the registry pattern (per [`04-registry.md`](04-registry.md)). `DeletionPolicy: Delete` and `UpdateReplacePolicy: Delete` because this is the V1 sandbox; production templates flip both to `Retain`.

```yaml
AWSTemplateFormatVersion: "2010-09-09"
Description: ERP POC seed table for erp.checkUserAccess (Decision 0015).

Resources:
  ErpUserAccessTable:
    Type: AWS::DynamoDB::Table
    DeletionPolicy: Delete
    UpdateReplacePolicy: Delete
    Properties:
      TableName: erp-poc-user-access
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: false
      SSESpecification:
        SSEEnabled: true

  SeedItemsCustomResource:
    Type: AWS::CloudFormation::CustomResource
    DependsOn: ErpUserAccessTable
    Properties:
      ServiceToken: !GetAtt SeedFunction.Arn
      TableName: !Ref ErpUserAccessTable
      Items:
        # Tenant t-acme — three users
        - { pk: "TENANT#t-acme", sk: "USER#u-alice",   hasAccess: true,  roles: ["admin"],            lastSeenAt: "2026-05-01T10:15:00Z" }
        - { pk: "TENANT#t-acme", sk: "USER#u-bob",     hasAccess: true,  roles: ["editor", "viewer"], lastSeenAt: "2026-04-29T22:04:11Z" }
        - { pk: "TENANT#t-acme", sk: "USER#u-carol",   hasAccess: false, roles: [],                   lastSeenAt: null }
        # Tenant t-globex — three users
        - { pk: "TENANT#t-globex", sk: "USER#u-dave",  hasAccess: true,  roles: ["viewer"],           lastSeenAt: "2026-05-03T08:00:00Z" }
        - { pk: "TENANT#t-globex", sk: "USER#u-erin",  hasAccess: true,  roles: ["editor"],           lastSeenAt: "2026-05-02T14:20:00Z" }
        - { pk: "TENANT#t-globex", sk: "USER#u-frank", hasAccess: false, roles: [],                   lastSeenAt: null }

Outputs:
  ErpUserAccessTableArn:
    Description: ARN of the ERP POC seed table — referenced by the handler's IAM exec role.
    Value: !GetAtt ErpUserAccessTable.Arn
    Export:
      Name: ErpPoc-UserAccessTable-Arn
```

The `SeedFunction` is a small inline Lambda that issues a `BatchWriteItem` once at stack-create time; its definition is omitted here because it is mechanical CFN custom-resource boilerplate — the handler repo's `infrastructure/` folder owns it.

### 2.3 Handler Lambda code skeleton — TypeScript with `@linq/mcp-handler-sdk`

Single file at `src/handler.ts`. Pinning `@linq/mcp-handler-sdk` to `^1.0.0` per the handler-repo changelog policy. The SDK provides `wrapHandler` (envelope in/out, schema validation, structured logging with `request_id`, error envelope helpers) and `verifyPlatformJwt` (JWKS fetch and cache, `aud` / `iss` / `exp` checks — wraps the `jose` primitive shown in §2.5).

```ts
// src/handler.ts
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, GetCommand } from "@aws-sdk/lib-dynamodb";
import {
  wrapHandler,
  verifyPlatformJwt,
  errorEnvelope,
  type HandlerContext,
} from "@linq/mcp-handler-sdk";
import inputSchema from "../schemas/input.json";
import outputSchema from "../schemas/output.json";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({}));
const TABLE_NAME = process.env.TABLE_NAME!;
const PLATFORM_JWKS_URL = process.env.PLATFORM_JWKS_URL!;       // https://mcp.linq.platform/.well-known/jwks.json
const EXPECTED_AUDIENCE = process.env.EXPECTED_AUDIENCE!;       // arn:aws:lambda:...:erp-check-user-access
const EXPECTED_ISSUER = process.env.EXPECTED_ISSUER!;           // https://mcp.linq.platform/identity-broker

interface Args { userId: string; tenantId?: string }   // tenantId in args is IGNORED — see R1 mitigation
interface Result { userId: string; tenantId: string; hasAccess: boolean; roles: string[]; lastSeenAt: string | null }

export const handler = wrapHandler<Args, Result>({
  inputSchema,
  outputSchema,
  async invoke(args, ctx: HandlerContext) {
    // R3 — verify the IdentityBroker JWT against the platform JWKS BEFORE serving.
    // SDK delegates to verifyPlatformJwt (§2.5); throws on any failure → SDK maps to AUTH error envelope.
    const claims = await verifyPlatformJwt(ctx.envelope.identityToken, {
      jwksUrl: PLATFORM_JWKS_URL,
      audience: EXPECTED_AUDIENCE,
      issuer: EXPECTED_ISSUER,
    });

    // R1 — tenant_id comes from the JWT, NEVER from args. SDK already strips args.tenantId,
    // but we read directly from claims here as a belt-and-braces enforcement.
    const tenantId = claims["tenant_id"] as string | undefined;
    if (!tenantId) {
      ctx.log.warn("missing tenant_id claim in IdentityBroker JWT", { sub: claims.sub });
      throw errorEnvelope({
        class: "AUTH",
        code: "TENANT_CLAIM_MISSING",
        retryable: false,
        message: "IdentityBroker JWT missing tenant_id claim",
      });
    }

    ctx.log.info("erp.checkUserAccess invoked", {
      request_id: ctx.envelope.callId,
      user_sub: claims.sub,
      tenant_id: tenantId,
      user_id: args.userId,
    });

    const res = await ddb.send(new GetCommand({
      TableName: TABLE_NAME,
      ConsistentRead: false,
      Key: { pk: `TENANT#${tenantId}`, sk: `USER#${args.userId}` },
    }));

    if (!res.Item) {
      throw errorEnvelope({
        class: "NOT_FOUND",
        code: "ERP_USER_NOT_FOUND",
        retryable: false,
        message: `User ${args.userId} not found in tenant ${tenantId}`,
      });
    }

    return {
      userId: args.userId,
      tenantId,
      hasAccess: Boolean(res.Item.hasAccess),
      roles: (res.Item.roles ?? []) as string[],
      lastSeenAt: (res.Item.lastSeenAt ?? null) as string | null,
    };
  },
});
```

The SDK enforces the input and output envelopes from [`role-passes/platform.md`](../role-passes/platform.md) §"Handler invocation contract." Logs are structured JSON; CloudWatch Logs Insights queries pivot on `request_id` to correlate with the platform audit log (closes R10 from the handler side).

### 2.4 Lambda IAM exec role — minimal, read-only on the seed table

The exec role lives in the handler repo at `infrastructure/exec-role.yaml`. Trust policy permits the Lambda service only; permissions allow `dynamodb:GetItem` on the single seed-table ARN and the standard CloudWatch Logs writes. **No `*` actions, no inline policy drift, no extra resources** (per the agent contract §"Working conventions").

```yaml
ErpCheckUserAccessExecRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: erp-check-user-access-exec
    AssumeRolePolicyDocument:
      Version: "2012-10-17"
      Statement:
        - Effect: Allow
          Principal: { Service: lambda.amazonaws.com }
          Action: sts:AssumeRole
    Policies:
      - PolicyName: ReadSeedTable
        PolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action: dynamodb:GetItem
              Resource: !ImportValue ErpPoc-UserAccessTable-Arn
      - PolicyName: WriteOwnLogs
        PolicyDocument:
          Version: "2012-10-17"
          Statement:
            - Effect: Allow
              Action:
                - logs:CreateLogStream
                - logs:PutLogEvents
              Resource:
                - !Sub arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aws/lambda/erp-check-user-access:*
            - Effect: Allow
              Action: logs:CreateLogGroup
              Resource: !Sub arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:*
```

Note the exec role does NOT grant `dynamodb:Query`, `Scan`, `PutItem`, `UpdateItem`, or `DeleteItem`. A future write-handler would add a separate role; v1 handlers are read-only by registry contract (`sideEffects: "read"`).

### 2.5 Handler-side JWT verification — `jose` primitive

Lives in the SDK at `@linq/mcp-handler-sdk/src/jwt.ts`. Reproduced here so the handler-side enforcement is auditable from the handler repo without unpacking the SDK.

```ts
// @linq/mcp-handler-sdk — verifyPlatformJwt
import { createRemoteJWKSet, jwtVerify, type JWTPayload, type JWTVerifyResult } from "jose";

const jwksCache = new Map<string, ReturnType<typeof createRemoteJWKSet>>();

export async function verifyPlatformJwt(
  token: string,
  opts: { jwksUrl: string; audience: string; issuer: string },
): Promise<JWTPayload> {
  // JWKS reuse — `jose` internally caches keys for ~10 min and tolerates `kid` rotation.
  let jwks = jwksCache.get(opts.jwksUrl);
  if (!jwks) {
    jwks = createRemoteJWKSet(new URL(opts.jwksUrl), {
      cacheMaxAge: 60 * 60 * 1000,        // 1 h cache per agent contract
      cooldownDuration: 30 * 1000,        // backoff on JWKS fetch failure
    });
    jwksCache.set(opts.jwksUrl, jwks);
  }

  let result: JWTVerifyResult;
  try {
    result = await jwtVerify(token, jwks, {
      audience: opts.audience,
      issuer: opts.issuer,
      // exp / nbf checked by jose by default; clock skew tolerance 30 s.
      clockTolerance: 30,
      algorithms: ["RS256", "ES256"],     // platform KMS asymmetric — no symmetric, no `none`
    });
  } catch (err) {
    // SDK callers turn this into errorEnvelope({ class: "AUTH", code: "JWT_INVALID", ... }).
    throw new Error(`platform JWT verification failed: ${(err as Error).message}`);
  }

  // Sanity check the act claim — the IdentityBroker MUST set act.sub = agent client_id.
  const act = result.payload.act as { sub?: string } | undefined;
  if (!act?.sub) {
    throw new Error("platform JWT missing act.sub claim — required by RFC 8693 wire shape");
  }

  return result.payload;
}
```

`aud`, `iss`, and `exp` are all enforced. Algorithm allowlist excludes `none` and any symmetric alg — the broker is KMS-signed, so the handler must not accept symmetrically-signed tokens.

### 2.6 Contract test stub — input and output schema diff with `ajv`

Lives at `test/contract.test.ts` and runs in handler-repo CI on every PR. Closes R14: schema drift between handler-repo schemas and registry-published schemas fails CI before drift can reach production.

```ts
// test/contract.test.ts
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import { fetch } from "undici";
import { describe, expect, it } from "@jest/globals";
import localInput from "../schemas/input.json";
import localOutput from "../schemas/output.json";

const REGISTRY_BASE = process.env.REGISTRY_SCHEMA_BASE
  ?? "https://platform-mcp-schemas.s3.amazonaws.com/erp.checkUserAccess/1.0.0";

async function fetchJson(url: string) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`registry schema fetch ${url} → ${r.status}`);
  return r.json();
}

describe("erp.checkUserAccess — registry contract", () => {
  const ajv = addFormats(new Ajv2020({ strict: true, allErrors: true }));

  it("local input schema is byte-equivalent to registry input schema", async () => {
    const remote = await fetchJson(`${REGISTRY_BASE}/input.json`);
    expect(localInput).toStrictEqual(remote);
  });

  it("local output schema is byte-equivalent to registry output schema", async () => {
    const remote = await fetchJson(`${REGISTRY_BASE}/output.json`);
    expect(localOutput).toStrictEqual(remote);
  });

  it("a known-good input validates against the local input schema", () => {
    const validate = ajv.compile(localInput);
    expect(validate({ userId: "u-alice" })).toBe(true);
  });

  it("a known-good output validates against the local output schema", () => {
    const validate = ajv.compile(localOutput);
    expect(validate({
      userId: "u-alice",
      tenantId: "t-acme",
      hasAccess: true,
      roles: ["admin"],
      lastSeenAt: "2026-05-01T10:15:00Z",
    })).toBe(true);
  });

  it("rejects an extra property — additionalProperties: false enforced", () => {
    const validate = ajv.compile(localInput);
    expect(validate({ userId: "u-alice", surprise: 1 })).toBe(false);
  });
});
```

The first two tests are the critical drift-detectors. The remaining two are smoke checks that the schemas are well-formed.

## 3. Acceptance criteria

The POC handler is **green** when all of the following observable signals hold. These map onto Phase-1 POC acceptance criteria 1, 3, and 8 from [`04-phase-1-poc.md`](../04-phase-1-poc.md), narrowed to the handler-side surface.

1. **Happy path returns the expected response.** Calling `erp.checkUserAccess({ userId: "u-alice" })` with a valid IdentityBroker JWT whose `tenant_id = t-acme` returns `{ userId: "u-alice", tenantId: "t-acme", hasAccess: true, roles: ["admin"], lastSeenAt: "2026-05-01T10:15:00Z" }`.
2. **Unknown user returns `NOT_FOUND`.** Calling with `userId = "u-doesnotexist"` returns the error envelope `{ class: "NOT_FOUND", code: "ERP_USER_NOT_FOUND", retryable: false, ... }`.
3. **Tenant-scope mismatch is rejected at the handler.** A request whose JWT carries `tenant_id = t-acme` but whose `args.tenantId = t-globex` is served using `t-acme` (the JWT value), and the response's `tenantId = t-acme`. The handler logs a structured `tenant_args_ignored` warning. (The MCP server is expected to strip `args.tenantId` before dispatch; this acceptance criterion verifies handler-side defense in depth.)
4. **JWT verification rejects bad tokens.** A request with an expired, wrong-`aud`, wrong-`iss`, or unsigned JWT fails with `class: "AUTH", code: "JWT_INVALID"` before any DynamoDB call.
5. **Contract test fails CI on schema drift.** Mutating `schemas/input.json` locally without a corresponding registry update fails the `byte-equivalent to registry` test on the next PR.
6. **IAM exec role grants only `dynamodb:GetItem` on the seed table.** `aws iam simulate-principal-policy` confirms `Scan`, `Query`, `PutItem`, `UpdateItem`, `DeleteItem`, and any other table all return `implicitDeny`.

## 4. Effort estimate

`2 d [ASSUMED]`. Scaffolding only — the Lambda is intentionally trivial. Day 1: handler code, schemas, seed-table CFN, exec-role CFN, local SAM-local smoke against mocked DynamoDB. Day 2: contract tests wired into handler-repo CI, JWT-verification negative-test matrix, structured-logging review, integration with the platform `linq-mcp-local` mock server (per [`role-passes/platform.md`](../role-passes/platform.md) onboarding step 3).

## 5. Open questions

- **Q-PROD.1 — Will the ERP product team own this handler in real life, or do we ship the POC under a synthetic product?** CC-4 sets sample product = ERP `[ASSUMED]`, with synthetic-product fallback if the ERP team is unavailable. *Forced-today guess: proceed with `erp.checkUserAccess` naming and seed table, but flag both the handler repo and the registry entry as `synthetic = true` until the ERP team confirms ownership; renaming the tool ID later is a single registry-item rewrite plus a `notifications/tools/list_changed` emission.* Tracked against Q-PROD.1 in [`05-open-questions.md`](../05-open-questions.md) when that file is updated.
- **Q-PROD.2 — Pin `@linq/mcp-handler-sdk` to a release tag or float on `^1.0.0`?** Platform contract says pin per release, but the SDK is being authored in parallel. *Forced-today guess: float on `^1.0.0` until the SDK ships a 1.0.0 GA tag; flip to a strict pin in the handler-repo changelog once that tag exists.*

## 6. Cross-references

- [`role-passes/platform.md`](../role-passes/platform.md) — handler invocation contract, error envelope, onboarding workflow, registry item shape. The handler in §2.3 is a literal implementation of the input and output envelopes specified there.
- [`implementation/03-mcp-server.md`](03-mcp-server.md) — the MCP server invokes this handler via the dispatcher's Lambda adapter. The handler's verification of `aud` and `iss` (§2.5) must match what the MCP server's IdentityBroker mints.
- [`implementation/04-registry.md`](04-registry.md) — the registry item for `erp.checkUserAccess` carries `inputSchemaRef` / `outputSchemaRef` pointing at the same S3 schemas the contract test in §2.6 fetches.
- [`implementation/06-cross-account.md`](06-cross-account.md) — the cross-account trust policy that lets the Platform MCP server `sts:AssumeRole` into the ERP product account is owned by `12-eng-security-iam`; this handler's exec role is unrelated to that trust path (the exec role is the Lambda's runtime role, not the cross-account assumed role).
- [`04-phase-1-poc.md`](../04-phase-1-poc.md) — POC acceptance criteria 1, 3, 5, 8 are the system-level acceptance signals this handler contributes to.
- [`03-risks-register.md`](../03-risks-register.md) — R1, R3, R14 (cited per artifact below).

## 7. Risks protected against

- **R1 — Tenant leakage at the handler.** The handler reads `tenant_id` from the verified IdentityBroker JWT and never from `args` (§2.3 — `claims["tenant_id"]`). Even if a malicious agent or a buggy MCP-server build tries to pass `args.tenantId`, the handler ignores it. The DynamoDB key is `TENANT#${tenantId}` where `tenantId` always comes from the JWT, so cross-tenant reads are mechanically impossible.
- **R3 — Token passthrough vs. MCP spec prohibition.** The handler verifies the IdentityBroker JWT against the platform JWKS at `/.well-known/jwks.json` before any DynamoDB call (§2.3, §2.5). It rejects any token whose `aud` is not its own audience, whose `iss` is not the IdentityBroker, or whose signature does not chain to the platform JWKS. A naïve MCP-server build that forwarded the agent's raw Auth0 M2M JWT would be rejected at the handler with `class: "AUTH"`.
- **R14 — `inputSchema` / `outputSchema` drift between registry and handler.** The contract test in §2.6 fetches both schemas from the registry's S3 bucket and asserts byte-equivalence with the handler's local copies. Drift fails CI on every PR — schema bumps without a registry update never merge.
