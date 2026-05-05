# Comparison matrix — proposed design vs. alternatives

The brief required formal comparison against three named alternatives. Each is scored against the brief's six evaluation criteria (security, governance, scalability, operability, agent UX, cost). Scores are a `1`–`5` integer from the architecture-review synthesis, not a benchmark; lower is worse.

| Approach | Security | Governance | Scalability | Operability | Agent UX | Cost | Total | Verdict |
|---|---|---|---|---|---|---|---|---|
| **(proposed) Centralized platform MCP with handler registry + STS dispatch** | 4 | 5 | 4 | 3 | 4 | 4 | **24** | **adopt for V1 (with refinements)** |
| (a) Federated MCP servers per product with shared identity broker | 3 | 2 | 4 | 3 | 3 | 3 | 18 | reject |
| (b) API Gateway / EventBridge fronting per-product handlers, MCP as thin adapter | 3 | 4 | 4 | 4 | 3 | 4 | 22 | viable; specific to whether LINQ already runs a mature internal API gateway |
| (c) Hybrid: thin platform MCP delegating to product-owned MCP servers | 4 | 4 | 5 | 4 | 4 | 4 | 25 | preferred long-term destination — reach incrementally via the proposed design's `handlerType: "remote-mcp"` escape hatch |

## What the criteria mean here

- **Security** — Identity model, end-user propagation, tenant isolation enforceability, audit completeness.
- **Governance** — Single point of policy enforcement, how easy it is to add a new product without diluting controls, how easy compliance scope expansion would be.
- **Scalability** — Behavior at the brief's 5–10× growth target (200–2000 handlers, 8–15 products).
- **Operability** — Failure isolation, on-call boundary clarity, rollback ergonomics, deployment cadence.
- **Agent UX** — Tool catalog ergonomics, latency, error legibility, context-window cost.
- **Cost** — Per-request cost trajectory, cost growth profile (sub-linear vs. linear in handler count), fixed-cost lines per added handler.

## Approach detail and trade-offs

### (proposed) Centralized platform MCP with handler registry + STS dispatch

**Strongest at:** governance and security — single authz seam, single audit log, single tools/list catalog. Lowest onboarding burden for product teams (write a Lambda, register an ARN). The architecture review's verdict is `approve-with-changes`; the changes are listed in [`00-overview.md`](00-overview.md) and the [ADR](../../decisions/0015-centralized-platform-mcp.md).

**Weakest at:** operability. Single broker means MCP-server outage stops all agent traffic. Mitigated for V1 by multi-AZ; multi-region triggered by external exposure. Platform team is potential bottleneck at registry write path; mitigated by policy-as-code on the registry write rather than manual review.

**Right when:** governance leverage matters more than blast radius isolation. Read-only V1 with 4 products fits exactly this profile.

### (a) Federated MCP servers per product with shared identity broker

**Strongest at:** scalability and blast radius. One product's MCP outage doesn't stop the others. Product teams own their server end-to-end with no platform-team queue.

**Weakest at:** governance. Every product team independently implements RFC 9728 metadata, audit logging, rate limiting, schema validation, and the Auth0 → STS bridge. At 4 products this is 4× duplicated infrastructure work with quality variance — and the auth implementation has the largest correctness blast radius. Onboarding for agents is also higher (multiple endpoints to discover).

**Right when:** the products' security and audit requirements have already diverged enough that one platform can't satisfy them all. **Not yet true for LINQ V1** — every product wants the same Auth0 + STS pattern.

### (b) API Gateway / EventBridge fronting per-product handlers, MCP as thin adapter

**Strongest at:** operability if LINQ already runs a mature internal API gateway. Reuses existing authn, throttling, request validation, and audit logging. Lower platform-team build cost — MCP server becomes a thin protocol adapter (`tools/list` → Gateway routes; `tools/call` → Gateway invocation).

**Weakest at:** agent UX. Forces MCP semantics (tool annotations, listChanged notifications, structured outputs) into a request/response shape that doesn't quite fit. Schema sync between MCP catalog and Gateway routes becomes a registry-of-its-own problem you didn't avoid.

**Right when:** LINQ already has a mature, observable internal API platform that handlers naturally live behind. **`[ASSUMED]` not yet confirmed for LINQ** — the architecture review surfaced this as Open Question Q5 in [`05-open-questions.md`](05-open-questions.md). If the answer is "yes, LINQ has Kong / Apigee at scale," revisit this row.

### (c) Hybrid: thin platform MCP delegating to product-owned MCP servers

**Strongest at:** scalability. Platform server owns identity, audit, rate limiting, per-tool authz, and `tools/list` aggregation. Product MCP servers own handler logic, schemas, and their own AWS resources. Communication is MCP-over-HTTPS between platform and product servers — re-using the protocol you've already invested in. Migration story to full federation is trivial; migration story from the proposed centralized design is also trivial.

**Weakest at:** initial cost. Two systems to design and build. Two extra hops on the cold path.

**Right when:** you want federation's scaling properties with central governance, and you can afford the up-front design cost. **The right destination, not the right starting point.** The architecture review's recommendation is to reserve `handlerType: "remote-mcp"` in the proposed registry today and activate the hybrid mode incrementally per-product when a stated threshold is crossed (handler count > 800 OR ≥ 2 teams review-bottlenecked).

## Why the proposed design wins for V1

Three factors:

1. **Governance is the dominant V1 problem.** With four products on heterogeneous stacks (Angular/.NET, Oracle, DynamoDB, Lambda, ECS, Step Functions) and a fresh AI-agent surface, a single authz seam and a single audit log give the platform team something to point at when compliance scope eventually expands. Federation gives up that lever.
2. **The centralized design has a federation escape hatch.** The proposed `handlerType: "remote-mcp"` reservation costs nothing today and converts a future federation migration from a re-platform into a feature flag. This collapses the "centralized vs. hybrid" decision from a one-way door into an incrementally-flippable lever.
3. **Cost is sub-linear conditional on three operational rules** that are easier to enforce in a centralized platform than across federated servers: shared M2M apps, shared per-product IAM roles, templated observability. Federation distributes the discipline burden across teams; centralization concentrates it where the platform team can enforce.

The architecture review's `approve-with-changes` verdict reflects this — the design is right; the refinements in the ADR are required to make it stay right at 5–10× growth.
