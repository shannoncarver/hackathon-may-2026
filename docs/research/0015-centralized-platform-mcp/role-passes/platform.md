# Role-pass memo: Platform Engineer

**Reviewer:** general-purpose (Platform lens)
**For:** Decision 0015 — Centralized Platform MCP Server
**Date:** 2026-05-04

## Findings

1. **Read-heavy registry favors a single-table DynamoDB design with a strong-consistency PK lookup on the hot path.** Every `tools/call` resolves a `toolId` to handler metadata, and `tools/list` aggregates per-agent identity. With 40–200 items at v1 and 5–10× growth, the working set fits in DynamoDB's per-partition cache; the design constraint is access-pattern coverage (point reads, version queries, owner queries, scope filtering), not size. Cite [`wiki/entities/mcp-tool-catalog.md`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md) — `tools/list` supports cursor-based pagination, which maps cleanly to DynamoDB Query + LastEvaluatedKey.

2. **`handlerType` must be invisible to the agent and load-bearing only inside the dispatcher.** The MCP spec exposes `name`, `description`, `inputSchema`, `outputSchema`, and `annotations` (per [`wiki/entities/mcp-tool-catalog.md`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)) — it does not expose runtime substrate. If we leak Lambda-vs-ECS-vs-Step-Function semantics into the agent layer, every product team's substrate choice becomes a breaking-change vector for every agent. The registry's `handlerType` selects a dispatcher adapter; the agent sees a uniform `tools/call` envelope.

3. **Cross-account dispatch should default to `sts:AssumeRole` with External ID, not Lambda resource policies, even though both are viable.** Per [`wiki/entities/lambda-resource-policy.md`](../../../../knowledge/wiki/entities/lambda-resource-policy.md), AWS itself recommends roles "for actions that don't operate on a function" and for broad multi-resource access — and v1 already needs three substrates (Lambda, ECS, Step Functions). One credential-acquisition pattern across all three handler types collapses the dispatcher's branching and matches the trust-model in [`wiki/entities/sts-assume-role-external-id.md`](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md). Resource-based policies remain a viable optimization for single-handler product accounts but should not be the platform default.

4. **Schema validation should be JSON Schema, not Smithy or OpenAPI.** MCP's `inputSchema` and `outputSchema` are JSON Schema by spec ([`wiki/entities/mcp-tool-catalog.md`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md) — REQUIRED `inputSchema` is a "JSON Schema object"). Anything else requires a translation layer at the protocol seam, and the resulting runtime errors will be confusing to debug. Smithy is richer for AWS service modeling; OpenAPI is richer for HTTP semantics. Neither buys us anything an MCP agent will use.

5. **Self-service registration is feasible but only when the registry has machine-checkable invariants.** With 4 product teams and a projected 5–10× handler growth, a platform-team-curated review queue becomes the bottleneck immediately. The only sustainable path is policy-as-code on the registry write path — a CI gate that lints inputSchema/outputSchema, validates `assumeRoleArn` matches an account-allowlist, requires an `owner` team that exists in the org directory, and rejects unknown `requiredScopes`. Once those checks are green, the write goes through without a platform-team review.

6. **The MCP `listChanged` notification ([`wiki/entities/mcp-tool-catalog.md`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md)) is the natural rollout primitive.** New handlers, version promotions, and feature-flag changes can be hot-published to connected agents without a reconnect. This is what makes blue/green at the registry layer cleaner than blue/green at the ARN layer for first-class platform behavior.

7. **The error envelope is the single most forward-compat-sensitive contract in this design.** Once agents start branching on error codes, the taxonomy is locked. v1 is read-only, so the obvious error classes (auth, not-found, rate-limit, upstream-timeout, upstream-error) are sufficient — but a v2 mutating handler will need additional classes (idempotency-conflict, precondition-failed, partial-success). Reserve those codes now even if no v1 handler emits them.

## Risks

- **HIGH — Registry write path becomes the platform-team queue.** If the gate workflow requires manual platform review for any handler change, every product team experiences a multi-day wait. *Mitigation:* policy-as-code in CI, with platform review reserved for narrow exceptions (new account onboarding, new substrate type, new IAM scope).

- **HIGH — `inputSchema`/`outputSchema` drift between registry and handler implementation.** A handler bumps its real I/O without bumping the registry schema, and the dispatcher passes through a payload that fails downstream. *Mitigation:* require contract tests in the handler's repo that diff against the registry's published schema; fail CI on drift.

- **HIGH — Asymmetric latency surfaces as agent timeouts.** A Step-Function-backed tool that takes 5 seconds looks identical to a 200ms Lambda from the agent's perspective; the agent's per-request budget gets blown silently. *Mitigation:* per-handler `timeoutMs` in the registry with a tier-based default, and an `expectedLatencyP50Ms` hint exposed in the MCP `description` field so agents can plan.

- **MED — Versioning ambiguity at the boundary.** "Latest stable" is a useful default for development but a sharp edge in production — agents that pin nothing will silently jump major versions. *Mitigation:* registry encodes `latestStable` as a label that points at a specific `version`; agents may request the label for dev and MUST pin for production. Deprecation removes the label, not the version.

- **MED — `listChanged` floods.** A noisy registry (frequent feature-flag flips, frequent version promotions) generates `notifications/tools/list_changed` storms; agents re-fetch unnecessarily. *Mitigation:* coalesce notifications server-side over a short window (e.g., 2s); track per-agent last-fetched cursor and only notify if their visible catalog actually changed.

- **MED — Cross-account STS quota.** AWS STS has account-level rate limits on `AssumeRole`. At 5–10× handler growth and a hot agent fleet, a naive "AssumeRole per call" pattern hits ceilings. *Mitigation:* credential cache in the dispatcher keyed on `(productAccount, externalId)`, refreshing at ~80% of session TTL.

- **LOW — DynamoDB hot partition on a single popular `toolId`.** Possible at 5–10× scale but mitigatable with DAX or in-process caching in the MCP server. Flag, don't pre-optimize.

- **LOW — `[ASSUMED]` LINQ has no existing internal-API gateway.** If one exists, the platform MCP server should treat it as the dispatcher target rather than direct cross-account invoke. Flagged for the Lead Architect.

## Recommendation

**Adopt the registry + dispatcher design with three platform-side guarantees.** First, the registry is a single DynamoDB table with one PK/SK access pattern on the hot path and three GSIs covering version-listing, owner-listing, and account-listing. Item shape exposes only what the dispatcher needs to dispatch and what the MCP layer needs to publish — no agent-visible coupling to substrate. Second, the dispatcher implements one credential-acquisition pattern (`sts:AssumeRole` with External ID per [`wiki/entities/sts-assume-role-external-id.md`](../../../../knowledge/wiki/entities/sts-assume-role-external-id.md)) and three thin substrate adapters (Lambda Invoke, ECS RunTask + result polling, Step Functions StartSyncExecution). The adapters normalize to one response envelope; everything above the adapter is substrate-agnostic. Third, the registry write path is policy-as-code with no manual review on the happy path — onboarding a new handler is a product-team PR against their own repo, not a ticket on the platform team.

**Hold the line on schema language and error envelope now.** JSON Schema for I/O matches the MCP spec and avoids translation at the protocol seam. The error envelope `{class, code, retryable, message, traceId}` should reserve mutation-related classes (idempotency-conflict, precondition-failed, partial-success) on day one, even though v1 read-only handlers won't emit them — agents will pattern-match on `class`, and we cannot add classes later without a v2 deprecation cycle.

**Treat `handlerType` asymmetry as a platform-internal concern, not an agent-visible one.** ECS and Step Functions invocations differ from Lambda in cold-start, latency, and credential semantics — but the agent does not need to know. Per-handler `timeoutMs` and `expectedLatencyP50Ms` in the registry, surfaced in the MCP tool `description`, give agents enough planning information without leaking substrate. If a handler genuinely needs async (a 2-minute log scan), wrap it in a sync facade that returns a `pending` resource_link and a follow-up `tools/call` to fetch the result — async-from-the-agent's-perspective is a v2 feature; v1 should hard-cap at 30s and hand any longer read off to a summarizer.

**Forward-compat for v2 writes hinges on three contracts.** Register an `idempotencyKey` parameter slot in the input envelope now (read handlers ignore it, write handlers will require it). Declare `sideEffects: "none" | "read" | "write"` in the registry item now (v1 is all `"read"`; v2 mutating handlers will be `"write"`, and the dispatcher's retry policy diverges on this field). Reserve mutation error classes in the error envelope now (see above). Each of these is a one-line addition today and a breaking change later.

## Concrete artifacts

### Registry DynamoDB schema (proposed)

**Table name:** `platform-mcp-handler-registry`
**Billing mode:** On-demand (read-heavy, predictable but variable; provisioned can come later if cost analysis demands it).
**Stream:** New and old images enabled — drives the MCP `listChanged` emitter and registry-audit log.

**Primary key**

| Attribute | Role | Example |
|---|---|---|
| `pk` | Partition key | `TOOL#erp.checkUserAccess` |
| `sk` | Sort key | `VERSION#1.2.0` |

**Hot path:** `GetItem(pk=TOOL#erp.checkUserAccess, sk=VERSION#<resolved-version>)`. The MCP server resolves a label (`stable`, `beta`) or a pinned version into a concrete `sk` via GSI1 before this read; for fully pinned calls the `GetItem` is direct.

**Label items** live alongside version items at the same `pk`:

| `pk` | `sk` | Attribute |
|---|---|---|
| `TOOL#erp.checkUserAccess` | `LABEL#stable` | `points_to: "1.2.0"` |
| `TOOL#erp.checkUserAccess` | `LABEL#beta` | `points_to: "2.0.0-rc.1"` |

Label updates are conditional writes; rollback = repoint the label to a prior version (one PutItem, no version migration).

**GSIs**

| Index | PK | SK | Purpose |
|---|---|---|---|
| `GSI1-by-status` | `status` (`active` / `deprecated` / `retired`) | `pk` | `tools/list` filtering — drives the agent-visible catalog. |
| `GSI2-by-owner` | `owner` (team slug) | `pk` | Ownership reports, on-call routing, change-impact queries. |
| `GSI3-by-account` | `productAccount` (12-digit AWS account ID) | `pk` | Account-scope invariant checks; "show all handlers in product-X account." |

**Item shape (version item)**

```json
{
  "pk": "TOOL#erp.checkUserAccess",
  "sk": "VERSION#1.2.0",
  "toolId": "erp.checkUserAccess",
  "version": "1.2.0",
  "status": "active",
  "deprecatedAfter": null,
  "retiredAfter": null,

  "handlerType": "lambda",
  "arn": "arn:aws:lambda:us-east-1:<acct>:function:erp-check-user-access:prod",
  "productAccount": "111122223333",
  "assumeRoleArn": "arn:aws:iam::111122223333:role/PlatformMcpInvoker",

  "title": "Check ERP user access",
  "description": "Read-only lookup of a user's ERP role assignments. P50 ~180ms. Read-only.",
  "inputSchemaRef": "s3://platform-mcp-schemas/erp.checkUserAccess/1.2.0/input.json",
  "outputSchemaRef": "s3://platform-mcp-schemas/erp.checkUserAccess/1.2.0/output.json",

  "sideEffects": "read",
  "idempotent": true,
  "timeoutMs": 5000,
  "expectedLatencyP50Ms": 180,
  "retryPolicy": { "maxAttempts": 3, "backoffMs": 200, "jitter": "full" },

  "requiredScopes": ["erp:read", "user:read"],
  "visibility": { "agentIdentities": ["*"], "featureFlag": null },

  "owner": "team-erp",
  "annotations": { "readOnlyHint": true, "destructiveHint": false },

  "createdAt": "2026-05-04T12:00:00Z",
  "updatedAt": "2026-05-04T12:00:00Z"
}
```

**Notes:**

- `inputSchemaRef` / `outputSchemaRef` are S3 URIs, not inline blobs — DynamoDB item-size limits become a real concern at richer schemas, and S3 versioning gives us a free audit trail. The MCP server caches resolved schemas in-process.
- `version` follows SemVer. `latestStable` lookup is `GetItem(pk=TOOL#..., sk=LABEL#stable)` → `points_to` → `GetItem(pk=TOOL#..., sk=VERSION#<that>)`. Two reads on label-resolved calls; a small price for atomic relabel.
- A `v1.0` → `v2.0` bump leaves the v1 item live with `status: "deprecated"`; agents pinned to `1.x` keep working. Retirement is a separate transition, gated by the deprecation timeline policy below.
- `sideEffects` is reserved-for-v2 today (always `"read"` in v1). Same for `idempotencyKey` in the input envelope (see invocation contract).

### Handler invocation contract (proposed)

**Wire-level input envelope (MCP server → dispatcher → handler)**

```json
{
  "envelope": {
    "version": "1",
    "toolId": "erp.checkUserAccess",
    "toolVersion": "1.2.0",
    "callId": "<uuid-v7>",
    "traceId": "<W3C traceparent>",
    "agentIdentity": { "subject": "<auth0-sub>", "scopes": ["erp:read", "user:read"] },
    "idempotencyKey": null,
    "deadlineMs": 5000
  },
  "args": { /* validated against inputSchema */ }
}
```

`idempotencyKey` reserved for v2 — read-only v1 handlers ignore it.

**Wire-level output envelope (handler → dispatcher → MCP server)**

```json
{
  "envelope": {
    "version": "1",
    "callId": "<uuid-v7>",
    "traceId": "<W3C traceparent>",
    "executedVersion": "1.2.0",
    "latencyMs": 184
  },
  "result": { /* validated against outputSchema */ },
  "error": null
}
```

On error, `result: null` and `error: <error envelope below>`.

**Error envelope**

```json
{
  "class": "AUTH" | "NOT_FOUND" | "INVALID_INPUT" | "UPSTREAM_TIMEOUT"
         | "UPSTREAM_ERROR" | "RATE_LIMITED" | "INTERNAL"
         | "IDEMPOTENCY_CONFLICT" | "PRECONDITION_FAILED" | "PARTIAL_SUCCESS",
  "code": "ERP_USER_NOT_FOUND",
  "retryable": false,
  "message": "User <id> not found in ERP directory",
  "traceId": "<W3C traceparent>",
  "details": { /* optional, schema-bounded */ }
}
```

The last three classes are reserved for v2 mutating handlers and MUST NOT be returned by v1 handlers — but the enum is locked now so agents can pattern-match safely.

**MCP error-code mapping (per [`wiki/entities/mcp-tool-catalog.md`](../../../../knowledge/wiki/entities/mcp-tool-catalog.md))**

| Internal class | MCP surface |
|---|---|
| `AUTH` | Tool-execution error, `isError: true`, content includes auth-failure summary; protocol-level 401 if the failure is at the MCP server's own auth boundary. |
| `NOT_FOUND` | Tool-execution error, `isError: true`. |
| `INVALID_INPUT` | Tool-execution error, `isError: true`; surfaces schema-validation messages. |
| `UPSTREAM_TIMEOUT` / `UPSTREAM_ERROR` / `RATE_LIMITED` / `INTERNAL` | Tool-execution error, `isError: true`; `retryable` flag respected by client retry logic. |
| Unknown `toolId` | JSON-RPC `-32602` per spec ("Unknown tool"). |

**Per-handler-type adapter notes**

| `handlerType` | Invocation | Credential acquisition | Response normalization | Notes |
|---|---|---|---|---|
| `lambda` | `Invoke` (RequestResponse) on `arn` (alias-locked per [`wiki/entities/lambda-resource-policy.md`](../../../../knowledge/wiki/entities/lambda-resource-policy.md)). | `sts:AssumeRole` on `assumeRoleArn` with External ID; cached creds. | Lambda payload IS the output envelope (handler boilerplate enforces shape via shared SDK). | Hot path; sub-second for warm invocations. |
| `ecs` | `RunTask` with overrides; result via task-defined output channel (S3 sentinel object or SSM parameter — pick one, document it). | Same `sts:AssumeRole`; ECS task itself runs under its own task-role. | Adapter polls for result with deadline budget; on timeout, emits `UPSTREAM_TIMEOUT`. | Cold-start tax visible. Use only for handlers that need ECS-specific runtime (large memory, long compute, custom binaries). |
| `step-function` | `StartSyncExecution` on `arn`. | Same `sts:AssumeRole`. | Step Functions output IS the output envelope; on `FAILED`/`TIMED_OUT`, map to error envelope. | Best for read flows that compose 2–4 sub-calls behind one tool. |

All three adapters share the same input envelope. Substrate divergence is fully encapsulated; the agent sees one tool with one schema regardless.

**Sync vs. async**

v1 is sync-only from the agent's perspective. Hard cap at 30s end-to-end (15s if the handler is a substrate that pays cold-start). Long reads (e.g., 2-minute log scans) wrap a Step Functions workflow that builds a summary and returns the summary synchronously — the workflow may be longer-running internally, but the agent-facing tool is sync. True async streaming (resource progress notifications) is a v2 design.

**Timeout and retry tier defaults**

| Tier | Default `timeoutMs` | Default retry |
|---|---|---|
| `fast-read` | 2000 | 3 attempts, 100ms backoff, full jitter |
| `standard-read` | 5000 | 3 attempts, 200ms backoff, full jitter |
| `slow-read` | 15000 | 2 attempts, 500ms backoff, full jitter |
| `composite-read` | 30000 | 1 attempt (no retry; idempotency at the composite layer) |

Per-handler override in the registry (`timeoutMs`, `retryPolicy`) wins. Dispatcher refuses to register a handler whose `timeoutMs` exceeds the tier ceiling without an explicit override flag.

### Onboarding workflow (proposed)

End-to-end: from "API exists in product account" to "agent can call it." Numbered steps; explicit gates flagged.

1. **[Product self-serve]** Product team writes the handler in their account's repo using the platform's `@linq/mcp-handler-sdk` (provides input/output envelope wrapping, error-envelope helpers, schema validators). Handler runs on Lambda by default; ECS/Step Functions opt-in.

2. **[Product self-serve]** Product team authors `inputSchema` and `outputSchema` (JSON Schema) in the handler repo. SDK generates a contract-test rig from these schemas.

3. **[Product self-serve]** Product team runs the platform's local mock MCP server (`linq-mcp-local`) against the handler. Mock validates input against `inputSchema`, invokes the handler in `sam local` or container-local mode, validates output against `outputSchema`, and prints a normalized envelope. No platform-team interaction.

4. **[Product self-serve]** Product team opens a PR to their own repo with handler code + schemas. CI runs unit tests, contract tests, and the platform-published `mcp-handler-lint` (validates registry-item shape, schema syntax, scope spelling, account-allowlist match, owner team exists).

5. **[Product self-serve, post-merge]** A GitHub Action in the product repo writes the registry item via the platform's registration API. The API enforces the same lints as CI plus IAM-side checks (the `assumeRoleArn` exists and is reachable; the account is on the allowlist). New handler enters with `status: "active"`, `visibility.featureFlag: "<team>-canary"`. Dispatcher honors the flag — only agents with the matching identity claim see it via `tools/list`.

6. **[Product self-serve]** Team promotes by removing the feature flag (one-line registry update via the same API). The MCP server emits `notifications/tools/list_changed`; connected agents re-fetch and the tool becomes globally visible.

7. **[Platform-team gate — narrow exceptions only]** Platform-team review is required only for: (a) new product account onboarding (new entry in the account-allowlist), (b) new `handlerType` substrate (e.g., adding Fargate as a fourth type), (c) new `requiredScopes` value not present in the central scope catalog. None of these are per-handler — they are per-product-or-platform-capability and should be rare.

**The bottleneck is gate (7), and it should fire only at boundary expansions, never at handler-by-handler additions.** A product team adding their 50th read handler hits zero platform-team queues.

## Open questions for Lead Architect

- **Does a LINQ internal-API gateway already exist (Kong, Apigee, custom)?** If yes, the dispatcher should target it rather than direct cross-account invoke, simplifying credential semantics and observability. *Guess if forced today: assume no shared gateway; design dispatcher as the only platform-managed seam.* `[ASSUMED]`

- **Is the `productAccount` set fully enumerable today, or do we need self-service account onboarding in v1?** The registry's account-allowlist is a platform-team gate; if onboarding cadence is "once per quarter," manual is fine. If it is "once per sprint," we need a self-service flow. *Guess if forced today: 4 accounts now, no onboarding flow needed in v1.* `[ASSUMED]`

- **Does Auth0's M2M scope catalog already have a curated `requiredScopes` list, or do we mint them per handler?** Per-handler scope minting will fragment the auth model fast. *Guess if forced today: stand up a central `scope-catalog` repo with platform-team approval on additions (this is one of the narrow gates above).* `[ASSUMED]`

- **What is the agent-identity model — one Auth0 client per agent type, or per-agent-instance?** This affects `visibility.agentIdentities` semantics and the cardinality of feature-flag rollouts.

- **Where does the registry's audit trail live — DynamoDB Streams + CloudWatch Logs, or do we need an append-only store (e.g., S3 with object lock)?** Required for v2 mutation handlers; nice-to-have at v1. *Guess if forced today: Streams → Firehose → S3 (immutable bucket).* `[ASSUMED]`

- **Are product teams expected to own the IAM role on their side (`PlatformMcpInvoker`), or does platform provision it via cross-account IaC?** Drives the onboarding-step ownership. (Security owns the trust-policy specifics; this is purely an operational ownership question.)

- **Do we want `outputSchema` mandatory in v1, or optional?** MCP spec marks it optional; making it mandatory now improves agent reliability but adds onboarding friction. *Guess if forced today: mandatory — the cost of authoring it is tiny next to the runtime debugging cost of unstructured output.*

## Forward-compat for v2 writes

Three contracts must be locked correctly now or v2 mutating handlers force a breaking change for every connected agent.

1. **Reserve `idempotencyKey` in the input envelope today.** Read handlers ignore it; write handlers will require it. If we add the field in v2, every agent SDK must update its envelope construction simultaneously — not feasible across an internal agent fleet.

2. **Reserve `sideEffects: "read" | "write"` in the registry item today.** v1 handlers are all `"read"`. The dispatcher's retry policy is aggressive on `"read"` (3 attempts, exponential backoff, full jitter — safe because reads are idempotent) and conservative on `"write"` (1 attempt, no automatic retry — caller must use `idempotencyKey`). Without this field, v2 writes either inherit v1's aggressive retry (correctness bug) or force a registry schema bump (breaking change).

3. **Reserve mutation error classes in the error envelope enum today.** `IDEMPOTENCY_CONFLICT`, `PRECONDITION_FAILED`, `PARTIAL_SUCCESS` MUST appear in the v1 enum even though no v1 handler emits them. Agents pattern-match on `class`; adding classes later means every agent's error-handling logic must update simultaneously. Reserving them now costs nothing and unblocks v2 entirely.
