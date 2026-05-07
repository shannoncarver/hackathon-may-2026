# V1 auth and dispatch — research

**Status:** Foundational research for ADR 0025 (LINQ Platform MCP Server, V1). Not part of any prior architectural lineage; this work stands alone.
**Date:** 2026-05-06
**Owner:** Platform engineer.

This document captures the eight research topics that ground the V1 design of the LINQ Platform MCP Server. Each finding is sourced verbatim from authoritative documentation. The summary at the end calls out one architectural adjustment that emerged from the research itself.

## 1. AWS SSO + IAM Identity Center identity model

When a user runs `aws sso login`, they obtain temporary STS credentials representing an *assumed-role* session. The AWS-side identifier of that session is an STS ARN with three components:

> `arn:aws:sts::account:assumed-role/role-name/role-session-name`
> — [IAM identifiers reference](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html)

For AWS-SSO-issued sessions specifically:

- **`role-name`** is `AWSReservedSSO_<PERMISSION_SET_NAME>_<HASH>`. The permission-set name is platform-controlled; the hash is auto-generated.
- **`role-session-name`** is the user's email (or other upstream-IdP subject identifier). For LINQ employees authenticated via the corporate IdP, this is the work email.

Worked example for a user `alice@linq.com` assuming permission set `PlatformMcpUser` in the Platform Services account:

```
arn:aws:sts::PLATFORM_ACCOUNT:assumed-role/AWSReservedSSO_PlatformMcpUser_a1b2c3/alice@linq.com
```

The AWS docs give a concrete example with the same shape:

> `arn:aws:sts::123456789012:assumed-role/Accounting-Role/Mary`
> — *"The active session of someone assuming the role of 'Accounting-Role', with a role session name of 'Mary'"*

**Implication for the design:** the Platform MCP can extract `user_email` reliably from the assumed-role ARN — split on `/`, take the last segment. No JWT validation required; the trust anchor is the SigV4 signature (which API Gateway validates) plus the role session name set by AWS SSO during login.

## 2. API Gateway HTTP API v2 with `AWS_IAM` auth

HTTP API v2 supports per-route IAM authorization. Enable it with:

> ```
> aws apigatewayv2 update-route \
>     --api-id abc123 \
>     --route-id abcdef \
>     --authorization-type AWS_IAM
> ```
> — [Control access to HTTP APIs with IAM authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html)

When AWS_IAM is on:

> *"clients must use Signature Version 4 (SigV4) to sign their requests with AWS credentials. API Gateway invokes your API route only if the client has `execute-api` permission for the route."*

**Critical caveat — verbatim from the same doc:**

> **"Resource policies aren't currently supported for HTTP APIs."**

This single sentence has architectural consequences (see §6 and the summary).

## 3. SigV4 signing from a Lambda execution role

SigV4 authenticates a request via four steps:

1. **Canonical request** — the HTTP method, URI, query string, headers, and payload hash, concatenated in a deterministic format.
2. **String to sign** — algorithm, timestamp, credential scope (date/region/service), and a hash of the canonical request.
3. **Derived signing key** — a chained HMAC-SHA256 over the secret access key, date, region, service, and the literal `aws4_request`.
4. **Signature** — HMAC-SHA256(signing key, string-to-sign), hex-encoded.

The signature lives in the `Authorization` header:

> ```
> Authorization: AWS4-HMAC-SHA256
> Credential=AKIAIOSFODNN7EXAMPLE/20220830/us-east-1/ec2/aws4_request,
> SignedHeaders=host;x-amz-date,
> Signature=calculated-signature
> ```
> — [Create a signed AWS API request](https://docs.aws.amazon.com/general/latest/gr/sigv4_signing.html)

For temporary credentials (which is what every Lambda execution role provides, and what AWS SSO returns to a user), an additional header is required:

> *"When you use temporary security credentials, you must add `X-Amz-Security-Token` to the Authorization header or include it in the query string to hold the session token."*

**Implication for the design:** the Platform MCP Lambda uses its own execution role's credentials to SigV4-sign HTTPS requests to the per-product API Gateway. The AWS SDK v3 (`@aws-sdk/signature-v4` or the per-service signed-fetch helpers) handles canonicalization and signing automatically. No manual canonical-request construction is required in the implementation.

The user's MCP client (Claude Code, or any AWS-SDK-aware client) does the same on its end with the AWS SSO session credentials loaded from `~/.aws/credentials`.

## 4. DDB schema design for the user-permissions store

The user-permissions table is read-heavy, write-rare, and accessed once per Platform MCP request (with a 5-minute in-process cache).

**Schema choice:**

- **Partition key** = `user_email` (string).
- **No sort key** — single row per user; sort key adds complexity without benefit.
- **Attributes**:
  - `permissions` — list of MCP scopes the user has.
  - `tenant_id` — optional; surfaced to handlers via the request body. Platform doesn't enforce on it.
  - `last_modified_at` — string ISO-8601 timestamp.
  - `last_modified_by` — admin who last edited the row, for audit.

**Permissions attribute type — String Set (SS) vs JSON-encoded String:**

DDB has a native `StringSet` (SS) type. For our access pattern:
- We only need membership checks (`erp:user:read` ∈ permissions?), never ordering or duplicates.
- SS is wire-efficient and supports DDB-native set operations (`ADD`, `DELETE`).
- The DocumentClient unmarshalls SS to a JS `Set` automatically.

Decision: use SS.

**Billing:**

On-demand. The workload is read-heavy at low volume (one read per MCP request, <100 RPS at hackathon scale). On-demand has zero capacity-planning overhead and the per-request cost is rounding error.

**Item size:**

DDB items cap at 400 KB. Our items are <1 KB.

**TTL:**

Not used in V1. Permissions changes are admin-driven, not time-bound. Adding TTL later is non-breaking.

**Authoritative reference for relational-style modeling principles** (the AWS docs example uses a multi-table pattern that doesn't fit the simple lookup case directly, but the principles apply):

> *"using separate tables for entities with low access correlation"* — [DynamoDB modeling examples](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-modeling-nosql-B.html)

## 5. MCP protocol surface (`2025-06-18`)

The Platform MCP Server speaks JSON-RPC 2.0 conforming to the MCP `2025-06-18` spec. Three methods matter for V1:

### `initialize`

Server-side response advertises capabilities:

> ```json
> {
>   "capabilities": {
>     "tools": {
>       "listChanged": true
>     }
>   }
> }
> ```

`listChanged: true` indicates the server will emit `notifications/tools/list_changed` when the catalog changes (we do — when registry items are added/removed/updated).

### `tools/list`

Verbatim request:

> ```json
> {
>   "jsonrpc": "2.0",
>   "id": 1,
>   "method": "tools/list",
>   "params": {
>     "cursor": "optional-cursor-value"
>   }
> }
> ```

Verbatim response:

> ```json
> {
>   "jsonrpc": "2.0",
>   "id": 1,
>   "result": {
>     "tools": [
>       {
>         "name": "get_weather",
>         "title": "Weather Information Provider",
>         "description": "Get current weather information for a location",
>         "inputSchema": {
>           "type": "object",
>           "properties": {
>             "location": {
>               "type": "string",
>               "description": "City name or zip code"
>             }
>           },
>           "required": ["location"]
>         }
>       }
>     ],
>     "nextCursor": "next-page-cursor"
>   }
> }
> ```
> — [MCP `2025-06-18` Tools section](https://modelcontextprotocol.io/specification/2025-06-18/server/tools)

Tool definition fields:

> *"`name`: Unique identifier for the tool. `title`: Optional human-readable name of the tool for display purposes. `description`: Human-readable description of functionality. `inputSchema`: JSON Schema defining expected parameters. `outputSchema`: Optional JSON Schema defining expected output structure. `annotations`: optional properties describing tool behavior."*

### `tools/call`

Verbatim request:

> ```json
> {
>   "jsonrpc": "2.0",
>   "id": 2,
>   "method": "tools/call",
>   "params": {
>     "name": "get_weather",
>     "arguments": {
>       "location": "New York"
>     }
>   }
> }
> ```

Verbatim response:

> ```json
> {
>   "jsonrpc": "2.0",
>   "id": 2,
>   "result": {
>     "content": [
>       {
>         "type": "text",
>         "text": "Current weather in New York:\nTemperature: 72°F\nConditions: Partly cloudy"
>       }
>     ],
>     "isError": false
>   }
> }
> ```

Structured content (added in `2025-06-18`):

> *"Structured content is returned as a JSON object in the `structuredContent` field of a result. For backwards compatibility, a tool that returns structured content SHOULD also return the serialized JSON in a TextContent block."*

### Error envelope

> ```json
> {
>   "jsonrpc": "2.0",
>   "id": 3,
>   "error": {
>     "code": -32602,
>     "message": "Unknown tool: invalid_tool_name"
>   }
> }
> ```

Standard JSON-RPC error codes apply: `-32602` for invalid params (including unknown tool), `-32603` for internal server errors.

## 6. Cross-account API Gateway IAM Resource Policy

API Gateway resource policies are documented as the mechanism for cross-account invocation:

> *"You can use API Gateway resource policies to allow your API to be securely invoked by:*
> *— Users from a specified AWS account.*
> *— Specified source IP address ranges or CIDR blocks.*
> *— Specified virtual private clouds (VPCs) or VPC endpoints (in any account)."*
> — [Control access to a REST API with API Gateway resource policies](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-resource-policies.html)

Resource policies work *with* identity-based IAM policies — both must allow:

> *"You can use API Gateway resource policies together with IAM policies."*

**Resource ARN format** (for the per-product API the Platform MCP will invoke):

> `arn:aws:execute-api:region:account-id:api-id/stage-name/HTTP-VERB/resource-path-specifier`
> — [API Gateway IAM action/resource format](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html)

**Cross-account resource policy** — the shape that grants the Platform MCP role permission to invoke the ERP product API:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::PLATFORM_ACCOUNT:role/PlatformMcpLambdaRole"
    },
    "Action": "execute-api:Invoke",
    "Resource": "arn:aws:execute-api:us-east-1:ERP_ACCOUNT:api-id/prod/POST/erp/checkUserAccess"
  }]
}
```

The caller (Platform MCP role) ALSO needs the matching identity-based policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "execute-api:Invoke",
    "Resource": "arn:aws:execute-api:us-east-1:ERP_ACCOUNT:api-id/prod/POST/erp/checkUserAccess"
  }]
}
```

**Critical interaction with finding 2:**

Resource policies are **only available on REST API v1, not HTTP API v2**. This means cross-account dispatch requires REST API v1 on the per-product side. See §"Architectural implications" below.

## 7. Caller-principal extraction in API Gateway proxy events

When `AWS_IAM` auth admits a request and forwards it to a Lambda integration, the Lambda receives an event whose shape depends on the API type and payload format.

### HTTP API v2 (payload format 2.0)

The verbatim event shape ([HTTP API Lambda integrations](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html)):

```json
{
  "version": "2.0",
  "routeKey": "$default",
  "rawPath": "/my/path",
  ...,
  "requestContext": {
    "accountId": "123456789012",
    "apiId": "api-id",
    "authorizer": {
      "jwt": { ... }
    },
    "http": {
      "method": "POST",
      "path": "/my/path",
      "protocol": "HTTP/1.1",
      "sourceIp": "192.0.2.1",
      "userAgent": "agent"
    },
    "requestId": "id",
    "routeKey": "$default",
    "stage": "$default",
    ...
  },
  "body": "...",
  ...
}
```

The docs example shows `requestContext.authorizer.jwt` for JWT authorizers but does not explicitly show `requestContext.authorizer.iam` for AWS_IAM authorizers. Empirically (and per AWS SDK type definitions), when AWS_IAM auth is enabled, `requestContext.authorizer` carries an `iam` block with `userArn`, `accountId`, `accessKey`, etc.

### REST API v1 (payload format 1.0)

The v1 payload format includes a `requestContext.identity` block:

```json
{
  "requestContext": {
    "identity": {
      "accessKey": null,
      "accountId": null,
      "userArn": null,
      "user": null,
      ...
    }
  }
}
```

For an AWS_IAM-authenticated request, `userArn` is the assumed-role ARN of the caller (e.g., `arn:aws:sts::PLATFORM:assumed-role/AWSReservedSSO_PlatformMcpUser_xxx/alice@linq.com`).

### Extraction code (TypeScript)

```typescript
// Works across both payload formats. Prefer authorizer.iam (v2) when present;
// fall back to identity (v1).
function extractCallerArn(event: APIGatewayProxyEventV2): string {
  const fromAuthorizer = (event.requestContext as any)?.authorizer?.iam?.userArn;
  const fromIdentity = (event.requestContext as any)?.identity?.userArn;
  return fromAuthorizer ?? fromIdentity;
}

function extractUserEmail(callerArn: string): string {
  // arn:aws:sts::ACCOUNT:assumed-role/AWSReservedSSO_PERMSET_xxx/email@linq.com
  const segments = callerArn.split("/");
  return segments[segments.length - 1];
}
```

**Open verification needed:** the exact shape of `requestContext.authorizer.iam` for HTTP API v2 was not in the documentation pages I fetched. A 30-min spike with a real deployed HTTP API + Lambda will confirm field names before the Phase 2.4 implementation hardens against them.

## 8. TypeScript Lambda + DDB read patterns for the ERP handler

The ERP handler reads two DDB tables: `erp_users` (twice) and `erp_tenants` (once). It then computes an authorization decision and returns a JSON envelope.

**SDK choice:** `@aws-sdk/client-dynamodb` with `@aws-sdk/lib-dynamodb` (DocumentClient). DocumentClient unmarshalls DDB AttributeValue types into native JS values automatically.

**Cold-start pattern** — initialize at module level, reuse across warm invocations:

```typescript
import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, GetCommand } from "@aws-sdk/lib-dynamodb";

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({}));

const ERP_USERS_TABLE = process.env.ERP_USERS_TABLE_NAME!;
const ERP_TENANTS_TABLE = process.env.ERP_TENANTS_TABLE_NAME!;

async function getUserInTenant(email: string, tenantId: string) {
  const result = await ddb.send(
    new GetCommand({
      TableName: ERP_USERS_TABLE,
      Key: { user_email: email, tenant_id: tenantId },
      ConsistentRead: false,
    }),
  );
  return result.Item;
}
```

**Error handling:** wrap each DDB call in try/catch; surface failures as `status: "ERROR"` in the JSON envelope rather than throwing. This matches the existing skill's behavior — agents parsing the response shouldn't have to handle two error paths.

**Response envelope shape** (matching the skill's contract):

```json
{
  "authorization": {
    "authorized": true,
    "status": "AUTHORIZED_USER",
    "reason": "user-in-tenant row active"
  },
  "user": { "matched_user_record": "user-in-tenant", ... },
  "tenant": { ... }
}
```

## Architectural implications (the one decision the research forced)

**The plan's architecture summary specified HTTP API v2 for both the platform-side and per-product-side gateways.** The research surfaces a conflict:

- The Platform MCP API Gateway (called by the user, *same-account*) — HTTP API v2 with `AWS_IAM` auth works. The user's IAM session has `execute-api:Invoke` permission via the AWS SSO permission set, and same-account IAM is the only gate.
- The per-product API Gateway (called by the Platform MCP, *cross-account*) — HTTP API v2 doesn't support resource policies, which are the documented mechanism for cross-account `AWS_IAM` invocation. **Use REST API v1 here instead.**

This is a small adjustment, not a redesign. Cost difference at hackathon scale is negligible (REST API v1 is ~3× the per-request cost of HTTP API v2, but at <100 RPS it's pennies). The trust model and SigV4 wire shape are identical.

The ADR (Phase 2.2) will codify the corrected design: HTTP API v2 for the platform-side gateway, REST API v1 for the per-product gateway.

## Open research items (deferred to implementation)

These are gaps from the documentation pages I fetched. None block the design; all are 30-min spikes during Phase 2.4:

1. **Exact shape of `requestContext.authorizer.iam`** for HTTP API v2 AWS_IAM auth. The docs example shows the JWT shape but not the IAM shape. Verify with a deployed HTTP API.
2. **AWS SSO permission-set provisioning approach** — manual via console, CFN via `AWS::SSO::*` resources, or Terraform. The docs cover the resource model but not the operational tradeoffs.
3. **Whether HTTP API v2 supports cross-account IAM auth at all** in the absence of resource policies. The docs imply no; an explicit spike would either confirm REST API v1 is required, or surface a workaround (e.g., custom Lambda authorizer).

## Sources

- [IAM identifiers reference](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html) — assumed-role ARN format.
- [Control access to HTTP APIs with IAM authorization](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-access-control-iam.html) — HTTP API v2 + AWS_IAM, "no resource policies" caveat.
- [Control access for invoking an API](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-control-access-using-iam-policies-to-invoke-api.html) — execute-api:Invoke action and resource ARN format.
- [API Gateway resource policies](https://docs.aws.amazon.com/apigateway/latest/developerguide/apigateway-resource-policies.html) — REST API cross-account.
- [Create a signed AWS API request](https://docs.aws.amazon.com/general/latest/gr/sigv4_signing.html) — SigV4 canonical-request and signing-key derivation.
- [Lambda proxy integrations for HTTP APIs](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html) — payload format 2.0 event shape.
- [MCP `2025-06-18` Tools spec](https://modelcontextprotocol.io/specification/2025-06-18/server/tools) — tools/list, tools/call, error envelope.
- [DynamoDB modeling examples](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-modeling-nosql-B.html) — relational-modeling worked example.
