# Implementation 08 — Testing strategy

**Decision:** [`0015-centralized-platform-mcp`](../../../decisions/0015-centralized-platform-mcp.md) — Phase B test strategy.
**Owner:** QA / Test Engineer (`15-eng-qa`).
**Status:** Draft for Phase B implementation.
**Effort estimate:** `4 d [ASSUMED]`.

## 1. Overview

This artifact defines the test strategy for the Phase-1 POC: a four-layer pyramid (unit, contract, integration, end-to-end) plus a manual smoke procedure, every V1 acceptance criterion mapped to at least one named test, every positive AC paired with a negative test, and a local-dev environment that an engineer reproduces with `docker compose up`. Runtime is Jest on Node 20 + TypeScript per cross-cutting decision CC-1; the sample handler under test is `erp.checkUserAccess(userId, tenantId)` per CC-4. Mocks are confined to the unit layer — integration and end-to-end tests run against the real Auth0 dev tenant and real cross-account dispatch into the ERP product sandbox account, because mocking OAuth is more trouble than it is worth and a mocked AssumeRole proves nothing about the design's load-bearing seam. The four named risks the test suite protects against are catalog-projection regressions (R4), the self-hosted RFC 9728 metadata document (R5), runaway agents (R8), audit-principal correlation across the platform audit log and product CloudTrail (R10), registry-to-handler schema drift (R14), and the daily audit-reconciliation alarm (R18).

## 2. Concrete artifacts

### 2.1 Test pyramid

| Layer | Framework | Where it runs | Named tests | Gates |
|---|---|---|---|---|
| **Unit** | Jest (Node 20 + TypeScript) | Per-package CI on every PR | `auth.spec.ts` (JWT validation matrix — 6 cases), `errors.spec.ts` (envelope + WWW-Authenticate shape), `registry.spec.ts` (resolution + cache TTL), `dispatcher.spec.ts` (10-step pipeline, per-substrate adapter), `identity-broker.spec.ts` (RFC 8693 wire shape, `act` claim, ≤ 5-min TTL), `schema.spec.ts` (JSON Schema validate + reject), `ratelimit.spec.ts` (token-bucket math) | Block PR merge on any failure |
| **Contract** | Jest + JSON Schema diff (`ajv` + registry S3 schema fetch) | Handler-repo CI on every PR; also platform-repo CI for `@linq/mcp-handler-sdk` | `erp-checkUserAccess.contract.spec.ts` — diff handler I/O against `inputSchemaRef` / `outputSchemaRef` published in registry; fail on additive, removal, or type drift | Block PR merge on drift (R14) |
| **Integration** | Jest + AWS SDK v3 against deployed sandbox | Nightly + on `main` push | `mcp-server.integration.spec.ts` (deployed Lambda + real Auth0 dev tenant + real DynamoDB registry + real cross-account AssumeRole into ERP sandbox + real handler invoke), `identity-broker.integration.spec.ts` (KMS-signed JWT verifies against platform JWKS), `audit.integration.spec.ts` (record lands in CloudWatch Logs within 30 s, principal correlates to product-account CloudTrail on `request_id`) | Block `main` deploy on failure |
| **End-to-end** | Jest + GitHub Actions matrix (one job per AC) | On every `main` push, also nightly | `ac01-e2e-success.e2e.spec.ts` ... `ac10-docs-parity.e2e.spec.ts` (one file per AC); plus 10 paired negatives (`ac01-e2e-failure.e2e.spec.ts`, `ac03-tenant-scope-rejection.e2e.spec.ts`, etc.) | Block release on any failure |

Cite: [Jest docs](https://jestjs.io/docs/getting-started), [ajv JSON Schema validator](https://ajv.js.org/), [`@modelcontextprotocol/inspector`](https://github.com/modelcontextprotocol/inspector).

### 2.2 AC-to-test coverage matrix

Every V1 acceptance criterion from [`04-phase-1-poc.md`](../04-phase-1-poc.md) §"Acceptance criteria" maps to at least one named test plus a paired negative case. Expected assertions cite the observable signal a CI job inspects.

| AC | Title | Positive test | Negative test | Expected assertion |
|---|---|---|---|---|
| **AC1** | End-to-end success | `ac01-e2e-success.e2e.spec.ts` | `ac01-handler-5xx.e2e.spec.ts` (handler returns 500 — broker emits `class=UPSTREAM_ERROR`, audit `decision=deny`, `denial_reason=upstream_error`) | Agent receives `{ result: { allowed: true } }`, `request_id` correlates platform audit log to ERP-account CloudTrail entry; full chain (`agent_client_id`, `user_sub`, `tool_id`, `handler_arn`, `tenant_id`) present in audit row |
| **AC2** | Audit completeness | `ac02-audit-fields.e2e.spec.ts` | `ac02-audit-missing-field.e2e.spec.ts` (synthetic broker build with one field stripped — pre-deploy lint catches it) | Audit JSON record contains all 11 named fields (per `01-architecture.md` audit contract); per-stage `latency_ms` sums to total within 5 ms |
| **AC3** | Tenant-scope enforcement | `ac03-tenant-scope-allow.e2e.spec.ts` (matching `tenant_id`) | `ac03-tenant-scope-reject.e2e.spec.ts` (user JWT `tenant_id=globex`, request `tenantId=acme`) | Negative: HTTP 403 with `class=AUTH, code=TENANT_SCOPE_VIOLATION, retryable=false`; **no STS call recorded** in CloudTrail; audit `decision=deny, denial_reason=tenant_scope` |
| **AC4** | Registry write enforcement | `ac04-registry-write-valid.spec.ts` (well-formed `sideEffects: "read"` entry accepted) | `ac04-registry-write-reject.spec.ts` (4 sub-cases: `sideEffects: "write"` rejected; missing `tenantSourceClaim` rejected; `assumeRoleArn` outside allowlist rejected; `owner` not in directory rejected) | Negative: registration API returns HTTP 400 with one specific `code` per sub-case; DynamoDB item count unchanged; CI lint reproduces the 4 rejections offline |
| **AC5** | Cache effectiveness | `ac05-cache-hit.integration.spec.ts` (second `tools/call` within 5 min) | `ac05-cache-bypass.integration.spec.ts` (`X-MCP-Cache-Bypass: 1` header forces miss; documented ops escape) | Positive: zero DynamoDB `GetItem` calls (X-Ray trace), zero `sts:AssumeRole` (CloudTrail), P50 ≤ 250 ms, P95 ≤ 800 ms; cite [cost-reliability.md §Caching strategy](../role-passes/cost-reliability.md) for TTL targets |
| **AC6** | Cold-path latency P95 ≤ 1500 ms | `ac06-cold-path-latency.e2e.spec.ts` (50 invocations after forced cold start; CloudWatch metric `Duration` aggregated) | `ac06-cold-path-budget-burn.e2e.spec.ts` (alert fires when P95 > 1500 ms for 7 consecutive days — drives provisioned-concurrency trigger from R15) | Positive: P95 of 50 cold invocations ≤ 1500 ms; cold start measured by absence of `Init Duration: 0` in CloudWatch Lambda Insights; cite [cost-reliability.md §SLO recommendation](../role-passes/cost-reliability.md) |
| **AC7** | `tools/list` projection | `ac07-projection-allowed.e2e.spec.ts` (`claude-code-internal` sees `erp.checkUserAccess`) | `ac07-projection-empty.e2e.spec.ts` (second M2M client `ops-dashboard-test` excluded by registry filter — receives empty `tools[]`) | Negative client receives `{"tools": []}`; **no full catalog leaks** (R4); test runs even with one tool to exercise the lever before the second tool ships |
| **AC8** | Token passthrough refusal | `ac08-broker-issued-token.e2e.spec.ts` (handler observes `aud = handler-audience`, not the agent's M2M `aud`) | `ac08-passthrough-injection.e2e.spec.ts` (test client injects agent M2M JWT into handler input as `args.token` and as `X-Forwarded-Authorization`) | Negative: MCP server **strips** `X-Forwarded-Authorization` and rejects `args.token` field at schema validation; handler receives only the IdentityBroker-issued JWT; audit shows `denial_reason=passthrough_attempt` if injection detected |
| **AC9** | `/.well-known/oauth-protected-resource` self-host | `ac09-well-known-curl.smoke.sh` (curl returns 200 with `authorization_servers[]` listing Auth0 + `resource` matching MCP server URI) | `ac09-www-authenticate-on-401.e2e.spec.ts` (unauthenticated request returns 401 with `WWW-Authenticate: Bearer resource_metadata="<URL>"`) | Positive: JSON document conforms to RFC 9728; closes R5 by self-host, independent of Auth0 RFC 9728 support |
| **AC10** | Documentation parity | `ac10-runbook-parity.spec.ts` (asserts presence of three runbooks at known paths and that each runbook references at least one CloudWatch alarm name from `10-observability-runbooks.md`) | `ac10-stale-link-check.spec.ts` (markdown link checker fails CI on broken cross-reference) | Three runbooks present (`mcp-server-unavailable.md`, `tenant-scope-rejection.md`, `on-call-boundary.md`); link audit clean. **Flag:** AC10 is partially automatable — content quality requires a Phase D human review pass; the link-check + presence assertion is the automatable subset |

### 2.3 JWT validation unit-test matrix

`auth.spec.ts` exercises six JWT defects against `verifyAgentJwt` and `verifyUserJwt`. Each row asserts both the rejection class and the `WWW-Authenticate` header shape so the broker conforms to MCP authorization spec 2025-06-18.

| Test name | JWT defect | Expected outcome |
|---|---|---|
| `rejects valid JWT signed by wrong issuer` | `iss = https://attacker.example.com` | HTTP 401, `class=AUTH, code=INVALID_ISSUER`; `WWW-Authenticate: Bearer error="invalid_token"` |
| `rejects expired JWT` | `exp` in the past by 1 s | HTTP 401, `code=TOKEN_EXPIRED`; `WWW-Authenticate` includes `error_description="The access token expired"` |
| `rejects JWT with wrong audience` | `aud = https://other.linq.platform` (RFC 8707 mismatch — R19) | HTTP 401, `code=INVALID_AUDIENCE` |
| `rejects unsigned JWT (alg=none)` | Header `{"alg":"none"}` | HTTP 401, `code=UNSIGNED_TOKEN`; never reaches JWKS lookup |
| `rejects JWT signed with unknown kid` | `kid = unknown-key-id` | HTTP 401, `code=INVALID_KID`; JWKS fetched once and cached for 1 h thereafter |
| `rejects request with missing Authorization header` | No bearer token | HTTP 401, `code=MISSING_TOKEN`; `WWW-Authenticate: Bearer resource_metadata="<URL>"` per RFC 9728 |
| `accepts valid JWT` | All claims valid, signed by JWKS-published key | HTTP 200; downstream pipeline proceeds; `agent_client_id` extracted from `sub` |

Cite: [MCP authorization spec 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/authorization), [RFC 8707 resource indicators](https://datatracker.ietf.org/doc/html/rfc8707).

### 2.4 Local-dev `docker-compose.yml` skeleton

Engineer runs `docker compose up` plus `npm run dev`, points the Anthropic MCP TypeScript SDK at `http://localhost:3000`, and exercises the full pipeline against localstack DynamoDB and a real Auth0 dev tenant. Cross-account dispatch is the one branch that diverges from production — local dev stubs the AssumeRole step with a long-lived dev IAM key and flags the divergence in the README. Integration tests deployed to the sandbox account exercise the real cross-account path.

```yaml
# tests/local-dev/docker-compose.yml
version: "3.9"
services:
  localstack:
    image: localstack/localstack:3.5
    ports: ["4566:4566"]
    environment:
      SERVICES: dynamodb,s3,kms,logs
      DEFAULT_REGION: us-east-1
      # Auth0 is the real dev tenant — not stubbed.
    volumes:
      - "./localstack-init:/etc/localstack/init/ready.d"  # seeds registry + schema bucket

  sam-local:
    image: public.ecr.aws/sam/build-nodejs20.x:latest
    working_dir: /workspace
    volumes:
      - "../..:/workspace"
    command: >
      sam local start-api
        --template infrastructure/03-mcp-server/template.yaml
        --port 3000
        --env-vars tests/local-dev/env.json
        --docker-network host
    depends_on: [localstack]

  registry-seed:
    image: amazon/aws-cli:2.17.0
    depends_on: [localstack]
    entrypoint: ["/bin/sh", "-c"]
    command: >
      "aws --endpoint-url=http://localstack:4566
        dynamodb put-item
        --table-name platform-mcp-handler-registry-dev
        --item file:///seed/erp-checkUserAccess.json"
    volumes:
      - "./seed:/seed:ro"
```

`tests/local-dev/env.json` carries the real Auth0 dev-tenant `AUTH0_ISSUER`, `AUTH0_AUDIENCE`, and JWKS URL — never a mock. Cite: [localstack DynamoDB docs](https://docs.localstack.cloud/user-guide/aws/dynamodb/), [SAM local docs](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-cli-command-reference-sam-local-start-api.html).

### 2.5 SAM local invocation script

```bash
#!/usr/bin/env bash
# tests/local-dev/invoke-tools-call.sh
set -euo pipefail

AGENT_TOKEN="$(./scripts/auth0-m2m-token.sh)"     # real Auth0 dev tenant
USER_TOKEN="$(./scripts/auth0-user-token.sh)"     # real Auth0 dev user

cat > /tmp/event.json <<'JSON'
{
  "rawPath": "/mcp",
  "headers": {
    "authorization": "Bearer __AGENT__",
    "x-user-token": "__USER__",
    "x-request-id": "local-dev-001"
  },
  "body": "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"erp.checkUserAccess\",\"arguments\":{\"userId\":\"u-1\",\"tenantId\":\"acme\"}}}"
}
JSON

sed -i '' "s|__AGENT__|${AGENT_TOKEN}|;s|__USER__|${USER_TOKEN}|" /tmp/event.json

sam local invoke McpServerFunction \
  --template infrastructure/03-mcp-server/template.yaml \
  --event /tmp/event.json \
  --env-vars tests/local-dev/env.json
```

### 2.6 MCP Inspector manual smoke procedure

After every sandbox deploy and before promoting to staging, an engineer runs the Inspector against the deployed URL and walks the four checks below. The smoke is gated as a release-checklist item — it is **not** automated because Inspector is interactive by design.

```bash
# 1. Self-hosted resource metadata (AC9, R5)
curl -fsS https://mcp.dev.linq.platform/.well-known/oauth-protected-resource | jq .
# Expect: { "resource": "https://mcp.dev.linq.platform", "authorization_servers": ["https://linq-dev.auth0.com"], ... }

# 2. WWW-Authenticate on 401
curl -i https://mcp.dev.linq.platform/mcp
# Expect: HTTP/1.1 401 ... WWW-Authenticate: Bearer resource_metadata="https://mcp.dev.linq.platform/.well-known/oauth-protected-resource"

# 3. Inspector — tools/list projection (AC7, R4)
npx @modelcontextprotocol/inspector \
  --transport http --url https://mcp.dev.linq.platform/mcp \
  --header "Authorization: Bearer ${CLAUDE_CODE_INTERNAL_TOKEN}"
# In the Inspector UI:
#   - Confirm `tools/list` returns exactly `erp.checkUserAccess` (one tool — projection lever exercised)
#   - Repeat with ${OPS_DASHBOARD_TEST_TOKEN} — confirm empty `tools[]`

# 4. Inspector — tools/call happy path (AC1)
#   - Invoke erp.checkUserAccess({ userId: "u-1", tenantId: "acme" })
#   - Confirm response shape matches outputSchema published in registry
#   - Tail CloudWatch Logs `/aws/lambda/platform-mcp-server-dev` — confirm one audit record per request
```

Cite: [`@modelcontextprotocol/inspector` README](https://github.com/modelcontextprotocol/inspector).

### 2.7 Audit reconciliation test

Daily reconciliation closes R18 (silent log-shipping failure). The test asserts the alarm fires when audit-row count diverges from MCP-server request count by more than 0.5%.

- **Test name:** `audit-reconciliation.integration.spec.ts`.
- **Setup:** synthetic 24-h window populated with 1,000 `tools/call` invocations against the sandbox; CloudWatch metric `McpServerRequestCount` records 1,000.
- **Positive assertion:** S3 audit object count for the same window equals 1,000 ± 5; reconciliation Lambda emits metric `AuditReconciliationDelta = 0`; alarm `AuditReconciliationDriftAlarm` stays in `OK`.
- **Negative test (`audit-reconciliation-drift.integration.spec.ts`):** disable the CloudWatch Logs subscription filter for 1 h, replay 100 invocations, re-enable the filter, run reconciliation; assert alarm transitions `OK → ALARM` within 5 min and the runbook `audit-reconciliation-drift.md` is referenced in the alarm description.
- **Frequency:** runs nightly in the sandbox; runs daily in production via the reconciliation Lambda itself.

## 3. Acceptance criteria — observable signals

Every V1 AC has a named test in §2.2. The CI gate at Phase E asserts:

- **CI signal:** all 10 positive E2E tests plus all 10 negative E2E tests pass on the deployed sandbox before any release tag is pushed.
- **Audit signal:** the daily `AuditReconciliationDriftAlarm` stays in `OK` for 7 consecutive days (matches POC M6 exit criterion).
- **Manual signal:** the Inspector smoke checklist (§2.6) is signed off in the release-readiness PR for every sandbox-to-staging promotion.
- **Coverage signal:** Jest coverage report in CI must show ≥ 90% line coverage on `auth.ts`, `dispatcher.ts`, `registry.ts`, and `errors.ts` (the four hot-path modules); flakiness is **not** papered over with `jest.retryTimes` — flaky tests block merge until root-caused.

**Flagged AC:** AC10 (documentation parity) is partially automatable. The link-check, runbook-presence, and alarm-name cross-reference assertions automate; reviewer judgment on runbook content quality does not. The Phase D QA pass plus a Documentation specialist review (`30-docs-generator`) carries the residual.

## 4. Effort estimate

`4 d [ASSUMED]` — one engineer.

Breakdown: 1 d for unit-test scaffolding plus the JWT matrix; 1 d for the contract-test rig (ajv + S3 schema fetch + registry diff); 1 d for the integration suite plus the docker-compose + SAM-local skeleton; 1 d for the 10 E2E specs plus the audit-reconciliation pair. Phase D QA review across the other 12 implementation artifacts is folded into the larger Phase D budget, not this number.

## 5. Open questions

- **Q10 (agent retry policy)** — Aggressive retries on read-only operations are fine in principle but turn a cache-miss storm into a thundering herd. Today's guess: mandate exponential backoff with jitter, max 3 retries, total budget 10 s, documented in the MCP client SDK. **Flag:** the rate-limit unit tests (`ratelimit.spec.ts`) and the AC8-paired load test depend on a known retry policy to assert the right token-bucket ceiling — if Q10 stays open, both tests assume the forced-today guess and re-run when the answer changes.
- **AC10 partial automation** — flagged in §3. Residual covered by Phase D human pass; surfaced here so the gap is explicit, not implicit.
- **Auth0 dev-tenant cost** — running real Auth0 calls in nightly integration consumes M2M tokens; cached at 23 h per [`cost-reliability.md`](../role-passes/cost-reliability.md), so steady-state cost is 1 token/day per service identity. Flag for re-check after first month of nightly runs.

## 6. Cross-references

- [`../04-phase-1-poc.md`](../04-phase-1-poc.md) — the 10 V1 acceptance criteria and milestone exit criteria; binding source for §2.2.
- [`../role-passes/cost-reliability.md`](../role-passes/cost-reliability.md) — caching strategy table; gates AC5 (P50/P95 timing assertions) and AC6 (cold-path P95 ≤ 1500 ms).
- [`../01-architecture.md`](../01-architecture.md) — reference flows (warm path, cold path, tenant-scope-rejection error path); each flow is exercised by a named test.
- [`../03-risks-register.md`](../03-risks-register.md) — risk-to-mitigation map; six risks listed in §7 trace back to mitigations defined here.
- [`./03-mcp-server.md`](./03-mcp-server.md) — module layout; unit-test files mirror this layout one-to-one.
- [`./04-registry.md`](./04-registry.md) — registration API; AC4 sub-cases test the four documented rejection classes.
- [`./07-poc-handler.md`](./07-poc-handler.md) — handler-side JWT verify and contract test rig (referenced from the implementation plan; this artifact treats the contract layer as inheriting from the handler repo).
- [`./10-observability-runbooks.md`](./10-observability-runbooks.md) — three runbooks AC10 asserts the presence of; alarm names referenced from `audit-reconciliation.integration.spec.ts`.

## 7. Risks protected against

- **R4 — context-window leak from full-catalog injection.** AC7 positive and negative tests prove the projection lever works with one tool and rejects an excluded client; the `tools/list` projection ships in the POC before the second tool lands.
- **R5 — Auth0 RFC 9728 support unconfirmed.** AC9 curl smoke plus the 401 `WWW-Authenticate` E2E test confirm the MCP server self-hosts the metadata document independent of Auth0.
- **R8 — runaway agent saturating downstream.** A load test fires 1,000 req/s from a single M2M identity; the assertion is HTTP 429 with `class=THROTTLE` from the per-agent token bucket and **no** corresponding handler-account Lambda invocation in CloudTrail.
- **R10 — STS session caching causes stale principal at audit time.** `audit.integration.spec.ts` asserts `request_id` embedded in `RoleSessionName` and STS session tags correlates the platform audit row to the product-account CloudTrail entry; covers the AC2 secondary requirement.
- **R14 — `inputSchema` / `outputSchema` drift.** The contract layer (`erp-checkUserAccess.contract.spec.ts`) runs in handler-repo CI on every PR and fails on any additive, removal, or type drift between handler I/O and registry-published schemas.
- **R18 — cross-account log shipping fails silently.** §2.7 audit-reconciliation positive and negative tests assert the alarm fires within 5 min of a synthetic shipping failure; closes the silent-gap mode the daily job is designed to detect.
