# Implementation plan — LINQ Platform MCP Server (V1)

**Status:** Draft awaiting plan approval. Phase 2.4 (code) gated on user sign-off.
**Date:** 2026-05-06
**Owner:** Platform engineer.
**ADR:** [`docs/decisions/0025-platform-mcp-server.md`](../../decisions/0025-platform-mcp-server.md)
**Implementation repo:** [`github.com/shannoncarver/platform-mcp-server-hackathon`](https://github.com/shannoncarver/platform-mcp-server-hackathon)
**Effort estimate:** ~12–14 hours of focused work across 26 tasks (excluding human-checkpoint pauses and AWS deploy waits).

## Goal and exit criteria

Implement [ADR 0025](../../decisions/0025-platform-mcp-server.md) end-to-end. Exit criteria:

1. `aws sso login --profile platform-mcp` produces credentials that work against the deployed Platform MCP API Gateway.
2. The Platform MCP Lambda extracts the user's email from the assumed-role ARN and looks up permissions in DynamoDB.
3. `tools/list` returns a projected catalog containing `erp.checkUserAccess` (and the three platform navigation tools); `tools/call erp.checkUserAccess` dispatches via SigV4 to the per-product API Gateway in `linq-erp-dev`.
4. The `erp.checkUserAccess` Lambda in `linq-erp-dev` reads `erp_users` and `erp_tenants`, enforces tenant scope, and returns a JSON authorization envelope.
5. Every request emits one structured-JSON audit record to CloudWatch Logs.
6. RBAC negative test passes: a user without the required permission row receives a typed authorization-denied response with no call to the product API.
7. Resource-policy negative test passes: removing the Platform MCP role ARN from the product API's resource policy yields `403 Forbidden` from the product API.

## Three task families

| Family | Repo / target | Owner | Approximate effort |
|---|---|---|---|
| **A** | `platform-mcp-server-hackathon` (Platform MCP code + Platform infra CFN) | Platform engineer | ~7 h |
| **B** | `linq-erp-dev` AWS account (ERP handler Lambda + REST API v1 + IaC) | Platform engineer (acting as product owner for the demo) | ~3 h |
| **C** | AWS SSO + DDB seeds + end-to-end demo | Platform engineer | ~2 h |

Families A and B can proceed in parallel until the integration test (C4). Family C runs after A and B deploy.

---

## Family A — Platform MCP server in the new repo

### A1 — Bootstrap the empty repo (20 min)

- Files: `package.json`, `tsconfig.json`, `tsconfig.test.json`, `jest.config.js`, `README.md`, `CHANGELOG.md`, `LICENSE` (MIT), `.gitignore`, `.editorconfig`. Create directory skeleton: `src/`, `src/routes/`, `test/`, `infra/cfn/`, `scripts/`.
- Tests: none.
- AC: `npm install` succeeds against an empty source tree; `npm test` exits 0 with "no tests found"; `npx tsc --noEmit` exits 0.
- Rollback: `rm -rf` and start over; the repo is empty, so no harm.

### A2 — Type definitions (20 min)

- Files: `src/types.ts` — `RegistryItem`, `AuditRecord`, `UserPrincipal`, `Caller`, `ToolListEntry`. No behavior, just types.
- Tests: type-shape assertions in `test/types.test.ts`.
- AC: `npx tsc --noEmit` clean.
- Rollback: revert.

### A3 — `errors.ts` (15 min)

- Files: `src/errors.ts` — JSON-RPC error envelope helpers (`rpcError`, `rpcOk`, `unauthorized`, `forbidden`); HTTP-level error helpers for API Gateway responses.
- Tests: `test/errors.test.ts` — verify error shapes match JSON-RPC 2.0 spec.
- AC: tests green; type-checks clean.
- Rollback: revert.

### A4 — `caller-identity.ts` (25 min)

- Files: `src/caller-identity.ts` — extract `user_email` from `requestContext.authorizer.iam.userArn` (or `requestContext.identity.userArn` as a fallback). Handle the AWS-SSO-shaped ARN: `arn:aws:sts::ACCOUNT:assumed-role/AWSReservedSSO_PERMSET_xxx/email`. Surface `account_id` and `permission_set_name` too.
- Tests: `test/caller-identity.test.ts` — table-driven cases for valid SSO ARN, malformed ARN, missing authorizer, alternate v1/v2 event payload shapes.
- AC: 6+ test cases pass; the parser handles both HTTP API v2 and REST API v1 payload shapes.
- Rollback: revert.

### A5 — `user-permissions-store.ts` (25 min)

- Files: `src/user-permissions-store.ts` — read `platform_mcp_user_permissions[user_email]` from DDB via `@aws-sdk/lib-dynamodb`. In-process LRU cache (5-min TTL, 1024-entry cap) keyed by email. Returns `{ permissions: Set<string>, tenant_id?: string, last_modified_at: string }` or `undefined`.
- Tests: `test/user-permissions-store.test.ts` — mock DDB client; verify cache hit/miss/expiry; verify SS attribute unmarshalling.
- AC: tests green including a TTL-expiry case; client is module-level (single per cold start).
- Rollback: revert.

### A6 — `registry.ts` (30 min)

- Files: `src/registry.ts` — DDB-backed tool registry. `getProjected(userEmail, permissions)` returns the slice of registry items whose `requiredPermissions[]` is satisfied by the user's permissions. `getById(toolId)` for `tools/call`. 5-min in-process cache for full registry; per-call projection is in-memory.
- Tests: `test/registry.test.ts` — projection includes/excludes correctly; cache TTL behavior; `getById` returns the right item.
- AC: tests green; projection takes O(n) over registry size; n ≤ 50 in V1.
- Rollback: revert.

### A7 — `audit.ts` (20 min)

- Files: `src/audit.ts` — emit one structured-JSON line per request to CloudWatch Logs via `@aws-sdk/client-cloudwatch-logs` or `console.log` (Lambda runtime captures stdout). Fields: `request_id`, `caller_email`, `caller_arn`, `tool_id`, `decision` (allow/deny), `denial_reason?`, `latency_ms`, `outbound_status?`.
- Tests: `test/audit.test.ts` — verify schema; verify JSON parses cleanly.
- AC: tests green; emitter is fail-safe (audit failure logs to stderr but doesn't break the request).
- Rollback: revert.

### A8 — `routes/tools-list.ts` (20 min)

- Files: `src/routes/tools-list.ts` — handle JSON-RPC `tools/list` with cursor pagination per MCP `2025-06-18`. Project by caller; emit `nextCursor` if more pages exist; cap page size at 50.
- Tests: `test/routes/tools-list.test.ts` — projection behaves correctly; cursor round-trips through 100-item registry; unknown cursor returns empty page (not error).
- AC: tests green; pagination is order-stable.
- Rollback: revert.

### A9 — `routes/tools-search.ts` (25 min)

- Files: `src/routes/tools-search.ts` — `platform.search_tools` returning `tool_reference[]` content blocks. Regex search against tool name + description over the projected catalog. Cap query length at 200; cap result count at 5.
- Tests: `test/routes/tools-search.test.ts` — happy path (regex match); query too long; malformed regex; RBAC negative (search of unauthorized tools returns nothing); rate-limit boundary.
- AC: 5+ test cases pass; matches Anthropic's "Custom tool search implementation" content-block shape.
- Rollback: revert.

### A10 — `sigv4-dispatcher.ts` (30 min)

- Files: `src/sigv4-dispatcher.ts` — SigV4-signed HTTPS POST to a product API Gateway URL. Uses `@aws-sdk/signature-v4` + `@aws-sdk/credential-provider-node` + `@smithy/protocol-http`. Surfaces network errors and non-2xx responses as typed errors.
- Tests: `test/sigv4-dispatcher.test.ts` — mock the HTTP layer; verify the `Authorization` header has `AWS4-HMAC-SHA256 Credential=…` shape; verify `X-Amz-Security-Token` present (Lambda execution role uses temp creds).
- AC: tests green; signing path uses ambient Lambda credentials with no explicit secret-loading.
- Rollback: revert.

### A11 — `routes/tools-call.ts` (30 min)

- Files: `src/routes/tools-call.ts` — `tools/call` dispatcher. Steps: (1) lookup tool by ID; (2) check visibility against user permissions (deny with `TOOL_NOT_FOUND` if not visible — leaks no metadata); (3) coarse RBAC check on `requiredPermissions`; (4) dispatch via `sigv4-dispatcher` to the registered URL; (5) emit audit; (6) return JSON-RPC result.
- Tests: `test/routes/tools-call.test.ts` — happy path; missing-tool returns RPC `-32602`; insufficient permissions returns `TOOL_NOT_FOUND` (RBAC negative); upstream 4xx surfaces correctly; upstream 5xx surfaces correctly.
- AC: 5+ test cases pass; the dispatcher passes through `{user_email, tenant_id, request_id}` in the body.
- Rollback: revert.

### A12 — `platform-handlers.ts` (20 min)

- Files: `src/platform-handlers.ts` — in-process handlers for `platform.whoami` (returns caller info) and `platform.list_products` (returns distinct namespace prefixes from the projected catalog).
- Tests: `test/platform-handlers.test.ts` — both return the correct shape; `whoami` reflects the actual caller; `list_products` filters by projection.
- AC: tests green.
- Rollback: revert.

### A13 — `index.ts` (25 min)

- Files: `src/index.ts` — Lambda handler. Parse APIGW v2 event; extract caller via `caller-identity.ts`; load permissions via `user-permissions-store.ts`; parse JSON-RPC body; dispatch to `tools/list`, `tools/call`, `platform.search_tools` based on method; return JSON-RPC envelope.
- Tests: `test/index.test.ts` — end-to-end event-to-response covering `tools/list`, `tools/call`, and an unknown method.
- AC: 3+ test cases pass; the handler is the only file with `export const handler =` and is what `infra/cfn/platform.yaml` points to.
- Rollback: revert.

⏸ **CHECKPOINT (after A13):** human review of the platform code before infra deploy. Run `npm test` locally; expect all tests green.

### A14 — Platform infrastructure CFN (30 min)

- Files: `infra/cfn/platform.yaml` — DDB tables (`platform_mcp_user_permissions`, `platform_mcp_tool_registry`); Platform MCP Lambda function + execution role; HTTP API v2 + `AWS_IAM` auth on `/jsonrpc`; CloudWatch Logs group; outputs for the API GW URL and the Lambda role ARN.
- Tests: stack synth via `aws cloudformation validate-template`.
- AC: stack validates clean; deploys to the Platform AWS account; outputs print the API GW URL and Lambda role ARN.
- Rollback: `aws cloudformation delete-stack`. DDB tables have `DeletionPolicy: Retain` to protect seeded data.

### A15 — Platform deploy + smoke (20 min)

- Files: `scripts/deploy-platform.sh` — wraps `sam build && sam deploy --stack-name platform-mcp-server --region us-east-1 --capabilities CAPABILITY_IAM`.
- Tests: smoke — `aws sso login --profile platform-mcp` → `curl --aws-sigv4 ...` an unauthenticated `tools/list` → expect 200 with empty `tools` array (registry is empty until C3).
- AC: smoke returns the expected empty list; CloudWatch shows one audit record.
- Rollback: re-run delete-stack.

⏸ **CHECKPOINT (after A15):** platform infra is live. Capture the API GW URL and the Platform MCP Lambda role ARN — both are inputs to family B.

---

## Family B — ERP handler in `linq-erp-dev`

### B1 — ERP handler Lambda code (30 min)

- Files: `infra/erp-handler/src/index.ts` (in the `platform-mcp-server-hackathon` repo, since the ERP handler is part of this hackathon's deliverable). Reads `erp_users` (twice) and `erp_tenants` (once) per the existing decision rules. Produces JSON envelope `{ authorization: { authorized, status, reason }, user, tenant }`.
- Tests: `infra/erp-handler/test/index.test.ts` — fixture-driven decision matrix covering `AUTHORIZED_USER`, `AUTHORIZED_SUPERUSER`, `USER_NOT_FOUND`, `USER_DISABLED`, `TENANT_DISABLED`, `TENANT_MISSING_BUT_USER_AUTHORIZED`.
- AC: 6+ test cases pass against mocked DDB.
- Rollback: revert.

### B2 — ERP handler enforces tenant + caller (15 min)

- Files: `infra/erp-handler/src/index.ts` (extend) — at the top of the handler, verify the request body includes `user_email` and `tenant_id`. The handler trusts these because the API Gateway's resource policy + AWS_IAM auth proves the call came from the Platform MCP role. Reject calls with missing fields as `400`.
- Tests: extend `test/index.test.ts` with body-validation cases.
- AC: missing fields surface as `400`; the body-validation logic runs before any DDB call.
- Rollback: revert.

### B3 — ERP infra CFN (25 min)

- Files: `infra/erp-handler/cfn/erp-handler.yaml` — REST API v1 with `/erp/checkUserAccess` (POST, `AWS_IAM` auth); resource policy listing the Platform MCP Lambda role ARN as `Allow execute-api:Invoke`; ERP handler Lambda; IAM exec role with read-only DDB access on `erp_users` and `erp_tenants`.
- Tests: stack synth via `aws cloudformation validate-template`.
- AC: stack validates clean.
- Rollback: revert + delete-stack.

### B4 — Deploy ERP infra to `linq-erp-dev` (20 min)

- Files: `scripts/deploy-erp-handler.sh` — `sam build && sam deploy --profile linq-erp-dev --stack-name erp-handler-platform-mcp --capabilities CAPABILITY_IAM --parameter-overrides PlatformMcpRoleArn=<from A14 outputs>`.
- Tests: smoke — `curl --aws-sigv4` from a temporary IAM identity that's NOT the Platform MCP role → expect `403 Forbidden`. Then test from the actual Platform MCP role (via A15 smoke) → expect `200`.
- AC: 403 from unauthorized callers; 200 from Platform MCP. Resource policy validated.
- Rollback: re-run delete-stack against `linq-erp-dev`.

### B5 — Wire `erp.checkUserAccess` into the registry (10 min)

- Files: a one-shot script `scripts/seed-tool-registry.ts` that writes a row to `platform_mcp_tool_registry`. Row: `{ toolId: "erp.checkUserAccess", version: "1.0.0", description: "...", inputSchema: { ... }, outputSchema: { ... }, requiredPermissions: ["erp:user:read"], productApiUrl: "<from B4 outputs>" }`.
- Tests: smoke run; `aws dynamodb get-item` confirms the row.
- AC: row present in DDB; calling `tools/list` from the user side now shows `erp.checkUserAccess`.
- Rollback: `aws dynamodb delete-item`.

⏸ **CHECKPOINT (after B5):** the cross-account invoke chain is fully wired. The next checkpoint is the end-to-end demo.

---

## Family C — AWS SSO + seeds + demo

### C1 — AWS SSO permission set (15 min)

- Files: none (manual provisioning via the AWS console for the hackathon). Document the steps in `README.md`.
- Tests: `aws sso login --profile platform-mcp` from the demo laptop produces working STS credentials.
- AC: `aws sts get-caller-identity --profile platform-mcp` returns an assumed-role ARN with `AWSReservedSSO_PlatformMcpUser_xxx/<email>` shape.
- Rollback: delete the permission set in the AWS console.

### C2 — Demo user permissions seed (10 min)

- Files: a one-shot script `scripts/seed-demo-user.ts`. Writes `{ user_email: "<demo-user-email>", permissions: Set(["erp:user:read"]), tenant_id: "<demo-tenant>", last_modified_at: <now>, last_modified_by: "hackathon-bootstrap" }`.
- Tests: smoke; verify with `aws dynamodb get-item`.
- AC: row present.
- Rollback: `aws dynamodb delete-item`.

### C3 — Platform navigation tools seeds (15 min)

- Files: extend `scripts/seed-tool-registry.ts` to also write `platform.whoami`, `platform.list_products`, and `platform.search_tools` rows. These three are always-loaded; their `productApiUrl` is the special value `inline://` (handled by `index.ts` as in-process dispatch via `platform-handlers.ts`).
- Tests: `tools/list` returns 4 tools (3 platform + `erp.checkUserAccess`).
- AC: catalog is complete.
- Rollback: delete-item per row.

### C4 — End-to-end demo run (30 min, includes scripting the CLI)

- Files: `scripts/demo-cli.ts` — minimal Node CLI: `aws sso login` → load credentials → SigV4-sign a `tools/call erp.checkUserAccess` JSON-RPC request → POST to the Platform MCP API GW → print the response.
- Tests: run the CLI; verify the response matches the ERP handler's expected envelope shape with `authorized: true` for the seeded demo user; then test a negative case (user without permission) and confirm the typed denial.
- AC: both happy-path and negative-path runs succeed; CloudWatch shows the per-request audit record.
- Rollback: N/A — demo only.

⏸ **CHECKPOINT (after C4):** demo is operational. PR review and merge into `main` for both repos.

---

## Risks and watch-list

- **HTTP API v2 IAM authorizer event shape uncertainty.** The deep-dive flagged that `requestContext.authorizer.iam` field shape isn't fully documented in the AWS pages I fetched. A1 of family A bakes in a fallback (try `authorizer.iam.userArn`, fall back to `identity.userArn`). If the deployed event surfaces something different, A4 needs adjustment. Keep this on the radar during A15 smoke.
- **AWS SSO permission-set propagation latency.** New SSO permission sets can take a few minutes to be assignable. C1 may need a coffee break.
- **DDB on-demand cold-start latency on first read.** Acceptable for the demo. If user notices a 200 ms first-call delay, consider provisioned read capacity for V1.5.
- **Resource policy on REST API v1 — `Principal` ARN matching.** The principal ARN in the resource policy must be the Platform MCP Lambda's role ARN, not the assumed-role STS ARN. Get this wrong and you'll see `Forbidden` with no audit trail. B3 should output this ARN clearly to make verification easy.
- **Deploy-region drift.** Platform infra and ERP infra must deploy in the same region (recommend `us-east-1`). Cross-region SigV4 is possible but adds latency and signing-region complexity. Hard-code the region in both deploy scripts.

## Cross-references

- ADR — [`docs/decisions/0025-platform-mcp-server.md`](../../decisions/0025-platform-mcp-server.md)
- Foundational research — [`deep-dives/v1-auth-and-dispatch-research.md`](deep-dives/v1-auth-and-dispatch-research.md)
- Implementation repo — [github.com/shannoncarver/platform-mcp-server-hackathon](https://github.com/shannoncarver/platform-mcp-server-hackathon)
