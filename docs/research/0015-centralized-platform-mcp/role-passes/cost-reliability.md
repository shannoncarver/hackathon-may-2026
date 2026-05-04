# Role-pass memo: Cost & Reliability Engineer

**Reviewer:** general-purpose (Cost & Reliability lens)
**For:** Decision 0015 — Centralized Platform MCP Server
**Date:** 2026-05-04

## Findings

1. **The per-request cost floor is dominated by MCP-server compute and downstream handler duration, not by registry, STS, or auth.** With session and registry caching in place, AWS-side per-request cost lands in the **$0.000005 – $0.00005** range at v1 scale — handler duration drives variance. STS AssumeRole is free ([AWS STS pricing](https://aws.amazon.com/iam/pricing/) — no charge for `sts:AssumeRole`); the cost concern is *latency* (~50–150 ms cold, ~30–80 ms warm) and request-count amplification, both of which session caching kills.

2. **Auth0 M2M billing is the largest non-AWS cost wildcard and the highest-leverage architectural decision in this memo.** Auth0 prices M2M apps **per Machine-to-Machine application, not per token issued** ([Auth0 pricing](https://auth0.com/pricing)). One M2M app per agent or per-handler explodes the bill linearly with handler count and breaks the "sub-linear in handler count" claim. Recommend **one M2M app per *service identity*** (e.g., one per logical agent class — "claude-code", "ops-dashboard", "internal-dev-tool") rather than per-handler or per-end-user. Internal humans authenticate via Auth0 user flows and the MCP server exchanges that for AWS creds; M2M is reserved for non-interactive agents.

3. **Caching is the highest-leverage move and should be designed in v1, not deferred.** Read-only + idempotent + small registry + low write rate = textbook cache-friendly workload. A 5-minute in-memory registry cache eliminates ~99% of DynamoDB reads at v1 scale [ASSUMED: handlers change <1×/hour during business hours]. STS session caching at 1 h TTL eliminates ~99% of AssumeRole calls. Auth0 M2M token caching at 23 h TTL eliminates ~99% of token-endpoint calls. Without these, the architecture pays N× the necessary downstream load and breaks SLOs under load.

4. **Lambda is the right v1 compute for the MCP server; revisit at scale.** Lambda's pay-per-invoke model fits 5K req/day cleanly (~$0.10/day at this volume), and the cold-start tax (200–800 ms for an HTTP-fronted Node/Python Lambda) is acceptable for internal agents. Fargate becomes attractive only when sustained QPS > ~50 or when an in-process registry cache is so valuable that container reuse beats per-invocation cold-cache penalties. Recommend **Lambda + Lambda SnapStart (Java) or provisioned concurrency = 2 (Node/Python) for the MCP server in v1 if P95 > 1500 ms after measurement**.

5. **Blast radius is "all-or-nothing" by design.** A centralized broker means MCP-server outage = all agent traffic dies. v1 mitigation: multi-AZ behind API Gateway + Lambda (default), no multi-region (premature). v2 (any customer exposure) requires multi-region active-passive and a documented failover runbook. The platform must publish an explicit "MCP server is unavailable — operate without agent automation" degradation playbook before any non-internal user touches it.

6. **Single-product handler outage is correctly isolated by the architecture** — the MCP server's per-handler invocation is independent, so a Lambda throttle in product account A does not affect product account B. The one cross-account coupling to watch is the **registry**: a bad registry write (wrong handler ARN, wrong external ID) silently fails AssumeRole or invocation for the affected handler. Mitigation: registry writes go through CI with a dry-run AssumeRole + handler-invoke-with-canary-payload validation step.

7. **Observability requires a centralized logging account from day 1.** Cross-account log shipping (CloudWatch Logs subscription filter → Kinesis Firehose → S3 in a logging account, or CloudWatch cross-account observability) is the v1 baseline. The audit trail must record: principal (agent + Auth0 user), tenant, tool name, handler ARN, latency, outcome, error class, downstream durations. Retention: **400 days minimum** in S3 with Object Lock in compliance mode for the audit subset, even though no certification is required in v1 — backfilling immutability later is hard.

8. **The "sub-linear in handler count" claim holds only with discipline.** Per-handler fixed costs to actively amortize: M2M apps (force shared identities), per-handler IAM roles (use one role per product account with handler-name-conditioned policies, not one role per handler), per-handler dashboards (use templated CloudWatch dashboards with handler as a dimension, not separate dashboards). With those decisions, marginal cost per added handler is registry storage (~$0/handler at any realistic scale) plus log volume — genuinely sub-linear.

## Risks

| Severity | Risk | Why | Mitigation |
|---|---|---|---|
| **HIGH** | Auth0 M2M cost explosion | Auth0 bills per M2M app; naive "one M2M per handler" or "one M2M per agent instance" makes cost linear in handler or user count | Mandate one M2M app per service identity class (3–5 total v1, ~10 at 3-yr); audit M2M app count quarterly |
| **HIGH** | MCP-server availability is the entire system's availability | Single broker = single dependency for every agent action | Multi-AZ in v1; document degradation path; require multi-region before any external-facing use |
| **HIGH** | Runaway agent saturating downstream | One misbehaving agent fires 1000 req/sec → cascades to product handlers → throttle DynamoDB, Lambda concurrency, CloudWatch ingest | Per-agent + per-tool token bucket at the MCP server; default 10 req/sec per agent identity; per-tenant cap; circuit-break per-handler at 5× baseline |
| **MED** | Cold-start latency violating Claude Code timeouts | Claude Code tool calls have implicit user-perceived deadlines (~3–10 s); MCP cold + handler cold can stack to 1–2 s | Provisioned concurrency = 2 on MCP-server Lambda once measured P95 > 1500 ms; publish per-handler warm-pool budgets |
| **MED** | Registry cache staleness causing handler-not-found 404s | New handlers added to registry but TTL hasn't expired in MCP-server cache | 5-min TTL + `tools/list_changed` MCP notification when registry writes occur; opt-in cache bypass header for ops |
| **MED** | Cross-account log shipping fails silently | Subscription filters break, Firehose throttles → audit gap | CloudWatch alarm on log-delivery lag; daily reconciliation job comparing MCP-server request count to audit-log row count |
| **LOW** | DynamoDB hot partition on registry under cache miss storm | All MCP-server replicas miss cache simultaneously after deploy | ON_DEMAND billing in v1 (no provisioned-throughput risk); if PROVISIONED later, add jittered cache warm-up |
| **LOW** | STS rate limits | STS has account-level rate limits (default 600 TPS shared) | Session caching keeps real STS calls to ~1 per (handler, session-window); monitor `ThrottlingException` rate |
| **LOW** | Auth0 outage | Auth0 down → no new tokens issued → MCP-server can't authenticate new agent sessions | 23 h M2M token cache absorbs short Auth0 outages; document "operate cached" mode; bypass for break-glass admin |

## Recommendation

**Build v1 on Lambda + API Gateway with aggressive caching and accept centralized blast radius.** The traffic profile (5K req/day, internal-only, read-only) does not justify Fargate's baseline cost or multi-region complexity. Lambda's per-invocation pricing makes cost effectively zero at v1 scale, and the cold-start tax is tolerable for non-customer-facing agent traffic. Spend the saved engineering budget on three things that compound: (1) the in-memory + ElastiCache two-tier registry cache, (2) a strict per-agent rate-limit primitive enforced at the MCP server, and (3) cross-account audit logging into a dedicated logging account from day one.

**Lock in shared M2M identities now.** This is the one decision that is genuinely hard to reverse — adding handlers under the same M2M app is trivial, but consolidating M2M apps later requires re-onboarding every agent. Pick 3–5 service identities (e.g., `claude-code-internal`, `ops-dashboard`, `internal-dev-tool`, plus one break-glass admin) and forbid per-handler M2M apps in the platform contract. Combined with shared per-product IAM roles (handler-name-conditioned policies rather than one role per handler), this is what makes the cost profile genuinely sub-linear in handler count.

**Defer multi-region and provisioned concurrency until measured need.** Do not pay either cost until v1 telemetry shows the trigger condition. Set explicit triggers: provisioned concurrency = 2 if MCP-server P95 > 1500 ms for 7 consecutive days; multi-region active-passive only when (a) any non-internal user is onboarded, or (b) Platform Services availability target moves from 99.5% to 99.9%. Documenting the trigger now prevents speculative spend and prevents the inverse failure of waiting too long after customer exposure.

## Concrete artifacts

### Per-request cost model (table)

All AWS prices from public US-East-1 pricing pages, May 2026. [ASSUMED: cache hit rates as noted; v1 region us-east-1.]

| Component | Per-request cost (USD) | Notes |
|---|---|---|
| API Gateway HTTP API request | $0.0000010 | [AWS API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/) — $1.00 per million for HTTP APIs |
| MCP-server Lambda invoke + 200 ms @ 512 MB | $0.0000019 | [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/) — $0.20/M req + $0.0000083/GB-s × 0.5 GB × 0.2 s |
| DynamoDB GetItem on registry | $0.0000003 | [DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/) — ON_DEMAND $0.25/M reads × **1% miss rate** = effectively $0.0000000025 amortized; raw cost shown without cache |
| STS AssumeRole | $0 | Free; latency cost only [ASSUMED: 95% session-cache hit at 1 h TTL] |
| Cross-account Lambda invoke + 500 ms @ 512 MB | $0.0000041 | Same Lambda pricing; handler-dependent |
| CloudWatch Logs ingest (~2 KB/request, both accounts) | $0.0000010 | [CloudWatch Logs pricing](https://aws.amazon.com/cloudwatch/pricing/) — $0.50/GB ingest × 4 KB |
| Cross-account log shipping (Firehose) | $0.00000012 | [Kinesis Firehose pricing](https://aws.amazon.com/kinesis/data-firehose/pricing/) — $0.029/GB × 4 KB |
| Auth0 M2M token issuance | $0 amortized | Per-app subscription cost; per-token marginal cost ~$0 with 23 h cache [ASSUMED: 99.99% cache hit] |
| **Total (warm path, cache hits)** | **~$0.0000083** | Dominated by handler Lambda duration |
| **Total (cold path, all caches miss)** | **~$0.0000260** | Adds full DynamoDB read + STS round-trip latency cost |

### Projected scale (table)

[ASSUMED: 5K req/day v1; 50 internal users × 100 req/day. 3-yr target: 50K req/day = 5–10× growth, with handler count growing 5–10× as the larger driver of cost surface area, not request volume.]

| Tier | Requests/day | Requests/month | Monthly AWS cost (USD) | Monthly Auth0 (USD) | First bottleneck | Second bottleneck |
|---|---|---|---|---|---|---|
| **Low (v1 launch)** | 1,000 | 30K | ~$0.25 | M2M app subscription (fixed, ~$50–$200/mo for 3–5 apps) [unable to verify Auth0 LINQ-tier pricing] | none — over-provisioned | log volume |
| **Mid (v1 steady)** | 5,000 | 150K | ~$1.25 | same fixed | none | log volume |
| **Scale target (3-yr)** | 50,000 | 1.5M | ~$13 | same fixed | MCP-server Lambda concurrency (~10 concurrent at burst) | DynamoDB read throughput if cache disabled |
| **Stress (10× scale-target)** | 500,000 | 15M | ~$130 | same fixed + possibly tier upgrade | API Gateway throttle (10K rps default soft limit — well above need) | CloudWatch Logs ingest cost ($1.5K/mo at 2 KB/request) |

Note: AWS marginal cost remains trivial through 3-yr target. **The dominant cost line at every tier is Auth0 M2M subscription + log ingest, not compute.** This is why M2M-app discipline matters more than Lambda-vs-Fargate.

### SLO recommendation (table)

[ASSUMED: Claude Code default tool-call timeout is implicit ~30 s but user-perceived timeout is ~5 s; ops dashboards refresh ~30 s.]

| Metric | v1 target (internal only) | v2 target (any external/customer exposure) |
|---|---|---|
| Availability (monthly) | **99.5%** (~3.6 h downtime/month) | **99.9%** (~43 min/month) |
| Latency P50 — registry lookup | 5 ms (cache hit) | 5 ms |
| Latency P50 — STS | 0 ms (cache hit) / 80 ms (miss) | 0 ms / 80 ms |
| Latency P50 — handler invoke | 100 ms | 100 ms |
| Latency P50 — total (warm) | **200 ms** | **150 ms** |
| Latency P95 — total | **1,500 ms** | **800 ms** |
| Latency P99 — total | **3,000 ms** | **1,500 ms** |
| Error rate (5xx + protocol errors) | **< 1%** | **< 0.1%** |
| Error budget burn alert | 50% budget consumed in 25% of window | 25% in 10% of window |
| Audit log delivery lag | < 5 min | < 1 min |

Justification: P95 of 1.5 s at v1 leaves headroom under Claude Code's user-perceived patience window (~5 s). Tightening to 800 ms at v2 reflects customer-facing latency expectations. The 99.5% v1 availability target accepts that scheduled maintenance and AWS-managed-service incidents will occasionally exceed budget; 99.9% requires multi-region and is appropriately deferred.

### Caching strategy (table)

| Cache | Mechanism | TTL | Invalidation | Estimated hit rate |
|---|---|---|---|---|
| Registry (in-process) | Lambda execution-context map | **5 min** | TTL expiry; explicit invalidation header for ops; `tools/list_changed` MCP notification on registry write | ~95% within a warm Lambda; ~70% across cold starts |
| Registry (shared) | ElastiCache Redis (single-AZ in v1, multi-AZ in v2) | **15 min** | Same as above + write-through from registry-write Lambda | ~99% combined with in-process |
| STS session creds | In-process map keyed by (product-account, role, external-id) | **1 h** for prod, **15 min** for non-prod | TTL expiry; on `AccessDenied` evict and retry once | ~99% under steady traffic |
| Handler results | Per-handler-declared TTL in registry; platform enforces via response cache | **0 s default, max 1 h**, declared per-handler in registry as `cacheTtlSeconds` | TTL expiry only (read-only handlers); no write-through invalidation in v1 | Variable — opt-in per handler |
| Auth0 M2M tokens | In-process map keyed by service identity | **23 h** (token valid 24 h, 1 h safety margin) | Refresh on 401 from downstream | ~99.99% |
| MCP `tools/list` (per-client) | Client-side, server emits ETag and `listChanged` notifications | client-controlled; server suggests 5 min | `notifications/tools/list_changed` per [wiki/entities/mcp-tool-catalog.md] | high — clients should cache aggressively |

## Open questions for Lead Architect

- **What is LINQ's actual Auth0 pricing tier and M2M app entitlement?** I cannot verify from public pricing what counts against the LINQ contract. Guess if forced today: **3–5 M2M apps fits within an Enterprise plan included entitlement; >20 likely triggers an upcharge.** Need Finance/IT to confirm before locking the M2M-per-service-identity rule.
- **Is multi-region required at v1 launch or deferred to v2?** Brief says internal-only. Guess if forced today: **deferred — single-region us-east-1 multi-AZ is correct for v1**, multi-region only on the trigger conditions in the recommendation.
- **What is the registry write cadence?** Cache TTLs assume <1 write per hour during business hours. Guess if forced today: **registry writes are CI-gated handler onboarding events, ~10–30 per week at v1, dropping to ~5/week at steady state**.
- **Centralized logging account — does Platform Services already have one?** If yes, use it; if no, this is a v1 prereq, not a v1 deliverable. Guess if forced today: **assume LINQ has a logging-OU account in AWS Organizations; if not, it's a 1-week parallel workstream.**
- **Per-handler `cacheTtlSeconds` — who declares it?** Handler authors will under-declare (everyone wants fresh data). Guess if forced today: **registry schema requires it as a non-null integer; default is 0; platform engineering reviews any value > 300 s during onboarding.**
- **What is the agent-side retry policy?** Aggressive retries on read-only operations are fine in principle but amplify a cache miss storm into a thundering herd. Guess if forced today: **mandate exponential backoff with jitter, max 3 retries, total budget 10 s; document in the MCP client SDK.**
- **Concurrent-execution cap on MCP-server Lambda?** AWS default is 1000 reserved concurrency per region per account. Guess if forced today: **set reserved concurrency = 50 in v1**; alarms at 80% utilization.

## Sub-linear cost claim

**Confirmed — with three preconditions.** The brief's claim that cost is sub-linear in handler count holds if and only if the platform enforces:

1. **Shared M2M apps across handlers** (one M2M per service identity, not per handler). Auth0 pricing is the dominant per-handler-fixed-cost trap; per-handler M2M apps make cost linear in handler count and would refute the claim outright.

2. **Shared per-product IAM roles with handler-name-conditioned policies** rather than one role per handler. Per-handler IAM roles are free in AWS but add audit-surface and rotation overhead that scales linearly with handler count; the resource-based-policy alternative ([wiki/entities/lambda-resource-policy.md]) avoids this for single-function grants and is preferable when the MCP server only invokes one Lambda per product.

3. **Templated dashboards/alarms with handler as a CloudWatch dimension**, not per-handler dashboards. CloudWatch dashboard count and custom-metric count are both billed; per-handler dashboards make observability cost linear.

With those three preconditions, **marginal cost per added handler is essentially zero** — registry storage rounds to $0 at any realistic count, IAM is free, dashboards are reused, and request-volume cost depends on actual handler usage rather than handler count. The non-AWS line items (Auth0 M2M, DataDog/observability seats if applicable — unable to verify LINQ's observability stack) are the ones to watch and gate behind shared identities.

**Without those preconditions, the claim refutes.** A naive "one M2M app + one IAM role + one dashboard per handler" implementation would make per-month fixed cost grow linearly (~$10–$50/handler/month at conservative tier-pricing assumptions), turning the 400–2000 handler 3-year target into a $4K–$100K/month fixed-cost line that dwarfs every other component in this memo. The architecture is sound; the operational discipline is what protects the cost profile.
