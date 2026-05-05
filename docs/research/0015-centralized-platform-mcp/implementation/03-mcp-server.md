# Implementation — 03 MCP Server (Lambda + JSON-RPC dispatcher)

**Decision:** [`0015-centralized-platform-mcp`](../../../decisions/0015-centralized-platform-mcp.md) — Phase B nested stack `03-mcp-server`.
**Owner:** Backend / MCP Server Engineer.
**Status:** Draft for Phase B implementation.
**Effort estimate:** `5 d [ASSUMED]`.

## 1. Overview

This Lambda is the JSON-RPC entry point for all internal AI agents calling LINQ products. It terminates Auth0 M2M JWTs, projects the registry catalog by `client_id`, runs the 10-step `tools/call` pipeline from [`01-architecture.md`](../01-architecture.md), and emits one audit record per request. The MCP server self-hosts `/.well-known/oauth-protected-resource` to close the RFC 9728 gap (R5) without an Auth0 dependency. Runtime is **Node 20 + TypeScript** [ASSUMED, Q-IMPL.1] using the Anthropic MCP TypeScript SDK pinned to MCP spec **2025-06-18** [CONFIRMED-by-ADR for the spec; SDK version pin tagged Q-IMPL.6]. The Lambda lives in nested stack `03-mcp-server` and depends on stacks `02-secrets` (Auth0 client config, KMS aliases) and `04-registry` (DynamoDB table ARN exported as `RegistryTableArn`) [CONFIRMED-by-ADR via CC-3].

## 2. Concrete artifacts

### 2.1 Module layout

```
src/mcp-server/
  index.ts                    # Lambda handler entry — APIGW v2 event router
  auth.ts                     # JWT verify + audience binding (RFC 8707)
  jwks.ts                     # JWKS fetcher with 1 h TTL, key-rotation tolerant
  registry.ts                 # 5-min in-process registry cache + bypass header
  dispatcher.ts               # 10-step tools/call pipeline orchestrator
  audit.ts                    # Single per-request JSON record emitter
  errors.ts                   # Error envelope + WWW-Authenticate builder
  ratelimit.ts                # Per-agent + per-tool token bucket (R8)
  routes/
    tools-list.ts             # Server-side projection by client_id (R4)
    tools-call.ts             # 10-step pipeline (R1, R3, R10, R13, R19)
    well-known.ts             # /.well-known/oauth-protected-resource (R5)
```

Shared modules ship as a Lambda layer to keep the handler bundle ≤ 5 MB and cold-path P95 ≤ 1500 ms (AC6, R15).

### 2.2 `index.ts` — Lambda handler entry

```ts
// src/mcp-server/index.ts
import type { APIGatewayProxyEventV2, APIGatewayProxyResultV2 } from "aws-lambda";
import { handleToolsCall } from "./routes/tools-call.js";
import { handleToolsList } from "./routes/tools-list.js";
import { handleWellKnown } from "./routes/well-known.js";
import { errorEnvelope, unauthorizedResponse } from "./errors.js";
import { verifyAgentJwt, verifyUserJwt } from "./auth.js";
import { emitAudit } from "./audit.js";
import { randomUUID } from "node:crypto";

// MCP spec pin — JSON-RPC 2.0, MCP 2025-06-18.
const PROTOCOL_VERSION = "2025-06-18";

export async function handler(
  event: APIGatewayProxyEventV2,
): Promise<APIGatewayProxyResultV2> {
  const requestId = event.headers["x-request-id"] ?? randomUUID();
  const startedAt = Date.now();

  // R5 — RFC 9728 self-host. Unauthenticated by design.
  if (event.rawPath === "/.well-known/oauth-protected-resource") {
    return handleWellKnown();
  }

  // Token validation — agent JWT mandatory; user JWT mandatory for tools/call.
  const agentToken = extractBearer(event.headers.authorization);
  if (!agentToken) return unauthorizedResponse(requestId);

  let agent;
  try {
    agent = await verifyAgentJwt(agentToken); // validates iss, aud, sig, kid, RFC 8707 resource (R19)
  } catch (e) {
    return unauthorizedResponse(requestId, (e as Error).message);
  }

  // JSON-RPC envelope dispatch.
  const rpc = JSON.parse(event.body ?? "{}");
  if (rpc.jsonrpc !== "2.0") {
    return errorEnvelope(requestId, -32600, "Invalid JSON-RPC request");
  }

  try {
    switch (rpc.method) {
      case "initialize":
        return jsonRpcOk(rpc.id, {
          protocolVersion: PROTOCOL_VERSION,
          capabilities: { tools: { listChanged: true } },
          serverInfo: { name: "linq-platform-mcp", version: "1.0.0" },
        });

      case "tools/list":
        return await handleToolsList({ agent, rpcId: rpc.id, requestId });

      case "tools/call": {
        const userToken = event.headers["x-user-token"];
        if (!userToken) return unauthorizedResponse(requestId, "missing X-User-Token");
        const user = await verifyUserJwt(userToken);
        return await handleToolsCall({
          agent,
          user,
          params: rpc.params,
          rpcId: rpc.id,
          requestId,
          startedAt,
        });
      }

      default:
        return errorEnvelope(requestId, -32601, `Unknown method: ${rpc.method}`);
    }
  } catch (err) {
    await emitAudit({
      request_id: requestId,
      decision: "deny",
      denial_reason: "unhandled_error",
      error: { class: "INTERNAL", message: (err as Error).message },
      latency_ms: { total: Date.now() - startedAt },
    });
    return errorEnvelope(requestId, -32603, "Internal error");
  }
}

function extractBearer(h: string | undefined): string | null {
  if (!h?.startsWith("Bearer ")) return null;
  return h.slice(7);
}

function jsonRpcOk(id: unknown, result: unknown): APIGatewayProxyResultV2 {
  return {
    statusCode: 200,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ jsonrpc: "2.0", id, result }),
  };
}
```

### 2.3 `auth.ts` — JWT verify + audience binding

```ts
// src/mcp-server/auth.ts
import { jwtVerify, type JWTPayload } from "jose";
import { getJwks } from "./jwks.js";

const ISSUER = process.env.AUTH0_ISSUER!;             // https://linq.auth0.com/
const MCP_AUDIENCE = process.env.MCP_AUDIENCE!;       // https://mcp.linq.platform
const PLATFORM_BROKER_ISSUER = process.env.PLATFORM_BROKER_ISSUER!; // identity-broker JWKS

export interface AgentPrincipal {
  client_id: string;
  scope: string[];
  jti: string;
  resource?: string; // RFC 8707
}

export interface UserPrincipal {
  sub: string;
  email?: string;
  permissions: string[];
  tenant_id?: string;
  jti: string;
  raw: JWTPayload;
}

export async function verifyAgentJwt(token: string): Promise<AgentPrincipal> {
  const jwks = await getJwks(ISSUER);
  const { payload } = await jwtVerify(token, jwks, {
    issuer: ISSUER,
    audience: MCP_AUDIENCE, // R19 — strict audience binding
    algorithms: ["RS256"],
  });

  // RFC 8707 resource parameter enforcement (R19).
  // Auth0 emits the requested resource in `aud` or a custom claim; reject mismatches.
  const resource = (payload as Record<string, unknown>).resource as string | undefined;
  if (resource && resource !== MCP_AUDIENCE) {
    throw new Error(`resource parameter mismatch: ${resource}`);
  }

  return {
    client_id: payload.azp as string ?? payload.client_id as string ?? payload.sub as string,
    scope: ((payload.scope as string) ?? "").split(" ").filter(Boolean),
    jti: payload.jti as string,
    resource,
  };
}

export async function verifyUserJwt(token: string): Promise<UserPrincipal> {
  const jwks = await getJwks(ISSUER);
  const { payload } = await jwtVerify(token, jwks, {
    issuer: ISSUER,
    audience: MCP_AUDIENCE, // user token must be audience-bound to MCP server, not passed downstream (R3)
    algorithms: ["RS256"],
  });
  return {
    sub: payload.sub as string,
    email: payload.email as string | undefined,
    permissions: (payload.permissions as string[]) ?? [],
    tenant_id: (payload["https://linq/tenant_id"] as string) ?? (payload.tenant_id as string),
    jti: payload.jti as string,
    raw: payload,
  };
}
```

### 2.4 `jwks.ts` — JWKS cache (1 h TTL, rotation-tolerant)

```ts
// src/mcp-server/jwks.ts
import { createRemoteJWKSet, type JWTVerifyGetKey } from "jose";

const CACHE = new Map<string, { jwks: JWTVerifyGetKey; fetchedAt: number }>();
const TTL_MS = 60 * 60 * 1000;   // 1 h
const COOLDOWN_MS = 30 * 1000;   // jose internal cooldown — accept new kid mid-TTL on miss

export async function getJwks(issuer: string): Promise<JWTVerifyGetKey> {
  const now = Date.now();
  const hit = CACHE.get(issuer);
  if (hit && now - hit.fetchedAt < TTL_MS) return hit.jwks;

  const jwks = createRemoteJWKSet(new URL(`${issuer}.well-known/jwks.json`), {
    cooldownDuration: COOLDOWN_MS,
    cacheMaxAge: TTL_MS,
  });
  CACHE.set(issuer, { jwks, fetchedAt: now });
  return jwks;
}
```

### 2.5 `routes/tools-call.ts` — 10-step pipeline

Each step name in the code matches the canonical pipeline in [`01-architecture.md`](../01-architecture.md) and the deep-dive in [`deep-dives/prompt-to-handler.md`](../deep-dives/prompt-to-handler.md). Comments call out the AC and R numbers each step closes.

```ts
// src/mcp-server/routes/tools-call.ts
import type { AgentPrincipal, UserPrincipal } from "../auth.js";
import { lookupTool } from "../registry.js";
import { exchangeIdentity } from "../identity-broker-client.js";
import { assumeRoleCached } from "../sts-cache.js";
import { dispatchHandler } from "../handler-adapters/index.js";
import { validateInput, validateOutput } from "../schema-validate.js";
import { allow as rateAllow } from "../ratelimit.js";
import { emitAudit } from "../audit.js";
import { errorEnvelope } from "../errors.js";

interface Args {
  agent: AgentPrincipal;
  user: UserPrincipal;
  params: { name: string; arguments: Record<string, unknown> };
  rpcId: unknown;
  requestId: string;
  startedAt: number;
}

export async function handleToolsCall(a: Args) {
  const stage: Record<string, number> = {};
  const t = (k: string) => (stage[k] = Date.now());
  const dt = (k: string) => Date.now() - stage[k];

  // STEP 1 — JWT validation already happened in index.ts. Latency captured in stage `auth`.
  stage.auth = a.startedAt;

  // STEP 2 — Registry lookup with 5-min in-process cache (R17, AC5).
  t("registry");
  const tool = await lookupTool(a.params.name, /* bypass */ false);
  if (!tool) return deny(a, "TOOL_NOT_FOUND", -32602, stage);

  // STEP 3 — Coarse-grained authorization. Agent scopes + user permissions.
  t("authz");
  const missingScope = tool.requiredScopes.find((s) => !a.agent.scope.includes(s));
  if (missingScope) return deny(a, "AGENT_SCOPE_DENIED", -32001, stage, tool);
  const missingPerm = tool.requiredPermissions.find((p) => !a.user.permissions.includes(p));
  if (missingPerm) return deny(a, "USER_PERMISSION_DENIED", -32001, stage, tool);

  // STEP 4 — Tenant scope enforcement BEFORE STS (AC3, R1).
  // Read tenant from the user's verified JWT — never from agent-supplied input.
  const claimName = tool.tenantSourceClaim;
  const verifiedTenant = (a.user.raw[claimName] as string) ?? a.user.tenant_id;
  if (!verifiedTenant) return deny(a, "TENANT_CLAIM_MISSING", -32001, stage, tool);
  const agentSuppliedTenant = a.params.arguments.tenantId as string | undefined;
  if (agentSuppliedTenant && agentSuppliedTenant !== verifiedTenant) {
    return deny(a, "TENANT_SCOPE_VIOLATION", -32001, stage, tool, { verifiedTenant });
  }

  // STEP 5 — Input schema validation (AJV + S3-resolved schema).
  t("schema");
  const inputErrors = await validateInput(tool, {
    ...a.params.arguments,
    tenantId: verifiedTenant, // platform injects, agent cannot override
  });
  if (inputErrors) return deny(a, "INPUT_SCHEMA_INVALID", -32602, stage, tool, { inputErrors });

  // STEP 6 — sideEffects: "read" gate. Belt-and-suspenders; registry rejects writes at registration.
  if (tool.sideEffects !== "read") return deny(a, "WRITE_NOT_ALLOWED_V1", -32001, stage, tool);

  // R3 — token passthrough refusal (AC8). Reject if input contains a JWT-shaped string.
  if (containsJwtLike(a.params.arguments)) {
    return deny(a, "TOKEN_PASSTHROUGH_REFUSED", -32001, stage, tool);
  }

  // R8 — per-agent + per-tool rate limit.
  if (!rateAllow(a.agent.client_id, tool.id)) {
    return deny(a, "RATE_LIMITED", -32002, stage, tool);
  }

  // STEP 7 — IdentityBroker token exchange (RFC 8693 wire shape).
  t("broker");
  const downstreamToken = await exchangeIdentity({
    subject_token: a.user.raw,
    actor_client_id: a.agent.client_id,
    audience: tool.handlerAudience,
    tenant_id: verifiedTenant,
    request_id: a.requestId,
  });

  // STEP 8 — sts:AssumeRole with per-product External ID + session tags (R10).
  t("sts");
  const creds = await assumeRoleCached({
    roleArn: tool.assumeRoleArn,
    externalId: tool.externalId,
    sessionName: `req-${a.requestId.slice(0, 24)}`,
    sessionTags: {
      tenant_id: verifiedTenant,
      user_sub: a.user.sub,
      agent_client_id: a.agent.client_id,
      request_id: a.requestId, // R10 — embed in session tags for CloudTrail correlation
    },
  });

  // STEP 9 — Dispatch via handlerType adapter; honor per-handler timeoutMs (R13).
  t("invoke");
  const result = await dispatchHandler(tool, creds, downstreamToken, {
    ...a.params.arguments,
    tenantId: verifiedTenant,
  }, { timeoutMs: tool.timeoutMs ?? 30_000 });

  // STEP 10 — Output validate, audit, return.
  t("validate_out");
  const outputErrors = await validateOutput(tool, result.payload);
  if (outputErrors) return deny(a, "OUTPUT_SCHEMA_INVALID", -32603, stage, tool, { outputErrors });

  await emitAudit({
    request_id: a.requestId,
    agent: { client_id: a.agent.client_id, scope: a.agent.scope, token_jti: a.agent.jti },
    user: { sub: a.user.sub, email: a.user.email, permissions: a.user.permissions, token_jti: a.user.jti },
    tool: { id: tool.id, version: tool.version },
    handler: {
      product: tool.product,
      arn: tool.handlerArn,
      assume_role_arn: tool.assumeRoleArn,
      session_name: `req-${a.requestId.slice(0, 24)}`,
    },
    tenant_id: verifiedTenant,
    decision: "allow",
    denial_reason: null,
    downstream_status: result.status,
    latency_ms: {
      auth: dt("auth"),
      registry_lookup: dt("registry"),
      authz: dt("authz"),
      schema: dt("schema"),
      broker: dt("broker"),
      sts_assume: dt("sts"),
      handler_invoke: dt("invoke"),
      total: Date.now() - a.startedAt,
    },
    error: null,
  });

  return {
    statusCode: 200,
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: a.rpcId,
      result: { content: [{ type: "text", text: JSON.stringify(result.payload) }] },
    }),
  };
}

function containsJwtLike(args: Record<string, unknown>): boolean {
  const re = /^ey[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/;
  return Object.values(args).some((v) => typeof v === "string" && re.test(v));
}

async function deny(
  a: Args,
  code: string,
  rpcCode: number,
  stage: Record<string, number>,
  tool?: { id: string; version: string },
  extra?: Record<string, unknown>,
) {
  await emitAudit({
    request_id: a.requestId,
    agent: { client_id: a.agent.client_id, scope: a.agent.scope, token_jti: a.agent.jti },
    user: { sub: a.user.sub, email: a.user.email, permissions: a.user.permissions, token_jti: a.user.jti },
    tool: tool ? { id: tool.id, version: tool.version } : undefined,
    decision: "deny",
    denial_reason: code,
    latency_ms: { total: Date.now() - a.startedAt, ...derivStage(stage) },
    error: extra ? { class: "AUTH", code, ...extra } : { class: "AUTH", code },
  });
  return errorEnvelope(a.requestId, rpcCode, code, a.rpcId);
}

function derivStage(s: Record<string, number>): Record<string, number> {
  const keys = Object.keys(s);
  const out: Record<string, number> = {};
  for (let i = 0; i < keys.length - 1; i++) out[keys[i]] = s[keys[i + 1]] - s[keys[i]];
  return out;
}
```

### 2.6 `audit.ts` — single per-request JSON record

```ts
// src/mcp-server/audit.ts
import { CloudWatchLogsClient, PutLogEventsCommand } from "@aws-sdk/client-cloudwatch-logs";

const cw = new CloudWatchLogsClient({});
const LOG_GROUP = process.env.AUDIT_LOG_GROUP!;
const LOG_STREAM = process.env.AUDIT_LOG_STREAM!;

export async function emitAudit(record: Record<string, unknown>): Promise<void> {
  // Stable shape — see role-passes/security-iam.md §"Audit log schema".
  // Single JSON line. Downstream Firehose → S3 with Object Lock retains it.
  const enriched = { ts: new Date().toISOString(), ...record };
  try {
    await cw.send(new PutLogEventsCommand({
      logGroupName: LOG_GROUP,
      logStreamName: LOG_STREAM,
      logEvents: [{ timestamp: Date.now(), message: JSON.stringify(enriched) }],
    }));
  } catch (e) {
    // Audit MUST NOT silently fail — surface via CloudWatch Metrics.
    console.error("AUDIT_EMIT_FAILED", JSON.stringify({ error: (e as Error).message, record_request_id: enriched.request_id }));
  }
}
```

### 2.7 `errors.ts` — envelope + WWW-Authenticate

```ts
// src/mcp-server/errors.ts
import type { APIGatewayProxyResultV2 } from "aws-lambda";

const RESOURCE_METADATA_URL = `${process.env.MCP_AUDIENCE}/.well-known/oauth-protected-resource`;

export function unauthorizedResponse(requestId: string, reason?: string): APIGatewayProxyResultV2 {
  return {
    statusCode: 401,
    headers: {
      "content-type": "application/json",
      "www-authenticate": `Bearer realm="linq-platform-mcp", resource_metadata="${RESOURCE_METADATA_URL}"${reason ? `, error_description="${reason}"` : ""}`,
      "x-request-id": requestId,
    },
    body: JSON.stringify({
      jsonrpc: "2.0",
      error: { code: -32000, message: "unauthorized", data: { request_id: requestId, reason } },
    }),
  };
}

export function errorEnvelope(
  requestId: string,
  rpcCode: number,
  message: string,
  rpcId?: unknown,
): APIGatewayProxyResultV2 {
  return {
    statusCode: rpcCode === -32000 ? 401 : 200,
    headers: { "content-type": "application/json", "x-request-id": requestId },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: rpcId ?? null,
      error: { code: rpcCode, message, data: { request_id: requestId } },
    }),
  };
}
```

### 2.8 `routes/well-known.ts` — RFC 9728 self-host

```ts
// src/mcp-server/routes/well-known.ts
import type { APIGatewayProxyResultV2 } from "aws-lambda";

export function handleWellKnown(): APIGatewayProxyResultV2 {
  return {
    statusCode: 200,
    headers: { "content-type": "application/json", "cache-control": "max-age=3600" },
    body: JSON.stringify({
      resource: process.env.MCP_AUDIENCE,
      authorization_servers: [process.env.AUTH0_ISSUER],
      bearer_methods_supported: ["header"],
      resource_documentation: "https://confluence.atlassian.linq.com/.../platform-mcp",
    }),
  };
}
```

### 2.9 `routes/tools-list.ts` — server-side projection

```ts
// src/mcp-server/routes/tools-list.ts
import { listToolsForClient } from "../registry.js";

export async function handleToolsList(args: { agent: { client_id: string; scope: string[] }; rpcId: unknown; requestId: string }) {
  // R4 — server-side projection by client_id. The registry's `allowedClientIds` filter is
  // applied here; agent never sees tools its identity is not authorized for.
  const tools = await listToolsForClient(args.agent.client_id, args.agent.scope);
  return {
    statusCode: 200,
    headers: { "content-type": "application/json", "x-request-id": args.requestId },
    body: JSON.stringify({
      jsonrpc: "2.0",
      id: args.rpcId,
      result: {
        tools: tools.map((t) => ({
          name: t.id,
          title: t.title,
          description: t.description,
          inputSchema: t.inputSchema,
        })),
      },
    }),
  };
}
```

### 2.10 SAM packaging notes

- **Build.** `sam build --use-container` (esbuild bundler, target ES2022, externals: `aws-sdk/*`).
- **Layer.** Shared modules (`auth`, `jwks`, `audit`, `errors`, `registry`, `ratelimit`) shipped as a Lambda layer consumed by the handler and the IdentityBroker Lambda.
- **Concurrency.** `ReservedConcurrentExecutions: 10` in V1 [CONFIRMED-by-ADR via `04-phase-1-poc.md`].
- **Provisioned concurrency.** Off in V1. Activate only after measured P95 > 1500 ms for 7 consecutive days (R15, AC6) [CONFIRMED-by-ADR].
- **Cold-start checklist.** Bundle ≤ 5 MB; lazy-import `@aws-sdk/client-sts` and `@aws-sdk/client-lambda` at first call; keep top-level work to env-var reads only; pre-warm `getJwks(ISSUER)` from an init hook only if cold-path measurement exceeds budget.
- **Deploy ordering.** This stack imports `RegistryTableArn` from stack `04-registry` and `IdentityBrokerInvokeArn` + `KmsKeyAlias` from stack `02-secrets` (CC-3). CFN `DependsOn` declared explicitly; nested stack drift detection on.

## 3. Acceptance criteria — observable signals

| AC | Signal | Source |
|---|---|---|
| **AC1** E2E success | `dispatcher.ts` 10-step pipeline returns `decision=allow` audit row + valid `tools/call` JSON-RPC response. | `routes/tools-call.ts` |
| **AC2** Audit completeness | Single CloudWatch log line per request matches the audit schema in [`role-passes/security-iam.md`](../role-passes/security-iam.md). | `audit.ts` |
| **AC3** Tenant-scope enforcement BEFORE STS | Step 4 returns `TENANT_SCOPE_VIOLATION` with no `sts.AssumeRole` CloudTrail entry. | `routes/tools-call.ts` step 4 |
| **AC5** Cache effectiveness | Second invocation within 5 min: 0 DDB GetItem calls (in-process cache hit) and 0 STS calls (session cache hit). | `registry.ts`, `sts-cache.ts` |
| **AC6** Cold-path P95 ≤ 1500 ms | CloudWatch metric `Duration` p95 over rolling 1 h ≤ 1500 ms with `ReservedConcurrentExecutions=10` and provisioned concurrency off. | SAM template |
| **AC7** `tools/list` projection | Two `client_id` values receive different tool lists from the same registry state. | `routes/tools-list.ts` |
| **AC8** Token passthrough refusal | Request whose `arguments` contain a JWT-shaped string returns `TOKEN_PASSTHROUGH_REFUSED` before `IdentityBroker` exchange. | `containsJwtLike()` in `routes/tools-call.ts` |
| **AC9** `/.well-known/oauth-protected-resource` | Unauthenticated GET returns the RFC 9728 metadata document; 401 responses carry `WWW-Authenticate: Bearer resource_metadata="..."`. | `routes/well-known.ts`, `errors.ts` |

## 4. Effort estimate

`5 d [ASSUMED]` — scaffold (0.5 d), auth + JWKS (0.5 d), registry cache + projection (0.5 d), 10-step pipeline (1.5 d), audit + errors + well-known (0.5 d), SAM packaging + layer wiring (0.5 d), tests + AC wiring (1 d).

## 5. Open questions

- **Q-IMPL.6 (MCP SDK version pin).** Pin `@modelcontextprotocol/sdk` to the latest 2025-06-18-conformant release. The exact npm version available at lock-in time is `unable to verify` — the spec is the contract, the SDK is the implementation. Hard fail on `initialize` if the client advertises a `protocolVersion` older than `2025-06-18`.
- **Q-IMPL.1 (TypeScript vs. Python).** Brief assumes Node 20 + TypeScript [ASSUMED]. The Anthropic MCP TypeScript SDK is the reference implementation, which is the primary reason. If LINQ standardizes on Python for Lambda, switch to `mcp` (Python SDK) and re-time at +1 d for type-checker parity.
- **Q-IMPL.X1 (rate-limit storage).** In-process token bucket (`ratelimit.ts`) is correct for `ReservedConcurrentExecutions=10`. At higher concurrency or multi-region, move to ElastiCache. Track but do not block V1.
- **Q-IMPL.X2 (RFC 8707 enforcement strictness).** Auth0's emission of the `resource` parameter as a top-level claim vs. inside `aud` is `unable to verify` from the wiki. The code accepts both, but a tighter check (require `resource` claim explicitly) is preferable once Auth0 behavior is confirmed.

## 6. Cross-references

- ADR — [`docs/decisions/0015-centralized-platform-mcp.md`](../../../decisions/0015-centralized-platform-mcp.md)
- Architecture & 10-step pipeline — [`../01-architecture.md`](../01-architecture.md)
- Phase-1 POC + AC list — [`../04-phase-1-poc.md`](../04-phase-1-poc.md)
- MCP/AI role pass — [`../role-passes/mcp-integration.md`](../role-passes/mcp-integration.md)
- Security & IAM role pass + audit schema — [`../role-passes/security-iam.md`](../role-passes/security-iam.md)
- Prompt-to-handler deep dive — [`../deep-dives/prompt-to-handler.md`](../deep-dives/prompt-to-handler.md)
- Risk register — [`../03-risks-register.md`](../03-risks-register.md)
- Open questions log — [`../05-open-questions.md`](../05-open-questions.md)

## 7. Risks protected against

- **R3** — Token passthrough refusal. `containsJwtLike()` rejects any JWT-shaped string in `tools/call.arguments` before `IdentityBroker` exchange; user-token forwarding is structurally impossible because `verifyUserJwt` requires `aud=MCP_AUDIENCE` (not the handler audience).
- **R4** — `tools/list` projection. `routes/tools-list.ts` filters by `client_id` server-side. The agent never sees tools outside its authorized slice.
- **R5** — RFC 9728 self-host. `routes/well-known.ts` serves the resource-server metadata; `errors.ts` emits `WWW-Authenticate: Bearer resource_metadata="..."` on 401. No Auth0 RFC 9728 dependency.
- **R8** — Rate limit. Per-agent + per-tool token bucket in `ratelimit.ts` defaults to 10 req/s per `(client_id, tool_id)`; circuit-break at 5× baseline per handler.
- **R10** — `request_id` correlation. Embedded in `RoleSessionName` and as an `sts:TagSession` tag, plus the audit record. CloudTrail in the product account joins on `request_id`.
- **R11** — `listChanged` debounce. The MCP server coalesces registry-stream notifications within a 30–60 s window before emitting `notifications/tools/list_changed` (debounce module not shown — lives in `registry.ts`'s stream consumer).
- **R13** — `timeoutMs` honored. Step 9 passes the registry-declared `timeoutMs` (default 30 000 ms) into `dispatchHandler`, which sets the substrate-level deadline.
- **R15** — Cold-start gate. Provisioned concurrency stays off until measured P95 > 1500 ms for 7 consecutive days; reserved concurrency = 10; bundle ≤ 5 MB; lazy AWS SDK imports.
- **R17** — Registry cache 5-min TTL + bypass header. `registry.ts` honors `X-Registry-Cache-Bypass: 1` for ops debugging; warm hits cost zero DDB calls.
- **R19** — RFC 8707 `resource` parameter binding. `auth.ts` checks the `resource` claim against `MCP_AUDIENCE` and rejects mismatches; `aud` strictness is enforced via `jose`'s `audience` option.

## 8. Disagreement / open

- **Reserved concurrency = 10 is tight for the POC, generous for V1 stable state.** The brief mandates it [CONFIRMED-by-ADR via `04-phase-1-poc.md`]. I would argue for `10` during POC and a measured ramp to `25–50` after the second product onboards, but this is a tuning matter, not a design objection. Flagged for the V1.5 retro.
- **In-process rate limiting is correct only at this concurrency.** With reserved concurrency = 10, the per-Lambda-instance token bucket approximates the global bucket within ~10% drift. If concurrency rises, ElastiCache-backed rate limiting becomes mandatory; do not silently scale concurrency without re-checking this.
- **JWT-shape detection (R3) is a heuristic, not a proof.** A handler input field that legitimately accepts long base64-encoded blobs could trigger a false positive on `^ey...\..+\..+$`. The cleaner enforcement is at the registry — disallow any `inputSchema` field whose `format` is `jwt` or whose name matches `*token*`. Recommended as a registry-side rule in addition to the runtime check.
- **The MCP `tools/call` response shape uses `content[]` with text-encoded JSON, not `structuredContent`.** This is the conservative V1 default — `structuredContent` is a 2025-06-18 addition and clients on older SDKs ignore it ([`role-passes/mcp-integration.md`](../role-passes/mcp-integration.md) finding 2). Once the platform commits to a typed-output style guide, swap to `structuredContent` + `outputSchema` per tool. Tracked in V1.5.
